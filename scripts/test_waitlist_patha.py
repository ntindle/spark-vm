"""Tests for site/waitlist_patha.py + the waitlistd path-A additions
(H15 build, slice 3 remainder).

Run from the repo root:  python3 -m pytest scripts/test_waitlist_patha.py -q

Covers the contracts docs/WAITLIST_OPERATIONS.md §2/§5/§6 set for the
email intake path:

- §2 parsing: exclusion list (From, inbox, @agentmail.to) applied before
  counting; `Owner:` line overrides extraction; exactly one candidate
  proceeds, zero/≥2 go to the clarification reply (DMARC-gated) or
  silent triage; optional pubkey + use-case extraction (280-char cap).
- §5: a reply saying "forget me" is never honored on its own — it
  triggers the confirmation email with the signed forget link; the row
  is not deleted by the reply.
- §6: per-sender rate limit (3 submissions / sender / day); clarification
  replies only on DMARC-aligned mail (no backscatter); the §4 3/24h
  transactional-email cap covers path-A sends; per-owner dedup on the
  normalized address.
- docs/FUNNEL_MEASUREMENT.md §3.4: waitlist_submitted carries
  path=email + inbound_auth for path-A rows (absent for path B).

stdlib only, no network.
"""

import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "site")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # waitlist_patha does `from waitlistd import ...`
    spec.loader.exec_module(mod)
    return mod


wd = load_module("waitlistd", os.path.join(SITE, "waitlistd.py"))
wp = load_module("waitlist_patha", os.path.join(SITE, "waitlist_patha.py"))

KEY = b"test-hmac-key-32-bytes-long-000000"
NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
INBOX = "waitlist-inbox@example.com"


class MutClock:
    def __init__(self, start=NOW):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_service(clock=None):
    tmp = tempfile.mkdtemp(prefix="waitlist-patha-test-")
    clock = clock or MutClock()
    return (wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock), tmp, clock)


def make_msg(from_addr, body, subject="join the waitlist"):
    return (f"From: {from_addr}\r\n"
            f"To: {INBOX}\r\n"
            f"Subject: {subject}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n{body}\r\n")


def spool_docs(tmp):
    out = []
    spool = os.path.join(tmp, "spool")
    for name in sorted(os.listdir(spool)):
        with open(os.path.join(spool, name), encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


def funnel_events(tmp):
    path = os.path.join(tmp, "funnel_events.jsonl")
    events = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_single_candidate_extracted():
    assert wp.extract_owner_candidate(
        "Please add owner@example.com to the list", "muse@x.io",
        INBOX) == "owner@example.com"


def test_from_address_excluded():
    # The only address in the body is the From address → zero candidates.
    assert wp.extract_owner_candidate(
        "From me again: muse-sender@example.org", "muse-sender@example.org",
        INBOX) is None


def test_inbox_address_excluded():
    body = f"Writing to {INBOX} about owner@example.com"
    assert wp.extract_owner_candidate(body, "muse@x.io", INBOX) == \
        "owner@example.com"


def test_agentmail_addresses_excluded():
    body = "owner@example.com and spark-agent@agentmail.to signed"
    assert wp.extract_owner_candidate(body, "muse@x.io", INBOX) == \
        "owner@example.com"


def test_owner_line_overrides_extraction():
    body = ("cc: a@example.com, b@example.com\n"
            "Owner: owner@example.com\n"
            "quoted: c@example.com")
    assert wp.extract_owner_candidate(body, "muse@x.io", INBOX) == \
        "owner@example.com"


def test_owner_line_invalid_address_clarifies():
    body = "Owner: not-an-address\ncc: a@example.com"
    assert wp.extract_owner_candidate(body, "muse@x.io", INBOX) is None


def test_two_candidates_clarifies():
    body = "Either a@example.com or b@example.com works"
    assert wp.extract_owner_candidate(body, "muse@x.io", INBOX) is None


def test_plus_tag_normalized():
    assert wp.extract_owner_candidate(
        "Owner: Jane.Doe+tag@Example.COM", "muse@x.io",
        INBOX) == "jane.doe@example.com"


def test_forget_intent_detected():
    assert wp.detect_forget_intent("Re: waitlist", "please forget me now")
    assert wp.detect_forget_intent("forget-me request", "hi")
    assert wp.detect_forget_intent("Re: waitlist", "please forget me.")
    assert not wp.detect_forget_intent("join", "add me please")


def test_forget_intent_not_triggered_by_addresses():
    # Email addresses (and the flower) containing forget-me substrings must
    # not route a signup into the forget flow.
    assert not wp.detect_forget_intent("join", "my address is forget-me@example.com")
    assert not wp.detect_forget_intent("join", "my address is forgetme@example.com")
    assert not wp.detect_forget_intent("join", "contact x@forget-me.com for details")
    assert not wp.detect_forget_intent("join", "i love forget-me-nots")


def test_pubkey_extraction():
    body = "Owner: o@example.com\nssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest\n"
    assert wp.extract_pubkey(body) == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest"
    assert wp.extract_pubkey("Owner: o@example.com") is None


def test_usecase_truncation():
    body = "Owner: o@example.com\nUse case: " + "x" * 400
    assert len(wp.extract_usecase(body)) == 280
    assert wp.extract_usecase("Owner: o@example.com") is None


# ---------------------------------------------------------------------------
# Intake flow
# ---------------------------------------------------------------------------


def test_accepted_row_shape():
    service, tmp, clock = make_service()
    body = ("Owner: owner@example.com\n"
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest\n"
            "Use case: training runs")
    raw = make_msg("muse-sender@example.org", body)
    result = wp.process_inbound(service, raw, auth="pass",
                               inbox_addr=INBOX)
    assert result["outcome"] == "accepted"
    row = service.rows[result["entry_id"]]
    assert row["owner_email"] == "owner@example.com"
    assert row["path"] == "email" and row["source"] == "email"
    assert row["inbound_auth"] is True
    assert row["muse_contact"] == "muse-sender@example.org"
    assert row["muse_pubkey"] == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest"
    assert row["use_case"] == "training runs"
    ev = [e for e in funnel_events(tmp)
          if e["event"] == "waitlist_submitted"][0]
    assert ev["attrs"] == {"path": "email", "inbound_auth": True}
    docs = spool_docs(tmp)
    assert len(docs) == 1
    assert docs[0]["to"] == "owner@example.com"
    # The §4 DRAFT path-A opener, not the form opener.
    assert "Your agent asked to join the spark-vm hosted waitlist" in \
        docs[0]["body"]


def test_inbound_auth_recorded_on_fail():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    result = wp.process_inbound(service, raw, auth="fail",
                               inbox_addr=INBOX)
    assert result["outcome"] == "accepted"
    row = service.rows[result["entry_id"]]
    assert row["inbound_auth"] is False
    ev = [e for e in funnel_events(tmp)
          if e["event"] == "waitlist_submitted"][0]
    assert ev["attrs"] == {"path": "email", "inbound_auth": False}


def test_resubmit_refreshes():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    first = wp.process_inbound(service, raw, auth="pass",
                               inbox_addr=INBOX)
    clock.advance(hours=1)
    second = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert second["outcome"] == "resubmitted"
    assert second["entry_id"] == first["entry_id"]
    assert len(spool_docs(tmp)) == 2  # fresh confirm email


def test_per_sender_intake_limit():
    service, tmp, clock = make_service()
    for i in range(3):
        raw = make_msg("muse@x.io", f"Owner: owner{i}@example.com")
        assert wp.process_inbound(service, raw, auth="pass",
                                  inbox_addr=INBOX)["outcome"] == "accepted"
    raw = make_msg("muse@x.io", "Owner: owner3@example.com")
    result = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "intake_limited"
    assert "owner3@example.com" not in service.by_email
    # Silent: no email spooled for the 4th attempt, triage got the raw.
    assert len(spool_docs(tmp)) == 3
    assert len(os.listdir(os.path.join(tmp, "triage"))) == 1


def test_intake_limit_resets_next_day():
    service, tmp, clock = make_service()
    for i in range(3):
        raw = make_msg("muse@x.io", f"Owner: owner{i}@example.com")
        wp.process_inbound(service, raw, auth="pass", inbox_addr=INBOX)
    clock.advance(hours=25)
    raw = make_msg("muse@x.io", "Owner: owner3@example.com")
    assert wp.process_inbound(service, raw, auth="pass",
                              inbox_addr=INBOX)["outcome"] == "accepted"


def test_ambiguous_clarified_on_auth_pass():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "a@example.com or b@example.com?")
    result = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "clarified"
    docs = spool_docs(tmp)
    assert len(docs) == 1
    assert docs[0]["to"] == "muse@x.io"
    assert "We couldn't tell which address is the owner" in docs[0]["body"]
    assert "Owner: you@example.com" in docs[0]["body"]
    assert "owner@example.com" not in service.by_email  # no row written


def test_ambiguous_silently_triaged_on_auth_fail():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "a@example.com or b@example.com?")
    result = wp.process_inbound(service, raw, auth="fail",
                                inbox_addr=INBOX)
    assert result["outcome"] == "triage"
    assert result["reason"] == "ambiguous_unauth"
    assert spool_docs(tmp) == []  # no backscatter: nothing spooled
    triaged = os.path.join(tmp, "triage", result["triage_file"])
    with open(triaged, encoding="utf-8") as fh:
        content = fh.read()
    assert "unauthenticated" in content
    assert "a@example.com" in content  # raw message preserved


def test_clarification_cap():
    service, tmp, clock = make_service()
    # Burn the 3/24h path-A send cap with clarification replies.
    for _ in range(3):
        raw = make_msg("muse@x.io", "a@example.com or b@example.com?")
        assert wp.process_inbound(service, raw, auth="pass",
                                  inbox_addr=INBOX)["outcome"] == "clarified"
    raw = make_msg("muse@x.io", "c@example.com or d@example.com?")
    assert wp.process_inbound(service, raw, auth="pass",
                              inbox_addr=INBOX)["outcome"] == \
        "clarification_capped"
    assert len(spool_docs(tmp)) == 3


def test_forget_reply_sends_confirmation_not_deletion():
    service, tmp, clock = make_service()
    raw = make_msg("owner@example.com", "Owner: owner@example.com")
    created = wp.process_inbound(service, raw, auth="pass",
                                 inbox_addr=INBOX)
    entry_id = created["entry_id"]
    forget_raw = make_msg("owner@example.com", "please forget me",
                          subject="Re: waitlist")
    result = wp.process_inbound(service, forget_raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "forget_request_sent"
    # The row is NOT deleted by the reply — deletion needs the link click.
    assert entry_id in service.rows
    docs = spool_docs(tmp)
    assert len(docs) == 2
    forget_doc = [d for d in docs if d.get("kind") == "forget_request"][0]
    assert forget_doc["to"] == "owner@example.com"
    assert "forget." in forget_doc["body"]  # the signed forget link
    assert "nothing is deleted" in forget_doc["body"]


def test_forget_reply_unknown_sender_triaged():
    service, tmp, clock = make_service()
    raw = make_msg("stranger@example.com", "forget me please")
    result = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "triage"
    assert result["reason"] == "forget_no_row"
    assert spool_docs(tmp) == []


def test_forget_link_in_email_validates():
    service, tmp, clock = make_service()
    raw = make_msg("owner@example.com", "Owner: owner@example.com")
    wp.process_inbound(service, raw, auth="pass", inbox_addr=INBOX)
    forget_raw = make_msg("owner@example.com", "forget me")
    wp.process_inbound(service, forget_raw, auth="pass",
                       inbox_addr=INBOX)
    doc = [d for d in spool_docs(tmp)
           if d.get("kind") == "forget_request"][0]
    token = doc["body"].split("token=")[1].split()[0].strip()
    assert token.startswith("forget.")
    row, status = service._lookup_token_row(token, kind="forget")
    assert status == "ok"


def test_auth_garbage_rejected():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    with pytest.raises(ValueError):
        wp.process_inbound(service, raw, auth="maybe", inbox_addr=INBOX)


def test_no_from_triaged():
    service, tmp, clock = make_service()
    raw = "Subject: hi\r\n\r\nOwner: owner@example.com\r\n"
    result = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "triage"
    assert result["reason"] == "no_from"


def test_cli_requires_auth_flag():
    with pytest.raises(SystemExit) as exc:
        wp.load_config([])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Review round 1 fixes
# ---------------------------------------------------------------------------


def test_forget_intent_checked_before_intake_gate():
    # QA B2: a spam-prevention limit must never swallow a §5 deletion
    # request. The sender owns a row AND burned the 3/day budget.
    service, tmp, clock = make_service()
    for i in range(3):
        raw = make_msg("a@example.com", f"Owner: o{i}@example.com")
        assert wp.process_inbound(service, raw, auth="pass",
                                  inbox_addr=INBOX)["outcome"] == "accepted"
    assert service.by_email.get("o0@example.com")
    forget_raw = make_msg("a@example.com", "Owner: o0@example.com\n"
                                           "please forget me")
    # o0's owner is o0@example.com, not the sender — craft the owned row:
    owned = make_msg("b@example.com", "Owner: b@example.com")
    wp.process_inbound(service, owned, auth="pass", inbox_addr=INBOX)
    clock.advance(hours=25)  # fresh budget day for b@example.com
    for i in range(3):
        raw = make_msg("b@example.com", f"Owner: q{i}@example.com")
        wp.process_inbound(service, raw, auth="pass", inbox_addr=INBOX)
    forget_raw = make_msg("b@example.com", "please forget me")
    result = wp.process_inbound(service, forget_raw, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "forget_request_sent"


def test_owner_override_excluded_addresses_clarify():
    # QA m2: the Owner: override can't register a pathological owner —
    # the inbox's own address and @agentmail.to are still filtered.
    # The From address is deliberately NOT filtered on the override: a
    # human-driven Muse's From routinely IS the owner's address.
    assert wp.extract_owner_candidate("Owner: muse@x.io", "muse@x.io",
                                      INBOX) == "muse@x.io"
    assert wp.extract_owner_candidate(f"Owner: {INBOX}", "muse@x.io",
                                      INBOX) is None
    assert wp.extract_owner_candidate("Owner: spark@agentmail.to",
                                      "muse@x.io", INBOX) is None
    # ...but a real override still wins.
    assert wp.extract_owner_candidate("Owner: owner@example.com\n"
                                      "cc: a@example.com",
                                      "muse@x.io", INBOX) == \
        "owner@example.com"


def test_forget_intent_negation():
    # Eng m4: "don't forget me" is not a deletion request.
    assert not wp.detect_forget_intent("hi", "please don't forget me")
    assert not wp.detect_forget_intent("hi", "do not forget me, thanks")
    assert not wp.detect_forget_intent("hi", "never forget me")
    assert wp.detect_forget_intent("hi", "please forget me")


def test_load_config_missing_env(monkeypatch):
    monkeypatch.delenv("WAITLIST_HMAC_KEY", raising=False)
    monkeypatch.setenv("WAITLIST_DATA", "/tmp")
    monkeypatch.setenv("WAITLIST_INBOX", INBOX)
    with pytest.raises(SystemExit) as exc:
        wp.load_config(["--auth", "pass"])
    assert exc.value.code == 2
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.delenv("WAITLIST_DATA", raising=False)
    with pytest.raises(SystemExit) as exc:
        wp.load_config(["--auth", "pass"])
    assert exc.value.code == 2
    monkeypatch.setenv("WAITLIST_DATA", "/tmp")
    monkeypatch.delenv("WAITLIST_INBOX", raising=False)
    with pytest.raises(SystemExit) as exc:
        wp.load_config(["--auth", "pass"])
    assert exc.value.code == 2


def _cli_stdin(monkeypatch, tmp_path, payload_bytes):
    """Point the path-A CLI at a real binary-backed stdin."""
    import io
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    monkeypatch.setenv("WAITLIST_INBOX", INBOX)
    monkeypatch.setattr("sys.stdin",
                        io.TextIOWrapper(io.BytesIO(payload_bytes)))
    return data


def test_oversize_stdin_triaged(tmp_path, monkeypatch, capsys):
    # Eng m3: a >1 MiB message is triaged, never parsed.
    data = _cli_stdin(monkeypatch, tmp_path,
                      b"x" * (wp.MAX_RAW_BYTES + 100))
    assert wp.main(["--auth", "pass"]) == 0
    assert "triage" in capsys.readouterr().out
    assert len(os.listdir(str(data / "triage"))) == 1


def test_stdin_byte_boundary(tmp_path, monkeypatch, capsys):
    # Eng B2 / QA B3: the cap is enforced on BYTES. Exactly 1 MiB
    # passes through to parsing; 1 MiB + 1 byte triages.
    msg = make_msg("muse@x.io", "Owner: owner@example.com").encode("utf-8")
    assert len(msg) < wp.MAX_RAW_BYTES
    pad = wp.MAX_RAW_BYTES - len(msg)
    exact = msg + b" " * pad
    assert len(exact) == wp.MAX_RAW_BYTES
    _cli_stdin(monkeypatch, tmp_path, exact)
    assert wp.main(["--auth", "pass"]) == 0
    assert "accepted" in capsys.readouterr().out

    _cli_stdin(monkeypatch, tmp_path, exact + b" ")
    assert wp.main(["--auth", "pass"]) == 0
    assert "triage" in capsys.readouterr().out


def test_multibyte_oversize_stdin_triaged(tmp_path, monkeypatch, capsys):
    # Eng B2: 1 MiB of 4-byte UTF-8 is 4 MiB of raw input — it must
    # trip the byte cap. (The old sys.stdin.read() character count let
    # it through.)
    payload = "😀".encode("utf-8") * (wp.MAX_RAW_BYTES // 4 + 10)
    assert len(payload) > wp.MAX_RAW_BYTES
    data = _cli_stdin(monkeypatch, tmp_path, payload)
    assert wp.main(["--auth", "pass"]) == 0
    assert "triage" in capsys.readouterr().out
    assert len(os.listdir(str(data / "triage"))) == 1


def test_non_utf8_stdin_triaged_lossily(tmp_path, monkeypatch, capsys):
    # Eng B2: undecodable input must not crash the pipeline — it is
    # decoded lossily and handled like any other mail (here: zero owner
    # candidates on auth=fail → silent triage, with the replacement
    # character in the triage file).
    payload = (b"From: muse@x.io\r\nTo: " + INBOX.encode() +
               b"\r\nSubject: hi\r\n\r\n\xff\xfe not utf-8 \x80\x81\r\n")
    data = _cli_stdin(monkeypatch, tmp_path, payload)
    assert wp.main(["--auth", "fail"]) == 0
    out = capsys.readouterr().out
    assert "triage" in out
    triaged = os.listdir(str(data / "triage"))
    assert len(triaged) == 1
    with open(str(data / "triage" / triaged[0]), encoding="utf-8") as fh:
        content = fh.read()
    assert "\ufffd" in content  # lossy decode marker, no surrogate crash


def test_clarification_body_has_no_dead_footer():
    # Design blocker 1: the clarification must not contradict itself —
    # no forget footer at all, honest closing instead.
    body = wd.CLARIFY_BODY
    assert "a fresh one arrives with every email" not in body
    assert "no deletion link in this email" in body
    assert "{forget_link}" not in body


def test_already_invited_patha_noop():
    service, tmp, clock = make_service()
    raw = make_msg("owner@example.com", "Owner: owner@example.com")
    wp.process_inbound(service, raw, auth="pass", inbox_addr=INBOX)
    row = service.rows[service.by_email["owner@example.com"]]
    service.confirm_post(row["active_token"])
    invited = service.send_invite_wave(
        pricing_lines="P", trial_terms="T", wave="w1", count=5)
    assert invited == [row["entry_id"]]
    before_rows = len(service.rows)
    before_spool = len(spool_docs(tmp))
    again = make_msg("muse@x.io", "Owner: owner@example.com")
    result = wp.process_inbound(service, again, auth="pass",
                                inbox_addr=INBOX)
    assert result["outcome"] == "already_invited"
    assert len(service.rows) == before_rows  # no duplicate row
    assert len(spool_docs(tmp)) == before_spool  # no new email
    assert service.rows[row["entry_id"]]["status"] == "invited"


# ---------------------------------------------------------------------------
# Unauthenticated-mail contract (QA B1 resolution: Design option B)
# ---------------------------------------------------------------------------
# "No outbound reply, ever" governs *replies to an unauthenticated
# sender* (the anti-backscatter rule — clarification only on auth=pass).
# Owner-bound double-opt-in (§2) and forget-confirmation (§5) mail is
# DELIBERATE on auth=fail input: the signed token link (proving inbox
# access), not the From, is the authority; third-party spraying is
# bounded by the unified §4 3/24h per-address cap.


def test_unauthenticated_valid_signup_sends_owner_confirm():
    # The confirm email is a double-opt-in challenge to the OWNER, not
    # a reply to the sender — it goes out on auth=fail by design (§3:
    # "Sybil resistance comes from the confirm gate ... not from
    # sender attestation").
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    result = wp.process_inbound(service, raw, auth="fail",
                               inbox_addr=INBOX)
    assert result["outcome"] == "accepted"
    docs = spool_docs(tmp)
    assert len(docs) == 1
    assert docs[0]["to"] == "owner@example.com"  # owner-bound, not sender
    row = service.rows[result["entry_id"]]
    assert row["inbound_auth"] is False


def test_unauthenticated_forget_reply_sends_owner_confirmation():
    # §5: the forget-confirmation email goes to the ROW OWNER on
    # auth=fail input — the signed link (proving inbox access), not the
    # From, authorizes the deletion. The reply itself deletes nothing.
    service, tmp, clock = make_service()
    raw = make_msg("owner@example.com", "Owner: owner@example.com")
    created = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    entry_id = created["entry_id"]
    forget_raw = make_msg("owner@example.com", "please forget me",
                          subject="Re: waitlist")
    result = wp.process_inbound(service, forget_raw, auth="fail",
                                inbox_addr=INBOX)
    assert result["outcome"] == "forget_request_sent"
    assert entry_id in service.rows  # NOT deleted by the reply
    forget_doc = [d for d in spool_docs(tmp)
                  if d.get("kind") == "forget_request"][0]
    assert forget_doc["to"] == "owner@example.com"


def test_unauthenticated_forget_unknown_sender_triaged_silently():
    # No row for the sender → silent triage, zero spool output.
    service, tmp, clock = make_service()
    raw = make_msg("stranger@example.com", "forget me please")
    result = wp.process_inbound(service, raw, auth="fail",
                                inbox_addr=INBOX)
    assert result["outcome"] == "triage"
    assert result["reason"] == "forget_no_row"
    assert spool_docs(tmp) == []


# ---------------------------------------------------------------------------
# Unified §4 3/24h cap (Eng B1): row + path-A ledgers count together
# ---------------------------------------------------------------------------


def test_unified_cap_counts_clarifications_against_confirms():
    # 1 confirm + 2 clarifications to one address, then the 4th total
    # send is suppressed — the old split ledgers allowed 3 + 3 = 6.
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    created = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    assert created["outcome"] == "accepted"
    assert len(spool_docs(tmp)) == 1  # the confirm
    assert service.spool_clarification("owner@example.com") is True
    assert service.spool_clarification("owner@example.com") is True
    # The fourth total send inside 24h is suppressed even though each
    # old-path ledger alone saw fewer than 3.
    assert service.spool_clarification("owner@example.com") is False
    assert len(spool_docs(tmp)) == 3


def test_unified_cap_counts_confirms_against_clarifications():
    # The other direction: path-A sends to an address with no row still
    # count against the later row's budget once the row exists.
    service, tmp, clock = make_service()
    assert service.spool_clarification("owner@example.com") is True
    assert service.spool_clarification("owner@example.com") is True
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    created = wp.process_inbound(service, raw, auth="pass",
                                inbox_addr=INBOX)
    # The confirm is the 3rd total send — allowed; the 4th is not.
    assert created["outcome"] == "accepted"
    assert len(spool_docs(tmp)) == 3
    row = service.rows[created["entry_id"]]
    assert service._queue_confirm_email(row) is False
    assert len(spool_docs(tmp)) == 3


def test_unified_cap_resets_after_24h():
    service, tmp, clock = make_service()
    raw = make_msg("muse@x.io", "Owner: owner@example.com")
    wp.process_inbound(service, raw, auth="pass", inbox_addr=INBOX)
    assert service.spool_clarification("owner@example.com") is True
    assert service.spool_clarification("owner@example.com") is True
    assert service.spool_clarification("owner@example.com") is False
    clock.advance(hours=25)
    # The 48h-pruned ledgers forgot the old sends — mail flows again.
    assert service.spool_clarification("owner@example.com") is True


def test_triage_inbound_accepts_bytes_and_surrogates():
    # Eng B2: triage_inbound must never crash on non-UTF-8 bytes or
    # lone surrogates — it decodes lossily / writes safely.
    service, tmp, clock = make_service()
    name = service.triage_inbound(b"\xff\xfe binary \x80", "binary")
    with open(os.path.join(tmp, "triage", name), encoding="utf-8") as fh:
        assert "\ufffd" in fh.read()
    name = service.triage_inbound("lone \ud800 surrogate", "surrogate")
    with open(os.path.join(tmp, "triage", name), encoding="utf-8") as fh:
        assert "surrogate" in fh.read()

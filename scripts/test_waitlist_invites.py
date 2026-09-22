"""Tests for site/waitlist_invites.py + the waitlistd invite additions
(H15 build, slice 3 remainder).

Run from the repo root:  python3 -m pytest scripts/test_waitlist_invites.py -q

Covers docs/WAITLIST_OPERATIONS.md §5/§7 for the invite sender:

- §7: waves invite FIFO by confirmed_at; the §7 DRAFT email carries
  pricing + trial terms filled at send time (the template never contains
  numbers); the signed position line ("You held #N in line"); 14-day
  expiry; `invite_sent` per mailed row (FUNNEL_MEASUREMENT.md §3.4);
  rows past the 3/24h cap stay confirmed for a later wave.
- §5/§7: expired invites roll the slot — the entry rejoins `confirmed`
  at the back of the queue with confirmed_at reset to the EXPIRY time
  (not now), no re-confirmation, no new funnel event; the invite token
  is consumed.
- Token shape: `invite.`-prefixed, HMAC-signed, single-use, 14-day TTL;
  cross-kind tokens never validate (confirm/forget ↔ invite).
- Fault-injection crash windows (deferred m2 follow-ups from the
  spool-then-single-commit reorder): a crash after `_consume_token(old)`
  but before the row commit in the re-invite path recovers by re-running
  against the confirmed row — fresh token, the stray email's link never
  validates (the flip was manual until issue #235's `--reinstate-confirmed`
  / `--diagnose` operator tooling landed); in the §7 expiry rollover the
  same window retries cleanly with the retired token staying consumed
  and no new email; a crash between the commit and the `invite_sent`
  event leaves the metrics conservatively under-reporting (never claiming
  what rows.jsonl doesn't show) and never re-invites or double-spools;
  the operator repairs the missing event with
  `waitlist_invites.py --reconcile` (issue #234), which re-derives it
  from rows.jsonl in the append-only posture.

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
    sys.modules[name] = mod  # waitlist_invites does `from waitlistd ...`
    spec.loader.exec_module(mod)
    return mod


wd = load_module("waitlistd", os.path.join(SITE, "waitlistd.py"))
wi = load_module("waitlist_invites", os.path.join(SITE, "waitlist_invites.py"))

KEY = b"test-hmac-key-32-bytes-long-000000"
NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
PRICING = "Starter — 2 vCPU / 8 GB — $24/mo\nPro — 8 vCPU / 32 GB — $96/mo"
TERMS = "14-day trial, card required up front per the Billing decision."


class MutClock:
    def __init__(self, start=NOW):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_service(clock=None):
    tmp = tempfile.mkdtemp(prefix="waitlist-invites-test-")
    clock = clock or MutClock()
    return (wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock), tmp, clock)


def confirm_row(service, email, clock, at=None):
    """A confirmed row: submit the form, then confirm via token."""
    service.submit_form({"owner_email": email}, "127.0.0.1")
    row = service.rows[service.by_email[email]]
    token = row["active_token"]
    status, _ = service.confirm_post(token)
    assert status == 200
    row = service.rows[service.by_email[email]]
    if at is not None:
        row["confirmed_at"] = wd.iso_z(at)
        service._save_row(row)
    return row


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


def wave(service, count=10, wave="wave1"):
    return service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                    wave=wave, count=count)


# ---------------------------------------------------------------------------
# Wave sending
# ---------------------------------------------------------------------------


def test_wave_invites_fifo():
    service, tmp, clock = make_service()
    first = confirm_row(service, "a@example.com", clock,
                        at=NOW - timedelta(days=2))
    second = confirm_row(service, "b@example.com", clock,
                         at=NOW - timedelta(days=1))
    third = confirm_row(service, "c@example.com", clock, at=NOW)
    invited = wave(service, count=2)
    assert invited == [first["entry_id"], second["entry_id"]]
    assert service.rows[first["entry_id"]]["status"] == "invited"
    assert service.rows[third["entry_id"]]["status"] == "confirmed"
    assert service.rows[first["entry_id"]]["invite_wave"] == "wave1"


def test_invite_email_body():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    docs = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(docs) == 1
    doc = docs[0]
    assert doc["to"] == "a@example.com"
    assert doc["subject"] == "You're off the waitlist — claim your box"
    # Pricing + trial terms filled at send time, verbatim.
    assert "Starter — 2 vCPU / 8 GB — $24/mo" in doc["body"]
    assert TERMS in doc["body"]
    # The signed position line.
    assert "You held #1 in line" in doc["body"]
    # The claim link carries an invite token.
    assert "/waitlist/claim?token=invite." in doc["body"]
    # 14-day expiry stated.
    assert "expires in 14 days" in doc["body"]
    # Compliance: no "free tier" wording anywhere in the invite.
    assert "free tier" not in doc["body"].lower()


def test_wave_invite_position_lines_rank_each_row():
    """Multi-row waves stamp each invite with the invitee's own rank.

    Regression: send_invite_wave used to compute queue_position() inside
    the loop, after earlier rows had flipped to invited (invited rows
    are not ranked), so every invite after the first read "#1".
    """
    service, tmp, clock = make_service()
    confirm_row(service, "a@example.com", clock, at=NOW - timedelta(days=2))
    confirm_row(service, "b@example.com", clock, at=NOW - timedelta(days=1))
    confirm_row(service, "c@example.com", clock, at=NOW)
    invited = wave(service, count=3)
    assert len(invited) == 3
    docs = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(docs) == 3
    bodies = {d["to"]: d["body"] for d in docs}
    assert "You held #1 in line" in bodies["a@example.com"]
    assert "You held #2 in line" in bodies["b@example.com"]
    assert "You held #3 in line" in bodies["c@example.com"]


def test_invite_emits_funnel_event():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    ev = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(ev) == 1
    assert ev[0]["ref"] == row["entry_id"]


def test_capped_row_stays_confirmed():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    # Burn the 3/24h cap on the row (confirm + two synthetic sends).
    row["email_sends"] = [clock().timestamp()] * 3
    service._save_row(row)
    invited = wave(service, count=1)
    assert invited == []
    assert service.rows[row["entry_id"]]["status"] == "confirmed"
    assert "invite_wave" not in service.rows[row["entry_id"]]
    assert [e for e in funnel_events(tmp)
            if e["event"] == "invite_sent"] == []


def test_wave_skips_unconfirmed():
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "pending@example.com"}, "127.0.0.1")
    invited = wave(service, count=5)
    assert invited == []
    assert service.rows[
        service.by_email["pending@example.com"]]["status"] == "pending"


def test_invite_token_wire_format():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    token = service.mint_invite_token(row["entry_id"], row["owner_email"])
    assert token.startswith("invite.")
    assert len(token.split(".")) == 5


def test_cross_kind_tokens_never_validate():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    invite_token = service.mint_invite_token(row["entry_id"],
                                             row["owner_email"])
    # An invite token is not a confirm token...
    _, status = service._lookup_token_row(invite_token, kind="confirm")
    assert status == "invalid"
    # ...and a confirm token is not an invite token.
    confirm_token = service.mint_token(row["entry_id"], row["owner_email"])
    _, status = service.lookup_invite_token(confirm_token)
    assert status == "invalid"


def test_invite_token_lifecycle():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    token = service.rows[row["entry_id"]]["active_invite_token"]
    found, status = service.lookup_invite_token(token)
    assert status == "ok" and found["entry_id"] == row["entry_id"]
    # Tampered payload.
    bad = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    _, status = service.lookup_invite_token(bad)
    assert status == "invalid"
    # Expired after the 14-day claim window.
    clock.advance(days=15)
    _, status = service.lookup_invite_token(token)
    assert status == "expired"


def test_reinvite_consumes_old_token():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1, wave="wave1")
    old_token = service.rows[row["entry_id"]]["active_invite_token"]
    # Operator error: the row is invited twice (two waves). The first
    # token must die — only the live token claims.
    service.rows[row["entry_id"]]["status"] = "confirmed"
    wave(service, count=1, wave="wave2")
    new_token = service.rows[row["entry_id"]]["active_invite_token"]
    assert new_token != old_token
    _, status = service.lookup_invite_token(old_token)
    assert status == "consumed"
    _, status = service.lookup_invite_token(new_token)
    assert status == "ok"


# ---------------------------------------------------------------------------
# Rollover
# ---------------------------------------------------------------------------


def test_rollover_returns_to_confirmed_at_expiry():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    invited_at = clock()
    wave(service, count=1)
    token = service.rows[row["entry_id"]]["active_invite_token"]
    expiry = invited_at + timedelta(seconds=wd.INVITE_TTL_SECONDS)
    clock.advance(days=15)
    rolled = service.rollover_expired_invites()
    assert rolled == [row["entry_id"]]
    row = service.rows[row["entry_id"]]
    assert row["status"] == "confirmed"
    # §5: confirmed_at reset to the EXPIRY time, not to now.
    assert row["confirmed_at"] == wd.iso_z(expiry)
    assert row["confirmed_at"] != wd.iso_z(clock())
    for key in ("invited_at", "invite_expires_at", "invite_wave",
                "active_invite_token"):
        assert key not in row
    _, status = service.lookup_invite_token(token)
    assert status == "consumed"
    # No funnel event for the rollover (taxonomy has none).
    kinds = [e["event"] for e in funnel_events(tmp)]
    assert kinds.count("invite_sent") == 1
    assert "invite_expired" not in kinds


def test_rollover_leaves_live_invites():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    clock.advance(days=13)
    assert service.rollover_expired_invites() == []
    assert service.rows[row["entry_id"]]["status"] == "invited"


def test_rollover_skips_undated_invite():
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    row = service.rows[row["entry_id"]]
    del row["invite_expires_at"]  # hand-edited store: can't prove expiry
    service._save_row(row)
    clock.advance(days=60)
    assert service.rollover_expired_invites() == []
    assert service.rows[row["entry_id"]]["status"] == "invited"


def test_rolled_row_reinvitable_next_wave():
    service, tmp, clock = make_service()
    confirm_row(service, "a@example.com", clock)
    wave(service, count=1, wave="wave1")
    clock.advance(days=15)
    service.rollover_expired_invites()
    invited = wave(service, count=1, wave="wave2")
    assert len(invited) == 1
    assert service.rows[invited[0]]["invite_wave"] == "wave2"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_cli_wave_and_rollover(tmp_path, monkeypatch, capsys):
    pricing = tmp_path / "pricing.txt"
    terms = tmp_path / "terms.txt"
    _write(str(pricing), PRICING)
    _write(str(terms), TERMS)
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    monkeypatch.setenv("WAITLIST_PUBLIC_HOST",
                       "https://waitlist.example.invalid")
    monkeypatch.setenv("WAITLIST_CLAIM_LIVE", "1")
    service = wd.WaitlistService(str(data), KEY,
                                 "https://waitlist.example.invalid",
                                 clock=MutClock())
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])

    assert wi.main(["--send-wave", "--wave", "w1", "--count", "5",
                    "--pricing-file", str(pricing),
                    "--trial-terms-file", str(terms)]) == 0
    out = capsys.readouterr().out
    assert "invited 1 row(s)" in out

    assert wi.main(["--send-wave", "--wave", "w1", "--count", "5",
                    "--pricing-file", str(pricing),
                    "--trial-terms-file", str(terms), "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out

    assert wi.main(["--rollover"]) == 0
    assert "rolled over 0" in capsys.readouterr().out


def test_cli_rejects_empty_pricing(tmp_path, monkeypatch):
    pricing = tmp_path / "pricing.txt"
    terms = tmp_path / "terms.txt"
    _write(str(pricing), "   \n")
    _write(str(terms), TERMS)
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    with pytest.raises(SystemExit) as exc:
        wi.main(["--send-wave", "--wave", "w1", "--count", "1",
                 "--pricing-file", str(pricing),
                 "--trial-terms-file", str(terms)])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Review round 1 fixes
# ---------------------------------------------------------------------------


def _invite_row(service, tmp, clock, email="a@example.com"):
    row = confirm_row(service, email, clock)
    invited = service.send_invite_wave(pricing_lines=PRICING,
                                       trial_terms=TERMS, wave="w1",
                                       count=5)
    assert invited == [row["entry_id"]]
    return service.rows[row["entry_id"]]


def _forget_token_from_invite_email(tmp):
    doc = [d for d in spool_docs(tmp) if d.get("kind") == "invite"][0]
    marker = "token=forget."
    idx = doc["body"].index(marker)
    return "forget." + doc["body"][idx + len(marker):].split()[0].strip()


def test_invite_email_forget_link_validates():
    # Eng B1 / QA B1: the §5 forget footer in the invite email must
    # validate for invited rows.
    service, tmp, clock = make_service()
    row = _invite_row(service, tmp, clock)
    token = _forget_token_from_invite_email(tmp)
    found, status = service._lookup_token_row(token, kind="forget")
    assert status == "ok"
    assert found["entry_id"] == row["entry_id"]


def test_forget_post_on_invited_row():
    # The full delete path works for invited rows: row gone, invite
    # token consumed with it.
    service, tmp, clock = make_service()
    row = _invite_row(service, tmp, clock)
    invite_token = row["active_invite_token"]
    token = _forget_token_from_invite_email(tmp)
    status, _page = service.forget_post(token)
    assert status == 200
    assert row["entry_id"] not in service.rows
    assert invite_token in service.consumed
    # The row is gone, so the claim lookup honestly reports invalid —
    # there is nothing left to claim.
    _, status = service.lookup_invite_token(invite_token)
    assert status == "invalid"


def test_wave_backfills_past_capped():
    # Eng M2 / QA m3: a capped head-of-line row must not eat a wave
    # slot — count=1 invites the next eligible row.
    service, tmp, clock = make_service()
    first = confirm_row(service, "a@example.com", clock,
                        at=NOW - timedelta(days=2))
    second = confirm_row(service, "b@example.com", clock,
                         at=NOW - timedelta(days=1))
    third = confirm_row(service, "c@example.com", clock, at=NOW)
    first["email_sends"] = [clock().timestamp()] * 3
    service._save_row(first)
    invited = wave(service, count=1)
    assert invited == [second["entry_id"]]
    assert service.rows[first["entry_id"]]["status"] == "confirmed"
    assert service.rows[third["entry_id"]]["status"] == "confirmed"


def test_rollover_idempotent():
    # QA m5: a second rollover run finds nothing to roll.
    service, tmp, clock = make_service()
    row = _invite_row(service, tmp, clock)
    clock.advance(days=15)
    assert service.rollover_expired_invites() == [row["entry_id"]]
    assert service.rollover_expired_invites() == []


def test_submit_form_already_invited():
    # Eng M1, form path: an invited owner's re-submit is an honest
    # no-op — no duplicate row, no dead confirm email.
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="w1", count=5)
    rows_before = len(service.rows)
    status, page = service.submit_form({"owner_email": "a@example.com"},
                                       "127.0.0.1")
    assert status == 200
    assert "Already invited" in page
    assert len(service.rows) == rows_before
    assert service.rows[row["entry_id"]]["status"] == "invited"
    # The invite token survived (the no-op must not clobber it).
    found, status = service.lookup_invite_token(
        service.rows[row["entry_id"]]["active_invite_token"])
    assert status == "ok"


def test_cli_claim_live_guard(tmp_path, monkeypatch, capsys):
    # Design Major 1: a real wave refuses to send while the claim route
    # is unbuilt; --dry-run and --rollover are unaffected.
    pricing = tmp_path / "pricing.txt"
    terms = tmp_path / "terms.txt"
    _write(str(pricing), PRICING)
    _write(str(terms), TERMS)
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    monkeypatch.delenv("WAITLIST_CLAIM_LIVE", raising=False)
    argv = ["--send-wave", "--wave", "w1", "--count", "1",
            "--pricing-file", str(pricing),
            "--trial-terms-file", str(terms)]
    with pytest.raises(SystemExit) as exc:
        wi.main(argv)
    assert exc.value.code == 2
    assert "WAITLIST_CLAIM_LIVE" in capsys.readouterr().err
    # --dry-run needs no attestation...
    assert wi.main(argv + ["--dry-run"]) == 0
    # ...and the attestation unlocks the real wave.
    monkeypatch.setenv("WAITLIST_CLAIM_LIVE", "1")
    service = wd.WaitlistService(str(data), KEY,
                                 "https://waitlist.example.invalid",
                                 clock=MutClock())
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    assert wi.main(argv) == 0
    assert "invited 1 row(s)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Spool-then-commit wave (QA B3): a spool failure must not strand a row
# ---------------------------------------------------------------------------


def test_wave_spool_failure_leaves_row_confirmed(monkeypatch):
    # A spool-write failure mid-wave (disk-full, crash window) must not
    # strand the row as invited-without-email and must not consume the
    # old token. The next wave retries cleanly — no duplicate mail to
    # rows that already went out.
    service, tmp, clock = make_service()
    a = confirm_row(service, "a@example.com", clock,
                    at=NOW - timedelta(days=2))
    b = confirm_row(service, "b@example.com", clock,
                    at=NOW - timedelta(days=1))
    # B already holds a live invite token (reinvite shape) — it must
    # survive the failed wave unconsumed.
    old_token = service.mint_invite_token(b["entry_id"], "b@example.com")
    b["active_invite_token"] = old_token
    service._save_row(b)

    real_open = open
    fail = {"on": True}

    def flaky_open(path, *args, **kwargs):
        if (fail["on"] and isinstance(path, str)
                and b["entry_id"] in path and "-invite-" in path):
            raise OSError("simulated disk-full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", flaky_open)

    invited = wave(service, count=2, wave="wave1")
    # A mailed fine; B's spool write failed → B untouched.
    assert invited == [a["entry_id"]]
    brow = service.rows[b["entry_id"]]
    assert brow["status"] == "confirmed"
    assert "invite_wave" not in brow
    assert brow["active_invite_token"] == old_token  # not consumed
    assert old_token not in service.consumed
    assert len([d for d in spool_docs(tmp)
                if d.get("kind") == "invite"]) == 1

    # Disk recovers: the next wave retries B cleanly — one new token,
    # the old one consumed only now, no duplicate mail to A.
    fail["on"] = False
    invited = wave(service, count=2, wave="wave2")
    assert invited == [b["entry_id"]]
    brow = service.rows[b["entry_id"]]
    assert brow["status"] == "invited"
    assert brow["active_invite_token"] != old_token
    assert old_token in service.consumed
    invites = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(invites) == 2
    assert {d["to"] for d in invites} == {"a@example.com", "b@example.com"}


# ---------------------------------------------------------------------------
# Spool-then-single-commit (m2 reorder): the wave must never commit an
# intermediate row state — one rows.jsonl append per invited row, and a
# crash between the spool write and that append degrades to
# "duplicate email on retry", never "invited row with no email".
# ---------------------------------------------------------------------------


def rows_lines_for(tmp, entry_id):
    path = os.path.join(tmp, "rows.jsonl")
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            if obj.get("entry_id") == entry_id:
                out.append(obj)
    return out


def test_wave_invite_single_commit_per_row():
    # Each invited row lands in rows.jsonl with ONE append carrying
    # status=invited + the token + the wave fields — no intermediate
    # confirmed-with-invite-token line that a crash could freeze in.
    service, tmp, clock = make_service()
    a = confirm_row(service, "a@example.com", clock,
                    at=NOW - timedelta(days=2))
    b = confirm_row(service, "b@example.com", clock,
                    at=NOW - timedelta(days=1))
    before = {r["entry_id"]: len(rows_lines_for(tmp, r["entry_id"]))
              for r in (a, b)}

    invited = wave(service, count=2)
    assert invited == [a["entry_id"], b["entry_id"]]
    for row in (a, b):
        lines = rows_lines_for(tmp, row["entry_id"])
        assert len(lines) == before[row["entry_id"]] + 1, \
            f"expected exactly one commit line for {row['entry_id']}"
        line = lines[-1]
        assert line["status"] == "invited"
        assert line["invite_wave"] == "wave1"
        assert line["active_invite_token"].startswith("invite.")
        assert "invite_expires_at" in line


def test_wave_crash_between_spool_and_commit(monkeypatch):
    # Fault injection: kill the wave after the spool write succeeded
    # but before the single row commit. On-disk state must be
    # "confirmed row + stray spooled email" — never invited-without-
    # email — and the retry must degrade to duplicate-mail with a
    # fresh token, the stray email's link never validating.
    service, tmp, clock = make_service()
    a = confirm_row(service, "a@example.com", clock,
                    at=NOW - timedelta(days=2))
    lines_before = len(rows_lines_for(tmp, a["entry_id"]))

    real_save = wd.WaitlistService._save_row
    calls = {"n": 0}

    def crashing_save(self, row):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated kill -9")
        return real_save(self, row)

    monkeypatch.setattr(wd.WaitlistService, "_save_row", crashing_save)

    with pytest.raises(RuntimeError, match="simulated kill"):
        wave(service, count=2, wave="wave1")

    # The spool write landed (the failure mode is duplicate-mail), but
    # the row was never committed: rows.jsonl grew by zero lines.
    assert len(rows_lines_for(tmp, a["entry_id"])) == lines_before
    invites = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(invites) == 1
    stray_token = invites[0]["body"].split("token=")[1].split()[0]

    # A fresh process view (post-restart): the row is confirmed, the
    # stray token was never recorded, its link validates as dead.
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    frow = fresh.rows[a["entry_id"]]
    assert frow["status"] == "confirmed"
    assert "active_invite_token" not in frow
    _, outcome = fresh.lookup_invite_token(stray_token)
    assert outcome != "ok"

    # Retry: the row is invited with a FRESH token; the user gets a
    # second email (duplicate on retry), the first email's link stays
    # dead, and exactly one invite_sent event exists per committed row.
    spool = os.path.join(tmp, "spool")
    before_retry = set(os.listdir(spool))
    invited = fresh.send_invite_wave(pricing_lines=PRICING,
                                     trial_terms=TERMS, wave="wave2",
                                     count=2)
    assert invited == [a["entry_id"]]
    frow = fresh.rows[a["entry_id"]]
    assert frow["status"] == "invited"
    assert frow["invite_wave"] == "wave2"
    # The retry's commit was a single append too.
    assert len(rows_lines_for(tmp, a["entry_id"])) == lines_before + 1
    invites = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(invites) == 2
    # Both invite filenames share the frozen-clock prefix and differ
    # only in their random suffix, so sorted order is a coin flip —
    # identify the retry's doc by set difference instead.
    new_files = set(os.listdir(spool)) - before_retry
    assert len(new_files) == 1, \
        f"expected exactly one new spool doc, got {new_files}"
    new_doc = json.load(
        open(os.path.join(spool, new_files.pop()), encoding="utf-8"))
    assert new_doc.get("kind") == "invite"
    new_token = new_doc["body"].split("token=")[1].split()[0]
    assert new_token != stray_token
    assert frow["active_invite_token"] == new_token
    row_after_retry, outcome = fresh.lookup_invite_token(stray_token)
    assert row_after_retry is None and outcome == "consumed"
    row_new, outcome = fresh.lookup_invite_token(new_token)
    assert row_new is not None and outcome == "ok"
    sent = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(sent) == 1
    assert sent[0]["ref"] == a["entry_id"]


# ---------------------------------------------------------------------------
# Exact 14-day expiry boundary (QA B4): lookup and rollover agree
# ---------------------------------------------------------------------------


def test_invite_expiry_boundary_exact_14d():
    # At exactly 14d the token is expired (age >= TTL) — lookup and
    # the rollover job agree; one second earlier both say live.
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1)
    token = service.rows[row["entry_id"]]["active_invite_token"]
    clock.advance(seconds=wd.INVITE_TTL_SECONDS - 1)
    _, status = service.lookup_invite_token(token)
    assert status == "ok"
    assert service.rollover_expired_invites() == []
    assert service.rows[row["entry_id"]]["status"] == "invited"
    clock.advance(seconds=1)  # exactly 14d after the wave
    _, status = service.lookup_invite_token(token)
    assert status == "expired"
    assert service.rollover_expired_invites() == [row["entry_id"]]
    assert service.rows[row["entry_id"]]["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Fault injection: the remaining crash windows (deferred m2 follow-ups from
# the spool-then-single-commit reorder, PR #220)
# ---------------------------------------------------------------------------


def test_reinvite_crash_between_consume_and_commit(monkeypatch):
    # Fault injection for the `_consume_token(old)` -> commit window in
    # the re-invite path: the old token's consume lands on disk, then the
    # wave dies before the single row commit. On-disk state must be "old
    # token consumed, row still invited with the old token" — the
    # operator recovers by re-running the wave against the confirmed row,
    # which mints a fresh token; the stray email's link never validates.
    # (The flip-to-confirmed step is manual today; see issue #235 for
    # the operator-tooling gap.)
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    wave(service, count=1, wave="wave1")
    old_token = service.rows[row["entry_id"]]["active_invite_token"]
    lines_before = len(rows_lines_for(tmp, row["entry_id"]))

    # Operator error, like test_reinvite_consumes_old_token: the invited
    # row is flipped back to confirmed and a second wave re-invites it.
    service.rows[row["entry_id"]]["status"] = "confirmed"

    crash = {"armed": True}
    real_save = wd.WaitlistService._save_row

    def crashing_save(self, r):
        if crash["armed"]:
            crash["armed"] = False
            raise RuntimeError("simulated kill -9")
        return real_save(self, r)

    monkeypatch.setattr(wd.WaitlistService, "_save_row", crashing_save)

    with pytest.raises(RuntimeError, match="simulated kill"):
        wave(service, count=1, wave="wave2")

    # The consume landed on disk (append-only file); the row commit did
    # not: rows.jsonl grew by zero lines, the on-disk row is still
    # invited with the old token, and the crashed wave's email is a
    # stray — the old token validates as consumed, the stray as dead.
    with open(os.path.join(tmp, "consumed_tokens.txt"),
              encoding="utf-8") as fh:
        assert old_token in fh.read().split()
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before
    disk_row = rows_lines_for(tmp, row["entry_id"])[-1]
    assert disk_row["status"] == "invited"
    assert disk_row["active_invite_token"] == old_token

    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    _, status = fresh.lookup_invite_token(old_token)
    assert status == "consumed"
    stray_docs = [d for d in spool_docs(tmp)
                  if d.get("kind") == "invite"]
    assert len(stray_docs) == 2  # wave1's email + the stray
    stray_tokens = {d["body"].split("token=")[1].split()[0]
                    for d in stray_docs}
    stray_token = (stray_tokens - {old_token}).pop()
    _, status = fresh.lookup_invite_token(stray_token)
    # Never recorded as the live token: fails the active-token check.
    assert status == "consumed"

    # Operator recovery (manual today — see issue #235 for the
    # operator-tooling gap): flip back to confirmed, re-run the wave.
    # The re-consume is a no-op, the new token mints and commits, and
    # the metrics stay conservative — exactly one invite_sent per
    # committed row. The crashed wave's stray email counts against the
    # §4 3/24h cap (it went out), so the recovery runs once the window
    # rolls.
    fresh.rows[row["entry_id"]]["status"] = "confirmed"
    clock.advance(hours=25)
    monkeypatch.setattr(wd.WaitlistService, "_save_row", real_save)
    invited = fresh.send_invite_wave(pricing_lines=PRICING,
                                     trial_terms=TERMS, wave="wave3",
                                     count=1)
    assert invited == [row["entry_id"]]
    frow = fresh.rows[row["entry_id"]]
    assert frow["status"] == "invited"
    new_token = frow["active_invite_token"]
    assert new_token not in (old_token, stray_token)
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before + 1
    _, status = fresh.lookup_invite_token(new_token)
    assert status == "ok"
    _, status = fresh.lookup_invite_token(old_token)
    assert status == "consumed"
    sent = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(sent) == 2
    assert all(e["ref"] == row["entry_id"] for e in sent)


def test_wave_crash_between_commit_and_emit(monkeypatch):
    # Fault injection for the commit -> `invite_sent` emit window: the
    # row commit lands, then the process dies before the funnel event.
    # On-disk state must be "invited row committed, email spooled, no
    # invite_sent event" — the metrics read conservatively and never
    # claim what rows.jsonl doesn't show. The retry must not re-invite
    # or double-spool.
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    lines_before = len(rows_lines_for(tmp, row["entry_id"]))

    crash = {"armed": True}
    real_emit = wd.WaitlistService._emit

    def crashing_emit(self, event, ref, attrs=None):
        if event == "invite_sent" and crash["armed"]:
            crash["armed"] = False
            raise RuntimeError("simulated kill -9")
        return real_emit(self, event, ref, attrs)

    monkeypatch.setattr(wd.WaitlistService, "_emit", crashing_emit)

    with pytest.raises(RuntimeError, match="simulated kill"):
        wave(service, count=1, wave="wave1")

    # The commit landed but the event did not: the row is invited on
    # disk, exactly one invite email is spooled, and funnel_events has
    # no invite_sent.
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before + 1
    disk_row = rows_lines_for(tmp, row["entry_id"])[-1]
    assert disk_row["status"] == "invited"
    token = disk_row["active_invite_token"]
    invites = [d for d in spool_docs(tmp) if d.get("kind") == "invite"]
    assert len(invites) == 1
    assert token in invites[0]["body"]
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]

    # Fresh view: the token is live; a retry waves nothing (invited
    # rows are not eligible) — no duplicate email, no synthesized event.
    # The missing event is repaired by the operator's --reconcile pass
    # (issue #234; covered by the test_reconcile_* tests below).
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    frow, status = fresh.lookup_invite_token(token)
    assert status == "ok" and frow["entry_id"] == row["entry_id"]
    monkeypatch.setattr(wd.WaitlistService, "_emit", real_emit)
    assert fresh.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                  wave="wave2", count=1) == []
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before + 1
    assert len([d for d in spool_docs(tmp)
                if d.get("kind") == "invite"]) == 1
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]


def test_rollover_crash_between_consume_and_commit(monkeypatch):
    # Fault injection for the `_consume_token` -> commit window in the
    # §7 expiry rollover: the invite token is consumed on disk, then the
    # crash hits before the row's return-to-confirmed commit. The retry
    # must finish the rollover cleanly — re-consume is a no-op, no
    # re-confirmation, no new funnel event.
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    invited_at = clock()
    wave(service, count=1, wave="wave1")
    token = service.rows[row["entry_id"]]["active_invite_token"]
    clock.advance(days=15)
    lines_before = len(rows_lines_for(tmp, row["entry_id"]))

    crash = {"armed": True}
    real_save = wd.WaitlistService._save_row

    def crashing_save(self, r):
        if crash["armed"]:
            crash["armed"] = False
            raise RuntimeError("simulated kill -9")
        return real_save(self, r)

    monkeypatch.setattr(wd.WaitlistService, "_save_row", crashing_save)

    with pytest.raises(RuntimeError, match="simulated kill"):
        service.rollover_expired_invites()

    # Consumed on disk, row untouched: still invited with the old
    # active token, rows.jsonl grew by zero lines.
    with open(os.path.join(tmp, "consumed_tokens.txt"),
              encoding="utf-8") as fh:
        assert token in fh.read().split()
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before
    disk_row = rows_lines_for(tmp, row["entry_id"])[-1]
    assert disk_row["status"] == "invited"
    assert disk_row["active_invite_token"] == token

    # Fresh view: the token reads consumed, the rollover is idempotent
    # — the retry completes it: back to confirmed at the EXPIRY time,
    # token fields popped, no funnel event.
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    _, status = fresh.lookup_invite_token(token)
    assert status == "consumed"
    monkeypatch.setattr(wd.WaitlistService, "_save_row", real_save)
    rolled = fresh.rollover_expired_invites()
    assert rolled == [row["entry_id"]]
    frow = fresh.rows[row["entry_id"]]
    assert frow["status"] == "confirmed"
    expiry = invited_at + timedelta(seconds=wd.INVITE_TTL_SECONDS)
    assert frow["confirmed_at"] == wd.iso_z(expiry)
    for key in ("invited_at", "invite_expires_at", "invite_wave",
                "active_invite_token"):
        assert key not in frow
    _, status = fresh.lookup_invite_token(token)
    assert status == "consumed"
    kinds = [e["event"] for e in funnel_events(tmp)]
    assert kinds.count("invite_sent") == 1
    assert "invite_expired" not in kinds
    assert len(rows_lines_for(tmp, row["entry_id"])) == lines_before + 1


# ---------------------------------------------------------------------------
# invite_sent reconciliation (issue #234)


def _crash_emit_once(monkeypatch, crash):
    """Fault-inject the commit -> invite_sent emit crash window."""
    real_emit = wd.WaitlistService._emit

    def crashing_emit(self, event, ref, attrs=None):
        if event == "invite_sent" and crash["armed"]:
            crash["armed"] = False
            raise RuntimeError("simulated kill -9")
        return real_emit(self, event, ref, attrs)

    monkeypatch.setattr(wd.WaitlistService, "_emit", crashing_emit)
    return real_emit


def _torn_append_once(monkeypatch, flag):
    """Fault-inject a kill -9 mid-append: write the first half of the
    payload, then raise — leaving a torn partial line with NO trailing
    newline at EOF, the way a real kill -9 tears the last append."""
    real_append = wd.WaitlistService._append

    def torn_append(self, name, obj):
        if flag["armed"] and name == "funnel_events.jsonl":
            flag["armed"] = False
            line = json.dumps(obj, sort_keys=True)
            path = os.path.join(self.data_dir, name)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line[:len(line) // 2])  # torn: no newline
            raise RuntimeError("simulated kill -9 mid-append")
        return real_append(self, name, obj)

    monkeypatch.setattr(wd.WaitlistService, "_append", torn_append)
    return real_append


def _crashed_invite_state(monkeypatch, clock=None):
    """Drive a wave into the commit -> emit crash window and return
    (tmp, clock, entry_id, live_token): an invited row committed on
    disk, exactly one invite email spooled, no invite_sent event."""
    service, tmp, clock = make_service(clock)
    row = confirm_row(service, "a@example.com", clock)
    crash = {"armed": True}
    _crash_emit_once(monkeypatch, crash)
    with pytest.raises(RuntimeError, match="simulated kill"):
        wave(service, count=1, wave="wave1")
    token = rows_lines_for(tmp, row["entry_id"])[-1]["active_invite_token"]
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]
    return tmp, clock, row["entry_id"], token


def test_reconcile_repairs_commit_crash_window(monkeypatch):
    tmp, clock, entry_id, token = _crashed_invite_state(monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    # The invite is live — the event is the only thing missing.
    _, status = fresh.lookup_invite_token(token)
    assert status == "ok"

    reconciled = fresh.reconcile_invite_events()
    assert reconciled == [entry_id]

    events = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(events) == 1
    event = events[0]
    assert event["ref"] == entry_id
    assert event["attrs"]["reconciled"] is True
    assert event["attrs"]["via"] == "reconcile_invite_events"
    assert event["attrs"]["wave"] == "wave1"
    assert "reason" in event["attrs"]
    # The 4-tuple shape the funnel taxonomy prescribes is preserved.
    assert set(event) == {"event", "at", "ref", "attrs"}

    # Idempotent: a second pass emits nothing new.
    assert fresh.reconcile_invite_events() == []
    assert len([e for e in funnel_events(tmp)
                if e["event"] == "invite_sent"]) == 1


def test_reconcile_skips_healthy_invite():
    service, tmp, clock = make_service()
    confirm_row(service, "a@example.com", clock)
    wave(service, count=1, wave="wave1")
    assert service.reconcile_invite_events() == []


def test_reconcile_skips_rolled_back_invite(monkeypatch):
    # Crash window, then the invite expires and rolls back to confirmed:
    # the dead invite can't convert, so there is no event to claim —
    # the next wave's fresh invite carries its own.
    tmp, clock, entry_id, token = _crashed_invite_state(monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    clock.advance(days=15)
    assert fresh.rollover_expired_invites() == [entry_id]
    assert fresh.rows[entry_id]["status"] == "confirmed"
    assert fresh.reconcile_invite_events() == []
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]

    # The next wave re-invites cleanly with its own event; reconcile
    # then has nothing to repair either.
    assert fresh.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                  wave="wave2", count=1) == [entry_id]
    events = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(events) == 1
    assert events[0]["ref"] == entry_id
    assert "reconciled" not in events[0]["attrs"]
    assert fresh.reconcile_invite_events() == []


def test_reconcile_skips_expired_live_invite(monkeypatch):
    # Crash window, then the invite expires with no rollover run (cron
    # down): the token is dead, the claim can never happen. Reconcile
    # stays conservative and emits nothing — recovery is the #235
    # operator tooling, not this pass.
    tmp, clock, entry_id, token = _crashed_invite_state(monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    clock.advance(days=15)
    _, status = fresh.lookup_invite_token(token)
    assert status == "expired"
    assert fresh.reconcile_invite_events() == []
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]


def test_reconcile_uses_current_invite_window(monkeypatch):
    # A re-invited row legitimately has an OLD invite_sent for its
    # previous invite; the at >= invited_at check means only the
    # current invite's event counts as covering.
    service, tmp, clock = make_service()
    row = confirm_row(service, "a@example.com", clock)
    entry_id = row["entry_id"]
    wave(service, count=1, wave="wave1")
    old_token = rows_lines_for(tmp, entry_id)[-1]["active_invite_token"]
    assert len([e for e in funnel_events(tmp)
                if e["event"] == "invite_sent"]) == 1

    # Expire + roll over, then crash the reinvite's emit window.
    clock.advance(days=15)
    assert service.rollover_expired_invites() == [entry_id]
    crash = {"armed": True}
    _crash_emit_once(monkeypatch, crash)
    with pytest.raises(RuntimeError, match="simulated kill"):
        wave(service, count=1, wave="wave2")
    new_token = rows_lines_for(tmp, entry_id)[-1]["active_invite_token"]
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    _, status = fresh.lookup_invite_token(old_token)
    assert status == "consumed"
    _, status = fresh.lookup_invite_token(new_token)
    assert status == "ok"

    # The old event does NOT cover the new invite: one reconciled event
    # is emitted for the current window, and re-running emits nothing.
    assert fresh.reconcile_invite_events() == [entry_id]
    events = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(events) == 2
    assert events[-1]["attrs"]["reconciled"] is True
    assert events[-1]["attrs"]["wave"] == "wave2"
    assert fresh.reconcile_invite_events() == []


def test_reconcile_dry_run(monkeypatch):
    tmp, clock, entry_id, _ = _crashed_invite_state(monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    assert fresh.reconcile_invite_events(dry_run=True) == [entry_id]
    # Dry run appends nothing.
    assert "invite_sent" not in [e["event"] for e in funnel_events(tmp)]
    assert fresh.reconcile_invite_events() == [entry_id]
    assert len([e for e in funnel_events(tmp)
                if e["event"] == "invite_sent"]) == 1


def test_reconcile_skips_torn_events_line(monkeypatch, capsys):
    service, tmp, clock = make_service()
    confirm_row(service, "a@example.com", clock)
    wave(service, count=1, wave="wave1")
    # A kill -9 can tear the last append mid-line; the pass must skip
    # the torn line loudly and still work — and the real event covers.
    with open(os.path.join(tmp, "funnel_events.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write("this is not json\n")
    assert service.reconcile_invite_events() == []
    assert "torn" in capsys.readouterr().err


def test_cli_reconcile(tmp_path, monkeypatch, capsys):
    # The operator path: crashed on disk, repaired through wi.main with
    # no WAITLIST_CLAIM_LIVE gate (reconcile sends no email).
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    monkeypatch.setenv("WAITLIST_PUBLIC_HOST",
                       "https://waitlist.example.invalid")
    monkeypatch.delenv("WAITLIST_CLAIM_LIVE", raising=False)
    service = wd.WaitlistService(str(data), KEY,
                                 "https://waitlist.example.invalid",
                                 clock=MutClock())
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    crash = {"armed": True}
    _crash_emit_once(monkeypatch, crash)
    with pytest.raises(RuntimeError, match="simulated kill"):
        service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                 wave="wave1", count=1)
    del service  # the CLI re-reads from disk under data_lock

    assert wi.main(["--reconcile", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would reconcile 1 missing invite_sent event(s)" in out
    assert entry_id in out

    assert wi.main(["--reconcile"]) == 0
    out = capsys.readouterr().out
    assert "reconciled 1 missing invite_sent event(s)" in out
    assert entry_id in out

    # Idempotent through the CLI as well.
    assert wi.main(["--reconcile"]) == 0
    assert "reconciled 0 missing invite_sent event(s)" in \
        capsys.readouterr().out


def test_reconcile_quarantines_torn_tail(monkeypatch):
    """A kill -9-torn invite_sent line must not glue the re-derived event
    onto the torn partial: the event occupies its own parseable physical
    line, exactly one invite_sent exists, and a second pass is a no-op.

    (Deliberate deviation from one reviewer-suggested assertion: the
    torn partial itself stays unparseable by design — the quarantine
    terminates it, never repairs it — so this pins "exactly one
    unparseable line, the torn partial" rather than "every line
    parses". Reconcile never amplifies the damage; its own emissions
    are always parseable and covering.)"""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    torn = {"armed": True}
    _torn_append_once(monkeypatch, torn)
    with pytest.raises(RuntimeError, match="simulated kill -9"):
        service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                 wave="wave1", count=1)

    reconciled = service.reconcile_invite_events()
    assert reconciled == [entry_id]

    with open(os.path.join(tmp, "funnel_events.jsonl"),
              encoding="utf-8") as fh:
        raw = fh.read()
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    parsed, unparseable = [], []
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            unparseable.append(ln)
    # The only unparseable line is the kill -9-torn partial itself.
    assert len(unparseable) == 1
    sent = [e for e in parsed if e["event"] == "invite_sent"]
    assert len(sent) == 1
    assert sent[0]["attrs"]["reconciled"] is True
    # The re-derived event sits on its OWN physical line (no gluing):
    # re-serializing it must recover exactly one line of the file.
    assert json.dumps(sent[0], sort_keys=True) in lines

    # The event now covers: a second pass is a clean no-op.
    assert service.reconcile_invite_events() == []


def test_reconcile_skips_consumed_active_token():
    """Reinvite crash between _consume_token and the re-commit
    (issue #235): the row is still invited but its active token reads
    'consumed' — reconcile must not emit; recovery is #235 tooling."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    entry_id = row["entry_id"]
    row = service.rows[entry_id]  # re-fetch: the wave re-saved the row
    assert service.lookup_invite_token(row["active_invite_token"])[1] == "ok"
    # Simulate the #235 crash: token consumed, row never re-committed.
    service._consume_token(row["active_invite_token"])
    assert service.lookup_invite_token(
        row["active_invite_token"])[1] == "consumed"

    assert service.reconcile_invite_events() == []
    sent = [e for e in funnel_events(tmp)
            if e["event"] == "invite_sent" and e["ref"] == entry_id]
    assert len(sent) == 1  # the original wave event only


def test_cli_reconcile_exactly_one_of(monkeypatch):
    """--reconcile combined with --send-wave exits 2 before any work."""
    service, tmp, clock = make_service()
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY)
    monkeypatch.setenv("WAITLIST_DATA", tmp)
    monkeypatch.setenv("WAITLIST_PUBLIC_HOST",
                       "https://waitlist.example.invalid")
    with pytest.raises(SystemExit) as exc:
        wi.main(["--send-wave", "--wave", "w1", "--reconcile"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        wi.main(["--reinstate-confirmed", "--rollover"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        wi.main(["--diagnose", "--send-wave"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# --reinstate-confirmed / --diagnose (issue #235)
# ---------------------------------------------------------------------------


def _crash_reinvite(service, monkeypatch):
    """Fault-inject the `_consume_token(old)` -> row-commit crash window
    from test_reinvite_crash_between_consume_and_commit: the old token's
    consume lands on disk, the row commit does not. Returns the row and
    the on-disk state."""
    tmp = service.data_dir
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    old_token = service.rows[entry_id]["active_invite_token"]
    lines_before = len(rows_lines_for(tmp, entry_id))

    crash = {"armed": True}
    real_save = wd.WaitlistService._save_row

    def crashing_save(self, r):
        if crash["armed"]:
            crash["armed"] = False
            raise RuntimeError("simulated kill -9")
        return real_save(self, r)

    monkeypatch.setattr(wd.WaitlistService, "_save_row", crashing_save)
    # Operator error, as in the fault-injection test: the invited row is
    # flipped back to confirmed (in-memory only) and a second wave
    # re-invites it, dying between _consume_token(old) and the commit.
    service.rows[entry_id]["status"] = "confirmed"
    with pytest.raises(RuntimeError, match="simulated kill"):
        service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                 wave="wave2", count=1)
    monkeypatch.setattr(wd.WaitlistService, "_save_row", real_save)
    disk_row = rows_lines_for(tmp, entry_id)[-1]
    assert disk_row["status"] == "invited"
    assert disk_row["active_invite_token"] == old_token
    return tmp, entry_id, old_token, lines_before


def test_reinstate_refuses_expired(monkeypatch):
    """B1: an expired-but-unconsumed invite is refused fail-loud —
    reinstating would keep the original queue position and silently
    skip the disclosed 14-day expiry -> back-of-queue rule. --rollover
    is the only path; --force does not override this."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    clock.advance(days=15)
    assert service.lookup_invite_token(
        service.rows[entry_id]["active_invite_token"])[1] == "expired"
    lines_before = len(rows_lines_for(tmp, entry_id))

    with pytest.raises(ValueError, match="--rollover"):
        service.reinstate_confirmed([entry_id], reason="stale invite")
    # The dry run refuses identically — no preview/reality divergence.
    with pytest.raises(ValueError, match="--rollover"):
        service.reinstate_confirmed([entry_id], reason="stale invite",
                                    dry_run=True)
    # --force is for retiring LIVE claim links, not for overriding
    # the disclosed expiry.
    with pytest.raises(ValueError, match="--rollover"):
        service.reinstate_confirmed([entry_id], reason="stale invite",
                                    force=True)
    assert len(rows_lines_for(tmp, entry_id)) == lines_before
    assert service.rows[entry_id]["status"] == "invited"


def test_reinstate_dedupes_entry_ids(monkeypatch):
    """E1: the same --entry-id twice appends exactly one revision."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    tmp, entry_id, old_token, lines_before = _crash_reinvite(service,
                                                            monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    reinstated = fresh.reinstate_confirmed(
        [entry_id, entry_id], reason="double-flagged by the operator")
    assert reinstated == [entry_id]
    assert len(rows_lines_for(tmp, entry_id)) == lines_before + 1


def test_reinstate_cross_wired_token(monkeypatch):
    """E2: a hand-damaged row carrying ANOTHER entry's live token
    diagnoses as "invalid" — never that entry's state — and repairing it
    (even with --force) never retires the other entry's claim link."""
    service, tmp, clock = make_service()
    ra = confirm_row(service, "a@example.com", clock,
                     at=NOW - timedelta(days=2))
    rb = confirm_row(service, "b@example.com", clock,
                     at=NOW - timedelta(days=1))
    clock.advance(hours=25)
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=2)
    ea, eb = ra["entry_id"], rb["entry_id"]
    b_token = service.rows[eb]["active_invite_token"]
    assert service.lookup_invite_token(b_token)[1] == "ok"
    # Hand-damage: A's row now carries B's live token.
    arow = service.rows[ea]
    arow["active_invite_token"] = b_token
    service._save_row(arow)

    diag = {d["entry_id"]: d for d in service.diagnose_invites()}
    assert diag[ea]["token_state"] == "invalid"
    assert "by hand" in diag[ea]["recommendation"]

    # Repairing A retires nothing of B's: the cross-wired token reads
    # "invalid", never "ok", so the force path never consumes it.
    service.reinstate_confirmed([ea], reason="cross-wired token")
    assert service.rows[ea]["status"] == "confirmed"
    assert service.lookup_invite_token(b_token)[1] == "ok"
    assert service.rows[eb]["status"] == "invited"


def test_reinstate_confirmed_crash_repair(monkeypatch):
    """#235 acceptance: the test-1 fault-injection recovery (invited row,
    token consumed, commit never landed) now runs through
    reinstate_confirmed — no hand-editing rows.jsonl."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    tmp, entry_id, old_token, lines_before = _crash_reinvite(service,
                                                            monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    assert fresh.lookup_invite_token(old_token)[1] == "consumed"
    confirmed_at = [r for r in rows_lines_for(tmp, entry_id)
                    if "confirmed_at" in r][-1]["confirmed_at"]
    events_before = funnel_events(tmp)
    spool_before = spool_docs(tmp)

    reinstated = fresh.reinstate_confirmed(
        [entry_id], reason="wave2 crashed between consume and commit; "
                           "re-waving with a fresh token")
    assert reinstated == [entry_id]
    frow = fresh.rows[entry_id]
    assert frow["status"] == "confirmed"
    # Crash repair, not expiry: the entry keeps its original queue
    # position; the invite keys are popped (rollover convention).
    assert frow["confirmed_at"] == confirmed_at
    for key in ("invited_at", "invite_expires_at", "invite_wave",
                "active_invite_token"):
        assert key not in frow
    assert frow["reinstate_reason"].startswith("wave2 crashed")
    assert "reinstate_at" in frow
    # Exactly one new rows.jsonl revision for the flip.
    assert len(rows_lines_for(tmp, entry_id)) == lines_before + 1
    # No funnel event for the reinstatement (taxonomy has none): the
    # event log is identical before and after the flip.
    assert funnel_events(tmp) == events_before
    # The reinstate itself spools nothing (no email): the documented
    # "sends no email" guarantee the §4 cap accounting depends on.
    assert spool_docs(tmp) == spool_before

    # The re-wave mints a fresh token; the stray email's link never
    # validates; exactly one invite_sent per committed row.
    clock.advance(hours=25)  # the stray email counted against the §4 cap
    invited = fresh.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                     wave="wave3", count=1)
    assert invited == [entry_id]
    new_token = fresh.rows[entry_id]["active_invite_token"]
    assert new_token != old_token
    assert fresh.lookup_invite_token(new_token)[1] == "ok"
    assert fresh.lookup_invite_token(old_token)[1] == "consumed"
    sent = [e for e in funnel_events(tmp) if e["event"] == "invite_sent"]
    assert len(sent) == 2


def test_reinstate_refuses_live_token(monkeypatch):
    """A live invite is refused without --force: reinstating would kill
    the claim link, so the operator must say so explicitly."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    token = service.rows[entry_id]["active_invite_token"]
    lines_before = len(rows_lines_for(tmp, entry_id))

    with pytest.raises(ValueError, match="still LIVE"):
        service.reinstate_confirmed([entry_id], reason="bounced email")
    # Nothing mutated: the row is still invited, no new revision.
    assert len(rows_lines_for(tmp, entry_id)) == lines_before
    assert service.rows[entry_id]["status"] == "invited"
    assert service.lookup_invite_token(token)[1] == "ok"


def test_reinstate_force_consumes_live_token(monkeypatch):
    """--force retires a live invite honestly: the token is consumed at
    reinstate time so the trail reads 'consumed', then the re-wave mints
    fresh."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    token = service.rows[entry_id]["active_invite_token"]
    clock.advance(hours=25)

    spool_before = spool_docs(tmp)
    reinstated = service.reinstate_confirmed(
        [entry_id], reason="invite email bounced; re-waving", force=True)
    assert reinstated == [entry_id]
    assert spool_docs(tmp) == spool_before  # no email from the reinstate
    frow = service.rows[entry_id]
    assert frow["status"] == "confirmed"
    assert frow["reinstate_consumed_live_token"] is True
    assert service.lookup_invite_token(token)[1] == "consumed"

    invited = service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                       wave="wave2", count=1)
    assert invited == [entry_id]
    assert service.lookup_invite_token(
        service.rows[entry_id]["active_invite_token"])[1] == "ok"


def test_reinstate_rejects_bad_entries(monkeypatch):
    """Unknown entries, non-invited rows, and an empty reason all fail
    loud — and validation runs before ANY row is mutated."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    row = service.rows[service.by_email["a@example.com"]]
    service.confirm_post(row["active_token"])
    entry_id = row["entry_id"]
    lines_before = len(rows_lines_for(tmp, entry_id))

    with pytest.raises(ValueError, match="no such entry"):
        service.reinstate_confirmed(["nope"], reason="x")
    with pytest.raises(ValueError, match="not 'invited'"):
        service.reinstate_confirmed([entry_id], reason="x")
    with pytest.raises(ValueError, match="reason is required"):
        service.reinstate_confirmed([entry_id], reason="   ")

    # No partial application: a valid + invalid pair commits nothing.
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    service._consume_token(service.rows[entry_id]["active_invite_token"])
    with pytest.raises(ValueError, match="no such entry"):
        service.reinstate_confirmed([entry_id, "nope"], reason="x")
    assert len(rows_lines_for(tmp, entry_id)) == lines_before + 1  # wave only
    assert service.rows[entry_id]["status"] == "invited"


def test_reinstate_dry_run_changes_nothing(monkeypatch):
    """dry_run returns the plan; rows.jsonl is untouched."""
    service, tmp, clock = make_service()
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    tmp, entry_id, old_token, lines_before = _crash_reinvite(service,
                                                            monkeypatch)
    fresh = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    plan = fresh.reinstate_confirmed([entry_id], reason="x", dry_run=True)
    assert len(plan) == 1
    assert plan[0]["entry_id"] == entry_id
    assert plan[0]["token_state"] == "consumed"
    assert "flip to confirmed" in plan[0]["would"]
    assert len(rows_lines_for(tmp, entry_id)) == lines_before
    assert fresh.rows[entry_id]["status"] == "invited"


def test_reinstate_keeps_queue_position(monkeypatch):
    """Two confirmed rows: the reinstated one rejoins at its original
    confirmed_at — ahead of the entry that confirmed after it."""
    service, tmp, clock = make_service()
    first = confirm_row(service, "a@example.com", clock,
                        at=NOW - timedelta(days=2))
    second = confirm_row(service, "b@example.com", clock,
                         at=NOW - timedelta(days=1))
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    service._consume_token(service.rows[first["entry_id"]]
                           ["active_invite_token"])
    clock.advance(hours=25)
    service.reinstate_confirmed([first["entry_id"]], reason="crash repair")
    # FIFO: the reinstated entry (older confirmed_at) invites first.
    invited = service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                       wave="wave2", count=2)
    assert invited[0] == first["entry_id"]
    assert invited[1] == second["entry_id"]


def test_diagnose_invites(monkeypatch):
    """Every invited row is bucketed: live, consumed (crash-suspect),
    expired (rollover-due), and hand-damaged (missing token)."""
    service, tmp, clock = make_service()
    # Distinct confirmed_at values: FIFO order across the two waves is
    # deterministic (same-second confirms tie-break on the random
    # entry_id, which would make the wave membership nondeterministic).
    emails = ["a@example.com", "b@example.com", "c@example.com",
              "d@example.com"]
    by_email = {}
    for i, email in enumerate(emails):
        row = confirm_row(service, email, clock,
                          at=NOW - timedelta(days=20 - i))
        by_email[email] = row["entry_id"]
    # Two waves 15 days apart give per-row invite ages: a and b's
    # invites go out first (expired by the second wave), c's and d's
    # are live.
    clock.advance(hours=25)  # clear of the §4 cap
    assert service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                    wave="wave1", count=2) == \
        [by_email["a@example.com"], by_email["b@example.com"]]
    clock.advance(days=15)
    assert service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                                    wave="wave2", count=2) == \
        [by_email["c@example.com"], by_email["d@example.com"]]
    # b: the crash state (token consumed, row still invited).
    service._consume_token(service.rows[by_email["b@example.com"]]
                           ["active_invite_token"])
    # d: hand-damaged — no invite token recorded.
    drow = service.rows[by_email["d@example.com"]]
    del drow["active_invite_token"]
    service._save_row(drow)

    diag = {d["entry_id"]: d for d in service.diagnose_invites()}
    assert set(diag) == set(by_email.values())
    assert diag[by_email["c@example.com"]]["token_state"] == "ok"
    assert "nothing to do" in diag[by_email["c@example.com"]]\
        ["recommendation"]
    assert diag[by_email["b@example.com"]]["token_state"] == "consumed"
    assert "--reinstate-confirmed" in diag[by_email["b@example.com"]]\
        ["recommendation"]
    assert diag[by_email["a@example.com"]]["token_state"] == "expired"
    assert "--rollover" in diag[by_email["a@example.com"]]["recommendation"]
    assert diag[by_email["d@example.com"]]["token_state"] == "missing"
    assert "by hand" in diag[by_email["d@example.com"]]["recommendation"]
    # Owner is masked, never the full address.
    assert all("@" not in d["owner"] for d in diag.values())


def _cli_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("WAITLIST_DATA", str(data))
    monkeypatch.setenv("WAITLIST_PUBLIC_HOST",
                       "https://waitlist.example.invalid")
    monkeypatch.delenv("WAITLIST_CLAIM_LIVE", raising=False)
    return str(data)


def test_cli_reinstate_and_diagnose(tmp_path, monkeypatch, capsys):
    """The operator path end to end: diagnose the crash state, preview
    with --dry-run, reinstate, re-wave. No WAITLIST_CLAIM_LIVE gate —
    nothing here sends email."""
    data = _cli_env(monkeypatch, tmp_path)
    clock = MutClock()
    service = wd.WaitlistService(data, KEY, "https://waitlist.example.invalid",
                                 clock=clock)
    service.submit_form({"owner_email": "a@example.com"}, "127.0.0.1")
    service.confirm_post(service.rows[service.by_email["a@example.com"]]
                         ["active_token"])
    entry_id = service.rows[service.by_email["a@example.com"]]["entry_id"]
    monkeypatch.setenv("WAITLIST_CLAIM_LIVE", "1")
    service.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                             wave="wave1", count=1)
    monkeypatch.delenv("WAITLIST_CLAIM_LIVE", raising=False)
    # Simulate the #235 crash: token consumed, row never re-committed.
    service._consume_token(service.rows[entry_id]["active_invite_token"])
    del service  # the CLI re-reads from disk under data_lock

    assert wi.main(["--diagnose"]) == 0
    out = capsys.readouterr().out
    assert entry_id in out and "consumed" in out
    assert "--reinstate-confirmed" in out

    assert wi.main(["--reinstate-confirmed", "--entry-id", entry_id,
                    "--reason", "wave2 crash; re-waving", "--dry-run"]) == 0
    assert "would" in capsys.readouterr().out

    assert wi.main(["--reinstate-confirmed", "--entry-id", entry_id,
                    "--reason", "wave2 crash; re-waving"]) == 0
    out = capsys.readouterr().out
    assert "reinstated 1 row(s)" in out and entry_id in out

    fresh = wd.WaitlistService(data, KEY, "https://waitlist.example.invalid",
                               clock=clock)
    frow = fresh.rows[entry_id]
    assert frow["status"] == "confirmed"
    assert frow["reinstate_reason"] == "wave2 crash; re-waving"

    # --reason is required even in dry-run; --entry-id is required.
    with pytest.raises(SystemExit) as exc:
        wi.main(["--reinstate-confirmed", "--entry-id", entry_id,
                 "--dry-run"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        wi.main(["--reinstate-confirmed", "--reason", "x"])
    assert exc.value.code == 2
    # Reinstating an already-confirmed row is refused (nothing to do).
    with pytest.raises(SystemExit) as exc:
        wi.main(["--reinstate-confirmed", "--entry-id", entry_id,
                 "--reason", "x"])
    assert exc.value.code == 2

    # Live-token refusal through the CLI without --force; --force
    # retires the live token and the row rejoins confirmed.
    clock2 = MutClock()
    clock2.advance(hours=25)  # the §4 cap is per 24h rolling window
    svc2 = wd.WaitlistService(data, KEY, "https://waitlist.example.invalid",
                              clock=clock2)
    svc2.submit_form({"owner_email": "b@example.com"}, "127.0.0.1")
    svc2.confirm_post(svc2.rows[svc2.by_email["b@example.com"]]
                      ["active_token"])
    eid2 = svc2.rows[svc2.by_email["b@example.com"]]["entry_id"]
    monkeypatch.setenv("WAITLIST_CLAIM_LIVE", "1")
    # count=2: the reinstated a@example.com (original, older
    # confirmed_at) re-waves first, then b — both hold live tokens.
    svc2.send_invite_wave(pricing_lines=PRICING, trial_terms=TERMS,
                          wave="wave2", count=2)
    monkeypatch.delenv("WAITLIST_CLAIM_LIVE", raising=False)
    del svc2
    with pytest.raises(SystemExit) as exc:
        wi.main(["--reinstate-confirmed", "--entry-id", eid2,
                 "--reason", "bounced"])
    assert exc.value.code == 2
    assert "LIVE" in capsys.readouterr().err
    assert wi.main(["--reinstate-confirmed", "--entry-id", eid2,
                    "--reason", "bounced", "--force"]) == 0
    assert "reinstated 1 row(s)" in capsys.readouterr().out
    svc3 = wd.WaitlistService(data, KEY, "https://waitlist.example.invalid",
                              clock=clock2)
    assert svc3.rows[eid2]["reinstate_consumed_live_token"] is True

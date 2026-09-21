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

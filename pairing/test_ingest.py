"""Tests for spark-pair.py ingest (issue #874: box-side durable-command ingest).

The HTTP layer is stubbed (fake plane); the approvals store is a tmp dir
(SVM_APPROVALS_DIR); the grant mint is stubbed at the _mint_grant seam.
Each test proves a security property of the ingest, not just wiring:
proof-of-plane-origin binding, idempotent stamping, the acked-watermark
cursor contract, tenant/aid binding, and fail-closed behavior.
"""
import io
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import spark_pair


BOX_ID = "box-test"
TOKEN = "tok-test"
AID = "a1b2c3d4e5f60718"
AID2 = "b2c3d4e5f60718293"


class Ctx:
    """Fake argparse namespace for cmd_ingest."""
    def __init__(self, tmp_path, **kw):
        self.dir = str(tmp_path / "state")
        self.control = "https://control.test"
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    c = Ctx(tmp_path)
    c.tmp = tmp_path  # the audit-line tests read CONFIRM_AUDIT here
    approvals = tmp_path / "approvals"
    for sub in ("pending", "answered", "consumed"):
        (approvals / sub).mkdir(parents=True)
    monkeypatch.setenv("SVM_APPROVALS_DIR", str(approvals))
    # Finding-50 fix: the requester is the pending file's owner, never a
    # field the item carries. Tests control it by patching the owner
    # lookup (the real filesystem owner in CI is not bdrive/swapd).
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "swapd")
    # Architecture B3: the ingest appends `answer` audit lines mirroring
    # confirmd's trail. Point the audit path at a tmp file per test.
    monkeypatch.setenv("CONFIRM_AUDIT",
                       str(tmp_path / "audit.log"))
    os.makedirs(c.dir, mode=0o700, exist_ok=True)
    with open(os.path.join(c.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": TOKEN}, f)
    c.approvals = str(approvals)
    return c


def _future_iso(seconds=3600):
    return (datetime.now(timezone.utc)
            + timedelta(seconds=seconds)).isoformat()


def _file_pending(ctx, aid=AID, **kw):
    # No "requester" field: Finding-50 reads the requester from the
    # file's owner, so a field here would be misleading (never consulted).
    item = {"id": aid, "credential": "openai", "host": "api.openai.com",
            "method": "POST", "path_prefix": "/v1/chat",
            "scope": "", "job": "job-1", "kind": "grant-request",
            "created": _future_iso(-7200), "expires": _future_iso(),
            "tenant_id": None}
    item.update(kw)
    with open(os.path.join(ctx.approvals, "pending", aid + ".json"),
              "w") as f:
        json.dump(item, f)
    return item


def _decision_payload(aid=AID, decision="deny", dseq=1, box_id=BOX_ID):
    return {"aid": aid, "decision": decision, "decision_seq": dseq,
            "idempotency_key":
                f"approval_decision:{box_id}:{aid}:{dseq}"}


def _cmd(seq, kind="approval_decision", payload=None, epoch=None):
    cmd = {"seq": seq, "kind": kind,
           "payload": payload if payload is not None
           else _decision_payload()}
    if epoch is not None:
        cmd["epoch"] = epoch
    return cmd


class FakePlane:
    """Stub for spark_pair._http honoring the #848 fetch/ack contract."""
    def __init__(self, commands=(), watermark=0):
        self.calls = []
        self.pending = list(commands)
        self.watermark = watermark
        self.acked = []
        self.pending_status = 200
        self.pending_body = None
        self.fail_ack = False

    def __call__(self, method, url, body=None, headers=None):
        self.calls.append((method, url, body))
        auth = (headers or {}).get("Authorization")
        assert auth == "Bearer " + TOKEN, f"bad auth {auth!r}"
        if "/commands/pending" in url:
            assert method == "GET"
            assert "limit=" in url
            if self.pending_body is not None:
                return self.pending_status, self.pending_body
            return self.pending_status, {
                "ok": True, "commands": self.pending,
                "acked_watermark": self.watermark, "lease_secs": 120}
        if url.endswith("/commands/ack"):
            assert method == "POST"
            if self.fail_ack:
                return 500, {"ok": False, "error": "boom"}
            self.acked.extend(body["seqs"])
            return 200, {"ok": True}
        raise AssertionError(f"unexpected {method} {url}")


def _run(ctx, plane, monkeypatch, mint=None):
    monkeypatch.setattr(spark_pair, "_http", plane)
    if mint is not None:
        monkeypatch.setattr(spark_pair, "_mint_grant", mint)
    return spark_pair.cmd_ingest(ctx)


def _consumed(ctx, aid=AID):
    p = os.path.join(ctx.approvals, "consumed", aid + ".json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def _cursor(ctx):
    with open(os.path.join(ctx.dir, "commands_cursor.json")) as f:
        return json.load(f)["cursor"]


class _MintResult:
    """Value object for a monkeypatched _mint_grant return."""

    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


class _MintOk:
    def __init__(self):
        self.argv = None

    def __call__(self, argv):
        self.argv = argv
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()


# --- stamping ----------------------------------------------------------------


def test_ingest_deny_stamps_consumed_and_advances_cursor(ctx, monkeypatch,
                                                         capsys):
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    rec = _consumed(ctx)
    assert rec is not None
    assert rec["decision"] == "deny"
    assert rec["decision_origin"] == "plane"
    assert rec["plane_seq"] == 11
    assert rec["idempotency_key"] == f"approval_decision:{BOX_ID}:{AID}:1"
    assert rec["answered_at"]  # the proxy's denial lookup needs this
    assert rec["answered_by"] is None  # wire v1 carries no owner principal
    assert rec["credential"] == "openai" and rec["host"] == "api.openai.com"
    assert rec["method"] == "POST" and rec["path_prefix"] == "/v1/chat"
    # Issue #73: a denial mints nothing, so a requester-planted
    # grant_ttl_hours must not survive into the answered record.
    assert "grant_ttl_hours" not in rec
    assert not os.path.exists(os.path.join(ctx.approvals, "pending",
                                           AID + ".json"))
    assert plane.acked == [11]
    assert _cursor(ctx) == 11


def test_ingest_consumed_record_mode_0600(ctx, monkeypatch):
    """#1211: the box-side consumed/<aid>.json is 0600, not 0644. It
    carries credential names, hosts, methods, and path prefixes — the
    data class the proxy keeps 0600 (finding 198) — and the box-side
    consumed/ dir is not access-restricted."""
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    p = os.path.join(ctx.approvals, "consumed", AID + ".json")
    assert os.path.exists(p)
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_ingest_write_answered_mode_0600(ctx):
    """#1211: _ingest_write_answered pins answered/<aid>.json 0600, not
    0644 — same data class as the consumed record (finding 198)."""
    rec = {"id": AID, "credential": "openai", "host": "api.openai.com",
           "method": "POST", "path_prefix": "/v1/chat",
           "decision": "approve", "decision_origin": "plane"}
    spark_pair._ingest_write_answered(ctx.approvals, AID, rec)
    p = os.path.join(ctx.approvals, "answered", AID + ".json")
    assert os.path.exists(p)
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    with open(p) as f:
        assert json.load(f)["decision"] == "approve"


def test_ingest_repair_tightens_legacy_0644_records(ctx):
    """#1211, box side: the ingest-startup repair chmods pre-fix 0644
    answered/ + consumed/ records to 0600, best-effort."""
    planted = []
    for sub in ("answered", "consumed"):
        p = os.path.join(ctx.approvals, sub, "legacy-aid.json")
        with open(p, "w") as f:
            json.dump({"id": "legacy-aid"}, f)
        os.chmod(p, 0o644)
        planted.append(p)
    spark_pair._repair_approval_file_modes(ctx.approvals)
    for p in planted:
        assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_ingest_deny_pops_planted_grant_ttl(ctx, monkeypatch):
    # The #73 parity check, made non-vacuous: the pending item carries a
    # requester-planted grant_ttl_hours and the denied record must drop it.
    _file_pending(ctx, grant_ttl_hours=999)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    rec = _consumed(ctx)
    assert rec["decision"] == "deny"
    assert "grant_ttl_hours" not in rec
    assert plane.acked == [11]


def test_ingest_pre_mint_terminal_race_not_minted(ctx, monkeypatch, capsys):
    # Security B1(b): the terminal record appears AFTER the ingest's
    # top-of-function check but BEFORE the mint. The pre-mint re-check
    # (immediately before _mint_grant) must see it and skip the mint
    # entirely — no grant, no stamp-over.
    _file_pending(ctx)
    calls = []
    real_window_ok = spark_pair._ingest_grant_window_ok

    def plant_then_check(item):
        # Simulate confirmd's answer path winning the record while the
        # ingest was validating: plant the terminal record, then run the
        # real window check. The pre-mint re-check runs next.
        local = {"id": AID, "decision": "deny", "answered_at": _future_iso(-5)}
        with open(os.path.join(ctx.approvals, "consumed", AID + ".json"),
                  "w") as f:
            json.dump(local, f)
        return real_window_ok(item)

    def counting_mint(argv):
        calls.append(argv)
        return _MintResult()

    monkeypatch.setattr(spark_pair, "_ingest_grant_window_ok", plant_then_check)
    monkeypatch.setattr(spark_pair, "_mint_grant", counting_mint)
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert calls == []  # the mint was never attempted
    assert not os.path.exists(os.path.join(ctx.approvals, "answered",
                                            AID + ".json"))
    assert plane.acked == [11]
    assert "won the race" in capsys.readouterr().out


def test_ingest_post_mint_terminal_race_no_stamp(ctx, monkeypatch, capsys):
    # Security B1(a): the terminal record lands DURING the mint (after
    # the mint returns 0). The grant is already minted and cannot be
    # un-minted — the ingest must NOT stamp over the winner, and must
    # journal the conflict loudly with the remediation runbook.
    _file_pending(ctx)

    def racy_mint(argv):
        # Simulate confirmd's answer path winning the record while the
        # writer was running: plant the terminal record, then report a
        # successful mint.
        local = {"id": AID, "decision": "deny", "answered_at": _future_iso(-5),
                 "requester": "swapd"}
        with open(os.path.join(ctx.approvals, "consumed", AID + ".json"),
                  "w") as f:
            json.dump(local, f)
        return _MintResult()

    monkeypatch.setattr(spark_pair, "_mint_grant", racy_mint)
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    # The winner's record is untouched (the ingest never stamped over it).
    rec = _consumed(ctx)
    assert rec["decision"] == "deny"
    assert "decision_origin" not in rec  # confirmd's local record, intact
    assert not os.path.exists(os.path.join(ctx.approvals, "answered",
                                            AID + ".json"))
    assert plane.acked == [11]
    err = capsys.readouterr().err
    assert "APPROVE/TERMINAL RACE" in err
    # The audit event carries the full tuple + the winning terminal state.
    for field in ("approval_id=a1b2c3d4e5f60718", "credential=openai",
                  "host=api.openai.com", "method=POST",
                  "path_prefix=/v1/chat", "job=job-1",
                  "winning_decision='deny'"):
        assert field in err, field
    assert "grant-writer revoke --job job-1" in err
    # The pending file belonged to confirmd's answer path, which removed
    # it when it stamped; the ingest's own removal is a safe no-op.


def test_ingest_window_lapsed_during_mint_stamps_expired(ctx, monkeypatch,
                                                         capsys):
    # The grant window lapses during the mint (no terminal record yet):
    # the honest outcome is expired, not a phantom approval.
    _file_pending(ctx, expires=_future_iso(3600))

    def slow_mint(argv):
        return _MintResult()

    monkeypatch.setattr(spark_pair, "_mint_grant", slow_mint)
    # Make the window lapse between the grant-window check and the
    # post-mint re-check: _ingest_item_expired flips after its first
    # (pre-mint) call, so the second (post-mint) call sees a lapsed item.
    real_expired = spark_pair._ingest_item_expired
    calls = {"n": 0}

    def flip(item):
        calls["n"] += 1
        if calls["n"] >= 2:
            return True  # lapsed during the mint
        return real_expired(item)

    monkeypatch.setattr(spark_pair, "_ingest_item_expired", flip)
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    rec = _consumed(ctx)
    assert rec["decision"] == "expired"
    assert rec["decision_origin"] == "plane"
    assert plane.acked == [11]
    assert "lapsed during the mint" in capsys.readouterr().out


def test_ingest_approve_mints_grant_via_single_writer(ctx, monkeypatch):
    _file_pending(ctx)
    mint = _MintOk()
    plane = FakePlane(commands=[_cmd(12, payload=_decision_payload(
        decision="approve"))], watermark=11)
    assert _run(ctx, plane, monkeypatch, mint=mint) == 0
    # The mint reuses confirmd's single-writer argv shape (Finding 60/64).
    argv = mint.argv
    assert argv[0] == spark_pair._grant_writer()
    assert argv[1] == "add"
    assert argv[argv.index("--approval-id") + 1] == AID
    assert argv[argv.index("--credential") + 1] == "openai"
    assert argv[argv.index("--host") + 1] == "api.openai.com"
    assert argv[argv.index("--method") + 1] == "POST"
    assert argv[argv.index("--ttl-hours") + 1] == "1"  # wire v1: default
    assert "--approval-expires" in argv  # issue #294's mint-time check
    rec = _consumed(ctx)
    assert rec["decision"] == "approve"
    assert rec["decision_origin"] == "plane"
    assert rec["grant_ttl_hours"] == 1
    assert plane.acked == [12]


def test_ingest_expire_stamps_terminal_record(ctx, monkeypatch):
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(13, payload=_decision_payload(
        decision="expire"))], watermark=12)
    assert _run(ctx, plane, monkeypatch) == 0
    rec = _consumed(ctx)
    assert rec["decision"] == "expired"
    assert rec["expired_by"] == "plane"
    assert rec["expired_at"]
    assert "answered_at" not in rec and "answered_by" not in rec
    assert plane.acked == [13]


def test_ingest_redelivery_is_idempotent(ctx, monkeypatch):
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    first = json.dumps(_consumed(ctx), sort_keys=True)
    # Simulate cursor loss with the idempotency log intact (crash between
    # stamp and cursor persist): the plane redelivers seq 11, the
    # idempotency key — not the cursor — is the backstop.
    os.remove(os.path.join(ctx.dir, "commands_cursor.json"))
    plane.watermark = 10
    assert _run(ctx, plane, monkeypatch) == 0
    assert json.dumps(_consumed(ctx), sort_keys=True) == first
    assert plane.acked == [11, 11]  # ack is idempotent; stamp is not repeated


def test_ingest_unknown_aid_rejected_not_stamped(ctx, monkeypatch, capsys):
    # No local pending item: the decision is not ours to stamp.
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]  # consumed, not redelivered forever
    err = capsys.readouterr().err
    assert "unknown aid" in err and "rejecting" in err


def test_ingest_unknown_kind_acked_not_executed(ctx, monkeypatch, capsys):
    plane = FakePlane(commands=[_cmd(11, kind="future_kind",
                                     payload={"x": 1})], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]
    assert "unknown command kind" in capsys.readouterr().out


def test_ingest_malformed_payload_acked_not_stamped(ctx, monkeypatch, capsys):
    _file_pending(ctx)
    bad = _decision_payload()
    bad["idempotency_key"] = "forged:key"  # never matches the canonical form
    plane = FakePlane(commands=[_cmd(11, payload=bad)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]
    assert "malformed" in capsys.readouterr().err


def test_ingest_wrong_box_key_rejected(ctx, monkeypatch):
    # The idempotency key binds box_id: a key minted for another box never
    # validates, even if everything else looks right.
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(
        box_id="box-other"))], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]


def test_ingest_bad_requester_refused(ctx, monkeypatch, capsys):
    # The Finding-50 fix reads the requester from the file owner: a
    # hostile owner ("mallory") refuses the stamp even though the item
    # itself carries no requester field at all.
    _file_pending(ctx)
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "mallory")
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]
    assert "unexpected requester" in capsys.readouterr().err


def test_ingest_item_requester_field_ignored(ctx, monkeypatch, capsys):
    # A requester-planted "requester" field must not launder a hostile
    # file owner: the field is never consulted, so the refusal stands.
    _file_pending(ctx, requester="swapd")
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "mallory")
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx) is None
    assert plane.acked == [11]
    assert "unexpected requester" in capsys.readouterr().err


def test_ingest_already_terminal_first_wins(ctx, monkeypatch):
    # confirmd's own answer path got there first: the plane decision is
    # superseded, not stamped over it.
    _file_pending(ctx)
    local = {"id": AID, "decision": "deny", "answered_at": _future_iso(-60),
             "answered_by": "owner@tailnet", "requester": "swapd",
             "credential": "openai", "host": "api.openai.com",
             "method": "POST", "path_prefix": "/v1/chat"}
    with open(os.path.join(ctx.approvals, "consumed", AID + ".json"),
              "w") as f:
        json.dump(local, f)
    plane = FakePlane(commands=[_cmd(12, payload=_decision_payload(
        decision="approve"))], watermark=11)
    mint = _MintOk()
    assert _run(ctx, plane, monkeypatch, mint=mint) == 0
    assert mint.argv is None  # no grant minted for a superseded decision
    assert _consumed(ctx)["answered_by"] == "owner@tailnet"  # untouched
    assert plane.acked == [12]


# --- fail-closed paths --------------------------------------------------------


def test_ingest_tenant_scoped_item_acked_loudly(ctx, monkeypatch, capsys):
    # A tenant-scoped item with a live window is permanently
    # unprocessable for this pre-H10 client: it must NOT wedge the queue
    # (acked, no stamp), but the run must exit 1 so the operator sees
    # the upgrade message — and later commands must still process.
    _file_pending(ctx, tenant_id="tenant-9")
    _file_pending(ctx, aid=AID2)
    plane = FakePlane(
        commands=[_cmd(11),
                  _cmd(12, payload=_decision_payload(aid=AID2, decision="approve"))],
        watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=_MintOk()) == 1  # attention -> 1
    assert _consumed(ctx) is None  # nothing stamped for the scoped item
    assert plane.acked == [11, 12]  # queue advanced past it
    assert _consumed(ctx, aid=AID2)["decision"] == "approve"
    captured = capsys.readouterr()
    assert "tenant-scoped item" in captured.err and "upgrade" in captured.err
    assert "ATTENTION" in captured.out


def test_ingest_tenant_scoped_expired_still_stamped(ctx, monkeypatch):
    # A tenant-scoped item whose window already lapsed drains honestly:
    # the expired stamp is clock-derived, not plane content, so it is
    # safe to land and it keeps the queue moving.
    _file_pending(ctx, tenant_id="tenant-9", expires=_future_iso(-10))
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    rec = _consumed(ctx)
    assert rec["decision"] == "expired"
    assert plane.acked == [11]


def test_ingest_failed_grant_mint_not_acked(ctx, monkeypatch):
    _file_pending(ctx)
    def boom(argv):
        class R:
            returncode = 2
            stdout = ""
            stderr = "disk full"
        return R()
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(
        decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=boom) == 1
    assert _consumed(ctx) is None  # nothing stamped without the grant
    assert plane.acked == []  # redelivery will retry the mint
    # The pending item is left in place for the retry.
    assert os.path.exists(os.path.join(ctx.approvals, "pending",
                                       AID + ".json"))


def test_ingest_cursor_is_highest_acked_never_highest_fetched(ctx, monkeypatch):
    # seq 11 ingests cleanly; seq 12's mint fails. The cursor must advance
    # past 11 (acked) but never past 12 (unacked) — otherwise 12's
    # redelivery would be skipped forever (the #848 cursor contract).
    _file_pending(ctx)
    aid2 = "b2c3d4e5f6071829"
    _file_pending(ctx, aid=aid2)

    def boom(argv):
        class R:
            returncode = 2
            stdout = ""
            stderr = "x"
        return R()
    cmds = [_cmd(11),
            _cmd(12, payload=_decision_payload(aid=aid2, decision="approve"))]
    plane = FakePlane(commands=cmds, watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=boom) == 1
    assert plane.acked == [11]
    assert _cursor(ctx) == 11


def test_ingest_approve_inside_mint_window_stamps_expired(ctx, monkeypatch):
    # Issue #534: the window lapsed too far for a safe mint — the honest
    # outcome is expired, and the writer is never invoked.
    _file_pending(ctx, expires=_future_iso(10))
    mint = _MintOk()
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(
        decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=mint) == 0
    assert mint.argv is None
    assert _consumed(ctx)["decision"] == "expired"
    assert plane.acked == [11]


def test_ingest_writer_expiry_refusal_stamps_expired(ctx, monkeypatch):
    # Issue #294: exit 3 = the approval's expiry crossed during the mint.
    _file_pending(ctx)
    def refused(argv):
        class R:
            returncode = 3
            stdout = ""
            stderr = ""
        return R()
    plane = FakePlane(commands=[_cmd(11, payload=_decision_payload(
        decision="approve"))], watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=refused) == 0
    assert _consumed(ctx)["decision"] == "expired"
    assert plane.acked == [11]


# --- cursor / transport -------------------------------------------------------


def test_ingest_interrupted_stamp_resumes_instead_of_rejecting(ctx, monkeypatch):
    # A previous run removed the pending item but crashed before the
    # consumed/ move: the aid looks "unknown" on redelivery, but our own
    # answered/ record (decision_origin=plane + idempotency key) proves
    # it is ours to finish — resuming must win over rejecting.
    item = _file_pending(ctx)
    key = f"approval_decision:{BOX_ID}:{AID}:1"
    rec = spark_pair._ingest_answer_record(item, AID, "deny", "swapd", 11,
                                           key)
    spark_pair._ingest_write_answered(ctx.approvals, AID, rec)
    os.remove(os.path.join(ctx.approvals, "pending", AID + ".json"))
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    done = _consumed(ctx)
    assert done is not None and done["decision"] == "deny"
    assert done["decision_origin"] == "plane"
    assert plane.acked == [11]


def test_ingest_corrupt_cursor_heals_from_watermark(ctx, monkeypatch, capsys):
    with open(os.path.join(ctx.dir, "commands_cursor.json"), "w") as f:
        f.write("{not json")
    plane = FakePlane(commands=[], watermark=41)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _cursor(ctx) == 41  # healed to highest acked, never to zero
    assert "healed" in capsys.readouterr().err


def test_ingest_first_run_starts_at_watermark(ctx, monkeypatch, capsys):
    plane = FakePlane(commands=[], watermark=41)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _cursor(ctx) == 41
    assert "acked_watermark=41" in capsys.readouterr().out


def test_ingest_epoch_transition_adopted(ctx, monkeypatch, capsys):
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11, epoch=7)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    with open(os.path.join(ctx.dir, "commands_cursor.json")) as f:
        cur = json.load(f)
    assert cur["epoch"] == 7
    assert "epoch" in capsys.readouterr().out


def _fetch_urls(plane):
    return [url for method, url, _body in plane.calls
            if method == "GET" and "/commands/pending" in url]


def test_ingest_fetch_sends_epoch_claim(ctx, monkeypatch):
    # #947: the box asserts its epoch on every fetch (?epoch=) so the
    # plane can detect a stale-epoch box and force re-sync.
    with open(os.path.join(ctx.dir, "commands_cursor.json"), "w") as f:
        json.dump({"cursor": 41, "epoch": 7}, f)
    plane = FakePlane(commands=[], watermark=41)
    assert _run(ctx, plane, monkeypatch) == 0
    urls = _fetch_urls(plane)
    assert urls, "expected at least one pending-fetch call"
    assert "epoch=7" in urls[0]


def test_ingest_fetch_omits_epoch_when_unknown(ctx, monkeypatch):
    # First run: no cursor file, no epoch to claim — a fresh box must
    # never assert a bogus epoch=0.
    plane = FakePlane(commands=[], watermark=0)
    assert _run(ctx, plane, monkeypatch) == 0
    urls = _fetch_urls(plane)
    assert urls, "expected at least one pending-fetch call"
    assert "epoch=" not in urls[0]


def test_ingest_401_says_repair(ctx, monkeypatch, capsys):
    plane = FakePlane()
    plane.pending_status = 401
    plane.pending_body = {"ok": False, "error": "bad token"}
    assert _run(ctx, plane, monkeypatch) == 1
    err = capsys.readouterr().err
    assert "re-pair" in err
    assert TOKEN not in err  # the token never reaches the log


def test_ingest_404_plane_missing_is_honest(ctx, monkeypatch, capsys):
    plane = FakePlane()
    plane.pending_status = 404
    plane.pending_body = {"ok": False, "error": "http=404",
                          spark_pair._TRANSPORT_404: True}
    assert _run(ctx, plane, monkeypatch) == 1
    assert "does not implement" in capsys.readouterr().err


def test_ingest_missing_approvals_dir_fails_loud(ctx, monkeypatch, capsys,
                                                tmp_path):
    monkeypatch.setenv("SVM_APPROVALS_DIR",
                       str(tmp_path / "nope"))
    plane = FakePlane()
    assert _run(ctx, plane, monkeypatch) == 1
    assert "confirmd" in capsys.readouterr().err
    assert plane.calls == []  # no network before the local check


def test_ingest_never_logs_the_token(ctx, monkeypatch, capsys):
    # The token must not reach stdout/stderr/ingest.log on any failure.
    plane = FakePlane()
    plane.pending_status = 500
    plane.pending_body = {"ok": False,
                          "error": f"plane says {TOKEN} is bad"}
    assert _run(ctx, plane, monkeypatch) == 1
    captured = capsys.readouterr()
    assert TOKEN not in captured.err and TOKEN not in captured.out
    log = open(os.path.join(ctx.dir, "ingest.log")).read()
    assert TOKEN not in log and "<redacted>" in log


def test_ingest_cursor_save_oserror_fails_loud(ctx, monkeypatch, capsys):
    # Engineering B3: an OSError from the state saves (ENOSPC/EACCES)
    # must fail closed with a loud log — never a traceback — and the
    # acked commands stay acked (their safety net is the consumed/
    # records plus the idempotency log, not the cursor).
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)

    def boom(d, cursor, epoch):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(spark_pair, "_save_ingest_cursor", boom)
    assert _run(ctx, plane, monkeypatch) == 1
    err = capsys.readouterr().err
    assert "state save failed" in err
    assert "Traceback" not in err
    assert plane.acked == [11]  # the ack already happened; stays acked
    # The stamp itself is durable in consumed/ regardless of the cursor.
    assert _consumed(ctx)["decision"] == "deny"


def test_ingest_mirrored_constants_match_sources():
    # The ingest duplicates constants from proxy/swap_addon.py and
    # confirm/confirmd.py by contract (same DAC boundary, read-only
    # cross-import). A drift between them would silently change aid
    # validation or the grant window — pin them equal so a future edit
    # to any of the three files breaks loudly here.
    import re
    repo_root = os.path.dirname(os.path.dirname(
        os.path.abspath(spark_pair.__file__)))
    addon_src = open(os.path.join(repo_root, "proxy",
                                  "swap_addon.py")).read()
    confirmd_src = open(os.path.join(repo_root, "confirm",
                                     "confirmd.py")).read()

    def pattern(src, name):
        m = re.search(rf"^{name}\s*=\s*re\.compile\(r\"([^\"]+)\"\)",
                      src, re.M)
        assert m, f"{name} pattern not found"
        return m.group(1)

    def number(src, name):
        m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
        assert m, f"{name} not found"
        return int(m.group(1))

    assert spark_pair._INGEST_AID_RE.pattern == \
        pattern(addon_src, "_AID_RE")
    assert spark_pair._INGEST_GRANT_MINT_WINDOW == \
        number(confirmd_src, "_GRANT_MINT_WINDOW")
    assert spark_pair._INGEST_GRANT_TTL_DEFAULT == \
        number(confirmd_src, "GRANT_TTL_DEFAULT")
    assert spark_pair._INGEST_GRANT_MINT_TIMEOUT == \
        number(confirmd_src, "_GRANT_MINT_TIMEOUT")


def _audit_lines(ctx):
    # The ctx fixture sets CONFIRM_AUDIT to tmp_path/"audit.log".
    p = os.path.join(str(ctx.tmp), "audit.log")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return f.read().splitlines()


def test_ingest_deny_emits_audit_line(ctx, monkeypatch):
    _file_pending(ctx)
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    lines = _audit_lines(ctx)
    assert len(lines) == 1
    line = lines[0]
    assert "event=answer" in line
    assert "decision=deny" in line
    assert "decision_origin=plane" in line
    assert "plane_seq=11" in line
    assert f"id={AID}" in line
    assert "requester=swapd" in line
    assert "ttl=" not in line  # deny mints nothing: no lifetime claimed


def test_ingest_approve_emits_audit_line_with_ttl(ctx, monkeypatch):
    _file_pending(ctx)
    plane = FakePlane(
        commands=[_cmd(11, payload=_decision_payload(decision="approve"))],
        watermark=10)
    assert _run(ctx, plane, monkeypatch, mint=_MintOk()) == 0
    lines = _audit_lines(ctx)
    assert len(lines) == 1
    assert "decision=approve" in lines[0]
    assert "ttl=1h" in lines[0]  # the granted lifetime, like #73's trail
    assert "decision_origin=plane" in lines[0]


def test_ingest_expire_emits_audit_line(ctx, monkeypatch):
    _file_pending(ctx, expires=_future_iso(-10))
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    lines = _audit_lines(ctx)
    assert len(lines) == 1
    assert "decision=expired" in lines[0]
    assert "decision_origin=plane" in lines[0]


def test_ingest_audit_write_failure_is_loud_not_fatal(ctx, monkeypatch,
                                                      capsys):
    # confirmd's posture: the audit call happens after the decision, so
    # a lost audit event is named loudly on stderr while the stamp
    # stands and the command is acked (failing closed here would wedge
    # the queue on a full disk with the decision already durable).
    _file_pending(ctx)
    monkeypatch.setenv("CONFIRM_AUDIT", "/nonexistent-dir/audit.log")
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _consumed(ctx)["decision"] == "deny"
    assert plane.acked == [11]
    assert "LOST AUDIT EVENT" in capsys.readouterr().err


def test_ingest_lost_terminal_race_emits_no_audit_line(ctx, monkeypatch):
    # The post-mint race path never stamps (B1a): no stamp, no audit
    # line — the winner's own path owns the trail for its record.
    _file_pending(ctx)

    def racy_mint(argv):
        local = {"id": AID, "decision": "deny", "answered_at": _future_iso(-5),
                 "requester": "swapd"}
        with open(os.path.join(ctx.approvals, "consumed", AID + ".json"),
                  "w") as f:
            json.dump(local, f)
        return _MintResult()

    monkeypatch.setattr(spark_pair, "_mint_grant", racy_mint)
    plane = FakePlane(
        commands=[_cmd(11, payload=_decision_payload(decision="approve"))],
        watermark=10)
    assert _run(ctx, plane, monkeypatch) == 0
    assert _audit_lines(ctx) == []


def test_ingest_fchmod_failure_closes_fd(ctx, monkeypatch, capsys):
    # #1155: the ingest wrapper's lock acquisition shared the leaky
    # shape — os.open + os.fchmod in one try, so an fchmod OSError
    # after a successful open returned 1 with the fd open. The
    # split-try fix closes the fd and keeps the loud degraded failure.
    def _raising_fchmod(fd, mode):
        raise OSError(1, "Operation not permitted")

    monkeypatch.setattr(os, "fchmod", _raising_fchmod)

    def _fds():
        return set(os.listdir("/proc/self/fd"))

    before = _fds()
    for _ in range(5):
        assert spark_pair.cmd_ingest(ctx) == 1
    assert _fds() == before, "fd leaked on fchmod failure"
    err = capsys.readouterr().err
    assert "cannot secure lock file" in err

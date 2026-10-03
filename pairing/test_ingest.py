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
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import spark_pair


BOX_ID = "box-test"
TOKEN = "tok-test"
AID = "a1b2c3d4e5f60718"


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
    approvals = tmp_path / "approvals"
    for sub in ("pending", "answered", "consumed"):
        (approvals / sub).mkdir(parents=True)
    monkeypatch.setenv("SVM_APPROVALS_DIR", str(approvals))
    os.makedirs(c.dir, mode=0o700, exist_ok=True)
    with open(os.path.join(c.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": TOKEN}, f)
    c.approvals = str(approvals)
    return c


def _future_iso(seconds=3600):
    return (datetime.now(timezone.utc)
            + timedelta(seconds=seconds)).isoformat()


def _file_pending(ctx, aid=AID, **kw):
    item = {"id": aid, "credential": "openai", "host": "api.openai.com",
            "method": "POST", "path_prefix": "/v1/chat",
            "scope": "", "job": "job-1", "kind": "grant-request",
            "created": _future_iso(-7200), "expires": _future_iso(),
            "requester": "swapd", "tenant_id": None}
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
    assert not os.path.exists(os.path.join(ctx.approvals, "pending",
                                           AID + ".json"))
    assert plane.acked == [11]
    assert _cursor(ctx) == 11


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
    _file_pending(ctx, requester="mallory")
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


def test_ingest_tenant_scoped_item_fails_closed(ctx, monkeypatch, capsys):
    _file_pending(ctx, tenant_id="tenant-9")
    plane = FakePlane(commands=[_cmd(11)], watermark=10)
    assert _run(ctx, plane, monkeypatch) == 1  # NOT acked: stays queued
    assert _consumed(ctx) is None
    assert plane.acked == []
    assert "failing closed" in capsys.readouterr().err


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

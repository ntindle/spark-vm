"""Tests for spark-pair.py upload-filings (issue #953: box-side filing uploader).

The HTTP layer is stubbed (fake plane); the approvals store is a tmp dir
(SVM_APPROVALS_DIR); the DAC-owner lookup is stubbed (the real filesystem
owner in CI is not bdrive/swapd). Each test proves a property of the
uploader, not just wiring: the G76.3 payload mapping (summary + detail
truncation under the plane's caps), pending-only upload (G76.4), the
bdrive/swapd writer-identity gate (G76.7), plane-unreachable degradation,
and fail-loud-no-traceback behavior on the cron path.
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
AID2 = "b2c3d4e5f60718293"


class Ctx:
    """Fake argparse namespace for cmd_upload_filings."""
    def __init__(self, tmp_path, **kw):
        self.dir = str(tmp_path / "state")
        self.control = "https://control.test"
        for k, v in kw.items():
            setattr(self, k, v)


class Plane:
    """Fake control plane: records POSTs, answers per configured script."""
    def __init__(self):
        self.posts = []  # (url, body) in arrival order
        self.script = []  # list of (status, payload) to serve in order

    def __call__(self, method, url, body=None, headers=None):
        assert method == "POST"
        assert url == ("https://control.test/v1/boxes/"
                       + BOX_ID + "/approvals/file")
        assert headers.get("Authorization") == "Bearer " + TOKEN, \
            "the box Bearer <redacted> travels on every file POST"
        self.posts.append((url, body))
        if self.script:
            return self.script.pop(0)
        return 201, {"ok": True, "aid": body["aid"], "deduped": False}


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    c = Ctx(tmp_path)
    approvals = tmp_path / "approvals"
    for sub in ("pending", "answered", "consumed"):
        (approvals / sub).mkdir(parents=True)
    monkeypatch.setenv("SVM_APPROVALS_DIR", str(approvals))
    # G76.7: the writer identity is the pending dir's DAC owner, enforced
    # as bdrive/swapd. Tests control the lookup (CI's owner is neither).
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "swapd")
    os.makedirs(c.dir, mode=0o700, exist_ok=True)
    with open(os.path.join(c.dir, "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": TOKEN}, f)
    c.approvals = str(approvals)
    c.plane = Plane()
    monkeypatch.setattr(spark_pair, "_http", c.plane)
    return c


def _future_iso(seconds=3600):
    return (datetime.now(timezone.utc)
            + timedelta(seconds=seconds)).isoformat()


def _file_pending(ctx, aid=AID, **kw):
    # Mirrors the proxy's _file_approval record shape (no requester field:
    # Finding-50 reads the requester from the file's owner).
    item = {"id": aid, "credential": "openai", "host": "api.openai.com",
            "method": "POST", "path_prefix": "/v1/chat",
            "kind": "grant-request",
            "created": _future_iso(-120), "expires": _future_iso(),
            "summary": ("POST api.openai.com/v1/chat for openai "
                        "(refused: no grant)")}
    item.update(kw)
    with open(os.path.join(ctx.approvals, "pending", aid + ".json"),
              "w") as f:
        json.dump(item, f)
    return item


def _run(capsys, fn, *a):
    rc = fn(*a)
    err = capsys.readouterr()
    return rc, err


# -- payload mapping (G76.3) --------------------------------------------

def test_uploads_pending_record_with_mapped_payload(ctx, capsys):
    _file_pending(ctx)
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert len(ctx.plane.posts) == 1
    url, body = ctx.plane.posts[0]
    assert body["aid"] == AID
    assert body["expires_in_secs"] == 3600
    # The detail tuple, Finding-49 discipline: no free text.
    detail = body["detail"]
    assert detail["credential"] == "openai"
    assert detail["host"] == "api.openai.com"
    assert detail["method"] == "POST"
    assert detail["path_prefix"] == "/v1/chat"
    assert detail["reason"] == "no grant"
    assert detail["filed_at"] and detail["expires"]
    assert len(body["summary"]) <= 256
    assert len(json.dumps(detail).encode()) <= 4096


def test_summary_truncated_to_250_plus_ellipsis(ctx, capsys):
    long_summary = ("POST " + "x" * 300 + ".example.com/a-very-long-path "
                    "for openai (refused: no grant)")
    _file_pending(ctx, summary=long_summary)
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    body = ctx.plane.posts[0][1]
    # 250 + "…" = 251: byte-exact under the plane's 256-char bound.
    assert len(body["summary"]) == 251
    assert body["summary"].endswith("…")
    assert body["summary"] == long_summary[:250] + "…"


def test_path_prefix_truncated_keeps_host_full(ctx, capsys):
    # A pathological 10 KB path must never breach the 4 KB detail cap;
    # the host stays intact (G76.3: truncate path_prefix, keep the host).
    evil = "/x" * 5000
    _file_pending(ctx, path_prefix=evil, host="api.openai.com")
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    detail = ctx.plane.posts[0][1]["detail"]
    assert len(json.dumps(detail).encode()) <= 4096
    assert detail["host"] == "api.openai.com"
    assert detail["path_prefix"].endswith("…")
    assert len(detail["path_prefix"]) < len(evil)


def test_reason_anchors_on_last_refused_suffix(ctx, capsys):
    # The path portion can carry a literal " (refused: " (the proxy
    # percent-decodes paths to fixpoint): the reason must come from the
    # LAST suffix, not the first.
    _file_pending(
        ctx,
        summary=("POST api.example.com/dl/my (refused: x) notes for "
                 "openai (refused: no grant)"))
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    detail = ctx.plane.posts[0][1]["detail"]
    assert detail["reason"] == "no grant"


def test_reason_absent_when_summary_has_no_suffix(ctx, capsys):
    # A filing from a different writer carries no (refused: …) suffix:
    # the detail tuple stays valid without a reason.
    _file_pending(ctx, summary="operator-filed note with no suffix")
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    detail = ctx.plane.posts[0][1]["detail"]
    assert "reason" not in detail


def test_deduped_counts_as_clean(ctx, capsys):
    # A retry of an already-filed aid returns deduped:true — idempotent
    # by construction; exit 0, no duplicate minted.
    _file_pending(ctx)
    ctx.plane.script.append((200, {"ok": True, "aid": AID,
                                  "deduped": True}))
    rc, out = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert "already on the plane" in out.out


# -- pending-only upload (G76.4) ----------------------------------------

def test_plane_aid_mismatch_retries(ctx, capsys):
    # The plane answers ok:true but names a DIFFERENT aid: the filing was
    # not accepted — it must not count as uploaded, and the record stays
    # for the next tick.
    _file_pending(ctx)
    ctx.plane.script.append((200, {"ok": True, "aid": "0000000000000000"}))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "will retry at the next cron tick" in err.err
    assert os.path.exists(os.path.join(ctx.approvals, "pending",
                                       AID + ".json"))


def test_plane_non_dict_body_retries(ctx, capsys):
    # A 200 with a non-object body cannot carry the plane's contract:
    # same loud-retry treatment as the aid mismatch.
    _file_pending(ctx)
    ctx.plane.script.append((200, ["not", "a", "dict"]))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "will retry at the next cron tick" in err.err


def test_expired_record_is_never_uploaded(ctx, capsys):
    # Locally dead already (the expiry reap will move it to consumed/):
    # no POST, exit 0 — not a failure. A second valid record proves the
    # scan actually ran and saw both.
    _file_pending(ctx, aid=AID, expires=_future_iso(-10))
    _file_pending(ctx, aid=AID2)
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert len(ctx.plane.posts) == 1
    assert ctx.plane.posts[0][1]["aid"] == AID2


def test_non_object_record_skipped_loud(ctx, capsys):
    with open(os.path.join(ctx.approvals, "pending", AID + ".json"),
              "w") as f:
        json.dump(["not", "an", "object"], f)
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "not an object" in err.err


def test_whitespace_summary_skipped_loud(ctx, capsys):
    _file_pending(ctx, summary="   \n  ")
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "empty summary" in err.err


def test_missing_tuple_field_skipped_loud(ctx, capsys):
    item = _file_pending(ctx)
    del item["host"]
    with open(os.path.join(ctx.approvals, "pending", AID + ".json"),
              "w") as f:
        json.dump(item, f)
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "no usable 'host'" in err.err


def test_answered_record_is_never_uploaded(ctx, capsys):
    # Denied/consumed records live outside pending/ — the scan cannot
    # see them (pending-only by construction).
    answered = {"id": AID, "decision": "deny"}
    with open(os.path.join(ctx.approvals, "answered", AID + ".json"),
              "w") as f:
        json.dump(answered, f)
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert ctx.plane.posts == []


def test_tmp_files_skipped_until_renamed(ctx, capsys):
    # Mid-write filings (proxy's tmp+replace) are not read half-written.
    _file_pending(ctx)
    os.rename(os.path.join(ctx.approvals, "pending", AID + ".json"),
              os.path.join(ctx.approvals, "pending", AID + ".json.tmp"))
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert ctx.plane.posts == []


# -- writer identity (G76.7) --------------------------------------------

def test_wrong_dir_owner_refuses_everything(ctx, capsys, monkeypatch):
    # The pending dir is agent-owned: no POST may go out — the writer
    # identity is the box, never the agent.
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "agentuser")
    _file_pending(ctx)
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "refusing to upload" in err.err
    assert "never the agent" in err.err


def test_agent_owned_file_skipped_in_box_owned_dir(ctx, capsys,
                                                   monkeypatch):
    # Security B1: the directory gate alone is not enough — a
    # box-owned dir can still hold an agent-planted filing. The
    # per-file owner check skips it while the box-owned sibling
    # still uploads.
    def fake_owner(path):
        base = os.path.basename(path)
        if base == "pending":
            return "swapd"
        if base == AID + ".json":
            return "agentuser"
        return "swapd"
    monkeypatch.setattr(spark_pair, "_ingest_file_owner", fake_owner)
    _file_pending(ctx, aid=AID)
    _file_pending(ctx, aid=AID2)
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert len(ctx.plane.posts) == 1
    assert ctx.plane.posts[0][1]["aid"] == AID2
    assert "owned by 'agentuser'" in err.err
    assert "never the agent" in err.err


# -- plane degradation ---------------------------------------------------

def test_401_fails_loud_with_repair_guidance(ctx, capsys):
    _file_pending(ctx)
    # A hostile plane echoes the token back inside its error string: the
    # redaction assertion below is vacuous unless the token actually
    # appears in the plane-controlled text (QA round-1).
    ctx.plane.script.append(
        (401, {"ok": False,
               "error": "bad bearer: Bearer " + TOKEN + " rejected"}))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "re-pair the box" in err.err
    assert TOKEN not in err.err  # the box token never reaches stderr...
    log = open(os.path.join(ctx.dir, "upload-filings.log")).read()
    assert TOKEN not in log  # ...or the cron log file
    assert "<redacted>" in err.err


def test_401_abort_skips_remaining_records(ctx, capsys):
    # The 401 aborts the whole pass: a dead token poisons every filing,
    # so records after the first are never attempted.
    _file_pending(ctx, aid=AID)
    _file_pending(ctx, aid=AID2)
    ctx.plane.script.append((401, {"ok": False, "error": "unauthorized"}))
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert len(ctx.plane.posts) == 1
    assert ctx.plane.posts[0][1]["aid"] == AID


def test_404_nonjson_reports_unimplemented(ctx, capsys):
    # The plane has no JSON at this path: honest "not implemented",
    # not an opaque failure.
    _file_pending(ctx)
    ctx.plane.script.append((404, {spark_pair._TRANSPORT_404: True,
                                  "ok": False, "error": "http=404"}))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "does not implement" in err.err


def test_transport_failure_leaves_local_filing(ctx, capsys):
    # Plane unreachable: loud failure, the pending record stays, the
    # next tick retries — the box-local approval flow is untouched.
    _file_pending(ctx)
    ctx.plane.script.append((0, {"ok": False, "error": "transport: down"}))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "will retry at the next cron tick" in err.err
    assert os.path.exists(os.path.join(ctx.approvals, "pending",
                                       AID + ".json"))


def test_one_bad_record_does_not_block_the_rest(ctx, capsys):
    # A 400 on the first filing (plane rejects it) is a per-record
    # failure: the second filing still uploads; the run exits 1 so the
    # operator sees the failure.
    _file_pending(ctx, aid=AID)
    _file_pending(ctx, aid=AID2)
    ctx.plane.script.append((400, {"ok": False, "error": "bad aid"}))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert len(ctx.plane.posts) == 2
    assert ctx.plane.posts[1][1]["aid"] == AID2


def test_mismatched_record_id_skipped_loud(ctx, capsys):
    # The filename aid and the record's id disagree: integrity failure,
    # never uploaded, exit 1 for operator attention.
    _file_pending(ctx, id="ffffffffffffffff")
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "does not match the filename" in err.err


def test_bad_aid_filename_skipped_loud(ctx, capsys):
    # "!" fails the local aid shape — the record is never trusted.
    with open(os.path.join(ctx.approvals, "pending", "not-an-aid!.json"),
              "w") as f:
        json.dump({"id": "not-an-aid!"}, f)
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert ctx.plane.posts == []
    assert "aid shape" in err.err


def test_empty_pending_is_clean(ctx, capsys):
    rc, out = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    assert ctx.plane.posts == []
    assert "0 uploaded" in out.out


def test_lock_file_is_0600(ctx, capsys):
    _file_pending(ctx)
    rc, _ = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 0
    st = os.stat(os.path.join(ctx.dir, ".upload-filings.lock"))
    assert oct(st.st_mode & 0o777) == "0o600"


def test_no_enrollment_fails_loud_not_traceback(ctx, capsys):
    os.unlink(os.path.join(ctx.dir, "enrollment.json"))
    rc, err = _run(capsys, spark_pair.cmd_upload_filings, ctx)
    assert rc == 1
    assert "Traceback" not in err.err
    assert "request" in err.err and "redeem" in err.err


def test_upload_filings_fchmod_failure_closes_fd(ctx, monkeypatch, capsys):
    # #1155: the upload-filings lock acquisition shared the leaky
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
        assert spark_pair.cmd_upload_filings(ctx) == 1
    assert _fds() == before, "fd leaked on fchmod failure"
    err = capsys.readouterr().err
    assert "cannot secure lock file" in err

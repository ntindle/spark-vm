"""Box-side filing-loop integration test (issue #876, S5 acceptance, slice 1).

Each leg of the box->plane->box filing loop has unit tests with hand-written
fixtures (proxy/test_swap_addon.py, pairing/test_upload_filings.py,
pairing/test_ingest.py). This suite proves the legs compose: a refusal filed
by the REAL proxy filing path is picked up by the REAL upload-filings scan
and POSTed to a contract-faithful plane, and an owner decision served as an
#873-shaped approval_decision command is stamped by the REAL ingest with
decision_origin="plane".

The plane itself is the one fake: it lives in a separate checkout
(docs/CONTROL_PLANE_API_REFERENCE.md) and is represented here by its pinned
contract -- #952's POST /v1/boxes/{id}/approvals/file semantics
({ok, aid, deduped}, idempotent on (box_id, aid)) and #873's
approval_decision command shape (docs/DURABLE_COMMANDS.md). The dashboard
decide tap is simulated by FilingPlane.owner_decide(), which enqueues exactly
what #873 enqueues on POST /v1/boxes/{id}/approvals/{aid}/decision.

Scope: the suite starts at the filing leg (SwapAddon._file_approval). The
refusal *decision* (the grant/registry check that leads to a refusal) is
unit-tested in proxy/test_swap_addon.py; what S5 needs is the
filing -> upload -> record -> decision -> stamp chain, plus (#984) the parked
agent's next poll: the real proxy serve leg
(_approval_signal_for_refusal, the decision point behind the H18
client-visible channel) is driven against the same approvals dir and the
terminal signal is asserted.
"""
import json
import os
import sys
import urllib.parse
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "proxy"))
import spark_pair  # noqa: E402
import swap_addon as sa  # noqa: E402


BOX_ID = "box-test"
TOKEN = "box-token-for-loop-test"
CONTROL = "https://control.test"


def _make_addon():
    """Minimal SwapAddon: just the state _file_approval touches.

    Deliberately NOT proxy/test_swap_addon.py's make_addon: the full
    request pipeline is out of scope (see module docstring), and this
    keeps the pairing suite decoupled from the proxy suite's helpers.
    """
    a = sa.SwapAddon.__new__(sa.SwapAddon)
    a._pending_cache = {}  # #563 per-tuple pending/ scan cache
    a._denial_cache = {}   # #307 per-tuple consumed/ denial cache
    a._expiry_cache = {}   # #511 per-tuple consumed/ expiry cache
    a._audit = lambda host, matched: True
    return a


class FilingPlane:
    """Contract-faithful control plane stub.

    Implements the pinned contracts the loop depends on, nothing more:
    - #952: POST /v1/boxes/{id}/approvals/file -> 201/200 {ok, aid,
      deduped}, idempotent on (box_id, aid).
    - #848/#873: GET .../commands/pending + POST .../commands/ack.
    owner_decide() enqueues the approval_decision command #873 enqueues
    when the owner taps decide in the dashboard.
    """

    def __init__(self):
        self.records = {}   # (box_id, aid) -> filed body
        self.posts = []     # every file POST in arrival order
        self.commands = []  # queued durable commands
        self.acked = []
        self.down = False

    def __call__(self, method, url, body=None, headers=None):
        auth = (headers or {}).get("Authorization")
        assert auth == "Bearer " + TOKEN, \
            "the box Bearer <redacted> travels on every plane call, got %r" % (auth,)
        if self.down:
            # The real _http normalizes transport failures to a (0, ...)
            # tuple rather than raising; the stub honors that contract.
            return 0, {"ok": False,
                       "error": "transport: plane unreachable (test outage)"}
        if method == "POST" and "/approvals/file" in url:
            box_id = urllib.parse.unquote(url.split("/v1/boxes/")[1]
                                          .split("/approvals/file")[0])
            aid = body["aid"]
            self.posts.append((box_id, dict(body)))
            key = (box_id, aid)
            if key in self.records:
                return 200, {"ok": True, "aid": aid, "deduped": True}
            self.records[key] = dict(body)
            return 201, {"ok": True, "aid": aid, "deduped": False}
        if method == "GET" and "/commands/pending" in url:
            return 200, {"ok": True, "commands": list(self.commands),
                         "acked_watermark": 0, "lease_secs": 120}
        if method == "POST" and url.endswith("/commands/ack"):
            self.acked.extend(body["seqs"])
            return 200, {"ok": True}
        raise AssertionError("unexpected plane call %s %s" % (method, url))

    def owner_decide(self, box_id, aid, decision):
        """What #873 does on POST .../approvals/{aid}/decision."""
        seq = 11 + len(self.commands)
        self.commands.append({
            "seq": seq,
            "kind": "approval_decision",
            "payload": {
                "aid": aid,
                "decision": decision,
                "decision_seq": 1,
                "idempotency_key":
                    "approval_decision:%s:%s:1" % (box_id, aid),
            },
        })
        return seq


class Ctx:
    """Fake argparse namespace for cmd_upload_filings / cmd_ingest."""

    def __init__(self, tmp_path):
        self.dir = str(tmp_path / "state")
        self.control = CONTROL


@pytest.fixture()
def loop(tmp_path, monkeypatch, capsys):
    """One shared approvals store for the proxy, the uploader, and the
    ingest -- the whole point: all three legs touch the SAME dir, so the
    suite proves the real cross-leg contract, not fixture agreement."""
    approvals = tmp_path / "approvals"
    for sub in ("pending", "answered", "consumed"):
        (approvals / sub).mkdir(parents=True)
    # Proxy leg: the real filing path writes SWAP_APPROVALS_DIR/pending/.
    # The VAPID push and the summons journal are separate features (#428
    # G4, H2) -- patched out so this suite tests the filing loop only.
    pdir = mock.patch.object(sa, "APPROVALS_DIR", str(approvals))
    pen = mock.patch.object(sa, "APPROVALS_ENABLED", True)
    push = mock.patch.object(sa, "_push_notify")
    summons = mock.patch.object(sa, "_summons_append")
    # Uploader + ingest legs: same physical store via SVM_APPROVALS_DIR,
    # box-owned per the G76.7 writer-identity gate (CI's owner is neither
    # bdrive nor swapd, so the lookup is stubbed like the unit suites).
    monkeypatch.setenv("SVM_APPROVALS_DIR", str(approvals))
    monkeypatch.setattr(spark_pair, "_ingest_file_owner",
                        lambda path: "swapd")
    # Ingest audit trail (Architecture B3): point at a tmp file per test.
    monkeypatch.setenv("CONFIRM_AUDIT", str(tmp_path / "audit.log"))
    os.makedirs(str(tmp_path / "state"), mode=0o700, exist_ok=True)
    with open(str(tmp_path / "state" / "enrollment.json"), "w") as f:
        json.dump({"box_id": BOX_ID, "token": TOKEN}, f)
    plane = FilingPlane()
    monkeypatch.setattr(spark_pair, "_http", plane)
    ctx = Ctx(tmp_path)
    ctx.approvals = str(approvals)
    ctx.plane = plane
    with pdir, pen, push, summons:
        yield ctx


def _file_refusal():
    """One proxy refusal through the real filing leg."""
    addon = _make_addon()
    signals = addon._file_approval("github", "github.com", "POST",
                                   "/gists", "no grant")
    assert len(signals) == 1
    aid, state = signals[0]
    assert state == "pending"
    return aid


def _pending_aids(ctx):
    return sorted(
        fn[:-len(".json")]
        for fn in os.listdir(os.path.join(ctx.approvals, "pending"))
        if fn.endswith(".json"))


def _consumed(ctx, aid):
    p = os.path.join(ctx.approvals, "consumed", aid + ".json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def test_refusal_reaches_plane_within_one_uploader_pass(loop, capsys):
    """S5 (1): a proxy refusal creates the plane record within one
    uploader interval -- the real filing, the real scan, one POST."""
    aid = _file_refusal()
    assert _pending_aids(loop) == [aid]

    assert spark_pair.cmd_upload_filings(loop) == 0

    # Exactly one plane record, keyed (box_id, aid), with the G76.3
    # payload mapping -- including the refusal reason the uploader parses
    # out of the proxy's pinned summary suffix.
    assert list(loop.plane.records) == [(BOX_ID, aid)]
    body = loop.plane.records[(BOX_ID, aid)]
    assert body["aid"] == aid
    assert "(refused: no grant)" in body["summary"]
    detail = body["detail"]
    assert detail["credential"] == "github"
    assert detail["host"] == "github.com"
    assert detail["method"] == "POST"
    assert detail["path_prefix"] == "/gists"
    assert detail["reason"] == "no grant"
    # The uploader caps the summary at the plane's bound (G76.3).
    assert len(body["summary"].encode()) <= 256


def test_retry_storm_returns_deduped(loop, capsys):
    """S5 (2): retry storms return deduped -- a second uploader pass over
    the same filing POSTs again but the plane creates no second record."""
    aid = _file_refusal()
    assert spark_pair.cmd_upload_filings(loop) == 0
    assert len(loop.plane.records) == 1

    assert spark_pair.cmd_upload_filings(loop) == 0

    assert len(loop.plane.posts) == 2  # the retry really re-POSTed
    assert len(loop.plane.records) == 1  # but nothing duplicated
    out = capsys.readouterr().out
    # The count, not the phrase: "0 already on the plane" also contains
    # the phrase, so only the count proves the dedupe branch ran.
    assert "1 already on the plane" in out


def test_plane_down_keeps_local_filing_and_drains_on_recovery(loop, capsys):
    """S5 (3): plane down -> local approvals unaffected and the upload
    backlog drains on recovery."""
    aid = _file_refusal()
    loop.plane.down = True

    assert spark_pair.cmd_upload_filings(loop) == 1  # loud failure

    # The local filing is untouched: the plane outage never breaks the
    # box-local approval flow.
    assert _pending_aids(loop) == [aid]
    assert loop.plane.records == {}
    err = capsys.readouterr()
    assert "will retry at the next cron tick" in err.out + err.err

    loop.plane.down = False
    assert spark_pair.cmd_upload_filings(loop) == 0
    assert list(loop.plane.records) == [(BOX_ID, aid)]


def test_owner_decision_roundtrip_stamps_plane_origin(loop, monkeypatch):
    """S5 (4): owner taps decide -> #873 command -> #874 ingest -> the
    parked filing carries the terminal decision with decision_origin
    "plane". The grant mint is stubbed (its own suite covers it); the
    decision command shape is the pinned #873 wire shape."""
    aid = _file_refusal()
    assert spark_pair.cmd_upload_filings(loop) == 0

    seq = loop.plane.owner_decide(BOX_ID, aid, "approve")

    class _MintOk:
        def __call__(self, argv):
            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

    monkeypatch.setattr(spark_pair, "_mint_grant", _MintOk())
    assert spark_pair.cmd_ingest(loop) == 0

    rec = _consumed(loop, aid)
    assert rec is not None
    assert rec["decision"] == "approve"
    assert rec["decision_origin"] == "plane"
    assert rec["idempotency_key"] == \
        "approval_decision:%s:%s:1" % (BOX_ID, aid)
    assert seq in loop.plane.acked


def test_denied_decision_reaches_parked_agent_poll(loop):
    """S5 (5, #984): the parked agent's next poll sees the terminal
    denial. After the plane decision is stamped by the real ingest, the
    real proxy serve leg (_approval_signal_for_refusal — the decision
    point behind the H18 client-visible channel) returns [(aid,
    "denied")] for the same tuple. The poll BEFORE the decision must
    see [(aid, "pending")] and must not file a second approval."""
    aid = _file_refusal()
    assert spark_pair.cmd_upload_filings(loop) == 0

    addon = _make_addon()

    def _poll():
        """One parked-agent poll, recorded exactly the way _resolve
        records it onto the H18 client-visible channel."""
        signals = addon._approval_signal_for_refusal(
            "github", "github.com", "POST", "/gists", "no grant")
        addon._approval_signal = None
        for sig_aid, state in signals:
            addon._record_approval_signal(sig_aid, state)
        return addon._approval_signal

    # Pre-decision poll: the agent sees pending; the pending filing is
    # coalesced, not re-filed (no second owner push).
    assert _poll() == [(aid, "pending")]
    assert _pending_aids(loop) == [aid]

    loop.plane.owner_decide(BOX_ID, aid, "deny")
    assert spark_pair.cmd_ingest(loop) == 0

    rec = _consumed(loop, aid)
    assert rec is not None
    assert rec["decision"] == "deny"
    assert rec["decision_origin"] == "plane"

    # The same addon instance: the pre-poll cached a negative #307
    # entry, so the serve leg re-scans past it (consumed/ dir-mtime
    # invalidation) to deliver the denial here. Composition-level pin
    # only: the #306 fresh re-check in _file_approval would deliver the
    # same terminal signal even if the cache never invalidated, so the
    # suite pins the delivery, not which layer fired.
    assert _poll() == [(aid, "denied")]
    assert _pending_aids(loop) == []


def test_filing_shape_satisfies_uploader_contract(loop):
    """The cross-leg schema pin: the proxy's filing output must carry
    every field the uploader's detail-tuple builder requires. If either
    side changes its shape, this breaks loudly instead of silently
    skipping every proxy-filed refusal at upload time."""
    aid = _file_refusal()
    with open(os.path.join(loop.approvals, "pending",
                           aid + ".json")) as f:
        rec = json.load(f)
    # _upload_detail's required tuple fields (G76.3).
    for key in ("credential", "host", "method", "path_prefix",
                "created", "expires"):
        v = rec.get(key)
        assert isinstance(v, str) and v, \
            "proxy filing must carry a usable %r for the uploader" % key
    # _upload_reason's pinned summary suffix.
    assert spark_pair._upload_reason(rec.get("summary")) == "no grant"
    # The uploader's own builder accepts the real filing, not just a
    # hand-written fixture.
    detail, derr = spark_pair._upload_detail(rec)
    assert derr is None, derr
    assert detail["reason"] == "no grant"

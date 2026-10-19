"""Tests for issue #1372 slice 1: `muse-job approvals` / `decide` / `answer`
operator subcommands plus pending-approval surfacing in `status`.

The REAL msp_approval module drives these tests (it imports msp_host and
msp_session, which are faked in sys.modules here -- the real module binds
to the fakes at import). The fake serve host records every call, pinning
the CLI<->approval-plane contract without a live `muse serve`. No tmux,
no git, no network.
"""
import argparse
import copy
import importlib.machinery
import importlib.util
import json
import os
import sys
import time
import types

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


class FakeHost:
    """Fake MSPHost: records every call(); handlers answer per-method."""

    instances = []

    def __init__(self, serve_argv, *, client_name, log_path=None, **kw):
        self.serve_argv = serve_argv
        self.client_name = client_name
        self.log_path = log_path
        self.calls = []
        self.handlers = {}
        self.opened = False
        self.closed = False
        FakeHost.instances.append(self)

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def call(self, method, params):
        self.calls.append((method, params))
        h = self.handlers.get(method)
        if h is None:
            raise AssertionError(f"no fake handler for {method}")
        return h(params)


# Wire shapes modeled on muse-job/tests/test_msp_approval.py's fixture
# (the invented parts there are documented as such; the CLI tests only
# assert the parts the client documents).
APPROVAL_WIRE = {
    "approvalId": "ap-1",
    "sessionId": "sess-1",
    "toolName": "exec",
    "subject": {"kind": "shell", "command": "rm -rf /tmp/x"},
    "rawArgs": '{"cmd": "rm -rf /tmp/x"}',
    "availableChoices": [
        {"choiceId": "allow-once", "label": "Allow once",
         "decision": "approved", "scope": "once",
         "acceptsFeedback": False},
        {"choiceId": "deny", "label": "Deny",
         "decision": "denied", "scope": "once",
         "acceptsFeedback": True},
    ],
    "currentRequirementId": {"approvalId": "ap-1", "sourceIndex": 0},
}

PROMPT_WIRE = {
    "userInputId": "ui-1",
    "sessionId": "sess-1",
    "toolName": "ask",
    "questions": [
        {"id": "q-trust", "header": "Workspace trust",
         "question": "Do you trust this workspace?",
         "options": [{"label": "Yes, trust it"}, {"label": "No"}],
         "selection": {"mode": "single"}},
        {"id": "q-free", "header": "Notes",
         "question": "Anything to add?",
         "options": [],
         "selection": {"mode": "single"}},
    ],
}


class FakeView:
    def __init__(self, state="working", active_turn_id="turn-1",
                 pending_summary="", last_terminal=None):
        self.state = state
        self.active_turn_id = active_turn_id
        self.pending_summary = pending_summary
        self.last_event_at = time.time()
        self.last_terminal = last_terminal


@pytest.fixture(autouse=True)
def _preserve_no_auto_update():
    # Same as test_msp_cli.py: _msp_host_for sets MUSE_NO_AUTO_UPDATE=1
    # process-wide; keep it from leaking into sibling test modules.
    had = os.environ.get("MUSE_NO_AUTO_UPDATE")
    yield
    if had is None:
        os.environ.pop("MUSE_NO_AUTO_UPDATE", None)
    else:
        os.environ["MUSE_NO_AUTO_UPDATE"] = had


@pytest.fixture()
def fakes(monkeypatch):
    """Install fake msp_host/msp_session/msp_events; real msp_approval
    binds to them at import."""
    FakeHost.instances.clear()
    ns = types.SimpleNamespace()
    # Drop any real cached copy so the real msp_approval module is
    # (re)imported fresh against this test's fakes. The real module
    # binds msp_host/msp_session at import from sys.modules, where the
    # fakes below are installed.
    sys.modules.pop("msp_approval", None)

    m_host = types.ModuleType("msp_host")

    class MSPError(Exception):
        pass

    class ServerError(MSPError):
        pass

    m_host.MSPError = MSPError
    m_host.ServerError = ServerError
    m_host.MSPHost = FakeHost

    m_session = types.ModuleType("msp_session")
    m_session.new_command_id = lambda: "cmd-1"
    m_session.check_command_id = lambda cid: cid
    ns.resume_calls = []
    ns.resume_error = None

    def resume_session(host, sid):
        ns.resume_calls.append(sid)
        if ns.resume_error is not None:
            raise ns.resume_error

    m_session.resume_session = resume_session

    m_events = types.ModuleType("msp_events")
    m_events.polled = []

    def poll_session_view(host, session_id, job_dir, *, replay_wait=2.0,
                          sink=None):
        m_events.polled.append((session_id, job_dir))
        return FakeView()

    m_events.poll_session_view = poll_session_view

    monkeypatch.setitem(sys.modules, "msp_host", m_host)
    monkeypatch.setitem(sys.modules, "msp_session", m_session)
    monkeypatch.setitem(sys.modules, "msp_events", m_events)
    # _msp_imports() loads all five sibling modules; the CLI paths under
    # test never touch turn/recovery, so stub modules suffice (mirrors
    # test_msp_cli.py's full five-fake set).
    monkeypatch.setitem(sys.modules, "msp_turn",
                        types.ModuleType("msp_turn"))
    monkeypatch.setitem(sys.modules, "msp_recovery",
                        types.ModuleType("msp_recovery"))

    # Install the serve-call handlers on every FakeHost as it is created.
    orig_init = FakeHost.__init__

    def patched_init(self, *a, **kw):
        orig_init(self, *a, **kw)
        self.handlers["approval/listPending"] = (
            lambda params: ns.list_pending_result(params))
        self.handlers["approval/decide"] = (
            lambda params: ns.decide_result(params))
        self.handlers["userInput/answer"] = (
            lambda params: ns.answer_result(params))

    def default_list_pending(params):
        return {"approvals": [copy.deepcopy(APPROVAL_WIRE)],
                "userInputs": [copy.deepcopy(PROMPT_WIRE)]}

    def default_decide(params):
        assert params["requirementId"] == \
            APPROVAL_WIRE["currentRequirementId"]
        # Fixture-faithful ack shape (cf. test_msp_approval.py's fake
        # serve): the CLI prints a key whitelist of this, never the raw
        # dict, so unvetted future server fields never reach the
        # operator's terminal.
        return {"approvalId": params["approvalId"],
                "commandId": params["commandId"],
                "status": "accepted", "terminal": True}

    def default_answer(params):
        return {"userInputId": params["userInputId"],
                "commandId": params["commandId"],
                "status": "accepted"}

    ns.list_pending_result = default_list_pending
    ns.decide_result = default_decide
    ns.answer_result = default_answer
    monkeypatch.setattr(FakeHost, "__init__", patched_init)
    ns.host_calls = lambda: [c for h in FakeHost.instances for c in h.calls]
    return ns


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_approvals", CLI_PATH)


def _make_job(cli, slug, **fields):
    jd = cli.job_dir(slug)
    os.makedirs(os.path.join(jd, "tmp"), exist_ok=True)
    os.makedirs(cli.METADATA_DIR, exist_ok=True)
    job = {"slug": slug, "state": "active", "started_at": time.time(),
           "transport": "msp", "session_uuid": "sess-1"}
    job.update(fields)
    with open(cli.job_json_path(slug), "w") as f:
        json.dump(job, f)
    with open(os.path.join(jd, "prompt.md"), "w") as f:
        f.write("do the thing")
    return jd


def _ns(**kw):
    return argparse.Namespace(**kw)


# -- approvals ------------------------------------------------------------

def test_approvals_lists_redacted(cli, fakes, capsys):
    # Issue #1372: the operator sees ids, titles, choice structure --
    # never subjects/rawArgs (real secrets may live there).
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "approval ap-1: Run shell command" in out
    assert "allow-once (approved)" in out and "deny (denied)" in out
    assert "user-input ui-1" in out
    # Issue #1773: the machine hint renders only behind --show-heuristic --
    # the default surface shows no machine verdict.
    assert "trust prompt" not in out
    assert "rm -rf /tmp/x" not in out
    assert "rawArgs" not in out
    methods = [c[0] for c in fakes.host_calls()]
    # One listPending for both planes (list_pending reads approvals and
    # prompts in a single round-trip so the two lists share one
    # point-in-time state).
    assert methods.count("approval/listPending") == 1


def test_approvals_show_heuristic_opt_in(cli, fakes, capsys):
    # Issue #1773: --show-heuristic renders the hint, reworded so its
    # non-authority is impossible to miss.
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False,
                               show_heuristic=True))
    assert rc == 0
    out = capsys.readouterr().out
    assert ("user-input ui-1 "
            "[hint: looks like a trust prompt — verify yourself]") in out


def test_approvals_show_heuristic_json_keeps_machine_field(cli, fakes, capsys):
    # Issue #1773: --json keeps the machine-readable looksLikeTrustPrompt
    # field regardless of --show-heuristic (scripts consume it; the issue
    # only gates the human tag).
    import json as _json
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=True, show_secrets=False))
    assert rc == 0
    out = _json.loads(capsys.readouterr().out)
    assert out["userInputs"][0]["looksLikeTrustPrompt"] is True


def test_approvals_json_redacted(cli, fakes, capsys):
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=True, show_secrets=False))
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["approvals"][0]["approvalId"] == "ap-1"
    assert "rm -rf /tmp/x" not in json.dumps(body)
    assert "rawArgs" not in json.dumps(body)
    assert body["userInputs"][0]["questions"][0]["mode"] == "single"


def test_approvals_show_secrets_warns(cli, fakes, capsys):
    # The smoke-CLI posture: unredacted output prints the raw wire params
    # AND warns on stderr on every invocation.
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=True, show_secrets=True))
    assert rc == 0
    captured = capsys.readouterr()
    assert "rm -rf /tmp/x" in captured.out
    assert "WARNING" in captured.err and "--show-secrets" in captured.err


def test_approvals_empty(cli, fakes, capsys):
    slug = "job1"
    _make_job(cli, slug)
    fakes.list_pending_result = lambda params: {"approvals": [],
                                                "userInputs": []}
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    assert "no pending approvals" in capsys.readouterr().out


def test_approvals_tmux_job_refused(cli, fakes):
    # A tmux job has no prompt plane: clear usage error, not a silent
    # empty list.
    slug = "tmuxjob"
    _make_job(cli, slug, transport="tmux")
    with pytest.raises(RuntimeError, match="MSP-transport"):
        cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))
    assert fakes.host_calls() == []


# -- decide ---------------------------------------------------------------

def test_decide_sends_fresh_requirement_id(cli, fakes, capsys):
    # The requirementId race guard is re-read from listPending just now
    # and sent verbatim; the admission ack is printed.
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                            choice_id="deny", feedback="nope"))
    assert rc == 0
    calls = fakes.host_calls()
    decide = [p for m, p in calls if m == "approval/decide"]
    assert len(decide) == 1
    assert decide[0]["approvalId"] == "ap-1"
    assert decide[0]["choiceId"] == "deny"
    assert decide[0]["feedback"] == "nope"
    assert decide[0]["requirementId"] == {"approvalId": "ap-1",
                                         "sourceIndex": 0}
    assert decide[0]["commandId"] == "cmd-1"
    body = json.loads(capsys.readouterr().out)
    assert body["approvalId"] == "ap-1"
    assert body["choiceId"] == "deny"
    assert body["status"] == "accepted"
    assert body["terminal"] is True
    # The ack prints with a key whitelist: the server's commandId echo
    # and any future fields never reach the operator's terminal.
    assert set(body) == {"approvalId", "choiceId", "status", "terminal"}


def test_decide_unknown_choice_never_hits_wire(cli, fakes):
    # Client-side validation fires before anything is sent: a bad
    # choice_id must not reach the server as a blind decision.
    slug = "job1"
    _make_job(cli, slug)
    with pytest.raises(RuntimeError, match="not one of"):
        cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                           choice_id="nuke", feedback=None))
    assert not [m for m, _ in fakes.host_calls()
                if m == "approval/decide"]


def test_decide_unknown_approval_lists_pending(cli, fakes):
    slug = "job1"
    _make_job(cli, slug)
    with pytest.raises(RuntimeError, match="no pending approval 'zzz'"):
        cli.cmd_decide(_ns(slug=slug, approval_id="zzz",
                           choice_id="deny", feedback=None))


def test_decide_stale_requirement_surfaces(cli, fakes):
    # A server-side stale-stage refusal is an error for the operator,
    # not a silent success: the real decide call's error propagates.
    slug = "job1"
    _make_job(cli, slug)
    m_host = sys.modules["msp_host"]

    def boom(params):
        raise m_host.ServerError("stale_requirement")

    fakes.decide_result = boom
    with pytest.raises(RuntimeError, match="stale_requirement"):
        cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                           choice_id="deny", feedback=None))


# -- answer ---------------------------------------------------------------

def test_answer_requires_explicit_classification(cli, fakes):
    # Issue #1372 / the recorded #211 decision: the CLI never classifies
    # prompts itself -- exactly one of the two flags is required.
    slug = "job1"
    _make_job(cli, slug)
    base = dict(slug=slug, user_input_id="ui-1", answers="[]",
                trust_policy_opt_in=False, classified_not_trust_prompt=False)
    with pytest.raises(RuntimeError, match="explicit classification"):
        cli.cmd_answer(_ns(**base))
    both = dict(base, trust_policy_opt_in=True,
                classified_not_trust_prompt=True)
    with pytest.raises(RuntimeError, match="only one"):
        cli.cmd_answer(_ns(**both))
    assert fakes.host_calls() == []


def test_answer_not_trust_prompt(cli, fakes, capsys):
    # A classified-ordinary prompt answers directly; the answers are
    # validated client-side (mode conformance) and never echoed to stdout.
    slug = "job1"
    _make_job(cli, slug)
    answers = json.dumps([
        {"questionId": "q-trust", "selectedLabel": "Yes, trust it"},
        {"questionId": "q-free", "freeText": "sekret-answer-text"},
    ])
    rc = cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                            answers=answers, trust_policy_opt_in=False,
                            classified_not_trust_prompt=True))
    assert rc == 0
    calls = fakes.host_calls()
    answer = [p for m, p in calls if m == "userInput/answer"]
    assert len(answer) == 1
    assert answer[0]["userInputId"] == "ui-1"
    wire = {a["questionId"]: a for a in answer[0]["answers"]}
    assert wire["q-trust"]["selectedLabel"] == "Yes, trust it"
    assert wire["q-free"]["freeText"] == "sekret-answer-text"
    out = capsys.readouterr().out
    assert "sekret-answer-text" not in out  # answers never echoed
    body = json.loads(out)
    assert body["userInputId"] == "ui-1"
    assert body["status"] == "accepted"
    assert set(body) == {"userInputId", "status"}  # ack key whitelist


def test_answer_trust_opt_in(cli, fakes, capsys):
    # The trust-policy opt-in routes through the explicit TrustPolicy
    # gate (the recorded #211 decision): a trust-looking prompt answers
    # only with the opt-in value in hand.
    slug = "job1"
    _make_job(cli, slug)
    answers = json.dumps([{"questionId": "q-trust",
                           "selectedLabel": "Yes, trust it"},
                          {"questionId": "q-free", "freeText": "n/a"}])
    rc = cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                            answers=answers, trust_policy_opt_in=True,
                            classified_not_trust_prompt=False))
    assert rc == 0
    answer = [p for m, p in fakes.host_calls() if m == "userInput/answer"]
    assert len(answer) == 1
    body = json.loads(capsys.readouterr().out)
    assert body["userInputId"] == "ui-1"
    assert body["status"] == "accepted"


def test_answer_bad_answers_fail_client_side(cli, fakes):
    # A mismatched answer (mode/label violation) fails loud here, never
    # on the wire.
    slug = "job1"
    _make_job(cli, slug)
    answers = json.dumps([{"questionId": "q-trust",
                           "selectedLabel": "Not an option"},
                          {"questionId": "q-free", "freeText": "x"}])
    with pytest.raises(RuntimeError, match="not one of the offered"):
        cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                           answers=answers, trust_policy_opt_in=False,
                           classified_not_trust_prompt=True))
    assert not [m for m, _ in fakes.host_calls() if m == "userInput/answer"]


def test_answer_invalid_json(cli, fakes):
    slug = "job1"
    _make_job(cli, slug)
    with pytest.raises(RuntimeError, match="not valid JSON"):
        cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                           answers="{nope", trust_policy_opt_in=False,
                           classified_not_trust_prompt=True))


def test_answer_tmux_job_refused(cli, fakes):
    slug = "tmuxjob"
    _make_job(cli, slug, transport="tmux")
    with pytest.raises(RuntimeError, match="MSP-transport"):
        cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1", answers="[]",
                           trust_policy_opt_in=False,
                           classified_not_trust_prompt=True))
    assert fakes.host_calls() == []


# -- status surfacing -----------------------------------------------------

def test_status_surfaces_pending_approvals(cli, fakes, capsys):
    # Issue #1372: a job blocked on operator input says so on the
    # primary overview, with the unblocking command named.
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_status(_ns(slug=slug, json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "approvals: 1 pending, user-input: 1 pending" in out
    assert f"muse-job approvals {slug}" in out


def test_status_json_carries_pending_counts(cli, fakes, capsys):
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_status(_ns(slug=slug, json=True))
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["pending_approvals"] == 1
    assert body["pending_user_inputs"] == 1


def test_status_pending_check_failure_degrades(cli, fakes, capsys):
    # The approval plane is additive: a failing listPending degrades to
    # an honest 'check failed' line, never breaks status.
    slug = "job1"
    _make_job(cli, slug)
    m_host = sys.modules["msp_host"]

    def boom(params):
        raise m_host.ServerError("listPending not supported")

    fakes.list_pending_result = boom
    rc = cli.cmd_status(_ns(slug=slug, json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "pending check failed" in out
    assert "job job1: transport=msp" in out  # the overview still renders


# -- supervisor-held sessions (Engineering B1) ------------------------------

def _held_elsewhere_error():
    # The single-attach refusal session/resume raises while the
    # supervisor holds the session (muse-job's _MSP_ALREADY_IN_USE_CODE).
    err = sys.modules["msp_host"].ServerError("session is already in use")
    err.code = -32021
    return err


def test_approvals_held_elsewhere_routes_via_supervisor(cli, fakes,
                                                        monkeypatch):
    # Issue #1396: the listing no longer fails on a supervisor-held
    # session -- the held-elsewhere race queues a read-only listing for
    # the supervisor instead (the _msp_steer pattern, mirroring
    # decide/answer's slice-2 behavior).
    slug = "job1"
    _make_job(cli, slug)
    fakes.resume_error = _held_elsewhere_error()
    routed = []
    monkeypatch.setattr(
        cli, "_msp_list_via_supervisor",
        lambda args: routed.append(args.slug) or 0)
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    assert routed == [slug]
    # The raced direct path opened a host but never listed on it
    # (resume failed single-attach); the listing went to the
    # supervisor instead.
    assert "approval/listPending" not in [m for m, _ in fakes.host_calls()]


def test_decide_held_elsewhere_routes_via_supervisor(cli, fakes,
                                                     monkeypatch):
    # Slice 2: decide no longer fails on a supervisor-held session --
    # the held-elsewhere race queues the decision for the supervisor
    # instead (the _msp_steer pattern).
    slug = "job1"
    _make_job(cli, slug)
    fakes.resume_error = _held_elsewhere_error()
    routed = []
    monkeypatch.setattr(
        cli, "_msp_decide_via_supervisor",
        lambda args, kind, fields: routed.append((kind, fields)) or 0)
    rc = cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                            choice_id="deny", feedback=None))
    assert rc == 0
    assert len(routed) == 1
    assert routed[0][0] == "decide"
    assert routed[0][1]["approval_id"] == "ap-1"


def test_answer_held_elsewhere_routes_via_supervisor(cli, fakes,
                                                     monkeypatch):
    # Slice 2: answer no longer fails on a supervisor-held session --
    # the held-elsewhere race queues the answer (with its trust
    # classification) for the supervisor instead.
    slug = "job1"
    _make_job(cli, slug)
    fakes.resume_error = _held_elsewhere_error()
    routed = []
    monkeypatch.setattr(
        cli, "_msp_decide_via_supervisor",
        lambda args, kind, fields: routed.append((kind, fields)) or 0)
    rc = cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1", answers="[]",
                            trust_policy_opt_in=False,
                            classified_not_trust_prompt=True))
    assert rc == 0
    assert len(routed) == 1
    assert routed[0][0] == "answer"
    assert routed[0][1]["trust"] is False


def test_status_snapshot_path_no_bogus_check_failed(cli, fakes, capsys):
    # Engineering B2: on the snapshot path (supervisor holds the
    # session -- the normal live case) listPending is never attempted,
    # so status must not print the "pending check failed" line that
    # falsely implies server drift. The view's own pending summary
    # (already printed) is the honest signal.
    slug = "job1"
    _make_job(cli, slug)
    fakes.resume_error = _held_elsewhere_error()
    snap = {"msp_state": "blocked_approval", "active_turn_id": "turn-1",
            "pending": "approval ap-1: Run shell command",
            "last_activity_age_s": 5, "t": time.time()}
    view_path = cli._msp_supervisor_files(slug)["view"]
    os.makedirs(os.path.dirname(view_path), exist_ok=True)
    with open(view_path, "w") as f:
        json.dump(snap, f)
    rc = cli.cmd_status(_ns(slug=slug, json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "pending check failed" not in out
    assert "approvals:" not in out
    assert "snapshot" in out  # the supervisor-held line still renders
    assert "approval ap-1" in out  # the view's pending summary


def test_show_secrets_without_json_warns(cli, fakes, capsys):
    # --show-secrets is only meaningful with --json; without it the
    # operator gets a warning, not silently-redacted output.
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=True))
    assert rc == 0
    captured = capsys.readouterr()
    assert "no effect without --json" in captured.err
    assert "rm -rf /tmp/x" not in captured.out

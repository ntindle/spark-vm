"""Tests for issue #1372 slice 2: the MSP approval supervise-path wiring.

- approval/request + userInput/request handlers registered on the
  supervisor's host (before open), surfacing server-issued prompts to
  the operator via the redacted journal and the request ledger.
- decide/answer routed through the supervisor on held sessions:
  queue-drain with result rendezvous.
- the trust gate: a queued answer MUST carry the operator's trust
  classification; trust=true answers go through answer_trust_prompt
  with an explicit TrustPolicy; unclassified answers are refused and
  never answered.

Same harness as test_msp_approval_cli.py: the REAL msp_approval module
drives these tests (it binds the faked msp_host/msp_session at import),
and a fake serve host records every call. No tmux, no git, no network.
"""
import argparse
import copy
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import stat
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
    """Fake MSPHost: records every call(); handlers answer per-method.

    set_request_handler records registrations and refuses registration
    after open() -- the real MSPHost documents registration-before-open
    as the only race-free shape.
    """

    instances = []

    def __init__(self, serve_argv, *, client_name, log_path=None, **kw):
        self.serve_argv = serve_argv
        self.client_name = client_name
        self.log_path = log_path
        self.calls = []
        self.handlers = {}
        self.request_handlers = {}
        self.opened = False
        self.closed = False
        FakeHost.instances.append(self)

    def set_request_handler(self, method, handler):
        if self.opened:
            raise AssertionError("request handler registered after open()")
        self.request_handlers[method] = handler

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


class FakeJobSignal:
    def __init__(self, kind, method, view_cursor=None, detail=None,
                 turn_id=None):
        self.kind = kind
        self.method = method
        self.detail = detail


APPROVAL_WIRE = {
    "approvalId": "ap-1",
    "sessionId": "sess-1",
    "toolName": "exec",
    "subject": {"kind": "shell", "command": "rm -rf /tmp/x"},
    "rawArgs": '{"cmd": "rm -rf /tmp/x"}',
    "title": "Run shell command",
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


@pytest.fixture(autouse=True)
def _preserve_no_auto_update():
    had = os.environ.get("MUSE_NO_AUTO_UPDATE")
    yield
    if had is None:
        os.environ.pop("MUSE_NO_AUTO_UPDATE", None)
    else:
        os.environ["MUSE_NO_AUTO_UPDATE"] = had


@pytest.fixture()
def fakes(monkeypatch):
    FakeHost.instances.clear()
    ns = types.SimpleNamespace()
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
    m_session.YOLO_APPROVAL_MODE = "allowAll"

    def resume_session(host, sid):
        pass

    m_session.resume_session = resume_session

    m_events = types.ModuleType("msp_events")
    m_events.JobSignal = FakeJobSignal

    def poll_session_view(host, session_id, job_dir, *, replay_wait=2.0,
                          sink=None):
        raise AssertionError("poll_session_view not stubbed in this test")

    m_events.poll_session_view = poll_session_view

    monkeypatch.setitem(sys.modules, "msp_host", m_host)
    monkeypatch.setitem(sys.modules, "msp_session", m_session)
    monkeypatch.setitem(sys.modules, "msp_events", m_events)
    monkeypatch.setitem(sys.modules, "msp_turn",
                        types.ModuleType("msp_turn"))
    monkeypatch.setitem(sys.modules, "msp_recovery",
                        types.ModuleType("msp_recovery"))

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
    return load_script("muse_job_cli_supervise", CLI_PATH)


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


def _journal_text(cli, slug):
    with open(cli._msp_journal_path(slug)) as f:
        return f.read()


# -- request-handler wiring ------------------------------------------------

def test_host_registers_request_handlers_before_open(cli, fakes):
    # The supervisor's host must register the approval/userInput
    # request handlers BEFORE open(): the real MSPHost documents
    # register-before-open as the only race-free shape (the fake
    # refuses late registration).
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    h1 = msp_approval.handle_approval_request(lambda a: None)
    h2 = msp_approval.handle_user_input_request(lambda p: None)
    host = cli._msp_host_for(
        slug, request_handlers={"approval/request": h1,
                                "userInput/request": h2})
    assert host.opened
    assert host.request_handlers["approval/request"] is h1
    assert host.request_handlers["userInput/request"] is h2
    host.close()


def test_on_approval_requested_journals_redacted(cli, fakes):
    # The server->client request surfaces to the operator immediately:
    # ids + title only. rawArgs/subjects (real secrets) never land in
    # the journal or the ledger. The ledger carries the operator-safe
    # shape (choices included) so `status` can render the decide
    # command on the held path.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    approval = msp_approval.parse_approval(copy.deepcopy(APPROVAL_WIRE))
    cli._msp_on_approval_requested(slug, approval)
    text = _journal_text(cli, slug)
    assert "approval/requested" in text
    assert "ap-1" in text
    assert "rm -rf /tmp/x" not in text
    assert "rawArgs" not in text
    entries = cli._msp_request_ledger_read(slug)
    assert len(entries) == 1
    assert entries[0]["kind"] == "approval"
    assert entries[0]["id"] == "ap-1"
    detail = entries[0]["detail"]
    assert detail["title"] == "Run shell command"
    assert [c["choiceId"] for c in detail["choices"]] == \
        ["allow-once", "deny"]
    assert "rm -rf /tmp/x" not in json.dumps(entries)


def test_on_user_input_requested_journals_counts(cli, fakes):
    # Question text is never journaled (their answers may be secrets);
    # the ledger carries the operator-safe shape (questions, options,
    # the trust tag) so `status` can render the answer command on the
    # held path, where `muse-job approvals` cannot list.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    prompt = msp_approval.parse_user_input(copy.deepcopy(PROMPT_WIRE))
    cli._msp_on_user_input_requested(slug, prompt)
    text = _journal_text(cli, slug)
    assert "userInput/requested" in text
    assert "ui-1" in text
    assert "2 question(s)" in text
    assert "Do you trust this workspace?" not in text
    entries = cli._msp_request_ledger_read(slug)
    assert entries[0]["kind"] == "user_input"
    assert entries[0]["id"] == "ui-1"
    detail = entries[0]["detail"]
    assert detail["looksLikeTrustPrompt"] is True
    assert [q["questionId"] for q in detail["questions"]] == \
        ["q-trust", "q-free"]
    assert detail["questions"][0]["options"] == ["Yes, trust it", "No"]
    # The ledger holds the actionable shape (the operator needs the
    # questions to compose answers); answers are never stored.
    assert "Do you trust this workspace?" in json.dumps(entries)
    assert set(detail) == {"userInputId", "looksLikeTrustPrompt",
                           "promptHash", "questions"}
    # The journaled hash is the real #1772 classification binding for
    # this exact prompt content, so a later classification can bind to
    # what was pending here.
    assert detail["promptHash"] == \
        msp_approval.prompt_content_hash(prompt)


# -- decision queue: drain ---------------------------------------------------

def _drain_host(cli):
    return FakeHost(["muse", "serve"], client_name="t")


def test_decide_queue_drains_on_supervisor_host(cli, fakes, capsys):
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-1", "choice_id": "deny", "feedback": "nope"},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    methods = [m for m, _ in fakes.host_calls()]
    assert "approval/decide" in methods
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "decided"
    # The ack is the key whitelist, never the raw server dict.
    assert set(result["ack"]) == {"approvalId", "choiceId", "status",
                                  "terminal"}
    assert result["ack"]["choiceId"] == "deny"
    # The decided request leaves the ledger: status stops advertising it.
    assert cli._msp_request_ledger_read(slug) == []


def test_answer_queue_trust_false_uses_plain_primitive(cli, fakes,
                                                       monkeypatch):
    # trust=false must reach the operator-driven primitive, never the
    # policy-gated entry point.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    calls = []
    orig_trust = msp_approval.answer_trust_prompt
    orig_plain = msp_approval.answer_user_input

    def spy_trust(*a, **kw):
        calls.append("trust")
        return orig_trust(*a, **kw)

    def spy_plain(*a, **kw):
        calls.append("plain")
        return orig_plain(*a, **kw)

    monkeypatch.setattr(msp_approval, "answer_trust_prompt", spy_trust)
    monkeypatch.setattr(msp_approval, "answer_user_input", spy_plain)
    answers = [{"questionId": "q-trust", "selectedLabel": "No"},
               {"questionId": "q-free", "freeText": "nothing"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1", "answers": answers, "trust": False},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert calls == ["plain"]
    assert ("userInput/answer" in [m for m, _ in fakes.host_calls()])
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "answered"
    # Answers are never echoed in the ack.
    assert "nothing" not in json.dumps(result)


def test_answer_queue_trust_true_routes_through_policy_gate(
        cli, fakes, monkeypatch):
    # trust=true must enter through answer_trust_prompt with the
    # explicit opt-in policy -- the no-gate primitive is not reachable
    # as the entry point.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    seen = []
    orig_trust = msp_approval.answer_trust_prompt

    def spy_trust(host, sid, prompt, answers, *, policy, command_id=None,
                  expected_prompt_hash=None):
        seen.append((policy, expected_prompt_hash))
        return orig_trust(host, sid, prompt, answers, policy=policy,
                          command_id=command_id,
                          expected_prompt_hash=expected_prompt_hash)

    monkeypatch.setattr(msp_approval, "answer_trust_prompt", spy_trust)
    orig_plain = msp_approval.answer_user_input
    plain_calls = []

    def spy_plain(*a, **kw):
        # The library's trust entry point delegates internally after
        # the policy check; only direct queue-path calls count here.
        plain_calls.append(a)
        return orig_plain(*a, **kw)

    monkeypatch.setattr(msp_approval, "answer_user_input", spy_plain)
    answers = [{"questionId": "q-trust", "selectedLabel": "Yes, trust it"},
               {"questionId": "q-free", "freeText": "x"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1", "answers": answers, "trust": True},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert len(seen) == 1
    assert seen[0][0].auto_answer_trust is True
    # A legacy queued entry carries no classification binding, so the
    # drain answers unbound (the pre-#1772 behavior is preserved).
    assert seen[0][1] is None
    assert ("userInput/answer" in [m for m, _ in fakes.host_calls()])
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "answered"


def test_answer_queue_prompt_hash_binding_refuses_reissue(cli, fakes):
    # #1772: a queued entry carrying the operator's classification
    # binding is verified at drain time -- a prompt re-issued while it
    # sat in the queue is refused with nothing on the wire.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    prompt = msp_approval.parse_user_input(copy.deepcopy(PROMPT_WIRE))
    bound = msp_approval.prompt_content_hash(prompt)
    calls = {"n": 0}
    orig = fakes.list_pending_result

    def reissuing(params):
        calls["n"] += 1
        if calls["n"] >= 2:
            mutated = copy.deepcopy(PROMPT_WIRE)
            mutated["questions"][0]["question"] = (
                "Do you trust this workspace? (RE-ISSUED)")
            return {"approvals": [], "userInputs": [mutated]}
        return orig(params)

    fakes.list_pending_result = reissuing
    answers = [{"questionId": "q-trust", "selectedLabel": "No"},
               {"questionId": "q-free", "freeText": "nothing"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1", "answers": answers, "trust": False,
         "prompt_hash": bound},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    methods = [m for m, _ in fakes.host_calls()]
    assert "userInput/answer" not in methods
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "error"
    assert "re-issued" in result["detail"]


def test_answer_queue_missing_trust_refused_fail_closed(cli, fakes):
    # The owner note on #1372: any future automated driver answering
    # through the queue must not silently opt out of the trust policy.
    # No classification -> refused, never answered.
    slug = "job1"
    _make_job(cli, slug)
    answers = [{"questionId": "q-free", "freeText": "nothing"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1", "answers": answers},  # no "trust" key
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    methods = [m for m, _ in fakes.host_calls()]
    # The gate fires before anything touches the wire: not even the
    # listPending read both plane helpers share.
    assert methods == []
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert "trust" in result["detail"]


def test_answer_queue_missing_trust_is_non_vacuous(cli, fakes):
    # The control for the fail-closed test: the IDENTICAL payload with
    # a classification passes the gate (the wire shows listPending was
    # reached) and only then fails answer validation (the single
    # question does not answer every question) -- proving the gate,
    # not validation, refused the unclassified entry.
    slug = "job1"
    _make_job(cli, slug)
    answers = [{"questionId": "q-free", "freeText": "nothing"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1", "answers": answers, "trust": False},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    methods = [m for m, _ in fakes.host_calls()]
    assert "approval/listPending" in methods  # gate passed, prompt fetched
    assert "userInput/answer" not in methods  # validation stopped it
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "error"  # not "refused": the gate let it in


def test_decide_queue_stale_turn_refused(cli, fakes):
    # A decision queued against a finished turn must never land on the
    # next turn (the turn_id tag is the anti-cross-turn guard).
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-1", "choice_id": "deny", "feedback": None},
        turn_id="turn-9")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert "approval/decide" not in [m for m, _ in fakes.host_calls()]
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert "older turn" in result["detail"]


def test_refuse_only_drain_marks_refused(cli, fakes):
    # The supervisor's post-loop pass: anything left in the queue gets
    # a terminal refused result instead of an orphaned entry the CLI
    # would rendezvous on until timeout.
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-1", "choice_id": "deny", "feedback": None},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, None, None, "turn-1",
                                  refuse_only=True)
    assert fakes.host_calls() == []
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert "exiting" in result["detail"]


def test_decide_unknown_approval_errors(cli, fakes):
    # The supervisor re-reads listPending before deciding: an approval
    # that vanished between the CLI's view and the drain is an error
    # result, not a blind wire call.
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-gone", "choice_id": "deny", "feedback": None},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert "approval/decide" not in [m for m, _ in fakes.host_calls()]
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "error"
    assert "ap-gone" in result["detail"]


def test_enqueue_decision_file_is_0600(cli, fakes):
    # Queued answers may carry real secrets: the queue file is 0600.
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1",
         "answers": [{"questionId": "q-free", "freeText": "s3cret"}],
         "trust": False},
        turn_id="turn-1")
    mode = stat.S_IMODE(
        os.stat(cli._msp_supervisor_files(slug)["decide_queue"]).st_mode)
    assert mode == 0o600
    # ...and the secret never leaks into the journal.
    assert "s3cret" not in _journal_text_safe(cli, slug)


def _journal_text_safe(cli, slug):
    try:
        return _journal_text(cli, slug)
    except OSError:
        return ""


# -- CLI routing ------------------------------------------------------------

def test_cmd_decide_routes_via_supervisor(cli, fakes, monkeypatch, capsys):
    # Supervisor alive: decide enqueues (with the turn tag) and prints
    # the rendezvoused ack; no fresh serve host is opened.
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    canned = {"status": "decided",
              "ack": {"approvalId": "ap-1", "choiceId": "deny",
                      "status": "accepted", "terminal": True}}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    rc = cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                            choice_id="deny", feedback="nope"))
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["choiceId"] == "deny"
    assert FakeHost.instances == []  # no direct host opened
    entries = [json.loads(line) for line in
               open(cli._msp_supervisor_files(slug)["decide_queue"])]
    assert len(entries) == 1
    assert entries[0]["kind"] == "decide"
    assert entries[0]["approval_id"] == "ap-1"
    assert entries[0]["choice_id"] == "deny"
    assert entries[0]["feedback"] == "nope"


def test_cmd_answer_carries_trust_classification(cli, fakes, monkeypatch,
                                                capsys):
    # The operator's --trust-policy-opt-in / --classified-not-trust-prompt
    # choice travels with the queued request; the drain's fail-closed
    # gate depends on it.
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    canned = {"status": "answered",
              "ack": {"userInputId": "ui-1", "status": "accepted"}}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    answers = '[{"questionId": "q-trust", "selectedLabel": "Yes"}]'
    rc = cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                            answers=answers, trust_policy_opt_in=True,
                            classified_not_trust_prompt=False))
    assert rc == 0
    entries = [json.loads(line) for line in
               open(cli._msp_supervisor_files(slug)["decide_queue"])]
    assert entries[0]["kind"] == "answer"
    assert entries[0]["trust"] is True
    # The queue stores the parsed answer list (ready for the drain).
    assert entries[0]["answers"] == json.loads(answers)


def test_cmd_answer_not_trust_classification(cli, fakes, monkeypatch,
                                             capsys):
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    canned = {"status": "answered",
              "ack": {"userInputId": "ui-1", "status": "accepted"}}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    rc = cli.cmd_answer(_ns(slug=slug, user_input_id="ui-1",
                            answers='[{"questionId": "q-free", '
                                    '"freeText": "x"}]',
                            trust_policy_opt_in=False,
                            classified_not_trust_prompt=True))
    assert rc == 0
    entries = [json.loads(line) for line in
               open(cli._msp_supervisor_files(slug)["decide_queue"])]
    assert entries[0]["trust"] is False


def test_cmd_decide_refused_raises_clean_error(cli, fakes, monkeypatch):
    # A refused rendezvous surfaces as a clean `muse-job: error:` line
    # (main()'s handler), not a traceback.
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    canned = {"status": "refused",
              "detail": "decision queued for an older turn"}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    with pytest.raises(RuntimeError, match="older turn"):
        cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                           choice_id="deny", feedback=None))


def test_cmd_decide_direct_path_unchanged(cli, fakes, capsys):
    # No supervisor: the direct _msp_call path still works (the
    # slice-1 contract is untouched).
    slug = "job1"
    _make_job(cli, slug)
    rc = cli.cmd_decide(_ns(slug=slug, approval_id="ap-1",
                            choice_id="deny", feedback="nope"))
    assert rc == 0
    assert "approval/decide" in [m for m, _ in fakes.host_calls()]
    body = json.loads(capsys.readouterr().out)
    assert body["approvalId"] == "ap-1"


# -- supervisor-mediated listing (issue #1396) ------------------------------

def test_list_queue_drains_on_supervisor_host(cli, fakes):
    # The "list" queue kind is read-only: the supervisor serves the
    # pending set from its already-open host (single-attach means the
    # CLI can never resume it itself), the ack is the redacted
    # operator-safe shape (no rawArgs, no answers), and neither the
    # journal nor the request ledger changes.
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "seeded"})
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": False},
                                    turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert "approval/listPending" in [m for m, _ in fakes.host_calls()]
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "listed"
    ack = result["ack"]
    assert ack["approvals"][0]["approvalId"] == "ap-1"
    assert ack["userInputs"][0]["userInputId"] == "ui-1"
    # Redacted: the wire shape's secret-carrying fields are absent.
    assert "rawArgs" not in json.dumps(ack)
    assert "rm -rf /tmp/x" not in json.dumps(ack)
    assert ack["rawApprovals"] is None
    assert ack["rawUserInputs"] is None
    # Read-only: the seeded ledger entry survives and no journal row
    # was written.
    assert [e["id"] for e in cli._msp_request_ledger_read(slug)] == ["ap-1"]
    assert not os.path.exists(cli._msp_journal_path(slug))


def test_list_queue_unredacted_ships_raw_shapes(cli, fakes):
    # --show-secrets --json through the supervisor: the ack carries
    # the raw wire shapes next to the redacted ones (the same 0600
    # rendezvous file the queued-answer payloads use).
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": True},
                                    turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "listed"
    ack = result["ack"]
    assert "rm -rf /tmp/x" in json.dumps(ack["rawApprovals"][0])
    assert ack["rawUserInputs"][0]["userInputId"] == "ui-1"
    # The redacted shapes are still present (fail-closed display).
    assert "rm -rf /tmp/x" not in json.dumps(ack["approvals"])


def test_list_unredacted_flag_must_be_bool_true(cli, fakes):
    # A truthy-but-not-True unredacted value (e.g. a hand-written
    # queue entry) must not leak raw wire params: only the CLI's
    # explicit boolean True authorizes the raw shapes.
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": "yes"},
                                    turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["ack"]["rawApprovals"] is None


def test_list_queue_stale_turn_refused_keeps_ledger(cli, fakes):
    # A listing queued against an older turn is refused with a
    # listing-worded message; the ledger is untouched (a listing never
    # resolves requests, so there is nothing to drop).
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "seeded"})
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": False},
                                    turn_id="turn-0")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert result["detail"] == "listing queued for an older turn"
    assert [e["id"] for e in cli._msp_request_ledger_read(slug)] == ["ap-1"]


def test_list_refuse_only_refused_keeps_ledger(cli, fakes):
    # Supervisor exiting: the listing is refused like decide/answer,
    # with no ledger change.
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "user_input", "ui-1",
                                   {"questions": []})
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": False},
                                    turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1", refuse_only=True)
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert "supervisor exiting" in result["detail"]
    assert [e["id"] for e in cli._msp_request_ledger_read(slug)] == ["ui-1"]


def test_cmd_approvals_routes_via_supervisor(cli, fakes, monkeypatch,
                                             capsys):
    # Supervisor alive: approvals enqueues a read-only "list" (with
    # the snapshot's turn tag) and renders the rendezvoused payload;
    # no fresh serve host is opened (single-attach).
    slug = "job1"
    _make_job(cli, slug)
    view_path = cli._msp_supervisor_files(slug)["view"]
    with open(view_path, "w") as f:
        json.dump({"t": time.time(), "msp_state": "blocked_approval",
                   "active_turn_id": "turn-1"}, f)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    payload = {"approvals": [{"approvalId": "ap-1", "title": "Run shell",
                              "choices": [{"choiceId": "deny",
                                           "decision": "denied"}]}],
               "userInputs": [], "rawApprovals": None,
               "rawUserInputs": None}
    canned = {"status": "listed", "ack": payload}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    rc = cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "approval ap-1: Run shell" in out
    assert FakeHost.instances == []  # no direct host opened
    entries = [json.loads(line) for line in
               open(cli._msp_supervisor_files(slug)["decide_queue"])]
    assert len(entries) == 1
    assert entries[0]["kind"] == "list"
    assert entries[0]["unredacted"] is False
    assert entries[0]["turn_id"] == "turn-1"


def test_cmd_approvals_supervisor_refused_raises(cli, fakes, monkeypatch):
    # A refused listing rendezvous surfaces as a clean `muse-job:
    # error:` line (main()'s handler), not a traceback.
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    canned = {"status": "refused",
              "detail": "listing queued for an older turn"}
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: canned)
    with pytest.raises(RuntimeError, match="older turn"):
        cli.cmd_approvals(_ns(slug=slug, json=False, show_secrets=False))


def test_list_via_supervisor_renders_real_drained_payload(
        cli, fakes, monkeypatch, capsys):
    # Non-vacuous: real enqueue + real drain on the fake serve host +
    # the real rendezvous read, rendered by the shared renderer. Change
    # the serve's pending set and the output follows.
    slug = "job1"
    _make_job(cli, slug)
    rid = cli._msp_enqueue_decision(slug, "list", {"unredacted": False},
                                    turn_id="t1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1", "t1")
    real_wait = cli._msp_wait_decision_result
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, r: real_wait(s, rid))
    rc = cli._msp_list_via_supervisor(
        _ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "approval ap-1: Run shell command" in out
    assert "(redacted; pass --show-secrets" in out
    # And again against a changed pending set: the output tracks the
    # wire, so this is not rendering a canned payload.
    fakes.list_pending_result = lambda params: {
        "approvals": [], "userInputs": []}
    rid2 = cli._msp_enqueue_decision(slug, "list", {"unredacted": False},
                                     turn_id="t1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1", "t1")
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, r: real_wait(s, rid2))
    rc = cli._msp_list_via_supervisor(
        _ns(slug=slug, json=False, show_secrets=False))
    assert rc == 0
    assert "no pending approvals or user-input prompts" in \
        capsys.readouterr().out


# -- status surface ----------------------------------------------------------

def test_request_ledger_surfaced_on_snapshot_status(cli, fakes):
    slug = "job1"
    _make_job(cli, slug)
    # The snapshot path (supervisor holds the session): seed a view
    # snapshot so _msp_status_from_snapshot has something to read.
    with open(cli._msp_supervisor_files(slug)["view"], "w") as f:
        json.dump({"t": time.time(), "msp_state": "blocked_approval",
                   "active_turn_id": "turn-1", "pending": "",
                   "last_activity_age_s": 1.0}, f)
    job = cli.load_job(slug)
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested"] == []
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   "Run shell command")
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested"][0]["id"] == "ap-1"
    # A decided request drops out of the advertised set.
    cli._msp_request_ledger_remove(slug, "approval", "ap-1")
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested"] == []


# -- issue #1437 (F-MSP-7): phantom-ledger fix --------------------------------

def _seed_view(cli, slug):
    with open(cli._msp_supervisor_files(slug)["view"], "w") as f:
        json.dump({"t": time.time(), "msp_state": "blocked_approval",
                   "active_turn_id": "turn-1", "pending": "",
                   "last_activity_age_s": 1.0}, f)


def test_requested_stale_when_supervisor_dead(cli, fakes, monkeypatch):
    # F-MSP-7's qualify-status half: ledger entries outliving a dead
    # supervisor must be marked stale, not advertised as actionable.
    slug = "job1"
    _make_job(cli, slug)
    _seed_view(cli, slug)
    job = cli.load_job(slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: False)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "Run shell command"})
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested_stale"] is True
    assert [e["id"] for e in st["requested"]] == ["ap-1"]


def test_requested_fresh_when_supervisor_alive(cli, fakes, monkeypatch):
    slug = "job1"
    _make_job(cli, slug)
    _seed_view(cli, slug)
    job = cli.load_job(slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "Run shell command"})
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested_stale"] is False


def test_requested_stale_false_on_empty_ledger(cli, fakes, monkeypatch):
    # No entries: nothing to qualify, supervisor aliveness is
    # irrelevant -- the key stays False, not None/missing.
    slug = "job1"
    _make_job(cli, slug)
    _seed_view(cli, slug)
    job = cli.load_job(slug)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: False)
    st = cli._msp_status_from_snapshot(slug, job)
    assert st["requested"] == []
    assert st["requested_stale"] is False


def test_status_render_marks_stale_requested(cli, fakes, monkeypatch,
                                             capsys):
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "Run shell command"})
    st = {"slug": slug,
          "requested": cli._msp_request_ledger_read(slug),
          "requested_stale": True}
    cli._msp_status_render_requested(st)
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "ap-1 [stale]" in out


def test_status_render_unmarked_when_fresh(cli, fakes, capsys):
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "Run shell command"})
    st = {"slug": slug,
          "requested": cli._msp_request_ledger_read(slug),
          "requested_stale": False}
    cli._msp_status_render_requested(st)
    out = capsys.readouterr().out
    assert "STALE" not in out
    assert "[stale]" not in out


def test_ledger_clear_never_raises_on_missing_file(cli, fakes):
    # _msp_ledger_update's never-raises contract extends to the clear.
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_clear(slug)
    assert cli._msp_request_ledger_read(slug) == []


def test_kill_clears_request_ledger(cli, fakes, monkeypatch):
    # F-MSP-7's kill-path half: the session is deleted on kill, so
    # every ledgered request is definitively dead.
    slug = "job1"
    _make_job(cli, slug)
    cli._msp_request_ledger_append(slug, "approval", "ap-1",
                                   {"title": "Run shell command"})
    cli._msp_request_ledger_append(slug, "user_input", "ui-1",
                                   {"questions": []})
    assert len(cli._msp_request_ledger_read(slug)) == 2
    monkeypatch.setattr(cli, "_msp_kill_supervisor", lambda s: False)
    monkeypatch.setattr(
        cli, "_msp_call",
        lambda slug_, job_, fn, pre_resume=True: (_ for _ in ()).throw(
            RuntimeError("no serve binary in tests")))
    rc = cli._msp_kill(_ns(slug=slug))
    assert rc == 0
    assert cli._msp_request_ledger_read(slug) == []
    assert cli.load_job(slug)["state"] == "killed"


# -- supervise_cmd wiring (QA B1) --------------------------------------------

def test_supervise_cmd_wires_request_handlers(cli, fakes, monkeypatch):
    # _msp_supervise_cmd must pass approval/request + userInput/request
    # handlers to the host constructor: without this, the whole
    # surface-immediately half of the slice dies silently while every
    # other test stays green.
    slug = "job1"
    _make_job(cli, slug)
    m_turn = sys.modules["msp_turn"]
    m_turn.start_turn = (
        lambda host, sid, prompt, **kw: ({"turnId": "turn-1"}, None))
    monkeypatch.setattr(cli, "trusted_job_paths",
                        lambda s, j: (os.path.join(cli.job_dir(s), "work"),
                                      "qa-repo", "job/" + s))
    captured = {}

    def fake_host_for(s, request_handlers=None):
        captured["handlers"] = dict(request_handlers or {})
        return FakeHost(["muse", "serve"], client_name="t")

    monkeypatch.setattr(cli, "_msp_host_for", fake_host_for)
    monkeypatch.setattr(cli, "_msp_supervise_loop",
                        lambda *a, **kw: None)
    cli._msp_supervise_cmd(_ns(slug=slug))
    handlers = captured["handlers"]
    assert set(handlers) == {"approval/request", "userInput/request"}
    # The wired handlers are the real factories: invoking one answers
    # the SS5.3.3 receipt and surfaces the request.
    receipt = handlers["approval/request"](
        {"params": copy.deepcopy(APPROVAL_WIRE)})
    assert receipt == {}
    assert "approval/requested" in _journal_text(cli, slug)
    receipt = handlers["userInput/request"](
        {"params": copy.deepcopy(PROMPT_WIRE)})
    assert receipt == {}
    assert "userInput/requested" in _journal_text(cli, slug)


# -- rendezvous: the real wait (QA B2) ----------------------------------------

def test_wait_decision_result_no_file_returns_none_promptly(cli, fakes):
    # The deadline must work: no result file -> None without hanging.
    slug = "job1"
    _make_job(cli, slug)
    t0 = time.time()
    assert cli._msp_wait_decision_result(slug, "dreq-0123456789ab",
                                         timeout_s=0) is None
    assert time.time() - t0 < 5


def test_wait_decision_result_mid_wait_write(cli, fakes):
    # A result written mid-wait is picked up: the poll loop is live,
    # not a single check.
    import threading
    slug = "job1"
    _make_job(cli, slug)
    rid = "dreq-abcdef012345"

    def writer():
        time.sleep(0.5)
        cli._msp_write_decision_result(slug, rid, "decided", "ok",
                                       ack={"approvalId": "ap-1"})

    th = threading.Thread(target=writer)
    th.start()
    try:
        result = cli._msp_wait_decision_result(slug, rid, timeout_s=10)
    finally:
        th.join()
    assert result["status"] == "decided"
    assert result["ack"]["approvalId"] == "ap-1"


def test_decide_via_supervisor_no_result_clean_error(cli, fakes,
                                                     monkeypatch):
    # Supervisor died between the liveness check and the drain: the
    # CLI raises a clean, actionable RuntimeError (the acceptance
    # criteria's "or a clean RuntimeError" branch).
    slug = "job1"
    _make_job(cli, slug)
    monkeypatch.setattr(cli, "_msp_wait_decision_result",
                        lambda s, rid: None)
    with pytest.raises(RuntimeError, match="no decision result after"):
        cli._msp_decide_via_supervisor(
            _ns(slug=slug), "decide",
            {"approval_id": "ap-1", "choice_id": "deny", "feedback": None})


# -- end-to-end: enqueue -> drain -> wait -> ack (QA B3) -----------------------

def test_decide_end_to_end_enqueue_drain_wait_ack(cli, fakes, monkeypatch,
                                                 capsys):
    # The full rendezvous contract in one test: the CLI enqueues (with
    # the snapshot's turn tag), the supervisor drains and executes on
    # its host, the CLI's real wait picks up the result file and prints
    # the ack.
    import threading
    slug = "job1"
    _make_job(cli, slug)
    view_path = cli._msp_supervisor_files(slug)["view"]
    with open(view_path, "w") as f:
        json.dump({"t": time.time(), "msp_state": "blocked_approval",
                   "active_turn_id": "turn-1", "pending": "",
                   "last_activity_age_s": 1.0}, f)
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    outcome = {}
    host = _drain_host(cli)

    def cli_thread():
        try:
            outcome["rc"] = cli._msp_decide_via_supervisor(
                _ns(slug=slug), "decide",
                {"approval_id": "ap-1", "choice_id": "deny",
                 "feedback": None})
        except Exception as e:  # pragma: no cover - test would fail
            outcome["error"] = e

    th = threading.Thread(target=cli_thread)
    th.start()
    try:
        # Let the CLI thread enqueue, then drain as the supervisor
        # would. The peek takes the shared lock so it never reads a
        # torn entry.
        deadline = time.time() + 10
        drained = False
        while time.time() < deadline and not drained:
            qpath = cli._msp_supervisor_files(slug)["decide_queue"]
            try:
                with open(qpath) as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        lines = f.readlines()
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except OSError:
                lines = []
            if lines:
                # The queue entry carried the snapshot's turn tag
                # (anti-cross-turn).
                assert json.loads(lines[0])["turn_id"] == "turn-1"
                cli._msp_drain_decision_queue(slug, host, "sess-1",
                                              "turn-1")
                drained = True
            else:
                time.sleep(0.2)
        assert drained, "CLI thread never enqueued"
    finally:
        th.join(timeout=30)
    assert not th.is_alive(), "rendezvous hung past the drain"
    assert outcome.get("rc") == 0, outcome.get("error")
    body = json.loads(capsys.readouterr().out)
    assert body["approvalId"] == "ap-1"
    assert body["choiceId"] == "deny"


def test_answer_queue_unknown_prompt_errors(cli, fakes):
    # Symmetric to the decide-kind vanish: an answer for a prompt that
    # is no longer pending is an "error" result, never a blind wire call.
    slug = "job1"
    _make_job(cli, slug)
    answers = [{"questionId": "q-trust", "selectedLabel": "No"},
               {"questionId": "q-free", "freeText": "nothing"}]
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-gone", "answers": answers, "trust": False},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    assert "userInput/answer" not in [m for m, _ in fakes.host_calls()]
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "error"
    assert "ui-gone" in result["detail"]


# -- status rendering + ledger lifecycle (Product B1/B2/B3) -------------------

def _seed_snapshot(cli, slug):
    view_path = cli._msp_supervisor_files(slug)["view"]
    with open(view_path, "w") as f:
        json.dump({"t": time.time(), "msp_state": "blocked_approval",
                   "active_turn_id": "turn-1", "pending": "",
                   "last_activity_age_s": 1.0}, f)


def test_status_renders_requested_with_runnable_commands(cli, fakes,
                                                         capsys,
                                                         monkeypatch):
    # The held-path operator story: `status` shows the request with the
    # full decide/answer command, mirroring cmd_approvals' direct-path
    # rendering -- choiceIds, questions, options, and the trust tag the
    # classification depends on.
    slug = "job1"
    _make_job(cli, slug)
    _seed_snapshot(cli, slug)
    # The held path means a live supervisor: without this the
    # aliveness check reads dead and the F-MSP-7 staleness qualifier
    # (issue #1437) applies instead of the fresh render below.
    monkeypatch.setattr(cli, "_msp_supervisor_alive", lambda s: True)
    msp_approval = cli._msp_approval()
    cli._msp_on_approval_requested(
        slug, msp_approval.parse_approval(copy.deepcopy(APPROVAL_WIRE)))
    cli._msp_on_user_input_requested(
        slug, msp_approval.parse_user_input(copy.deepcopy(PROMPT_WIRE)))
    job = cli.load_job(slug)
    st = cli._msp_status_from_snapshot(slug, job)
    assert len(st["requested"]) == 2
    cli._msp_status_render_requested(st)
    out = capsys.readouterr().out
    assert "approval ap-1: Run shell command" in out
    assert ("muse-job decide job1 --approval-id ap-1 "
            "--choice-id <id>") in out
    assert "allow-once (approved)" in out and "deny (denied)" in out
    # Issue #1773: the default surface shows no machine verdict ...
    assert "trust prompt" not in out
    assert "Do you trust this workspace?" in out
    assert "Yes, trust it, No" in out
    # ... and --show-heuristic renders the explicitly non-authoritative hint.
    cli._msp_status_render_requested(st, show_heuristic=True)
    out = capsys.readouterr().out
    assert ("user-input ui-1 "
            "[NOT a classification: heuristic hint -- verify yourself]") in out
    assert ("muse-job answer job1 --user-input-id ui-1 "
            "--answers") in out
    assert "--classified-not-trust-prompt|--trust-policy-opt-in" in out
    # Agent-influenced strings are terminal-sanitized at render.
    assert "rm -rf /tmp/x" not in out


def test_stale_turn_refusal_drops_ledger(cli, fakes):
    # A stale-turn refusal is terminal: the request can no longer be
    # pending server-side, so `status` must stop advertising it.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    cli._msp_on_approval_requested(
        slug, msp_approval.parse_approval(copy.deepcopy(APPROVAL_WIRE)))
    assert len(cli._msp_request_ledger_read(slug)) == 1
    rid = cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-1", "choice_id": "deny", "feedback": None},
        turn_id="turn-9")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    assert cli._msp_request_ledger_read(slug) == []


def test_refuse_only_refusal_drops_ledger(cli, fakes):
    # Same terminal reasoning for the supervisor-exit drain.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    cli._msp_on_approval_requested(
        slug, msp_approval.parse_approval(copy.deepcopy(APPROVAL_WIRE)))
    cli._msp_enqueue_decision(
        slug, "decide",
        {"approval_id": "ap-1", "choice_id": "deny", "feedback": None},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, None, None, "turn-1",
                                  refuse_only=True)
    assert cli._msp_request_ledger_read(slug) == []


def test_missing_trust_refusal_keeps_ledger(cli, fakes):
    # A policy refusal is NOT terminal: the request is still genuinely
    # pending and the operator can re-issue the command with a
    # classification -- it stays advertised.
    slug = "job1"
    _make_job(cli, slug)
    msp_approval = cli._msp_approval()
    cli._msp_on_user_input_requested(
        slug, msp_approval.parse_user_input(copy.deepcopy(PROMPT_WIRE)))
    rid = cli._msp_enqueue_decision(
        slug, "answer",
        {"user_input_id": "ui-1",
         "answers": [{"questionId": "q-free", "freeText": "x"}]},
        turn_id="turn-1")
    cli._msp_drain_decision_queue(slug, _drain_host(cli), "sess-1",
                                  "turn-1")
    result = json.loads(open(cli._msp_decision_result_path(slug, rid)).read())
    assert result["status"] == "refused"
    entries = cli._msp_request_ledger_read(slug)
    assert len(entries) == 1 and entries[0]["id"] == "ui-1"


def test_status_render_survives_null_ledger_fields(cli, fakes, capsys):
    # Engineering round-2: a null in a list-valued ledger field (disk
    # corruption, hand-edit) must degrade, never kill `muse-job
    # status` with a traceback (issue #23 H3's persistent-kill pattern).
    slug = "job1"
    _make_job(cli, slug)
    path = cli._msp_supervisor_files(slug)["requests"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump([
            {"ts": time.time(), "kind": "approval", "id": "ap-1",
             "detail": {"approvalId": "ap-1", "title": "t",
                        "choices": None}},
            {"ts": time.time(), "kind": "user_input", "id": "ui-1",
             "detail": {"userInputId": "ui-1",
                        "looksLikeTrustPrompt": False,
                        "questions": None}},
            {"ts": time.time(), "kind": "user_input", "id": "ui-2",
             "detail": {"userInputId": "ui-2",
                        "looksLikeTrustPrompt": False,
                        "questions": [{"questionId": "q1", "mode": "single",
                                       "prompt": "p", "options": None}]}},
            "not-a-dict",
            {"ts": time.time(), "kind": "approval", "id": "ap-2",
             "detail": None},
        ], f)
    st = {"slug": slug, "requested": cli._msp_request_ledger_read(slug)}
    cli._msp_status_render_requested(st)  # must not raise
    out = capsys.readouterr().out
    assert "approval ap-1: t" in out
    assert "user-input ui-1" in out
    assert "user-input ui-2" in out

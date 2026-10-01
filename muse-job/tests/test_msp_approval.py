"""Hermetic tests for muse-job/bin/msp_approval.py (issue #225).

No `muse` binary is needed: every test drives a fake `muse serve`
fixture that speaks NDJSON JSON-RPC 2.0 over stdio and implements the
approval/user-input plane (approval/listPending, approval/decide,
userInput/answer) with the wire shapes the module documents -- UUIDv7
command ids, the requirementId race guard, per-question mode
validation, and the SS5.3.3 presentation receipt for server-initiated
approval/request and userInput/request.

Fixture-invented behavior (documented in the module, NOT wire-verified):
the pending-approval record (toolName "exec", shell subject, two
choices allow-once/deny with acceptsFeedback on the deny); the pending
user-input prompt (one single trust question, one multiple question,
one freeText question with empty options); the -32053 stale-
requirement refusal reason "stale_requirement"; the -32052 bad-choice
refusal; the -32057 userInputAnswerInvalid refusal; the "test/emit"
hook that fires server-initiated requests on demand so the routing
helpers can be tested end to end.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import stat
import sys

import pytest

BIN_PATH = os.path.join(os.path.dirname(__file__), "..", "bin",
                        "msp_approval.py")


def load_mod(name="msp_approval_under_test"):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, BIN_PATH)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


mspa = load_mod()

# ---------------------------------------------------------------------------
# Fake `muse serve` with an approval/user-input plane.
# ---------------------------------------------------------------------------
FAKE_APPROVAL_SERVE = (
    "#!/usr/bin/env python3\n"
    + r'''
import argparse, copy, json, re, sys, uuid

ap = argparse.ArgumentParser()
ap.add_argument("--record", default=None)
args = ap.parse_args()

rec = open(args.record, "a") if args.record else None
initialized = False
req_seq = [1000]

approvals = {
    "ap-1": {
        "approvalId": "ap-1",
        "sessionId": "sess-a",
        "itemId": "item-1",
        "turnId": "turn-1",
        "taskId": "task-1",
        "toolCallId": "tc-1",
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
        "viewCursor": "vc-1",
        "judgeEscalated": False,
        "protectedWrite": False,
        "sourceRange": {},
    },
}
prompts = {
    "ui-1": {
        "userInputId": "ui-1",
        "sessionId": "sess-a",
        "itemId": "item-2",
        "turnId": "turn-1",
        "toolCallId": "tc-2",
        "toolName": "ask",
        "viewCursor": "vc-2",
        "questions": [
            {"id": "q-trust", "header": "Workspace trust",
             "question": "Do you trust this workspace?",
             "options": [{"label": "Yes, trust it"}, {"label": "No"}],
             "selection": {"mode": "single"}},
            {"id": "q-multi", "header": "",
             "question": "Which apply?",
             "options": [{"label": "A"}, {"label": "B"},
                         {"label": "C"}],
             "selection": {"mode": "multiple", "minSelections": 1,
                           "maxSelections": 2}},
            {"id": "q-free", "header": "Notes",
             "question": "Anything to add?",
             "options": [],
             "selection": {"mode": "single"}},
        ],
    },
}

def record(msg):
    if rec:
        rec.write(json.dumps(msg) + "\n")
        rec.flush()

def send(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()

def err(rid, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    send({"jsonrpc": "2.0", "id": rid, "error": e})

UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

def check_command_id(rid, params):
    cid = params.get("commandId")
    if not isinstance(cid, str) or not UUID7_RE.match(cid):
        err(rid, -32602, "invalid commandId: expected UUIDv7",
            {"kind": "invalidParams"})
        return False
    return True

def check_drift_list(rid, params):
    sid = params.get("sessionId")
    if not (isinstance(sid, str) and sid.startswith("drift:")):
        return False
    case = sid[len("drift:"):]
    if case == "notdict":
        send({"jsonrpc": "2.0", "id": rid, "result": "not-a-dict"})
    elif case == "no-approvals":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"userInputs": []}})
    elif case == "empty-choices":
        bad = copy.deepcopy(approvals["ap-1"])
        bad["availableChoices"] = []
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"approvals": [bad], "userInputs": []}})
    elif case == "no-userinputs":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"approvals": []}})
    else:
        return False
    return True

def validate_answers(prompt, answers):
    """Mirror of the wire's SS5.10.2 answer validation."""
    by_id = {q["id"]: q for q in prompt["questions"]}
    seen = set()
    for a in answers:
        qid = a.get("questionId")
        q = by_id.get(qid)
        if q is None or qid in seen:
            return False
        seen.add(qid)
        kinds = [k for k in ("selectedLabel", "selectedLabels",
                             "freeText") if k in a and a[k] is not None]
        if len(kinds) != 1:
            return False
        kind = kinds[0]
        labels = [o["label"] for o in q["options"]]
        mode = q["selection"]["mode"] if labels else "freeText"
        if kind == "selectedLabel":
            if mode != "single" or a[kind] not in labels:
                return False
        elif kind == "selectedLabels":
            sel = q["selection"]
            vs = a[kind]
            if (mode != "multiple" or not isinstance(vs, list)
                    or any(v not in labels for v in vs)
                    or not sel.get("minSelections", 0)
                    <= len(vs)
                    <= sel.get("maxSelections", len(labels))):
                return False
        else:
            if mode != "freeText" or len(a[kind]) > 500:
                return False
        note = a.get("note")
        if note is not None and (not isinstance(note, str)
                                 or len(note) > 500):
            return False
    return seen == set(by_id)

def emit_request(kind, ident, corrupt):
    req_seq[0] += 1
    rid = req_seq[0]
    if kind == "approval":
        params = copy.deepcopy(approvals[ident])
        method = "approval/request"
    else:
        params = copy.deepcopy(prompts[ident])
        method = "userInput/request"
    if corrupt == "no-id":
        params.pop("approvalId", None)
        params.pop("userInputId", None)
    send({"jsonrpc": "2.0", "id": rid, "method": method,
          "params": params})
    # Read the client's answer (the presentation receipt or an error)
    # before answering test/emit: the client answers promptly on its
    # reader thread, so this cannot deadlock.
    line = sys.stdin.readline()
    record({"testEmitResponse": json.loads(line)})
    return {"emitted": method, "requestId": rid}

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if msg.get("method") == "test/emit":
        # Test-only hook: fire a server-initiated request on demand.
        # Handled before the initialized gate so routing can be tested
        # without a session.
        params = msg.get("params") or {}
        record(msg)
        result = emit_request(params.get("kind"),
                              params.get("id"),
                              params.get("corrupt"))
        send({"jsonrpc": "2.0", "id": msg.get("id"),
              "result": result})
        continue
    record(msg)
    method, rid = msg.get("method"), msg.get("id")
    params = msg.get("params") or {}
    if method is None:
        continue
    if method == "initialized":
        initialized = True
        continue
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"protocolVersion": "1",
                         "serverInfo": {"name": "fake-muse-serve",
                                        "version": "0"}}})
        continue
    if not initialized:
        err(rid, -32099, "Not initialized")
        continue
    if method == "approval/listPending":
        if check_drift_list(rid, params):
            continue
        sid = params.get("sessionId")
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "approvals": [a for a in approvals.values()
                          if a["sessionId"] == sid],
            "userInputs": [p for p in prompts.values()
                           if p["sessionId"] == sid]}})
    elif method == "approval/decide":
        if not check_command_id(rid, params):
            continue
        aid = params.get("approvalId")
        ap = approvals.get(aid)
        if ap is None:
            err(rid, -32000, "unknown approval")
            continue
        if params.get("requirementId") != ap["currentRequirementId"]:
            err(rid, -32053, "stale requirement",
                {"kind": "commandRejected",
                 "reason": "stale_requirement"})
            continue
        ids = [c["choiceId"] for c in ap["availableChoices"]]
        if params.get("choiceId") not in ids:
            err(rid, -32052, "unknown choice",
                {"kind": "commandRejected",
                 "reason": "unknown_choice"})
            continue
        fb = params.get("feedback")
        if fb is not None:
            ch = next(c for c in ap["availableChoices"]
                      if c["choiceId"] == params["choiceId"])
            if not ch["acceptsFeedback"]:
                err(rid, -32052, "choice does not accept feedback",
                    {"kind": "commandRejected",
                     "reason": "feedback_not_accepted"})
                continue
        del approvals[aid]
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"approvalId": aid,
                         "commandId": params["commandId"],
                         "status": "accepted", "terminal": True}})
    elif method == "userInput/answer":
        if not check_command_id(rid, params):
            continue
        uid = params.get("userInputId")
        pr = prompts.get(uid)
        if pr is None:
            err(rid, -32000, "unknown user input")
            continue
        answers = params.get("answers")
        if not isinstance(answers, list) or not validate_answers(
                pr, answers):
            err(rid, -32057, "answer does not match the prompt",
                {"kind": "commandRejected",
                 "reason": "userInputAnswerInvalid"})
            continue
        del prompts[uid]
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"userInputId": uid,
                         "commandId": params["commandId"],
                         "status": "accepted"}})
    else:
        err(rid, -32601, "unknown method")
''')


def _write_approval_serve(tmp_path):
    """Write the approval-plane fixture; return (argv, record)."""
    path = tmp_path / "fake_approval_serve.py"
    path.write_text(FAKE_APPROVAL_SERVE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    record = tmp_path / "record.jsonl"
    argv = [sys.executable, str(path), "--record", str(record)]
    return argv, record


@pytest.fixture()
def approval_serve(tmp_path):
    """Write the approval-plane fixture; return (argv, record)."""
    return _write_approval_serve(tmp_path)


def read_record(record):
    if not os.path.exists(str(record)):
        return []
    return [json.loads(l) for l in open(str(record)) if l.strip()]


def make_host(argv, **kw):
    kw.setdefault("client_name", "test_client")
    kw.setdefault("request_timeout", 5.0)
    return mspa.MSPHost(argv, **kw)


def method_calls(record, method):
    return [m for m in read_record(record) if m.get("method") == method]


UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def get_prompt(host):
    prompts = mspa.list_pending_user_inputs(host, "sess-a")
    assert len(prompts) == 1
    return prompts[0]


GOOD_ANSWERS = [
    {"questionId": "q-trust", "selectedLabel": "Yes, trust it"},
    {"questionId": "q-multi", "selectedLabels": ["A", "C"]},
    {"questionId": "q-free", "freeText": "looks fine"},
]


# -- approval/listPending ----------------------------------------------------

def test_list_pending_parses_approvals(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
    assert len(approvals) == 1
    ap = approvals[0]
    assert ap.approval_id == "ap-1"
    assert ap.available_choices == ["allow-once", "deny"]
    # The race guard is the full requirement ref, kept verbatim.
    assert ap.requirement_id == {"approvalId": "ap-1", "sourceIndex": 0}
    assert ap.title == "Run shell command"
    assert "rm -rf /tmp/x" in (ap.detail or "")
    assert ap.session_id == "sess-a"
    assert ap.raw["toolName"] == "exec"


def test_list_pending_empty_for_unknown_session(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        assert mspa.list_pending_approvals(host, "sess-nobody") == []
        assert mspa.list_pending_user_inputs(host, "sess-nobody") == []


def test_list_pending_drift_fails_loud(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        with pytest.raises(mspa.MSPApprovalError):
            mspa.list_pending_approvals(host, "drift:notdict")
        with pytest.raises(mspa.MSPApprovalError):
            mspa.list_pending_approvals(host, "drift:no-approvals")
        with pytest.raises(mspa.MSPApprovalError):
            mspa.list_pending_approvals(host, "drift:empty-choices")
        with pytest.raises(mspa.MSPApprovalError):
            mspa.list_pending_user_inputs(host, "drift:no-userinputs")


def test_list_pending_validates_session_id(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        with pytest.raises(ValueError):
            mspa.list_pending_approvals(host, "")
        with pytest.raises(ValueError):
            mspa.list_pending_user_inputs(host, None)


# -- approval/decide ---------------------------------------------------------

def test_decide_sends_requirement_guard_and_uuid7(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
        result = mspa.decide_approval(host, "sess-a", approvals[0],
                                      "allow-once")
    assert result["approvalId"] == "ap-1"
    assert result["status"] == "accepted"
    calls = method_calls(record, "approval/decide")
    assert len(calls) == 1
    params = calls[0]["params"]
    assert params["approvalId"] == "ap-1"
    assert params["choiceId"] == "allow-once"
    assert params["sessionId"] == "sess-a"
    # The requirementId race guard travels verbatim.
    assert params["requirementId"] == {"approvalId": "ap-1",
                                       "sourceIndex": 0}
    assert UUID7_RE.match(params["commandId"])
    assert "feedback" not in params


def test_decide_rejects_unknown_choice_client_side(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
        with pytest.raises(ValueError, match="not one of"):
            mspa.decide_approval(host, "sess-a", approvals[0], "nuke-it")
    # Nothing went on the wire: the refusal happened client-side.
    assert method_calls(record, "approval/decide") == []


def test_decide_stale_requirement_surfaces_server_error(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
        ap = approvals[0]
        # Simulate a stage change racing the decision: the guard no
        # longer matches what the server holds.
        ap.requirement_id = {"approvalId": "ap-1", "sourceIndex": 99}
        with pytest.raises(mspa.ServerError) as ei:
            mspa.decide_approval(host, "sess-a", ap, "allow-once")
    assert ei.value.code == -32053


def test_decide_feedback_only_where_accepted(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
        ap = approvals[0]
        # allow-once does not accept feedback: refused client-side,
        # before the wire.
        with pytest.raises(ValueError, match="does not accept feedback"):
            mspa.decide_approval(host, "sess-a", ap, "allow-once",
                                  feedback="because reasons")
        assert method_calls(record, "approval/decide") == []
        # deny accepts feedback: travels with the decision.
        result = mspa.decide_approval(host, "sess-a", ap, "deny",
                                      feedback="not today")
    assert result["status"] == "accepted"
    params = method_calls(record, "approval/decide")[0]["params"]
    assert params["feedback"] == "not today"


def test_decide_validates_types(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        approvals = mspa.list_pending_approvals(host, "sess-a")
        ap = approvals[0]
        with pytest.raises(ValueError):
            mspa.decide_approval(host, "sess-a", "not-an-approval",
                                  "allow-once")
        with pytest.raises(ValueError):
            mspa.decide_approval(host, "sess-a", ap, "")
        with pytest.raises(ValueError):
            mspa.decide_approval(host, "sess-a", ap, "deny",
                                  feedback=123)


# -- userInput/answer: parsing ------------------------------------------------

def test_user_input_parsing_modes(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
    assert prompt.user_input_id == "ui-1"
    by_id = {q.question_id: q for q in prompt.questions}
    assert by_id["q-trust"].mode == "single"
    assert by_id["q-trust"].options == ["Yes, trust it", "No"]
    assert by_id["q-multi"].mode == "multiple"
    assert by_id["q-multi"].min_selections == 1
    assert by_id["q-multi"].max_selections == 2
    # Empty options -> freeText mode (the resolved ambiguity).
    assert by_id["q-free"].mode == "freeText"
    assert by_id["q-free"].options == []
    assert "Workspace trust" in by_id["q-trust"].prompt_text
    assert "Do you trust this workspace?" in by_id["q-trust"].prompt_text


def test_looks_like_trust_prompt(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
    assert mspa.looks_like_trust_prompt(prompt) is True
    other = mspa.UserInputPrompt("ui-x", [
        mspa.Question("q1", "single", "Pick a color", ["red", "blue"])])
    assert mspa.looks_like_trust_prompt(other) is False


# -- userInput/answer: the call ------------------------------------------------

def test_answer_all_questions_wire_shape(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        result = mspa.answer_user_input(host, "sess-a", prompt,
                                        GOOD_ANSWERS)
    assert result["userInputId"] == "ui-1"
    assert result["status"] == "accepted"
    calls = method_calls(record, "userInput/answer")
    assert len(calls) == 1
    params = calls[0]["params"]
    assert params["userInputId"] == "ui-1"
    assert params["sessionId"] == "sess-a"
    assert UUID7_RE.match(params["commandId"])
    assert params["answers"] == GOOD_ANSWERS


def test_answer_bad_label_rejected_client_side(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        bad = [dict(GOOD_ANSWERS[0], selectedLabel="Maybe")] + \
            GOOD_ANSWERS[1:]
        with pytest.raises(ValueError, match="not one of the offered"):
            mspa.answer_user_input(host, "sess-a", prompt, bad)
    assert method_calls(record, "userInput/answer") == []


def test_answer_overlong_freetext_rejected(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        bad = GOOD_ANSWERS[:2] + [
            {"questionId": "q-free", "freeText": "x" * 501}]
        with pytest.raises(ValueError, match="500"):
            mspa.answer_user_input(host, "sess-a", prompt, bad)
    assert method_calls(record, "userInput/answer") == []


def test_answer_mode_mismatch_rejected(approval_serve):
    argv, record = approval_serve
    cases = [
        # selectedLabels on a single-mode question.
        [dict(GOOD_ANSWERS[0], selectedLabels=["Yes, trust it"])] +
        GOOD_ANSWERS[1:],
        # selectedLabel on a multiple-mode question.
        [GOOD_ANSWERS[0],
         {"questionId": "q-multi", "selectedLabel": "A"},
         GOOD_ANSWERS[2]],
        # freeText on a single-mode question.
        [{"questionId": "q-trust", "freeText": "sure"}] +
        GOOD_ANSWERS[1:],
        # selectedLabel on a freeText question.
        GOOD_ANSWERS[:2] +
        [{"questionId": "q-free", "selectedLabel": "x"}],
        # Two answer kinds at once.
        [dict(GOOD_ANSWERS[0], freeText="also")] + GOOD_ANSWERS[1:],
        # No answer kind at all.
        [{"questionId": "q-trust"}] + GOOD_ANSWERS[1:],
    ]
    with make_host(argv) as host:
        prompt = get_prompt(host)
        for bad in cases:
            with pytest.raises(ValueError):
                mspa.answer_user_input(host, "sess-a", prompt, bad)
    assert method_calls(record, "userInput/answer") == []


def test_answer_selection_bounds_enforced(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        # min 1: empty selection refused.
        bad_min = [GOOD_ANSWERS[0],
                   {"questionId": "q-multi", "selectedLabels": []},
                   GOOD_ANSWERS[2]]
        with pytest.raises(ValueError, match="outside the allowed"):
            mspa.answer_user_input(host, "sess-a", prompt, bad_min)
        # max 2: three labels refused; unknown label refused.
        bad_max = [GOOD_ANSWERS[0],
                   {"questionId": "q-multi",
                    "selectedLabels": ["A", "B", "C"]},
                   GOOD_ANSWERS[2]]
        with pytest.raises(ValueError, match="outside the allowed"):
            mspa.answer_user_input(host, "sess-a", prompt, bad_max)
        bad_label = [GOOD_ANSWERS[0],
                     {"questionId": "q-multi",
                      "selectedLabels": ["A", "Z"]},
                     GOOD_ANSWERS[2]]
        with pytest.raises(ValueError, match="not among the offered"):
            mspa.answer_user_input(host, "sess-a", prompt, bad_label)
    assert method_calls(record, "userInput/answer") == []


def test_answer_requires_every_question_exactly_once(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        with pytest.raises(ValueError, match="unanswered"):
            mspa.answer_user_input(host, "sess-a", prompt,
                                   GOOD_ANSWERS[:2])
        with pytest.raises(ValueError, match="duplicate"):
            mspa.answer_user_input(host, "sess-a", prompt,
                                   GOOD_ANSWERS + [GOOD_ANSWERS[0]])
        with pytest.raises(ValueError, match="unknown questionId"):
            mspa.answer_user_input(host, "sess-a", prompt,
                                   GOOD_ANSWERS[:2] +
                                   [{"questionId": "nope",
                                     "freeText": "x"}])
        with pytest.raises(ValueError, match="unknown keys"):
            mspa.answer_user_input(host, "sess-a", prompt,
                                   [dict(GOOD_ANSWERS[0],
                                         bogus="x")] + GOOD_ANSWERS[1:])
    assert method_calls(record, "userInput/answer") == []


def test_answer_note_bound_and_session_guard(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        noted = [dict(GOOD_ANSWERS[0], note="operator was here")] + \
            GOOD_ANSWERS[1:]
        result = mspa.answer_user_input(host, "sess-a", prompt, noted)
        assert result["status"] == "accepted"
    calls = method_calls(record, "userInput/answer")
    assert calls[0]["params"]["answers"][0]["note"] == "operator was here"


def test_answer_note_overlong_rejected(approval_serve):
    argv, _ = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        bad = [dict(GOOD_ANSWERS[0], note="n" * 501)] + GOOD_ANSWERS[1:]
        with pytest.raises(ValueError, match="500"):
            mspa.answer_user_input(host, "sess-a", prompt, bad)


def test_answer_cross_session_refused(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        with pytest.raises(ValueError, match="across sessions"):
            mspa.answer_user_input(host, "sess-other", prompt,
                                   GOOD_ANSWERS)
    assert method_calls(record, "userInput/answer") == []


# -- trust policy --------------------------------------------------------------

def test_trust_policy_default_deny(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        # No policy at all: fail closed.
        with pytest.raises(mspa.MSPApprovalError, match="TrustPolicy"):
            mspa.answer_trust_prompt(host, "sess-a", prompt,
                                     GOOD_ANSWERS, policy=None)
        # Default policy: fail closed.
        with pytest.raises(mspa.MSPApprovalError,
                           match="never auto-answer"):
            mspa.answer_trust_prompt(host, "sess-a", prompt,
                                     GOOD_ANSWERS,
                                     policy=mspa.TrustPolicy())
        # A non-policy object is not an opt-in either.
        with pytest.raises(mspa.MSPApprovalError, match="TrustPolicy"):
            mspa.answer_trust_prompt(host, "sess-a", prompt,
                                     GOOD_ANSWERS,
                                     policy={"auto_answer_trust": True})
    assert method_calls(record, "userInput/answer") == []


def test_trust_policy_opt_in_answers(approval_serve):
    argv, record = approval_serve
    with make_host(argv) as host:
        prompt = get_prompt(host)
        policy = mspa.TrustPolicy(auto_answer_trust=True)
        result = mspa.answer_trust_prompt(host, "sess-a", prompt,
                                          GOOD_ANSWERS, policy=policy)
    assert result["status"] == "accepted"
    assert len(method_calls(record, "userInput/answer")) == 1


# -- server->client request routing --------------------------------------------

def test_approval_request_routing_receipt(approval_serve):
    argv, record = approval_serve
    seen = []
    with make_host(argv) as host:
        host.set_request_handler(
            "approval/request",
            mspa.handle_approval_request(seen.append))
        result = host.call("test/emit",
                           {"kind": "approval", "id": "ap-1"})
    assert result["emitted"] == "approval/request"
    assert len(seen) == 1
    ap = seen[0]
    assert isinstance(ap, mspa.Approval)
    assert ap.approval_id == "ap-1"
    assert ap.available_choices == ["allow-once", "deny"]
    # The SS5.3.3 presentation receipt: an empty object.
    responses = [m for m in read_record(record)
                 if "testEmitResponse" in m]
    assert len(responses) == 1
    assert responses[0]["testEmitResponse"]["result"] == {}


def test_user_input_request_routing_receipt(approval_serve):
    argv, record = approval_serve
    seen = []
    with make_host(argv) as host:
        host.set_request_handler(
            "userInput/request",
            mspa.handle_user_input_request(seen.append))
        result = host.call("test/emit",
                           {"kind": "userInput", "id": "ui-1"})
    assert result["emitted"] == "userInput/request"
    assert len(seen) == 1
    prompt = seen[0]
    assert isinstance(prompt, mspa.UserInputPrompt)
    assert prompt.user_input_id == "ui-1"
    assert [q.question_id for q in prompt.questions] == \
        ["q-trust", "q-multi", "q-free"]
    responses = [m for m in read_record(record)
                 if "testEmitResponse" in m]
    assert responses[0]["testEmitResponse"]["result"] == {}


def test_request_routing_drift_answers_error(approval_serve):
    argv, record = approval_serve
    seen = []
    with make_host(argv) as host:
        host.set_request_handler(
            "approval/request",
            mspa.handle_approval_request(seen.append))
        host.call("test/emit", {"kind": "approval", "id": "ap-1",
                                "corrupt": "no-id"})
    # Drifted params: the callback never ran; the host answered a
    # JSON-RPC error (the prompt stays pending, re-issued on next
    # subscribe per SS5.3.3).
    assert seen == []
    responses = [m for m in read_record(record)
                 if "testEmitResponse" in m]
    assert "error" in responses[0]["testEmitResponse"]


def test_request_routing_callback_error_answers_error(approval_serve):
    argv, record = approval_serve
    def boom(_ap):
        raise RuntimeError("operator surface exploded")
    with make_host(argv) as host:
        host.set_request_handler(
            "approval/request", mspa.handle_approval_request(boom))
        host.call("test/emit", {"kind": "approval", "id": "ap-1"})
    responses = [m for m in read_record(record)
                 if "testEmitResponse" in m]
    resp = responses[0]["testEmitResponse"]
    assert "error" in resp
    assert "operator surface exploded" in resp["error"]["message"]


def test_handler_factories_validate_callback(approval_serve):
    with pytest.raises(ValueError):
        mspa.handle_approval_request(None)
    with pytest.raises(ValueError):
        mspa.handle_user_input_request("nope")


# -- smoke CLI redaction ---------------------------------------------------------

def test_cli_list_pending_redacts_by_default(approval_serve, capsys):
    argv, _ = approval_serve
    rc = mspa.main(["list-pending", "--session-id", "sess-a", "--",
                    *argv])
    assert rc == 0
    out = capsys.readouterr()
    body = json.loads(out.out)
    assert body["approvals"][0]["approvalId"] == "ap-1"
    # rawArgs carry the real command: withheld without --show-secrets.
    assert "rm -rf /tmp/x" not in out.out
    assert "redacted" in out.err.lower()


def test_cli_list_pending_show_secrets(approval_serve, capsys):
    argv, _ = approval_serve
    rc = mspa.main(["--show-secrets", "list-pending",
                    "--session-id", "sess-a", "--", *argv])
    assert rc == 0
    out = capsys.readouterr()
    body = json.loads(out.out)
    assert body["approvals"][0]["rawArgs"] == '{"cmd": "rm -rf /tmp/x"}'
    assert "NOT" in out.err and "redacted" in out.err.lower()


def test_cli_answer_redacts_answers(approval_serve, capsys):
    argv, _ = approval_serve
    answers = json.dumps(GOOD_ANSWERS)
    # ui-1 looks like a trust prompt, so the CLI routes through the
    # policy gate: without --trust-policy-opt-in it fails closed.
    with pytest.raises(mspa.MSPApprovalError, match="never auto-answer"):
        mspa.main(["answer", "--session-id", "sess-a",
                   "--user-input-id", "ui-1", "--answers", answers,
                   "--", *argv])
    rc = mspa.main(["answer", "--session-id", "sess-a",
                    "--user-input-id", "ui-1", "--answers", answers,
                    "--trust-policy-opt-in", "--", *argv])
    assert rc == 0
    out = capsys.readouterr()
    body = json.loads(out.out)
    assert body["result"]["status"] == "accepted"
    assert "Yes, trust it" not in out.out
    assert body["answers"].startswith("<redacted")

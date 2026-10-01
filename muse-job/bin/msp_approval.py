#!/usr/bin/env python3
"""msp_approval.py -- MSP approval and user-input plane client for muse-job v2 (#225).

Prompt/approval-plane methods on top of bin/msp_host.py's transport
(issue #221), the fourth slice of the #228 muse-job v2 migration (drive
jobs over MSP instead of scraping a tmux TUI):

- ``approval/listPending`` -- pull the pending tool approvals (and user
  prompts) for a session: the log-fold read dual of the re-issued
  server->client requests. No lease, works on loaded and unloaded
  sessions, never subscribes.
- ``approval/decide``     -- decide one approval with the requirementId
  race guard (a standard SS3 command: UUIDv7 commandId, durable intake
  before ack, value-identical replay).
- ``userInput/answer``    -- answer every question of an open user-input
  prompt (workspace trust, etc.) with explicit structured answers --
  the protocol replacement for the #211 trust-prompt auto-answer hack
  (sending ``1``+Enter into a tmux pane).
- ``approval/request`` / ``userInput/request`` -- server->client request
  routing helpers that convert the wire params into ``Approval`` /
  ``UserInputPrompt`` and invoke a caller-supplied callback, answering
  with the SS5.3.3 presentation receipt (an empty object).

This kills the rest of the #211 bug class on the prompt path: no
terminal keystrokes, no "which number is the right answer" guessing,
no blind Enter. Answers travel as structured JSON validated client-side
before they touch the wire.

Trust-policy decision (carried over from #211 -- RECORDED HERE)
--------------------------------------------------------------
#211 flagged auto-answering trust prompts (workspace trust, etc.) as
needing review: a trust prompt is the model's way of asking the
OPERATOR to vouch for something, and silently answering "yes" on the
operator's behalf is a standing security decision, not a UI detail.
Answering over MSP is cleaner than keystroke injection, but the policy
question stands. The decision recorded here (and on issue #225):

1. Default posture: NEVER auto-answer a trust prompt. There is no
   implicit opt-in, no environment sniffing, no "yolo implies trust".
2. Auto-answering is allowed ONLY when the operator passes an explicit
   ``TrustPolicy(auto_answer_trust=True)`` to ``answer_trust_prompt``.
   The policy object exists so the opt-in is a deliberate, auditable
   value in the caller's hands -- not a flag buried in config.
3. The standing ``--yolo`` posture maps to ``approvalMode=allowAll`` on
   the wire (see msp_session.YOLO_APPROVAL_MODE), but trust prompts are
   SEPARATE from tool approvals: ``allowAll`` auto-satisfies tool
   approvals; it does NOT answer ``userInput`` prompts. A ``--yolo`` job
   therefore still needs an explicit ``TrustPolicy`` to auto-answer a
   workspace-trust prompt; without one, the prompt surfaces through the
   ``userInput/request`` handler to the operator.
4. ``answer_user_input`` answers any prompt the caller hands it -- it is
   the operator-driven primitive (the operator already decided to
   answer by calling it). ``answer_trust_prompt`` is the auto-answer
   entry point and refuses without the opt-in policy (fail-closed).

Wire-shape provenance
---------------------
The method names and param/result shapes come from the exported schema
bundle (``muse schema generate-json-schema``, muse 1.4.2 on spark-vm,
kept at ~/workspace/muse-job-v2/msp.schema.json) -- ``ApprovalDecide*
``, ``ApprovalListPending*``, ``ApprovalRequestParams``,
``UserInputAnswer*``, ``UserInputRequestParams``, ``RequestReceipt`` --
cross-checked against the SS5.x design notes embedded in the schema
descriptions. NOT live-verified against the deployment binary this
turn: the module validates what it sends, parses results defensively,
and fails loud (MSPApprovalError) on shape drift instead of guessing.
MSPHost's schema-fingerprint pin (``verify_schema_on_open``) is the
drift tripwire -- pass ``expected_schema_fingerprint`` from the
deployment binary when opening the host.

Resolved ambiguities (recorded, not guessed silently)
----------------------------------------------------
- The schema's ``UserInputSelectionMode`` is a CLOSED enum:
  ``single | multiple`` -- there is no ``freeText`` mode on the wire,
  even though answers may carry ``freeText``. This module treats a
  question with an EMPTY options list as freeText mode (a prompt asking
  for typed text); ``single``/``multiple`` questions must answer with
  ``selectedLabel``/``selectedLabels`` respectively. Mode conformance
  is validated client-side before anything goes on the wire.
- ``RequestReceipt`` (the SS5.3.3 presentation receipt) is an EMPTY
  object: the request handlers below answer ``{}``. The receipt
  acknowledges presentation only -- the decision/answer always travels
  as a separate ``approval/decide`` / ``userInput/answer`` command.
- ``handle_approval_request`` / ``handle_user_input_request`` are
  handler FACTORIES: they take the caller-supplied callback and return
  the server-request handler to plug into
  ``MSPHost.set_request_handler("approval/request", ...)`` /
  ``("userInput/request", ...)``. The brief's ``(host, ...)`` shorthand
  was ambiguous; the factory shape is the one that plugs in.
- ``requirementId`` is the full ``currentRequirementId`` ref object
  (``{approvalId, sourceIndex}``), passed back verbatim -- the multi-
  stage race guard, not a bare string.

Fixture provenance (what the hermetic test fixture invents)
-----------------------------------------------------------
The fake ``muse serve`` in ``muse-job/tests/test_msp_approval.py``
stands in for wire shapes no transcript pins down. Its invented
details:
- the pending-approval record (toolName "exec", shell subject with a
  ``command``, two choices ``allow-once``/``deny`` with
  ``acceptsFeedback`` on the deny);
- the pending user-input prompt (one ``single`` trust question with two
  options, one ``multiple`` question, one freeText question with empty
  options);
- the ``-32053`` stale-requirement refusal reason
  ``stale_requirement``;
- ``approval/request`` / ``userInput/request`` server-initiated
  requests (the fixture emits them on demand via a ``testEmit`` hook).
The client only asserts the parts it documents (ids, choice sets, the
requirementId echo, mode validation), so the invented details can be
wrong without the client misbehaving.

Security and trust
------------------
Same posture as msp_host.py, which this module does not weaken:
approval ``rawArgs``, subjects, and user-input answers may contain real
secret values. Results are NEVER redacted, never logged, never printed
by the library functions. The smoke CLI below prints results to stdout
-- it redacts by DEFAULT (approval subjects/rawArgs and user-input
answers are withheld unless ``--show-secrets`` is passed explicitly)
and warns on stderr on every invocation. ``TrustPolicy`` values are not
secret, but the ANSWERS they gate may be -- never log them.
"""

import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msp_host import MSPError, MSPHost, ServerError  # noqa: E402  (sibling module)
from msp_session import check_command_id, new_command_id  # noqa: E402  (#222 layer)

# userInput/answer bounds, from the UserInputAnswerParams schema
# description ("freeText (<=500 chars); plus an optional note (<=500)").
_FREETEXT_MAX = 500
_NOTE_MAX = 500

# Modes the Question dataclass carries. 'freeText' is a client-side
# derivation (see the module docstring): the wire enum is closed to
# single|multiple.
QUESTION_MODES = ("single", "multiple", "freeText")

# Heuristic markers for looks_like_trust_prompt: the caller routes, this
# is only a convenience -- never a security boundary.
_TRUST_MARKERS = ("trust",)


class MSPApprovalError(MSPError):
    """An approval/user-input call failed or its shape drifted off the wire."""


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class ApprovalChoiceInfo:
    """One entry of an approval's availableChoices."""

    __slots__ = ("choice_id", "label", "decision", "accepts_feedback", "scope")

    def __init__(self, choice_id, label, decision, accepts_feedback, scope):
        self.choice_id = choice_id
        self.label = label
        self.decision = decision
        self.accepts_feedback = accepts_feedback
        self.scope = scope

    def __repr__(self):
        return (
            f"ApprovalChoiceInfo(choice_id={self.choice_id!r}, "
            f"label={self.label!r}, decision={self.decision!r})"
        )


class Approval:
    """A pending tool approval, parsed from approval/request params."""

    def __init__(self, approval_id, requirement_id, choices, title=None,
                 detail=None, session_id=None, raw=None):
        self.approval_id = approval_id
        # The currentRequirementId race guard, kept verbatim (a dict
        # {approvalId, sourceIndex}) so decide sends it back untouched.
        self.requirement_id = requirement_id
        self.choices = list(choices)  # [ApprovalChoiceInfo]
        self.title = title
        self.detail = detail
        self.session_id = session_id
        self.raw = raw if raw is not None else {}

    @property
    def available_choices(self):
        """The choice ids the server will accept right now."""
        return [c.choice_id for c in self.choices]

    def choice(self, choice_id):
        """Return the ApprovalChoiceInfo for choice_id (KeyError if absent)."""
        for c in self.choices:
            if c.choice_id == choice_id:
                return c
        raise KeyError(choice_id)

    def __repr__(self):
        return (
            f"Approval(approval_id={self.approval_id!r}, "
            f"choices={self.available_choices!r}, title={self.title!r})"
        )


class Question:
    """One question of a user-input prompt."""

    def __init__(self, question_id, mode, prompt_text, options,
                 min_selections=0, max_selections=None, header=None):
        if mode not in QUESTION_MODES:
            raise ValueError(
                f"mode must be one of {QUESTION_MODES}, got {mode!r}"
            )
        self.question_id = question_id
        self.mode = mode
        self.prompt_text = prompt_text
        self.options = list(options)  # labels
        self.min_selections = min_selections
        self.max_selections = (
            len(self.options) if max_selections is None else max_selections
        )
        self.header = header

    def __repr__(self):
        return (
            f"Question(question_id={self.question_id!r}, mode={self.mode!r}, "
            f"options={self.options!r})"
        )


class UserInputPrompt:
    """An open user-input prompt, parsed from userInput/request params."""

    def __init__(self, user_input_id, questions, session_id=None, raw=None):
        self.user_input_id = user_input_id
        self.questions = list(questions)  # [Question]
        self.session_id = session_id
        self.raw = raw if raw is not None else {}

    def question(self, question_id):
        """Return the Question for question_id (KeyError if absent)."""
        for q in self.questions:
            if q.question_id == question_id:
                return q
        raise KeyError(question_id)

    def __repr__(self):
        return (
            f"UserInputPrompt(user_input_id={self.user_input_id!r}, "
            f"questions={[q.question_id for q in self.questions]!r})"
        )


class TrustPolicy:
    """Explicit operator opt-in for auto-answering trust prompts.

    Default posture: NEVER auto-answer (``auto_answer_trust=False``).
    The ONLY way to auto-answer is to construct
    ``TrustPolicy(auto_answer_trust=True)`` and pass it to
    ``answer_trust_prompt`` -- a deliberate, auditable value in the
    caller's hands. See the module docstring's trust-policy decision.
    """

    def __init__(self, *, auto_answer_trust=False):
        self.auto_answer_trust = bool(auto_answer_trust)

    def __repr__(self):
        return f"TrustPolicy(auto_answer_trust={self.auto_answer_trust!r})"


# ---------------------------------------------------------------------------
# Parsing (wire params -> value objects; fail loud on drift)
# ---------------------------------------------------------------------------

def _check_session_id(session_id):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"session_id must be a non-empty string, got {session_id!r}"
        )
    return session_id


def _summarize_subject(subject, tool_name, raw_args):
    """Derive a human-readable (title, detail) from an approval subject.

    Unknown subject kinds render generically and are NEVER auto-approved
    (per the ApprovalSubject schema description) -- this function only
    describes; the decision stays with the caller.
    """
    kind = subject.get("kind") if isinstance(subject, dict) else None
    if kind == "shell":
        return ("Run shell command",
                subject.get("command") or raw_args or "")
    if kind == "fileAccess":
        access = subject.get("access") or "access"
        return (f"File {access}", subject.get("path") or "")
    if kind == "network":
        host = subject.get("host") or ""
        port = subject.get("port")
        target = subject.get("target") or ""
        where = f"{host}:{port}" if port else host
        return ("Network access", f"{where} {target}".strip())
    if kind == "unixSocket":
        return ("Unix socket access", subject.get("path") or "")
    if kind == "process":
        return ("Process action",
                subject.get("command") or subject.get("target") or "")
    if kind == "tool":
        name = subject.get("toolName") or tool_name or "tool"
        return (f"Tool call: {name}", raw_args or "")
    # Open discriminator: render generically.
    detail_bits = []
    if isinstance(subject, dict):
        for key in ("command", "path", "target", "host"):
            val = subject.get(key)
            if val:
                detail_bits.append(f"{key}={val}")
    if tool_name:
        detail_bits.append(f"tool={tool_name}")
    return (f"Approval ({kind or 'unknown kind'})",
            "; ".join(detail_bits))


def parse_approval(params):
    """Parse approval/request params into an Approval; fail loud on drift."""
    if not isinstance(params, dict):
        raise MSPApprovalError(
            "approval/request params must be a dict, got "
            f"{type(params).__name__}"
        )
    approval_id = params.get("approvalId")
    if not isinstance(approval_id, str) or not approval_id:
        raise MSPApprovalError(
            "approval/request params have no approvalId "
            f"(keys: {sorted(params)[:10]})"
        )
    raw_choices = params.get("availableChoices")
    if not isinstance(raw_choices, list) or not raw_choices:
        raise MSPApprovalError(
            f"approval {approval_id!r}: availableChoices must be a "
            f"non-empty list, got {raw_choices!r}"
        )
    choices = []
    for c in raw_choices:
        if not isinstance(c, dict) or not c.get("choiceId"):
            raise MSPApprovalError(
                f"approval {approval_id!r}: malformed choice entry "
                f"{c!r} (drift)"
            )
        choices.append(ApprovalChoiceInfo(
            choice_id=c["choiceId"],
            label=c.get("label"),
            decision=c.get("decision"),
            accepts_feedback=bool(c.get("acceptsFeedback")),
            scope=c.get("scope"),
        ))
    requirement_id = params.get("currentRequirementId")
    if not isinstance(requirement_id, dict) or not requirement_id.get(
            "approvalId"):
        raise MSPApprovalError(
            f"approval {approval_id!r}: currentRequirementId is not a "
            f"requirement ref (drift): {requirement_id!r}"
        )
    subject = params.get("subject")
    if not isinstance(subject, dict) or not subject.get("kind"):
        raise MSPApprovalError(
            f"approval {approval_id!r}: subject has no kind (drift)"
        )
    title, detail = _summarize_subject(
        subject, params.get("toolName"), params.get("rawArgs"))
    return Approval(
        approval_id=approval_id,
        requirement_id=copy.deepcopy(requirement_id),
        choices=choices,
        title=title,
        detail=detail,
        session_id=params.get("sessionId"),
        raw=copy.deepcopy(params),
    )


def parse_question(q):
    """Parse one UserInputQuestion into a Question; fail loud on drift."""
    if not isinstance(q, dict):
        raise MSPApprovalError(
            f"userInput question must be a dict, got {type(q).__name__}"
        )
    qid = q.get("id")
    if not isinstance(qid, str) or not qid:
        raise MSPApprovalError(
            f"userInput question has no id (keys: {sorted(q)[:10]})"
        )
    selection = q.get("selection")
    if not isinstance(selection, dict):
        raise MSPApprovalError(
            f"question {qid!r}: selection is not a dict (drift)"
        )
    wire_mode = selection.get("mode")
    raw_options = q.get("options")
    if not isinstance(raw_options, list):
        raise MSPApprovalError(
            f"question {qid!r}: options is not a list (drift)"
        )
    labels = []
    for o in raw_options:
        if not isinstance(o, dict) or not isinstance(o.get("label"), str):
            raise MSPApprovalError(
                f"question {qid!r}: malformed option entry {o!r} (drift)"
            )
        labels.append(o["label"])
    # Resolved ambiguity (see module docstring): the wire mode enum is
    # closed to single|multiple. A question with no options is asking for
    # typed text -- treat it as freeText mode.
    if not labels:
        mode = "freeText"
    elif wire_mode == "single":
        mode = "single"
    elif wire_mode == "multiple":
        mode = "multiple"
    else:
        raise MSPApprovalError(
            f"question {qid!r}: unknown selection mode {wire_mode!r} "
            "(drift; wire enum is single|multiple)"
        )
    min_sel = selection.get("minSelections", 0)
    max_sel = selection.get("maxSelections", len(labels))
    if (not isinstance(min_sel, int) or isinstance(min_sel, bool)
            or not isinstance(max_sel, int) or isinstance(max_sel, bool)
            or min_sel < 0 or max_sel < 0 or min_sel > max_sel):
        raise MSPApprovalError(
            f"question {qid!r}: bad selection bounds "
            f"min={min_sel!r} max={max_sel!r} (drift)"
        )
    header = q.get("header") or ""
    body = q.get("question") or ""
    if header and body and header != body:
        prompt_text = f"{header}\n{body}"
    else:
        prompt_text = header or body
    return Question(
        question_id=qid,
        mode=mode,
        prompt_text=prompt_text,
        options=labels,
        min_selections=min_sel,
        max_selections=max_sel,
        header=header or None,
    )


def parse_user_input(params):
    """Parse userInput/request params into a UserInputPrompt; fail loud."""
    if not isinstance(params, dict):
        raise MSPApprovalError(
            "userInput/request params must be a dict, got "
            f"{type(params).__name__}"
        )
    user_input_id = params.get("userInputId")
    if not isinstance(user_input_id, str) or not user_input_id:
        raise MSPApprovalError(
            "userInput/request params have no userInputId "
            f"(keys: {sorted(params)[:10]})"
        )
    raw_questions = params.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise MSPApprovalError(
            f"userInput {user_input_id!r}: questions must be a non-empty "
            f"list, got {raw_questions!r}"
        )
    questions = [parse_question(q) for q in raw_questions]
    seen = set()
    for q in questions:
        if q.question_id in seen:
            raise MSPApprovalError(
                f"userInput {user_input_id!r}: duplicate question id "
                f"{q.question_id!r} (drift)"
            )
        seen.add(q.question_id)
    return UserInputPrompt(
        user_input_id=user_input_id,
        questions=questions,
        session_id=params.get("sessionId"),
        raw=copy.deepcopy(params),
    )


def looks_like_trust_prompt(prompt):
    """Heuristic: does this prompt look like a trust prompt?

    Scans headers, prompt text, option labels, and the tool name for
    trust markers. This is a ROUTING convenience for the caller -- not a
    security boundary. The enforcement point is ``answer_trust_prompt``,
    which refuses without an explicit opt-in ``TrustPolicy`` no matter
    what this returns.
    """
    if not isinstance(prompt, UserInputPrompt):
        raise ValueError(
            f"prompt must be a UserInputPrompt, got {type(prompt).__name__}"
        )
    bits = [str(prompt.raw.get("toolName") or "")]
    for q in prompt.questions:
        bits.append(q.header or "")
        bits.append(q.prompt_text or "")
        bits.extend(q.options)
    haystack = "\n".join(bits).lower()
    return any(m in haystack for m in _TRUST_MARKERS)


# ---------------------------------------------------------------------------
# Client calls
# ---------------------------------------------------------------------------

def list_pending_approvals(host, session_id):
    """Return the session's pending approvals as [Approval].

    ``approval/listPending`` is a log-fold read: no lease, works on
    loaded and unloaded sessions, never subscribes. Ordering is by
    opening viewCursor; empty list when nothing is pending. The result
    is point-in-time -- ``decide_approval`` carries the requirementId
    race guard regardless of how the caller learned the state.

    Raises ValueError for client-side validation failures,
    MSPApprovalError when the result drifts off the wire shape.
    """
    _check_session_id(session_id)
    result = host.call("approval/listPending", {"sessionId": session_id})
    if not isinstance(result, dict):
        raise MSPApprovalError(
            "approval/listPending returned a non-dict result: "
            f"{type(result).__name__}"
        )
    raw = result.get("approvals")
    if not isinstance(raw, list):
        raise MSPApprovalError(
            "approval/listPending result has no 'approvals' list "
            f"(keys: {sorted(result)[:8]})"
        )
    return [parse_approval(a) for a in raw]


def list_pending_user_inputs(host, session_id):
    """Return the session's pending user-input prompts as [UserInputPrompt].

    Same ``approval/listPending`` call as ``list_pending_approvals`` --
    the wire returns both planes together. Additive helper for the #227
    wiring slice and the smoke CLI (the #225 contract names the
    approvals half; prompts need a parser too).
    """
    _check_session_id(session_id)
    result = host.call("approval/listPending", {"sessionId": session_id})
    if not isinstance(result, dict):
        raise MSPApprovalError(
            "approval/listPending returned a non-dict result: "
            f"{type(result).__name__}"
        )
    raw = result.get("userInputs")
    if not isinstance(raw, list):
        raise MSPApprovalError(
            "approval/listPending result has no 'userInputs' list "
            f"(keys: {sorted(result)[:8]})"
        )
    return [parse_user_input(p) for p in raw]


def decide_approval(host, session_id, approval, choice_id, *,
                    feedback=None, command_id=None):
    """Decide one approval; return the approval/decide result dict.

    Sends ``requirementId`` = the approval's ``currentRequirementId``
    verbatim -- the multi-stage race guard: a decision aimed at a stale
    stage fails server-side (``-32053``) instead of landing on the wrong
    one. ``feedback`` is only valid on choices whose ``acceptsFeedback``
    is true (checked client-side first). ``command_id`` defaults to a
    fresh UUIDv7 per call (an applied command id may not be reused --
    pass your own only for retry-after-unacknowledged semantics).

    The authoritative outcome is ``approval/resolved`` /
    ``approval/updated`` on the view stream; this returns the admission
    ack (``terminal`` false means more requirements remain and an
    updated ``approval/request`` follows).

    Raises ValueError when ``choice_id`` is not one of the approval's
    current available choices (client-side, before anything is sent),
    MSPApprovalError on result drift.
    """
    _check_session_id(session_id)
    if not isinstance(approval, Approval):
        raise ValueError(
            f"approval must be an Approval, got {type(approval).__name__}"
        )
    if not isinstance(choice_id, str) or not choice_id:
        raise ValueError(
            f"choice_id must be a non-empty string, got {choice_id!r}"
        )
    try:
        chosen = approval.choice(choice_id)
    except KeyError:
        raise ValueError(
            f"choice_id {choice_id!r} is not one of approval "
            f"{approval.approval_id!r}'s available choices "
            f"{approval.available_choices!r} -- refusing to decide blind"
        )
    if feedback is not None:
        if not isinstance(feedback, str):
            raise ValueError(
                f"feedback must be a string, got {type(feedback).__name__}"
            )
        if not chosen.accepts_feedback:
            raise ValueError(
                f"choice {choice_id!r} does not accept feedback "
                f"(acceptsFeedback is false) -- refusing to send it"
            )
    cid = (check_command_id(command_id) if command_id is not None
           else new_command_id())
    params = {
        "approvalId": approval.approval_id,
        "choiceId": choice_id,
        "commandId": cid,
        "requirementId": copy.deepcopy(approval.requirement_id),
        "sessionId": session_id,
    }
    if feedback is not None:
        # Feedback travels live-steer only: the schema notes it is never
        # persisted in the durable audit record.
        params["feedback"] = feedback
    result = host.call("approval/decide", params)
    if not isinstance(result, dict):
        raise MSPApprovalError(
            "approval/decide returned a non-dict result: "
            f"{type(result).__name__}"
        )
    if result.get("approvalId") != approval.approval_id:
        raise MSPApprovalError(
            "approval/decide result is for a different approval "
            f"({result.get('approvalId')!r} != {approval.approval_id!r})"
        )
    return result


def _validate_answer(question, answer):
    """Validate one answer dict against its Question; return the wire dict.

    ``answer`` carries ``questionId`` plus exactly one of
    ``selectedLabel`` / ``selectedLabels`` / ``freeText`` (and an
    optional ``note`` <=500 chars). Mode conformance is enforced:
    single -> selectedLabel must be one of the options; multiple ->
    selectedLabels within min/max and all in options; freeText ->
    string <=500 chars. Anything else fails loud (ValueError) BEFORE
    the wire: a mismatched answer would fail server-side as -32057
    ``userInputAnswerInvalid`` anyway, and failing here keeps the bad
    value out of the session entirely.
    """
    if not isinstance(answer, dict):
        raise ValueError(
            f"answer for question {question.question_id!r} must be a dict, "
            f"got {type(answer).__name__}"
        )
    allowed = {"questionId", "selectedLabel", "selectedLabels", "freeText",
               "note"}
    unknown = sorted(set(answer) - allowed)
    if unknown:
        raise ValueError(
            f"answer for question {question.question_id!r} has unknown "
            f"keys {unknown!r} (allowed: {sorted(allowed)})"
        )
    present = [k for k in ("selectedLabel", "selectedLabels", "freeText")
               if k in answer and answer[k] is not None]
    if len(present) != 1:
        raise ValueError(
            f"answer for question {question.question_id!r} must carry "
            f"exactly one of selectedLabel/selectedLabels/freeText, got "
            f"{present!r}"
        )
    kind = present[0]
    wire = {"questionId": question.question_id}
    if kind == "selectedLabel":
        if question.mode != "single":
            raise ValueError(
                f"question {question.question_id!r} is mode "
                f"{question.mode!r}: selectedLabel is only valid for "
                f"'single' questions"
            )
        label = answer["selectedLabel"]
        if not isinstance(label, str):
            raise ValueError(
                f"question {question.question_id!r}: selectedLabel must "
                f"be a string, got {type(label).__name__}"
            )
        if label not in question.options:
            raise ValueError(
                f"question {question.question_id!r}: selectedLabel "
                f"{label!r} is not one of the offered options "
                f"{question.options!r} -- refusing to answer blind"
            )
        wire["selectedLabel"] = label
    elif kind == "selectedLabels":
        if question.mode != "multiple":
            raise ValueError(
                f"question {question.question_id!r} is mode "
                f"{question.mode!r}: selectedLabels is only valid for "
                f"'multiple' questions"
            )
        labels = answer["selectedLabels"]
        if not isinstance(labels, list) or any(
                not isinstance(x, str) for x in labels):
            raise ValueError(
                f"question {question.question_id!r}: selectedLabels must "
                f"be a list of strings, got {labels!r}"
            )
        bad = [x for x in labels if x not in question.options]
        if bad:
            raise ValueError(
                f"question {question.question_id!r}: selectedLabels "
                f"{bad!r} are not among the offered options "
                f"{question.options!r} -- refusing to answer blind"
            )
        n = len(labels)
        if not question.min_selections <= n <= question.max_selections:
            raise ValueError(
                f"question {question.question_id!r}: selected {n} "
                f"option(s), outside the allowed "
                f"{question.min_selections}..{question.max_selections} "
                f"range"
            )
        wire["selectedLabels"] = list(labels)
    else:  # freeText
        if question.mode != "freeText":
            raise ValueError(
                f"question {question.question_id!r} is mode "
                f"{question.mode!r}: freeText is only valid for "
                f"'freeText' questions"
            )
        text = answer["freeText"]
        if not isinstance(text, str):
            raise ValueError(
                f"question {question.question_id!r}: freeText must be a "
                f"string, got {type(text).__name__}"
            )
        if len(text) > _FREETEXT_MAX:
            raise ValueError(
                f"question {question.question_id!r}: freeText is "
                f"{len(text)} chars, over the {_FREETEXT_MAX}-char wire "
                f"bound"
            )
        wire["freeText"] = text
    note = answer.get("note")
    if note is not None:
        if not isinstance(note, str):
            raise ValueError(
                f"question {question.question_id!r}: note must be a "
                f"string, got {type(note).__name__}"
            )
        if len(note) > _NOTE_MAX:
            raise ValueError(
                f"question {question.question_id!r}: note is "
                f"{len(note)} chars, over the {_NOTE_MAX}-char wire bound"
            )
        wire["note"] = note
    return wire


def answer_user_input(host, session_id, prompt, answers, *, command_id=None):
    """Answer every question of an open prompt; return the result dict.

    ``answers`` is a list of dicts, one per question, each with
    ``questionId`` plus exactly one of ``selectedLabel`` /
    ``selectedLabels`` / ``freeText`` (and an optional ``note``).
    Every question must be answered exactly once -- the wire answers
    EVERY question (SS5.10.2), and a partial answer would fail
    server-side anyway. Mode conformance is validated client-side first
    (see _validate_answer); mismatches fail loud here, never on the
    wire. ``command_id`` defaults to a fresh UUIDv7 per call.

    This is the operator-driven primitive: calling it IS the decision to
    answer. For the auto-answer path (trust prompts answered without a
    human in the loop), use ``answer_trust_prompt``, which additionally
    requires an explicit ``TrustPolicy`` opt-in.

    Raises ValueError for client-side validation failures,
    MSPApprovalError on result drift.
    """
    _check_session_id(session_id)
    if not isinstance(prompt, UserInputPrompt):
        raise ValueError(
            f"prompt must be a UserInputPrompt, got {type(prompt).__name__}"
        )
    if not isinstance(answers, list) or not answers:
        raise ValueError(
            f"answers must be a non-empty list, got {answers!r}"
        )
    if (prompt.session_id is not None
            and prompt.session_id != session_id):
        raise ValueError(
            f"prompt {prompt.user_input_id!r} belongs to session "
            f"{prompt.session_id!r}, not {session_id!r} -- refusing to "
            f"answer across sessions"
        )
    by_id = {q.question_id: q for q in prompt.questions}
    seen = set()
    wire_answers = []
    for a in answers:
        qid = a.get("questionId") if isinstance(a, dict) else None
        if qid not in by_id:
            raise ValueError(
                f"answer references unknown questionId {qid!r} "
                f"(prompt has {sorted(by_id)!r})"
            )
        if qid in seen:
            raise ValueError(
                f"duplicate answer for questionId {qid!r}: every "
                f"question must be answered exactly once"
            )
        seen.add(qid)
        wire_answers.append(_validate_answer(by_id[qid], a))
    missing = sorted(set(by_id) - seen)
    if missing:
        raise ValueError(
            f"unanswered questions {missing!r}: userInput/answer must "
            f"answer every question"
        )
    cid = (check_command_id(command_id) if command_id is not None
           else new_command_id())
    params = {
        "answers": wire_answers,
        "commandId": cid,
        "sessionId": session_id,
        "userInputId": prompt.user_input_id,
    }
    result = host.call("userInput/answer", params)
    if not isinstance(result, dict):
        raise MSPApprovalError(
            "userInput/answer returned a non-dict result: "
            f"{type(result).__name__}"
        )
    if result.get("userInputId") != prompt.user_input_id:
        raise MSPApprovalError(
            "userInput/answer result is for a different prompt "
            f"({result.get('userInputId')!r} != {prompt.user_input_id!r})"
        )
    return result


def _require_trust_policy(policy):
    """Fail closed unless the caller passed an explicit opt-in TrustPolicy."""
    if not isinstance(policy, TrustPolicy):
        raise MSPApprovalError(
            "auto-answering a trust prompt requires an explicit "
            f"TrustPolicy (got {type(policy).__name__}); see the module "
            f"docstring's trust-policy decision (#211 carried over)"
        )
    if not policy.auto_answer_trust:
        raise MSPApprovalError(
            "TrustPolicy denies auto-answering trust prompts (default "
            "posture: never auto-answer). Pass "
            "TrustPolicy(auto_answer_trust=True) to opt in explicitly."
        )


def answer_trust_prompt(host, session_id, prompt, answers, *, policy,
                        command_id=None):
    """Auto-answer a trust prompt ONLY with an explicit opt-in policy.

    This is the auto-answer entry point (the #211-carried decision, see
    the module docstring): without ``policy`` being a
    ``TrustPolicy(auto_answer_trust=True)``, it raises MSPApprovalError
    fail-closed -- a trust prompt is the model's way of asking the
    OPERATOR to vouch for something, and silently answering "yes" is a
    standing security decision, never a default.

    The standing ``--yolo`` posture (``approvalMode=allowAll``) does NOT
    satisfy this: ``allowAll`` governs tool approvals, not userInput
    prompts. Use ``looks_like_trust_prompt`` to route prompts here.

    Answers are validated exactly as in ``answer_user_input``; on
    success delegates to it and returns its result dict.
    """
    _require_trust_policy(policy)
    return answer_user_input(host, session_id, prompt, answers,
                             command_id=command_id)


# ---------------------------------------------------------------------------
# Server->client request routing
# ---------------------------------------------------------------------------

def handle_approval_request(on_approval):
    """Build the ``approval/request`` server-request handler.

    ``on_approval`` is the caller-supplied callback receiving an
    ``Approval``. The returned handler plugs into
    ``MSPHost.set_request_handler("approval/request", ...)``: it parses
    the wire params (fail loud on drift), invokes the callback, and
    answers the SS5.3.3 presentation receipt -- an empty object. The
    receipt acknowledges presentation ONLY; the decision travels as a
    separate ``approval/decide`` command.

    The handler runs on the transport's reader thread: it must not call
    ``host.call()`` itself (MSPHost raises -- re-entrant dispatch would
    deadlock); the callback must hand the decision work to its own
    thread. If parsing or the callback raises, the host answers a
    JSON-RPC error -- per SS5.3.3 that means "this connection could not
    present the request": the approval stays pending and is re-issued on
    the next subscribe.
    """
    if not callable(on_approval):
        raise ValueError("on_approval must be callable")

    def _handler(request):
        params = request.get("params") if isinstance(request, dict) else None
        approval = parse_approval(params)  # fail loud on drift
        on_approval(approval)
        return {}  # SS5.3.3 presentation receipt: empty RequestReceipt

    return _handler


def handle_user_input_request(on_prompt):
    """Build the ``userInput/request`` server-request handler.

    ``on_prompt`` is the caller-supplied callback receiving a
    ``UserInputPrompt``. The returned handler plugs into
    ``MSPHost.set_request_handler("userInput/request", ...)``: it parses
    the wire params (fail loud on drift), invokes the callback, and
    answers the SS5.3.3 presentation receipt -- an empty object. The
    answer travels as a separate ``userInput/answer`` command.

    Same reader-thread rules as ``handle_approval_request``: no
    ``host.call()`` from the callback; hand answer work to your own
    thread. A raised exception answers a JSON-RPC error, leaving the
    prompt pending for re-issue on the next subscribe.
    """
    if not callable(on_prompt):
        raise ValueError("on_prompt must be callable")

    def _handler(request):
        params = request.get("params") if isinstance(request, dict) else None
        prompt = parse_user_input(params)  # fail loud on drift
        on_prompt(prompt)
        return {}  # SS5.3.3 presentation receipt: empty RequestReceipt

    return _handler


# ---------------------------------------------------------------------------
# Smoke CLI
# ---------------------------------------------------------------------------

def _redacted_approval(a):
    """Operator-safe summary of an Approval (no rawArgs/subject detail)."""
    return {
        "approvalId": a.approval_id,
        "title": a.title,
        "sessionId": a.session_id,
        "choices": [
            {"choiceId": c.choice_id, "label": c.label,
             "decision": c.decision, "scope": c.scope,
             "acceptsFeedback": c.accepts_feedback}
            for c in a.choices
        ],
    }


def _redacted_prompt(p):
    """Operator-safe summary of a UserInputPrompt (structure, no answers)."""
    return {
        "userInputId": p.user_input_id,
        "sessionId": p.session_id,
        "looksLikeTrustPrompt": looks_like_trust_prompt(p),
        "questions": [
            {"questionId": q.question_id, "mode": q.mode,
             "header": q.header, "prompt": q.prompt_text,
             "options": q.options,
             "minSelections": q.min_selections,
             "maxSelections": q.max_selections}
            for q in p.questions
        ],
    }


def main(argv):
    """Smoke CLI: exercise the approval/user-input plane on a real host.

    Usage: msp_approval.py [--client-name N] [--show-secrets]
        <list-pending|decide|answer> [options] -- <serve argv...>, e.g.
    msp_approval.py list-pending --session-id sess-abc -- muse serve
    msp_approval.py decide --session-id sess-abc --approval-id ap-1 \\
        --choice-id allow-once -- muse serve
    msp_approval.py answer --session-id sess-abc --user-input-id ui-1 \\
        --answers '[{"questionId":"q1","selectedLabel":"Yes"}]' -- muse serve

    Default output is REDACTED: approval subjects/rawArgs and user-input
    answers are withheld unless --show-secrets is passed explicitly.
    Even with --show-secrets, the WARNING below applies.
    """
    ap = argparse.ArgumentParser(
        description="MSP approval/user-input smoke CLI (#225)",
        epilog="WARNING: printed results are NOT redacted with "
               "--show-secrets and may contain real secret values (approval "
               "subjects, raw tool args, prompt answers) -- do not paste "
               "that output where agents can read it.",
    )
    ap.add_argument("--client-name", default="msp_approval")
    ap.add_argument("--show-secrets", action="store_true",
                    help="print full raw wire params/answers (NOT redacted)")
    sub = ap.add_subparsers(dest="action", required=True)

    def add_serve(p):
        # REMAINDER inside a subparser keeps optionals parseable; the
        # literal "--" separator lands in the list and is stripped below.
        p.add_argument("serve", nargs=argparse.REMAINDER,
                       help="serve argv after --, e.g. -- muse serve")

    p_list = sub.add_parser("list-pending",
                            help="approval/listPending for a session")
    p_list.add_argument("--session-id", required=True)
    add_serve(p_list)

    p_decide = sub.add_parser("decide", help="approval/decide one approval")
    p_decide.add_argument("--session-id", required=True)
    p_decide.add_argument("--approval-id", required=True)
    p_decide.add_argument("--choice-id", required=True)
    p_decide.add_argument("--feedback", default=None)
    add_serve(p_decide)

    p_answer = sub.add_parser("answer",
                              help="userInput/answer one prompt")
    p_answer.add_argument("--session-id", required=True)
    p_answer.add_argument("--user-input-id", required=True)
    p_answer.add_argument("--answers", required=True,
                          help="JSON list of answer dicts, e.g. "
                          "'[{\"questionId\":\"q1\",\"selectedLabel\":"
                          "\"Yes\"}]'")
    p_answer.add_argument("--trust-policy-opt-in", action="store_true",
                          help="pass an explicit TrustPolicy("
                          "auto_answer_trust=True) (see module docstring)")
    add_serve(p_answer)

    args = ap.parse_args(argv)
    serve = list(args.serve)
    if serve and serve[0] == "--":
        serve = serve[1:]
    if not serve:
        ap.error("need serve argv after --")

    host = MSPHost(serve, client_name=args.client_name)
    with host:
        if args.action == "list-pending":
            approvals = list_pending_approvals(host, args.session_id)
            prompts = list_pending_user_inputs(host, args.session_id)
            if args.show_secrets:
                out = {"approvals": [a.raw for a in approvals],
                       "userInputs": [p.raw for p in prompts]}
            else:
                out = {"approvals": [_redacted_approval(a)
                                     for a in approvals],
                       "userInputs": [_redacted_prompt(p) for p in prompts]}
        elif args.action == "decide":
            approvals = list_pending_approvals(host, args.session_id)
            approval = next(
                (a for a in approvals
                 if a.approval_id == args.approval_id), None)
            if approval is None:
                ap.error(f"no pending approval {args.approval_id!r} "
                         f"(saw {[a.approval_id for a in approvals]!r})")
            # The requirementId race guard is read fresh from listPending
            # just now; a stale stage still fails server-side (-32053).
            result = decide_approval(host, args.session_id, approval,
                                     args.choice_id,
                                     feedback=args.feedback)
            out = {"result": result}
        else:  # answer
            prompts = list_pending_user_inputs(host, args.session_id)
            prompt = next(
                (p for p in prompts
                 if p.user_input_id == args.user_input_id), None)
            if prompt is None:
                ap.error(f"no pending user input {args.user_input_id!r} "
                         f"(saw {[p.user_input_id for p in prompts]!r})")
            try:
                answers = json.loads(args.answers)
            except ValueError as e:
                ap.error(f"--answers is not valid JSON: {e}")
            policy = (TrustPolicy(auto_answer_trust=True)
                      if args.trust_policy_opt_in else TrustPolicy())
            if looks_like_trust_prompt(prompt):
                result = answer_trust_prompt(host, args.session_id, prompt,
                                             answers, policy=policy)
            else:
                result = answer_user_input(host, args.session_id, prompt,
                                           answers)
            if args.show_secrets:
                out = {"result": result, "answers": answers}
            else:
                out = {"result": result,
                       "answers": "<redacted; pass --show-secrets to print>"}
    # Redaction posture: say it on stderr on EVERY invocation, not just in
    # --help: this output lands on stdout, where it is one pipe or paste
    # away from somewhere an agent can read it.
    if args.show_secrets:
        print(
            "WARNING: --show-secrets was passed: this output is NOT "
            "redacted and may contain real secret values (approval "
            "subjects, raw tool args, prompt answers) -- do not paste it "
            "where agents can read it.",
            file=sys.stderr,
        )
    else:
        print(
            "NOTE: output redacted by default (approval subjects/rawArgs "
            "and prompt answers withheld); --show-secrets prints them.",
            file=sys.stderr,
        )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

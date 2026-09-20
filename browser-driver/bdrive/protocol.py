"""Fixed action protocol for bdrive (browser-driver/SPEC.md §5).

Transport-agnostic JSON: the orchestrator submits one ordered actions
array per call; each action runs in order and the first failure stops
the array. Anything outside the fixed vocabulary is rejected, not
interpreted.

This module owns validation only. It never touches a browser, a
socket, or the network — the execution backend (a later slice)
consumes :class:`ValidatedCall` and produces :class:`ActionReceipt`
values. Configuration (socket path, profile dir, proxy URL) lives in
``bdrive.config`` and is deliberately not read here, so the protocol
does not cement any deployment assumption (H17: do not cement the
same-box-proxy assumption behind an interface).

Wire format of a call::

    {"session": "<session id>",
     "ref_scope": "<token from the newest observation, or null>",
     "actions": [{"action": "goto", "url": "https://example.com",
                  "timeout_ms": 15000},
                 {"action": "click", "ref": "@e3"}]}

Every action object carries its parameters flat with an ``"action"``
discriminator. ``ref_scope`` is required whenever any action addresses
an element ref, and must equal the token the daemon issued with the
newest observation — refs from any older observation are stale and
rejected (SPEC §4).

Validation rules enforced here, beyond the fixed vocabulary:

- unknown parameters fail loud — no silent absorption
- ``goto`` is restricted to http/https (no javascript:, file:, data:)
- ``snapshot`` is an observation-only call: never combined with other
  actions in the same array
- post-navigation rule: after ``goto``, only an exact-text ``wait`` or
  ref-free ``look`` / ``get_text`` / ``get_html`` / ``state`` may follow
  in the same array
- durations are capped at ``MAX_TIMEOUT_MS`` and the actions array at
  ``MAX_ACTIONS_PER_CALL`` — a compromised orchestrator cannot wedge
  the driver or DoS it with a giant array
- ``fill_card`` carries only a job id; any value payload is rejected —
  card values flow through the dedicated issuer pathway (SPEC §7),
  never through this protocol
- SPEC §13 (never log field contents): ``SENSITIVE_PARAMS`` declares
  which params carry operator/page data; backends must log only via
  ``ValidatedAction.redacted_params()``

Receipts (SPEC §5) carry one of three statuses:

- ``completed`` — the action ran (even if a later action failed).
- ``unknown`` — it may have run; inspect the page, never blindly
  repeat. Carries a human ``error`` string.
- ``not_started`` — stopped before this action. May carry an
  ``actionability_reason`` (not_visible, obscured, disabled,
  not_editable, not_hittable, unstable, timeout); reasons are only
  valid on ``not_started``.
"""

import hmac
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProtocolError(ValueError):
    """A call that violates the protocol. ``code`` is machine-readable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Action vocabulary (SPEC §5)
# ---------------------------------------------------------------------------

REF_RE = re.compile(r"\A@e[0-9]+\Z")  # \A..\Z, not ^..$: "@e1\n" must not pass

#: Actions the v1 daemon serves (SPEC §16 item 1).
STAGE_V1 = "v1"
#: Actions declared by the protocol but served by the v1.1 daemon.
STAGE_V1_1 = "v1.1"

#: Statuses of an action receipt (SPEC §5).
STATUS_COMPLETED = "completed"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_STARTED = "not_started"
STATUSES = (STATUS_COMPLETED, STATUS_UNKNOWN, STATUS_NOT_STARTED)

#: Why an action never started (SPEC §5). Only valid on ``not_started``.
ACTIONABILITY_REASONS = (
    "not_visible",
    "obscured",
    "disabled",
    "not_editable",
    "not_hittable",
    "unstable",
    "timeout",
)

CLICK_KINDS = ("left", "right", "double")
SCROLL_DIRECTIONS = ("up", "down", "left", "right", "top", "bottom")

#: Hard ceiling on per-action timeouts: a driver that hangs for five
#: minutes is wedged; fail loud instead of blocking the agent loop.
MAX_TIMEOUT_MS = 300_000

#: Hard ceiling on the actions array in one call: an unbounded array
#: is a CPU/memory DoS vector from a compromised orchestrator.
MAX_ACTIONS_PER_CALL = 256


def is_nonempty_str(value):
    return isinstance(value, str) and len(value) > 0


def _check_ref(value, what):
    if not is_nonempty_str(value) or not REF_RE.match(value):
        raise ProtocolError(
            "bad_params",
            "%s must look like @e1, got %r" % (what, value),
        )


def _check_timeout_ms(value):
    if not isinstance(value, bool) and isinstance(value, int):
        if 1 <= value <= MAX_TIMEOUT_MS:
            return
    raise ProtocolError(
        "bad_params",
        "timeout_ms must be an int in [1, %d], got %r"
        % (MAX_TIMEOUT_MS, value),
    )


def _v_goto(params):
    url = params.get("url")
    if not is_nonempty_str(url):
        raise ProtocolError("bad_params", "goto requires a non-empty url")
    if ":" not in url:
        # A bare "http"/"https" with no colon would otherwise pass the
        # scheme check and send the browser to a search engine instead
        # of failing loud.
        raise ProtocolError(
            "bad_goto_scheme", "goto requires a URL with a scheme, got %r" % (url,)
        )
    scheme = url.split(":", 1)[0].lower()
    # http/https only: file:, javascript:, data: and friends never
    # navigate — the driver is not a file reader or a script runner.
    # SPEC §5 allows hsurr: placeholders inside the query string; the
    # swap happens at egress (a later slice), so this check does not
    # forbid them.
    if scheme not in ("http", "https"):
        raise ProtocolError(
            "bad_goto_scheme",
            "goto allows http/https only, got scheme %r" % scheme,
        )


def _v_click(params):
    _check_ref(params.get("ref"), "click.ref")
    kind = params.get("kind", "left")
    if kind not in CLICK_KINDS:
        raise ProtocolError(
            "bad_params", "click.kind must be one of %s, got %r"
            % ("/".join(CLICK_KINDS), kind)
        )


def _v_ref_only(action):
    def check(params):
        _check_ref(params.get("ref"), action + ".ref")

    return check


def _v_ref_text(action):
    def check(params):
        _check_ref(params.get("ref"), action + ".ref")
        if not isinstance(params.get("text"), str):
            raise ProtocolError(
                "bad_params", "%s.text must be a string" % action
            )

    return check


def _v_press(params):
    if not is_nonempty_str(params.get("key")):
        raise ProtocolError("bad_params", "press requires a non-empty key")
    if "ref" in params:
        _check_ref(params.get("ref"), "press.ref")


def _v_select(params):
    _check_ref(params.get("ref"), "select.ref")
    if not isinstance(params.get("value"), str):
        raise ProtocolError("bad_params", "select.value must be a string")


def _v_scroll(params):
    if "ref" in params:
        _check_ref(params.get("ref"), "scroll.ref")
    direction = params.get("direction")
    if direction is not None and direction not in SCROLL_DIRECTIONS:
        raise ProtocolError(
            "bad_params",
            "scroll.direction must be one of %s, got %r"
            % ("/".join(SCROLL_DIRECTIONS), direction),
        )
    pixels = params.get("pixels")
    # pixels is uncapped by design: a single scroll's work is bounded
    # by the page regardless of the count. Only durations
    # (wait.time_ms, gesture.click_hold_ms, timeout_ms) wedge the
    # driver, and those are capped at MAX_TIMEOUT_MS.
    if pixels is not None and (
        isinstance(pixels, bool) or not isinstance(pixels, int) or pixels <= 0
    ):
        raise ProtocolError("bad_params", "scroll.pixels must be a positive int")


def _v_get_text_html(action):
    def check(params):
        if "ref" in params:
            _check_ref(params.get("ref"), action + ".ref")

    return check


def _v_get_attr(params):
    _check_ref(params.get("ref"), "get_attr.ref")
    if not is_nonempty_str(params.get("attribute")):
        raise ProtocolError(
            "bad_params", "get_attr requires a non-empty attribute name"
        )


def _v_wait(params):
    present = [k for k in ("text", "text_gone", "time_ms") if k in params]
    # SPEC §4: exactly one of text / text_gone / time_ms.
    if len(present) != 1:
        raise ProtocolError(
            "bad_params",
            "wait takes exactly one of text/text_gone/time_ms, got %s"
            % ("/".join(present) if present else "none"),
        )
    key = present[0]
    if key in ("text", "text_gone"):
        # An empty exact-text wait is a vacuous match that returns
        # immediately; require non-empty like every other text field.
        if not is_nonempty_str(params[key]):
            raise ProtocolError(
                "bad_params", "wait.%s must be a non-empty string" % key
            )
    else:
        ms = params[key]
        if isinstance(ms, bool) or not isinstance(ms, int) or ms <= 0:
            raise ProtocolError(
                "bad_params", "wait.time_ms must be a positive int"
            )
        if ms > MAX_TIMEOUT_MS:
            raise ProtocolError(
                "timeout_too_large",
                "wait.time_ms exceeds MAX_TIMEOUT_MS (%d)" % MAX_TIMEOUT_MS,
            )


def _v_upload(params):
    _check_ref(params.get("ref"), "upload.ref")
    grant_ids = params.get("grant_ids")
    # grant_ids are opaque, task-bound file-grant identifiers (SPEC §5,
    # §10); the driver never learns host paths from the protocol.
    if (
        not isinstance(grant_ids, list)
        or not grant_ids
        or not all(is_nonempty_str(g) for g in grant_ids)
    ):
        raise ProtocolError(
            "bad_params", "upload.grant_ids must be a non-empty list of strings"
        )


def _v_gesture(params):
    if not is_nonempty_str(params.get("instruction")):
        raise ProtocolError(
            "bad_params", "gesture requires a non-empty instruction"
        )
    if not is_nonempty_str(params.get("gesture")):
        raise ProtocolError(
            "bad_params", "gesture requires a non-empty gesture name"
        )
    for key in ("max_points", "click_hold_ms"):
        if key in params:
            value = params[key]
            lo = 1 if key == "max_points" else 0
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < lo
            ):
                raise ProtocolError(
                    "bad_params", "gesture.%s must be an int >= %d" % (key, lo)
                )
            if key == "click_hold_ms" and value > MAX_TIMEOUT_MS:
                raise ProtocolError(
                    "timeout_too_large",
                    "gesture.click_hold_ms exceeds MAX_TIMEOUT_MS (%d)"
                    % MAX_TIMEOUT_MS,
                )
    if "motion_profile" in params and not is_nonempty_str(
        params["motion_profile"]
    ):
        raise ProtocolError(
            "bad_params", "gesture.motion_profile must be a non-empty string"
        )


def _v_fill_card(params):
    # Carries no values by design (SPEC §7): obox names the job, bdrive
    # fetches the card entries itself over its peer-checked socket.
    if not is_nonempty_str(params.get("job")):
        raise ProtocolError("bad_params", "fill_card requires a non-empty job")


def _v_nothing(params):
    # open, back, forward, reload, state, snapshot, cookies_clear, pdf:
    # no parameters beyond the universal timeout_ms.
    pass


def _v_look(params):
    if "full_page" in params and not isinstance(params["full_page"], bool):
        raise ProtocolError("bad_params", "look.full_page must be a bool")


# name -> (validator, stage, needs_ref, observation_only)
_ACTIONS = {
    "open": (_v_nothing, STAGE_V1, False, False),
    "goto": (_v_goto, STAGE_V1, False, False),
    "back": (_v_nothing, STAGE_V1, False, False),
    "forward": (_v_nothing, STAGE_V1, False, False),
    "reload": (_v_nothing, STAGE_V1, False, False),
    "state": (_v_nothing, STAGE_V1, False, True),
    "click": (_v_click, STAGE_V1, True, False),
    "fill": (_v_ref_text("fill"), STAGE_V1, True, False),
    "type": (_v_ref_text("type"), STAGE_V1, True, False),
    "press": (_v_press, STAGE_V1, False, False),
    "select": (_v_select, STAGE_V1, True, False),
    "check": (_v_ref_only("check"), STAGE_V1, True, False),
    "snapshot": (_v_nothing, STAGE_V1, False, True),
    "look": (_v_look, STAGE_V1, False, True),
    "get_text": (_v_get_text_html("get_text"), STAGE_V1, False, True),
    "wait": (_v_wait, STAGE_V1, False, True),
    "cookies_clear": (_v_nothing, STAGE_V1, False, False),
    "hover": (_v_ref_only("hover"), STAGE_V1_1, True, False),
    "scroll": (_v_scroll, STAGE_V1_1, False, False),
    "uncheck": (_v_ref_only("uncheck"), STAGE_V1_1, True, False),
    "focus": (_v_ref_only("focus"), STAGE_V1_1, True, False),
    "get_html": (_v_get_text_html("get_html"), STAGE_V1_1, False, True),
    "get_attr": (_v_get_attr, STAGE_V1_1, True, True),
    "get_value": (_v_ref_only("get_value"), STAGE_V1_1, True, True),
    "gesture": (_v_gesture, STAGE_V1_1, False, False),
    "upload": (_v_upload, STAGE_V1_1, True, False),
    "download": (_v_ref_only("download"), STAGE_V1_1, True, False),
    "pdf": (_v_nothing, STAGE_V1_1, False, False),
    "fill_card": (_v_fill_card, STAGE_V1_1, False, False),
}

#: The fixed vocabulary, in spec order. Anything not in this set is
#: rejected, not interpreted.
ACTION_NAMES = tuple(_ACTIONS)

#: Per-action parameter names the validator understands (beyond the
#: universal ``timeout_ms``). Unknown keys are rejected — a misspelled
#: parameter must fail loud, never be silently ignored. Every action in
#: the vocabulary has an entry; param-less actions carry an explicit
#: empty set so the fail-closed default is deliberate, not implicit.
_ACTION_KEYS = {
    "open": set(),
    "goto": {"url"},
    "back": set(),
    "forward": set(),
    "reload": set(),
    "state": set(),
    "click": {"ref", "kind"},
    "fill": {"ref", "text"},
    "type": {"ref", "text"},
    "press": {"key", "ref"},
    "select": {"ref", "value"},
    "check": {"ref"},
    "snapshot": set(),
    "look": {"full_page"},
    "get_text": {"ref"},
    "wait": {"text", "text_gone", "time_ms"},
    "cookies_clear": set(),
    "hover": {"ref"},
    "scroll": {"ref", "pixels", "direction"},
    "uncheck": {"ref"},
    "focus": {"ref"},
    "get_html": {"ref"},
    "get_attr": {"ref", "attribute"},
    "get_value": {"ref"},
    "gesture": {"instruction", "gesture", "max_points", "click_hold_ms",
                "motion_profile"},
    "upload": {"ref", "grant_ids"},
    "download": {"ref"},
    "pdf": set(),
    "fill_card": {"job"},
}
assert set(_ACTION_KEYS) == set(_ACTIONS), \
    "param-key table must cover the whole vocabulary"


def _action_entry(name):
    """Fetch the vocabulary entry, failing closed with ProtocolError.

    A non-string or unknown name is ``unknown_action`` — never a
    TypeError/KeyError escaping to the caller (a daemon catching only
    ProtocolError must see a clean rejection for attacker input).
    """
    if not isinstance(name, str):
        raise ProtocolError(
            "unknown_action",
            "action name must be a string, got %r" % (name,),
        )
    try:
        return _ACTIONS[name]
    except KeyError:
        raise ProtocolError(
            "unknown_action",
            "%r is not in the fixed vocabulary (rejected, not interpreted)"
            % (name,),
        )


def action_stage(name):
    """Deployment stage serving this action (``"v1"`` or ``"v1.1"``)."""
    return _action_entry(name)[1]


def action_needs_ref(name):
    """True when the action addresses an element ref (@eN)."""
    return _action_entry(name)[2]


def is_observation_only(name):
    """True for actions that never mutate page state."""
    return _action_entry(name)[3]


# ---------------------------------------------------------------------------
# ref_scope lifecycle (SPEC §4)
# ---------------------------------------------------------------------------


class RefScope:
    """Issues and validates observation-scoped locator tokens.

    The daemon holds one ``RefScope`` per browser session. Every new
    observation rotates the token; refs are actionable only with the
    token from the exact observation that supplied them, and only the
    newest observation's tree is actionable — older trees are redacted
    by the daemon (see ``bdrive.observation.redact_for_history``).

    Tokens are unguessable (``secrets.token_hex``); comparisons are
    constant-time. The socket peer check is the real gate — this is
    defense in depth against a confused-deputy replaying an old tree.
    """

    def __init__(self):
        self._counter = 0
        self._token = None

    def rotate(self):
        """Issue the token for a new observation; invalidates the old."""
        self._counter += 1
        self._token = "rs_%d_%s" % (self._counter, secrets.token_hex(8))
        return self._token

    @property
    def current(self):
        """The live token, or None before the first observation."""
        return self._token

    def accepts(self, token):
        """True only when ``token`` is the live observation token."""
        if not is_nonempty_str(token) or self._token is None:
            return False
        return hmac.compare_digest(token, self._token)


# ---------------------------------------------------------------------------
# Call validation
# ---------------------------------------------------------------------------

#: Actions allowed after a ``goto`` inside the same array (SPEC §4):
#: an exact-text ``wait``, or ref-free ``look`` / ``get_text`` /
#: ``get_html`` / ``state``. Never ``snapshot``, never a locator action
#: on the old tree.
_POST_GOTO_ACTIONS = ("look", "get_text", "get_html", "state")


#: Params that carry operator or page data (SPEC §13: field contents
#: are never logged). ``goto``'s URL is included: query strings may
#: carry real tokens as well as hsurr: placeholders. The vocabulary
#: owner declares this once so no future backend has to re-derive
#: which params are sensitive.
SENSITIVE_PARAMS = {
    "fill": frozenset({"text"}),
    "type": frozenset({"text"}),
    "select": frozenset({"value"}),
    "goto": frozenset({"url"}),
}


def _freeze(value):
    """Deeply freeze a validated value: dicts -> MappingProxyType,
    lists/tuples -> tuples. Scalars pass through."""
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class ValidatedAction:
    """One validated action. ``params`` is deeply frozen (MappingProxyType
    / tuples): the "validated" object cannot be mutated after validation,
    and nested values are detached from the caller's payload. Lists in
    the payload (e.g. ``grant_ids``) surface as tuples."""

    name: str
    params: Mapping
    timeout_ms: int = 0

    def redacted_params(self):
        """Params safe for logging: SPEC §13 declares field contents
        (selectors, text, URLs) are never logged. Backends must log
        only through this, never ``params`` directly."""
        sensitive = SENSITIVE_PARAMS.get(self.name, frozenset())
        out = {}
        for key, value in self.params.items():
            if key in sensitive:
                out[key] = "<redacted>"
            elif isinstance(value, tuple):
                out[key] = list(value)
            else:
                out[key] = value
        return out


@dataclass(frozen=True)
class ValidatedCall:
    session: str
    ref_scope: str | None
    actions: tuple


def _validate_action_object(obj, index):
    if not isinstance(obj, dict):
        raise ProtocolError(
            "bad_params", "actions[%d] must be an object, got %r" % (index, obj)
        )
    name = obj.get("action")
    validator, _stage, _needs_ref, _obs_only = _action_entry(name)
    params = {k: v for k, v in obj.items() if k not in ("action", "timeout_ms")}
    unknown = set(params) - _ACTION_KEYS[name]
    if unknown:
        raise ProtocolError(
            "bad_params",
            "actions[%d] (%s): unknown parameter(s) %s"
            % (index, name, sorted(unknown)),
        )
    validator(params)
    timeout_ms = obj.get("timeout_ms", 0)
    if timeout_ms:
        _check_timeout_ms(timeout_ms)
    elif "timeout_ms" in obj:
        raise ProtocolError(
            "bad_params",
            "actions[%d] (%s): timeout_ms must be a positive int"
            % (index, name),
        )
    return ValidatedAction(
        name=name, params=_freeze(params), timeout_ms=timeout_ms
    )


def _check_post_navigation_rule(validated):
    """SPEC §4: after ``goto``, only exact-text ``wait`` or ref-free
    ``look`` / ``get_text`` / ``get_html`` / ``state`` may follow."""
    navigated = False
    for i, action in enumerate(validated):
        if navigated:
            ok = action.name == "wait" and "text" in action.params
            ok = ok or (
                action.name in _POST_GOTO_ACTIONS and "ref" not in action.params
            )
            if not ok:
                raise ProtocolError(
                    "post_navigation_violation",
                    "actions[%d] (%s): after goto only an exact-text wait "
                    "or ref-free look/get_text/get_html/state may follow"
                    % (i, action.name),
                )
        if action.name == "goto":
            navigated = True


def validate_call(payload, scope=None):
    """Validate a raw call dict against the protocol.

    ``scope`` is the session's :class:`RefScope` (or None for
    transport-level validation only). Raises :class:`ProtocolError`
    with a machine-readable ``code`` on any violation. Returns a
    :class:`ValidatedCall`.
    """
    if not isinstance(payload, dict):
        raise ProtocolError("bad_envelope", "call must be a JSON object")
    session = payload.get("session")
    if not is_nonempty_str(session):
        raise ProtocolError("bad_envelope", "call.session must be non-empty")
    raw_actions = payload.get("actions")
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ProtocolError(
            "bad_envelope", "call.actions must be a non-empty array"
        )
    if len(raw_actions) > MAX_ACTIONS_PER_CALL:
        raise ProtocolError(
            "too_many_actions",
            "call.actions has %d actions, max %d"
            % (len(raw_actions), MAX_ACTIONS_PER_CALL),
        )
    validated = tuple(
        _validate_action_object(obj, i) for i, obj in enumerate(raw_actions)
    )
    if len(validated) > 1 and any(a.name == "snapshot" for a in validated):
        # SPEC §4: snapshot is an observation-only call, never combined
        # with actions in the same array.
        raise ProtocolError(
            "snapshot_not_alone",
            "snapshot is never combined with other actions in one call",
        )
    _check_post_navigation_rule(validated)

    ref_scope = payload.get("ref_scope")
    # Any action addressing an element ref — mandatory or optional
    # (press/scroll/get_text/get_html take an optional ref) — needs the
    # live observation token (SPEC §4).
    needs_scope = any(
        action_needs_ref(a.name) or "ref" in a.params for a in validated
    )
    if needs_scope:
        if not is_nonempty_str(ref_scope):
            raise ProtocolError(
                "missing_ref_scope",
                "actions address element refs; ref_scope is required",
            )
        if scope is not None and not scope.accepts(ref_scope):
            raise ProtocolError(
                "stale_ref_scope",
                "ref_scope does not match the newest observation; "
                "re-snapshot and retry with fresh refs",
            )
    return ValidatedCall(
        session=session, ref_scope=ref_scope, actions=validated
    )


# ---------------------------------------------------------------------------
# Receipts (SPEC §5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionReceipt:
    """One action's outcome. The daemon builds these; the agent acts on them."""

    action: str
    status: str
    actionability_reason: str | None = None
    error: str | None = None

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ProtocolError(
                "bad_receipt", "unknown receipt status %r" % (self.status,)
            )
        if self.actionability_reason is not None:
            if self.status != STATUS_NOT_STARTED:
                raise ProtocolError(
                    "bad_receipt",
                    "actionability_reason is only valid on not_started "
                    "receipts",
                )
            if self.actionability_reason not in ACTIONABILITY_REASONS:
                raise ProtocolError(
                    "bad_receipt",
                    "unknown actionability_reason %r"
                    % (self.actionability_reason,),
                )

    def to_dict(self):
        out = {"action": self.action, "status": self.status}
        if self.actionability_reason is not None:
            out["actionability_reason"] = self.actionability_reason
        if self.error is not None:
            out["error"] = self.error
        return out


@dataclass
class CallResult:
    """The daemon's answer to a call: one receipt per action plus the
    terminal observation (SPEC §4: a fresh AX capture is automatic
    after every action call). ``stopped_at`` is the index of the first
    non-completed action, or None when the whole array completed."""

    session: str
    receipts: list = field(default_factory=list)
    observation: dict | None = None
    stopped_at: int | None = None

    def to_dict(self):
        return {
            "session": self.session,
            "receipts": [r.to_dict() for r in self.receipts],
            "observation": self.observation,
            "stopped_at": self.stopped_at,
        }

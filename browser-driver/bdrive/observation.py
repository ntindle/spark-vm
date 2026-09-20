"""Observation schema for bdrive (browser-driver/SPEC.md §4).

The agent's primary sense is the accessibility tree, not pixels. Every
observation carries: current URL, page title, target/document identity,
a ``ref_scope`` token, and an AX snapshot whose element locators
(``@e1``, ``@e2``, …) carry role, accessible name, and enabled/visible
state. Locator refs are valid only with the ``ref_scope`` token from
the exact observation that supplied them — and only the newest
observation's tree is actionable. Older trees are redacted before they
leave the daemon (``redact_for_history``): the envelope survives, the
tree does not.

Like ``bdrive.protocol``, this module is pure validation — no browser,
no I/O.
"""

from bdrive.protocol import MAX_PARAM_LEN, REF_RE, ProtocolError, is_nonempty_str


#: Hard cap on AX tree depth. The tree is derived from the rendered
#: page DOM — attacker-controlled on any hostile site — so a recursive
#: walk is a RecursionError DoS reachable by merely visiting a malicious
#: page. Traversal is iterative and anything deeper than this fails loud
#: as ProtocolError, never as a raw RecursionError.
MAX_AX_DEPTH = 1000


def _check_node(node, path):
    # Iterative: an explicit stack of (node, path, depth) instead of
    # recursion, so a hostile page cannot crash the daemon via
    # RecursionError (the daemon catches only ProtocolError).
    stack = [(node, path, 0)]
    while stack:
        node, path, depth = stack.pop()
        if depth > MAX_AX_DEPTH:
            raise ProtocolError(
                "bad_observation",
                "%s: AX tree exceeds max depth %d" % (path, MAX_AX_DEPTH),
            )
        if not isinstance(node, dict):
            raise ProtocolError(
                "bad_observation", "%s: AX node must be an object" % path
            )
        ref = node.get("ref")
        if not is_nonempty_str(ref) or not REF_RE.match(ref):
            raise ProtocolError(
                "bad_observation", "%s: node ref must look like @e1" % path
            )
        if not is_nonempty_str(node.get("role")):
            raise ProtocolError(
                "bad_observation", "%s: node role must be non-empty" % path
            )
        if not isinstance(node.get("name"), str):
            raise ProtocolError(
                "bad_observation", "%s: node name must be a string" % path
            )
        for flag in ("enabled", "visible"):
            if not isinstance(node.get(flag), bool):
                raise ProtocolError(
                    "bad_observation",
                    "%s: node %s must be a bool" % (path, flag),
                )
        children = node.get("children", [])
        if not isinstance(children, list):
            raise ProtocolError(
                "bad_observation", "%s: children must be an array" % path
            )
        for i, child in enumerate(children):
            stack.append((child, "%s.children[%d]" % (path, i), depth + 1))
        frame = node.get("frame")
        if frame is not None and not is_nonempty_str(frame):
            raise ProtocolError(
                "bad_observation",
                "%s: frame must be a non-empty string" % path,
            )
        unknown = set(node) - {
            "ref", "role", "name", "enabled", "visible", "children", "frame",
        }
        if unknown:
            raise ProtocolError(
                "bad_observation",
                "%s: unknown node field(s) %s" % (path, sorted(unknown)),
            )


def build_observation(url, title, target, ref_scope, nodes):
    """Build and validate an observation dict.

    ``target`` identifies the page/document (e.g. the Playwright target
    id); ``nodes`` is the AX tree (list of node dicts). Raises
    :class:`ProtocolError` on any schema violation.
    """
    obs = {
        "url": url,
        "title": title,
        "target": target,
        "ref_scope": ref_scope,
        "ax": nodes,
    }
    validate_observation(obs)
    return obs


def validate_observation(obs):
    """Validate an observation dict in place. Raises
    :class:`ProtocolError` with code ``bad_observation``."""
    if not isinstance(obs, dict):
        raise ProtocolError("bad_observation", "observation must be an object")
    # Envelope-level cap (B9): url/title/target/ref_scope are
    # page-derived (a hostile page controls document.title) and are not
    # action params, so the call-level scan does not cover them.
    for key in ("url", "title", "target", "ref_scope"):
        value = obs.get(key)
        if isinstance(value, str) and len(value) > MAX_PARAM_LEN:
            raise ProtocolError(
                "bad_observation",
                "observation.%s exceeds %d chars (len %d)"
                % (key, MAX_PARAM_LEN, len(value)),
            )
    if not is_nonempty_str(obs.get("url")):
        raise ProtocolError("bad_observation", "observation.url required")
    if not isinstance(obs.get("title"), str):
        raise ProtocolError("bad_observation", "observation.title required")
    if not is_nonempty_str(obs.get("target")):
        raise ProtocolError("bad_observation", "observation.target required")
    if not is_nonempty_str(obs.get("ref_scope")):
        raise ProtocolError("bad_observation", "observation.ref_scope required")
    nodes = obs.get("ax")
    if not isinstance(nodes, list):
        raise ProtocolError("bad_observation", "observation.ax must be an array")
    for i, node in enumerate(nodes):
        _check_node(node, "ax[%d]" % i)
    unknown = set(obs) - {"url", "title", "target", "ref_scope", "ax"}
    if unknown:
        raise ProtocolError(
            "bad_observation", "unknown field(s) %s" % sorted(unknown)
        )


def redact_for_history(obs):
    """Redact an older observation for the history/log.

    SPEC §4: only the newest observation's tree is actionable, so older
    trees must not survive in a form the agent could act on. The
    envelope (url, title, target, ref_scope) is kept for the audit
    trail; the tree is replaced with its node count.

    The retained ``ref_scope`` token is safe only because the daemon
    rotates it on every new observation (``RefScope.rotate``): a token
    from a redacted observation never validates against the live
    scope, so the log carries no actionable locator.
    """
    validate_observation(obs)

    def count(nodes):
        # Iterative: the tree can be hostile-nested (see MAX_AX_DEPTH).
        total = 0
        stack = list(nodes)
        while stack:
            node = stack.pop()
            total += 1
            stack.extend(node.get("children", []))
        return total

    return {
        "url": obs["url"],
        "title": obs["title"],
        "target": obs["target"],
        "ref_scope": obs["ref_scope"],
        "ax_redacted": True,
        "ax_node_count": count(obs["ax"]),
    }

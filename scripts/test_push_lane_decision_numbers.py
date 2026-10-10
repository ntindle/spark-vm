#!/usr/bin/env python3
"""Push-lane D-series decision-number uniqueness.

The push lane's design decisions are numbered (D3-D89+, plus
letter-suffixed sub-decisions like D56d) and cited across docs and code;
the number is the lane's cross-reference spine. A reused number silently
re-points every citation: the 20261010-0259 arch turn found D78 live as
two different decisions — "digest fanout" in
hosted/push_send_loop.py vs "per-candidate error isolation" in
hosted/push_sweep.py + docs/PUSH_SWEEP_SCHEDULER_DESIGN.md — after a
doc-only renumber (#1248) left the code side untouched. The digest
fanout is D89 now (docs/PUSH_LANE_CONVERGENCE_2026-10-10.md cites it).

This test fails when one D-number is pinned to two different decision
titles, so a collision breaks CI at the PR that introduces it instead
of drifting into the corpus.

Note: only pin *declarations* count — prose citations like the
convergence doc's "(... per-box fanout is unimplementable without a
schema change, D89)" are invisible to the test. That is deliberate:
citations don't define meaning; the declaration in
hosted/push_send_loop.py does.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The push lane's D-series lives in these files (decisions are pinned in
# the design docs and the modules that implement them).
CORPUS = [
    "docs/PUSH_SWEEP_SCHEDULER_DESIGN.md",
    "docs/PUSH_SENDER_SCHEMA_CONTRACT.md",
    "docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md",
    "docs/PUSH_LANE_CONVERGENCE_2026-10-05.md",
    "docs/PUSH_LANE_CONVERGENCE_2026-10-10.md",
    "hosted/push_enqueue.py",
    "hosted/push_events.py",
    "hosted/push_payload.py",
    "hosted/push_send_loop.py",
    "hosted/push_sender.py",
    "hosted/push_sweep.py",
]

# Pin-declaration shapes actually used in the corpus. Each entry is
# (pattern, kind) where kind is "num_first" (groups: num, title),
# "title_first" (groups: title, num), or "group" (groups: "D1/D2" list,
# title — every member gets the title).
_PIN_RES = [
    # - **D78 — digest fanout.** / **D78. Per-candidate error isolation ...**
    (re.compile(r"\*\*D(\d{1,3}[a-z]?)\s*[—–.\-]\s*([^*\n]{3,80})"),
     "num_first"),
    # #: D83 — attempts per (work item x device) ... /
    # #: D50/D56 — the outbox work-item outcome the loop claims.
    (re.compile(r"#:\s*((?:D\d{1,3}[a-z]?/?)+)\s*[—–\-]\s+([^\n]{3,80})"),
     "group"),
    # # -- D3/D89 fanout --  (each D-number in the group gets the title)
    (re.compile(r"#\s*--\s*((?:D\d{1,3}[a-z]?/?)+)\s*[—–\-]?\s*([^\n]{0,60})"),
     "group"),
    # # D79 — per-kind plaintext / # D8/D68 — ... / # D56c: the page ...
    # (the corpus's most common code pin shape; the separator must be
    # followed by whitespace so "D69-style" adjectives never match)
    (re.compile(r"#\s*((?:D\d{1,3}[a-z]?/?)+)\s*[—–\-:]\s+([^\n]{3,80})"),
     "group"),
    # - **Per-candidate error isolation (D78).**  (title = leading bold
    # text; the parenthesized number must sit INSIDE the same bold span —
    # a trailing "(D48e)" after the closing ** is a citation, not a
    # declaration. Skipped when the bold text itself starts with a
    # D-number — that's a cross-citation like "**D60. Reminder timing
    # (D8).**", whose D60 pin the first shape already captures)
    (re.compile(r"\*\*([^*]{3,80})\(D(\d{1,3}[a-z]?)\)[^*]*\*\*"),
     "title_first"),
    # """D84 — canonical-JSON serialization ... / """D56d/D80/D85 — gate-2: ...
    (re.compile(r'"""((?:D\d{1,3}[a-z]?/?)+)\s*[—–\-]\s+([^\n]{3,80})'),
     "group"),
    # D10: per-(box, hour) <= 3, ...  (contract-doc line-start pins)
    (re.compile(r"^D(\d{1,3}[a-z]?):\s*([^\n]{3,80})"), "num_first"),
]

_NUM_RE = re.compile(r"D(\d{1,3}[a-z]?)")


def _norm(title):
    t = title.lower().replace("`", "")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


# Known same-decision multi-title pins: one decision legitimately has
# several pin titles (facets pinned in different places). Each entry
# names its source so a future reader can verify the sameness claim —
# adding a title here instead of renumbering is a human decision the
# diff makes review-visible. A number with a title NOT in its set fails
# the suite, allowlisted or not.
FACETS = {
    # D8 reminder timing: the parameterized-timing pin
    # (docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md) + the min-TTL facet
    # (hosted/push_events.py:146).
    "8": {
        "reminder timing is parameterized not t 15m",
        "approvals with a shorter ttl never qualify for a reminder",
    },
    # D10 page budget: the contract pin
    # (docs/PUSH_SENDER_SCHEMA_CONTRACT.md:107) + the taxonomy restatement
    # (docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md).
    "10": {
        "per box hour 3 per owner hour 10 the bound caps",
        "page budget per box hour 3 per owner hour 10",
    },
    # D11 expiry no-page terminal: two taxonomy-doc wordings
    # (docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md:113,120).
    "11": {
        "expiry is a no page terminal",
        "expiry pages nothing",
    },
    # D50 inline-vs-outbox: the decision (hosted/push_enqueue.py:41) +
    # the outbox-work-item facet (:458) + the OUTCOME_QUEUED group pin
    # (hosted/push_send_loop.py:266, shared with D56).
    "50": {
        "inline vs outbox outbox",
        "the outbox work item device until fanout at send d51",
        "the outbox work item outcome the loop claims",
    },
    # D52 atomic reservation: the primitive + two comment facets
    # (all hosted/push_enqueue.py).
    "52": {
        "atomic reservation primitive",
        "one atomic statement over both scopes the scalar subquery not",
        "one atomic reservation over the applicable scopes",
    },
    # D53 dedup: the rule + the fast-path facet (hosted/push_enqueue.py).
    "53": {
        "dedup rule",
        "dedup fast path before the budget gate a replay consumes",
    },
    # D54 digest trigger/coalescing: the enqueue split + the over-budget
    # facet (hosted/push_enqueue.py) + the #1064 assembly restatement
    # (docs/PUSH_LANE_CONVERGENCE_2026-10-05.md).
    "54": {
        "digest enqueue split",
        "over budget audit row digest coalescing no send",
        "new 1064 digest assembly delivery",
    },
    # D55 VAPID sub: the pin + the contact facet (hosted/push_enqueue.py).
    "55": {
        "vapid sub",
        "the vapid sub contact d48e the plane operator owns it",
    },
    # D57 page-once: the DB invariant (hosted/push_enqueue.py:234, and
    # its comment restatement) + the predicate facet
    # (docs/PUSH_SENDER_SCHEMA_CONTRACT.md section 1.3).
    "57": {
        "page once is a db invariant",
        "page once as a db invariant see module docstring the",
        "the predicate covers suppressed terminal too",
    },
    # D61 superseded-audit key (page key + U+0000 "superseded"): the same
    # U+0000-suffix mechanism, written at gate-1 by the sweep (the audit
    # row + the lease-vested comment, hosted/push_events.py) and at
    # gate-2 by the send loop (hosted/push_send_loop.py).
    "61": {
        "gate 1 superseded audit",
        "the lease vested due but the re read finds the record",
        "the gate 2 audit key suffix page key u 0000 superseded",
    },
    # D68 candidate-SELECT hint: the design doc + the sweep module
    # (docs/PUSH_SWEEP_SCHEDULER_DESIGN.md, hosted/push_sweep.py:31).
    "68": {
        "the sweep s candidate select is a hint not a decision",
        "the candidate select is a hint not a decision",
    },
    # D69 bounded work: the design doc + the sweep module (:96).
    "69": {
        "bounded work per sweep overlap is safe not prevented",
        "bounded work per sweep the candidate query pages instead of",
    },
    # D71 DO-alarm retirement: the design doc + the sweep module.
    "71": {
        "the do alarm retirement rule made concrete d9 s rule",
        "do alarm retirement",
    },
    # D73 one clock: the design doc + the sweep module.
    "73": {
        "one clock one read pure arithmetic",
        "one clock one read",
    },
    # D77 digest suppression-audit key: the design doc + push_enqueue.
    "77": {
        "the digest s suppression audit uses a suffixed key",
        "the digest s suppression audit carries its own key",
    },
    # D78 per-candidate error isolation: the design-doc declaration
    # (with feature tag) + the sweep module's bare declaration
    # (hosted/push_sweep.py:60). Also pinned by
    # test_historical_collisions_stay_fixed below.
    "78": {
        "per candidate error isolation feature 20261006 1759",
        "per candidate error isolation",
    },
    # D79 per-kind plaintext: the mapping + its two constant blocks +
    # the section shorthand (all hosted/push_send_loop.py).
    "79": {
        "per kind plaintext",
        "plane authored fixed summaries for non approval kinds",
        "ttl pins for non approval kinds seconds",
        "plaintext",
    },
    # D80 gate-2 fail-safe: the pin + the predicate docstring + the
    # missing-record comment (all hosted/push_send_loop.py).
    "80": {
        "gate 2 fail safe",
        "gate 2 the page is suppressed unless the re read",
        "a missing record fails safe a page that cannot prove",
    },
    # D81 parked-not-dropped: the pin + the comment
    # (hosted/push_send_loop.py).
    "81": {
        "parked not dropped",
        "parked not dropped the row and its reservation stay",
    },
    # D82 retry pacing: the pin + the pacing comment + the _retry_stats
    # docstring facet (all hosted/push_send_loop.py).
    "82": {
        "retry pacing",
        "pacing not due yet",
        "retry count latest sent at for one page x box x device",
    },
    # D83 retry budget: the constant + two comment facets
    # (hosted/push_send_loop.py).
    "83": {
        "retry budget",
        "attempts per work item x device before the page dead letters",
        "the retry budget is spent dead letter without",
    },
    # D84 plaintext serialization: the module pin + the docstring
    # restatement (hosted/push_send_loop.py).
    "84": {
        "plaintext serialization",
        "canonical json serialization of a 970 payload mapping",
    },
    # D85 gate-2 named predicate: the pin + the shared gate-2 docstring
    # (hosted/push_send_loop.py).
    "85": {
        "gate 2 is a named predicate",
        "gate 2 the page is suppressed unless the re read",
    },
    # D87 digest reset: the pin + the comment (hosted/push_send_loop.py).
    "87": {
        "digest reset on delivery",
        "digest reset the window s coalescing is consumed by",
    },
    # D89 digest fanout: the bold declaration + the "# -- D3/D89
    # fanout --" group-comment shorthand (hosted/push_send_loop.py).
    # Also pinned by test_historical_collisions_stay_fixed below.
    "89": {
        "digest fanout",
        "fanout",
    },
    # D56 sender-loop contract: the "later slice" pin
    # (hosted/push_enqueue.py:131) + the OUTCOME_QUEUED group pin shared
    # with D50 (hosted/push_send_loop.py:266) — the loop claims the
    # outbox work item per D56a.
    "56": {
        "sender loop contract later slice",
        "the outbox work item outcome the loop claims",
    },
    # D56b terminal transaction: the pin + the docstring
    # (hosted/push_send_loop.py).
    "56b": {
        "terminal transaction",
        "one transaction the attempt audit row is already inserted",
    },
    # D56c fanout multiplicity: the pin + the docstring + the
    # per-device completion comment (hosted/push_send_loop.py:853).
    "56c": {
        "fanout multiplicity",
        "one row per box x device x attempt inserted immediately",
        "the page completes when every live device has a terminal",
    },
    # D56d gate-2 scope: the pin + the aid-kinds comment + the shared
    # gate-2 docstring (hosted/push_send_loop.py).
    "56d": {
        "gate 2 scope",
        "gate 2 applies to aid keyed kinds only",
        "gate 2 the page is suppressed unless the re read",
    },
    # D56e suppressed_terminal shape: the pin + the docstring
    # (hosted/push_send_loop.py).
    "56e": {
        "suppressed terminal shape",
        "a boundary extension row device all send columns",
    },
    # D56f retry state: the pin + three docstring/comment facets
    # (hosted/push_send_loop.py).
    "56f": {
        "retry state",
        "one row per box x device x attempt inserted immediately",
        "retry count latest sent at for one page x box x device",
        "the attempt row lands immediately after the post",
    },
}


def _pins():
    found = {}
    for rel in CORPUS:
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for line in text.split("\n"):
            for pat, kind in _PIN_RES:
                for m in pat.finditer(line):
                    if kind == "group":
                        nums = _NUM_RE.findall(m.group(1))
                        title = m.group(2).strip()
                    elif kind == "title_first":
                        title, num = m.group(1).strip(), m.group(2)
                        if re.match(r"D\d", title):
                            continue  # cross-citation, not a declaration
                        nums = [num]
                    else:
                        nums = [m.group(1)]
                        title = m.group(2).strip()
                    if not title:
                        continue
                    for num in nums:
                        found.setdefault(num, []).append(
                            (rel, _norm(title)))
    return found


def test_decision_numbers_are_unique():
    collisions = []
    pins = _pins()
    for num in sorted(pins, key=lambda x: (len(x), x)):
        titles = {}
        for rel, title in pins[num]:
            titles.setdefault(title, []).append(rel)
        allowed = FACETS.get(num, set())
        foreign = [t for t in titles if t not in allowed]
        # A new meaning for an allowlisted number is exactly one foreign
        # title — that must fail too, loudly, so extending FACETS is the
        # explicit human decision, not a silent collision shield.
        if len(foreign) > 1 or (num in FACETS and foreign):
            detail = "; ".join(
                "%r (%s)" % (t, ", ".join(sorted(set(titles[t]))))
                for t in sorted(foreign))
            collisions.append("D%s pinned to %d meanings: %s"
                              % (num, len(foreign), detail))
    assert not collisions, (
        "push-lane D-series collision(s) — one number, two decisions:\n"
        + "\n".join(collisions)
        + "\nRenumber the newer pin (see docs/PUSH_LANE_CONVERGENCE_2026-10-10.md"
          " for the D78->D89 precedent).")


def test_historical_collisions_stay_fixed():
    """Regression pin for the numbers that have collided before."""
    pins = _pins()
    titles_78 = {_norm(t) for _, t in pins.get("78", [])}
    # The docs declaration carries the feature tag; the sweep module's
    # own declaration is the bare title — same decision, two facets.
    assert titles_78 == {
        "per candidate error isolation feature 20261006 1759",
        "per candidate error isolation",
    }, ("D78 must stay the sweep's per-candidate error isolation, found: %r"
        % (titles_78,))
    titles_89 = {_norm(t) for _, t in pins.get("89", [])}
    assert "digest fanout" in titles_89, (
        "D89 must stay the sender loop's digest fanout, found: %r"
        % (titles_89,))

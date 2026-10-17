# Rollout alert-stack gap analysis, 2026-10-17: the #1557 remainder set after #1629

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `e7aeadb` (2026-10-17 ~12:0x CDT)
plus the GitHub API for issue state. Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do, not
promises. No rollout code ships in this analysis; nothing here deploys
anything.

This document is the follow-up the 2026-10-17 1059 slot could not finish:
that turn judged #1630/#1631/#1632 unbuildable in its scope ("no signal
source yet" for #1631) and shipped #1629 instead. It answers the exact
question left open: **what signal source does the alert stack have NOW,
and what does each remainder owe?**

## Non-overlap map (what this doc is not)

- `docs/GATE_CHANNEL_ROLLOUT_GAP_ANALYSIS.md` — the 2026-10-17 0729 gap
  analysis that filed #1629–#1634 (findings F-GR-1–F-GR-6, decisions
  D-GR-1–D-GR-4). This doc does not re-file; it re-verifies the three
  alert-stack remainders (#1630/#1631/#1632) against the tree AFTER
  #1629 merged.
- `docs/RELEASE_GATE_CHANNEL_DESIGN.md` — the G18 design (#609): §7 is
  the vision (fifth alert rule reads the collector's gate answer-age
  field), §8 names the `fleet status` line. Not amended here — the
  issue-body amendments are proposed as pointer comments.
- `docs/UPDATE_EVENT_REPORTING.md` — the G17 alert-rule home: §4 holds
  rules 1–4 + the rule-5 tail-discontinuity (#1006). The fold the G18
  design promised never landed — tracked on #1631.

## 1. Lane state (pinned 2026-10-17 ~12:0x CDT)

| Slice | State |
|---|---|
| S1a acceptance sketch (#830) | Shipped |
| S1b hook loop (#1034) | Shipped — `fleet/gate_hook.sh` writes the box status file every 60–120s |
| S1b toolset `_read_pin` cap (#1629) | **Shipped 2026-10-17** — PR #1648, merge `e7aeadb` |
| G17 S2 mapping rows (#1630) | OPEN — see F-GA-3 |
| Fifth alert rule, correlated gate-stale (#1631) | OPEN — see F-GA-1, F-GA-4, F-GA-5 |
| `fleet status` gate-stale line (#1632) | OPEN — see F-GA-2 |
| G15 S2 operator tooling / wave assignment (#1633), G15 S3 hosted (#1634) | OPEN — out of this turn's scope (multi-slot) |

## 2. Findings

### F-GA-1 — #1631's "no signal source" premise is stale (verified)

The 0729 analysis (F-GR-3) and the 1059 turn both recorded #1631 as
blocked on "the S1b collector slice". That is no longer true:

- `fleet/box_snapshot.py::_read_gate_status` (S1b, #1325, closed) reads
  the hook's status file and derives `frozen` + `answer_age_s` with
  per-field nulls and notes (never raises, never fabricates).
- `fleet/inventory.py` aggregates `gate{permitted_commit,
  permitted_toolset_pin, frozen, answer_age_s}` per box (L64, L304,
  L349–361) — the box-side snapshot's gate block feeds the fleet-side
  collection.
- Covered by `fleet/test_inventory.py:72/581/688-701` and
  `fleet/test_box_snapshot.py` gate tests — wired, not aspirational.

The collector's gate answer-age field EXISTS fleet-wide. **#1631 is
rule-only now**: a collector-reading alert rule (the G18-specified fifth
rule; the sixth row in the S1 alert set alongside #1006's
tail-discontinuity) that fires when `answer_age_s` is stale across the
fleet and pages once per fleet-wide outage, not per box. The
"collector slice first" precondition retires.

### F-GA-2 — #1632's named surface does not exist (verified)

#1632's acceptance names `fleet status`. No such command exists in the
tree: `fleet/console.py` is the watch dashboard (alerts/waves boards via
`fleet/api.py`); the CLI surface is `fleet events watch` /
`fleet events crosscheck`. `fleet/README.md:142` names the line as the
aspirational remaining S1b slice — the command itself is the missing
half.

The operator read surfaces that DO exist: the inventory JSON (the
collector), the `fleet events watch` alert board, `fleet events
crosscheck`. Minting a new `fleet status` command for one line is the
expensive option; the cheap, honest one is the fold in D-GA-2.

### F-GA-3 — #1630's emit leg is unblocked (verified)

`fleet/events.py:102-104` declares `skipped-frozen` /
`deferred-arc` as S2/S3-forward rows "with no legacy producer". The
hook loop already computes exactly the conditions that emit them:
`fleet-freeze` / `wave-not-live` (the freeze branch) and arc deferral —
box-local facts in the hook's trust domain. The build is a box-side
journal emit into `fleet/events.py::append_events`, the same journal
the S1 canonicalizer scans. #1630's acceptance stands as written;
no design work is owed.

### F-GA-4 — null-age semantics are unpinned (new)

A box whose hook never ran (or whose status file is unreadable) yields
`answer_age_s: null`. The correlated rule must pin this: **null means
"unknown", never "stale"** — otherwise the fleet-wide page fires on
collector gaps, not on gate silence. A hook-dead box is its own
incident, visible via the inventory note field, not via the stale rule.
(No issue owns this pin; it rides #1631's build.)

### F-GA-5 — the staleness threshold is unpinned (new)

The rule's "stale" predicate must exceed the hook interval (60–120s) +
sync cadence + ε, or it pages on normal sync jitter. Proposed:
`stale := answer_age_s > max(600s, 3 × hook_interval + sync_cadence)`.
The exact constant is #1631's builder's call; the inequality shape is
the pinned part. (No issue owns this pin; it rides #1631's build.)

### F-GA-6 — #1629 and the staleness rule are complementary (verified)

#1629's `_toolset_gate_cap` caps the convergence *target* at tick time
(reading the gate answer); the correlated rule measures answer
*freshness* (reading its age). Different axes, no overlap, no conflict.

## 3. Decisions

- **D-GA-1:** #1631's acceptance is amended — the "reads the collector's
  gate answer-age field (NOT the event stream)" half stands verbatim;
  the "when the S1b slice lands" precondition is retired, because the
  slice landed (#1325). The rule is build-ready: null-age = unknown
  (F-GA-4), threshold shape per F-GA-5.
- **D-GA-2:** #1632's acceptance is amended — per-box gate-stale folds
  into the alert board as the per-box line attached to (and beneath)
  the #1631 correlated page; no new `fleet status` command is owed.
  The alert must carry the affected box list to be actionable.
- **D-GA-3:** #1630's acceptance stands unchanged — build-ready, no
  design owed.

## 4. Amendments (pointer comments posted)

- #1630: build-ready, acceptance stands (F-GA-3).
- #1631: acceptance amended per D-GA-1 (collector exists; null + threshold pins).
- #1632: acceptance amended per D-GA-2 (alert-board fold, no new command).
- #1557: pointer comment carrying this doc's location.

No new issues filed — the three remainders are now precisely specified
builds, and their issue bodies carry the pins via the comments above.

# Rollout alert-stack gap analysis, 2026-10-17: the #1557 remainder set after #1629

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `e7aeadb` (2026-10-17 ~11:55 CDT)
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
  D-GR-1–D-GR-4). This doc does not re-file those; it re-verifies the
  three alert-stack remainders (#1630/#1631/#1632) against the tree AFTER
  #1629 merged.
- `docs/RELEASE_GATE_CHANNEL_DESIGN.md` — the G18 design (#609): §7 is
  the vision (fifth alert rule reads the collector's gate answer-age
  field, NOT the event stream); the line is named in §3 (L176) and §4
  (L207). Not amended here — the issue-body amendments are proposed as
  pointer comments.
- `docs/UPDATE_EVENT_REPORTING.md` — the G17 alert-rule home: §4 holds
  rules 1–4 + the rule-5 tail-discontinuity (#1006). The fold the G18
  design promised never landed — tracked on #1631.

## 1. Lane state (pinned 2026-10-17 ~11:55 CDT)

| Slice | State |
|---|---|
| S1a acceptance sketch (#830) | Shipped |
| S1b hook loop (#1034) | Shipped — `fleet/gate_hook.sh` writes the box status file every 60–120s |
| S1b toolset `_read_pin` cap (#1629) | **Shipped 2026-10-17** — PR #1648, merge `e7aeadb` |
| S1b collector half (#1325) | Shipped — `box_snapshot` reads the hook status file; `inventory` aggregates `gate.answer_age_s` |
| G17 S2 mapping rows (#1630) | OPEN — see F-GA-3 |
| Fifth alert rule, correlated gate-stale (#1631) | OPEN — see F-GA-1, F-GA-4, F-GA-5 |
| `fleet status` gate-stale line (#1632) | OPEN — see F-GA-2 |
| S2 box-side event-journal sink (#1649) | **FILED this turn** — the #1630 emit leg's missing dependency |
| G15 S2 operator tooling / wave assignment (#1633), G15 S3 hosted (#1634) | OPEN — out of this turn's scope (multi-slot) |

## 2. Findings

### F-GA-1 — #1631's "no signal source" premise is stale (verified, scoped)

The 0729 analysis (F-GR-3) and the 1059 turn both recorded #1631 as
blocked on "the S1b collector slice". In code terms that is no longer
true:

- `fleet/box_snapshot.py::_read_gate_status` (S1b, #1325, closed) reads
  the hook's status file and derives `frozen` + `answer_age_s` with
  per-field nulls and notes (never raises, never fabricates).
- `fleet/inventory.py` aggregates `gate{permitted_commit,
  permitted_toolset_pin, frozen, answer_age_s}` per box (L64, L304,
  L349–361) — the box-side snapshot's gate block feeds the fleet-side
  collection.
- Covered by `fleet/test_inventory.py:72/581/688-701` and
  `fleet/test_box_snapshot.py` gate tests — wired in the collection
  pipeline, not aspirational.

Two honest bounds ride with this (Architecture review):

- **Emitter cadence is manual.** `box_snapshot.py` has no timer/service
  in the tree; the only documented path is manual ("run on the box",
  `fleet/README.md:278-284`). The rule's signal is only as fresh as the
  operator's pull cadence. #1631's build must either ship a snapshot
  cadence + estate pull or gate on the existing `_is_eligible` staleness
  window (inventory.py:664) so the rule degrades loudly when the
  collection goes stale.
- **The record drops `emitted_at`.** `box_snapshot.py:187` emits it;
  `inventory.py`'s record schema (L64) does not carry it. `answer_age_s`
  in the record is therefore *emit-time* age, and the rule cannot
  correct for pull latency — the threshold shape in F-GA-5 must cover
  pull latency as well as hook interval and sync cadence.

**#1631 is rule-only now**, with the cadence precondition and the
dropped-field seam named above. The "collector slice first"
precondition retires.

### F-GA-2 — #1632's named surface does not exist (verified)

#1632's acceptance names `fleet status`. No such command exists in the
tree: `fleet/console.py` is the watch dashboard (alerts/waves boards via
`fleet/api.py`); the CLI surface is `fleet events watch` /
`fleet events crosscheck` (`inventory.py:981-1044` subparsers:
collect/inventory/drift/rebuild/prune/events/api). `fleet/README.md:142`
names the line as the aspirational remaining S1b slice — the command
itself is the missing half.

The operator read surfaces that DO exist: the inventory JSON (the
collector), the `fleet events watch` alert board, `fleet events
crosscheck`. Minting a new `fleet status` command for one line is the
expensive option; the cheap, honest one is the fold in D-GA-2.

### F-GA-3 — #1630: mapping rows build-ready, emit leg needs the S2 sink (verified)

Separating what is true from what is not (both role reviews):

- **True:** the G17 outcome rows `skipped-frozen` / `deferred-arc` are
  reserved in the vocabulary at `fleet/events.py:102-103` — the mapping
  rows themselves are specified and writable now.
- **Not true:** the emit leg. The reason tokens `fleet-freeze` /
  `wave-not-live` exist **nowhere** in the tree (only in the design doc)
  — `gate_query.py`'s implementation vocabulary is `no-signal: …` /
  `freeze flag set` / `gate ok`, with the wave-not-live branch folded
  into `component_permitted()` as a boolean. Arc deferral is computed
  **nowhere** in the hook/gate path (`gate_hook.sh` is: run query →
  write status file → print summary; `box_snapshot.py:184` stubs
  `arc_active: None` as "the G15 gate hook's slice (not S1)").
- **The emission point does not exist.** The hook's journal summary goes
  to the box's **systemd journal**; `fleet/events.py::append_events`
  writes the **operator's fleet store**, which is box-unreachable and
  has no box→estate transport. The box-side journal (`update-events.jsonl`,
  `UPDATE_EVENT_REPORTING.md` §S2) exists only in the design doc.

So #1630's emit leg owes: (a) the implementation-reason → G17-outcome
token mapping, (b) the S2 box-side journal sink + box→estate transport,
(c) arc-deferral detection. (b) is filed this turn as **#1649**;
#1630's acceptance is amended to name it as the emit-leg dependency.

### F-GA-4 — null-age semantics are unpinned (new)

`answer_age_s` has two shapes of absence: `null` (hook never ran or the
status file is unreadable) vs growing non-null (a dead hook whose file
ages). The rule must pin this: **null means "unknown", never
"stale"**; a dead hook's growing age is legitimately pageable stale
signal. Hook-dead is otherwise visible via the inventory note field.
(No issue owns this pin; it rides #1631's build.)

### F-GA-5 — the staleness threshold is unpinned (new)

The rule's "stale" predicate must exceed the hook interval (60–120s) +
sync cadence + pull latency + ε (per the F-GA-1 dropped-`emitted_at`
seam), or it pages on normal sync jitter. Proposed shape:
`stale := answer_age_s > max(600s, 3 × hook_interval + sync_cadence +
pull_latency)`. The exact constant is #1631's builder's call; the
inequality shape is the pinned part. (No issue owns this pin; it rides
#1631's build.)

### F-GA-6 — #1629 and the staleness rule are complementary (verified)

#1629's `_toolset_gate_cap` caps the convergence *target* at tick time
(reading the gate answer); the correlated rule measures answer
*freshness* (reading its age). Different axes, no overlap, no conflict.

## 3. Decisions

- **D-GA-1:** #1631's acceptance is amended — the "reads the collector's
  gate answer-age field (NOT the event stream)" half stands verbatim;
  the "when the S1b slice lands" precondition is retired (it landed in
  #1325, scoped per F-GA-1). The rule is build-ready: cadence
  precondition (snapshot cadence + estate pull, or `_is_eligible`
  gating), null-age = unknown (F-GA-4), threshold shape per F-GA-5.
- **D-GA-2:** #1632's acceptance is amended — per-box gate-stale folds
  into the alert board as the per-box line attached to (and beneath)
  the #1631 correlated page; no new `fleet status` command is owed.
  The alert must carry the affected box list to be actionable.
- **D-GA-3:** #1630's acceptance is amended — the mapping rows
  (`skipped-frozen` / `deferred-arc` vocabulary) are build-ready now;
  the emit leg names **#1649** (S2 box-side journal sink + box→estate
  transport) as its dependency, plus the reason-token mapping and
  arc-deferral detection design.

## 4. Issues filed and amendments (pointer comments posted)

- **#1649 filed this turn:** S2 box-side event-journal sink +
  box→estate transport (`UPDATE_EVENT_REPORTING.md` §S2: a dedicated
  box-side journal both updaters append in-shape, bounded 12k/10k
  discipline, read by the collector). #779 (the G16/G17 umbrella) is
  closed; no open tracker owned this. #1630's emit leg depends on it.
- #1630: comment — acceptance amended per D-GA-3 (mapping rows now,
  emit leg depends on #1649).
- #1631: comment — acceptance amended per D-GA-1 (collector exists;
  cadence precondition; null + threshold pins).
- #1632: comment — acceptance amended per D-GA-2 (alert-board fold, no
  new command).
- #1557: pointer comment carrying this doc's location.

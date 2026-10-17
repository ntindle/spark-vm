# Collector signal-contract gap analysis (2026-10-17)

**Scope:** the fleet collector's operator-facing signal contract — what
`fleet/inventory.py` records promise vs what the S1 alert rules
(`docs/UPDATE_EVENT_REPORTING.md` §4) and the operator surfaces actually
need. Open-source track (operator estates), serving #1631 (the G18 §7
fifth alert rule) and #1632 (`fleet status` gate-stale line).

**Pinned to:** main `0a70109b` (2026-10-17). Follow-up to the 2026-10-17
alert-stack analysis (`ROLLOUT_ALERT_STACK_GAP_2026-10-17.md`), which
named these seams but scoped them to #1631's rule.

## Vision

The design corpus promises the collector as the fleet's single
signal source:

- `UPDATE_EVENT_REPORTING.md` §4 S1's five alert rules are evaluated on
  every collect: rules 1–4 read the event journal; rule 5, tail
  discontinuity (#1006), fires from the collector's continuity check.
  The correlated gate-stale rule (#1631, specified by G18 §7) must
  read the collector's gate answer-age field, because a fleet-wide
  sync outage is invisible in the event stream by design (G17 §3: the
  S1 canonicalizer infers nothing from gate silence).
- The inventory table and the crosscheck surface render per-box gate
  state (`frozen`) with an explicit three-state rendering
  (`inventory.py`: "yes"/"no"/"n/a").
- The record schema (`inventory.py`) carries `observed_at` (the
  collector's receive time) alongside each box's signals.

## State (verified on main `0a70109b`)

The pipeline is `fleet/box_snapshot.py` (box emits) →
`fleet/inventory.py` collect (operator aggregates). Ground truth:

- `box_snapshot.py:187` emits `emitted_at` (snapshot emission, box
  clock) and `gate: {frozen, answer_age_s}` — where `answer_age_s` is
  computed on the box as `now − generated_at` of the hook status
  file, floored at 0 (`_read_gate_status`, box_snapshot.py:54). The
  hook file's own `generated_at` is **not** carried in the snapshot.
  Per-field nulls with prose notes are folded into the snapshot's
  top-level `note` (`"; "`-joined).
- `inventory.py` builds the record with `observed_at` (collect time)
  and copies `gate.frozen` / `gate.answer_age_s` verbatim
  (inventory.py:358-361). **It drops `emitted_at`** — no reference
  anywhere in inventory.py — and carries no `gate.generated_at`.
  The record's notes get `"box snapshot note: %s"`, so the per-field
  prose notes survive, stringly-typed.
- Eligibility (`_is_eligible`, inventory.py:664) and the table's
  "stale" flag are computed on `observed_at` — collector-freshness,
  not box-freshness.

## Findings

- **F-SC-1 — `emitted_at` is destroyed at the collector boundary.**
  The box's own emission clock never reaches the record. The operator
  cannot distinguish "box emitted 2 min ago, collector was slow" from
  "box emitted 2 h ago" — `observed_at − emitted_at` (the
  transport/collection-delay signal) is uncomputable from the record.
- **F-SC-2 — `answer_age_s` is an emit-time age frozen into the
  record.** #1631's acceptance ("reads the collector's gate
  answer-age field") cannot be implemented literally on the stored
  field: by the time any rule or surface reads the record, the stored
  age is stale by (collect latency + read latency). The true age is
  `now − generated_at`, but `generated_at` is not carried — so the
  rule has no trustworthy input today, only the frozen convenience
  value.
- **F-SC-3 — null semantics are producer-documented, consumer-unpinned.**
  `_read_gate_status` defines per-field nulls (a bad timestamp nulls
  only the age; a bad state nulls only frozen). Consumers handle nulls
  by accident, not by contract: the table renders "n/a" explicitly
  (inventory.py:731), the crosscheck falls null `frozen` through to
  `"unexplained"` (inventory.py:850) rather than misreading it as
  live — correct behavior today, but nothing pins it, and the
  null-age = unknown pin (F-GA-4, via D-GA-1) was scoped to #1631's
  rule only.
- **F-SC-4 — the gate notes reach the operator but unstructured.**
  "gate status file not present" vs "answer.state not frozen/live"
  vs "generated_at in the future" all arrive as one `"box snapshot
  note: ..."` string. Fine for a human reading notes; no structured
  consumer should ever parse it (none does today).
- **F-SC-5 — eligibility is collector-freshness, which is the wrong
  clock for gate staleness.** A box whose snapshot is fresh at the
  collector but whose hook answer is old looks "eligible" while its
  gate answer is stale. The staleness question needs box clocks
  (`emitted_at`, `generated_at`); the eligibility question needs the
  collector clock (`observed_at`). The record currently has only the
  second.

## Decisions

- **D-SC-1 — carry `gate.generated_at` on the inventory record**
  (ISO 8601, the hook status file's own timestamp, null when the
  box couldn't parse one). Readers that need truth recompute age as
  `now − generated_at`; `answer_age_s` stays as the box-computed
  convenience (emit-time age, clearly labeled as such in the doc).
  Recomputed age is `max(0, now − generated_at)` in aware UTC —
  negative deltas are clock skew, floored exactly like
  `_read_gate_status` floors them (box_snapshot.py:98-101), so the
  rule and the surface can never diverge on the same record.
- **D-SC-2 — carry `emitted_at` on the inventory record** (the
  snapshot's own emission timestamp, box clock). `observed_at` keeps
  its meaning (collector receive time). The difference becomes the
  transport/collection-delay signal; both clocks stay visible. Box
  and collector clocks are unsynchronized, so the delta inherits the
  module's existing skew discipline: `FUTURE_SKEW_TOLERANCE_S = 300`
  (flag, don't drop; ordering never trusts box clocks) — a negative
  `observed_at − emitted_at` is skew, not time travel.
- **D-SC-3 — pin the null contract for gate fields, generalizing
  F-GA-4 / D-GA-1:** null `answer_age_s`/`generated_at` = unknown, never stale
  by itself (hook-dead is its own incident, visible via the notes);
  null `frozen` = undecidable, i.e. no evidence — alert rules and
  surfaces must treat it as "no evidence", never as "live" or
  "frozen". This pins the behavior consumers already exhibit
  (table "n/a", crosscheck "unexplained") as the contract.
- **D-SC-4 — #1631's acceptance is amended:** the correlated
  gate-stale rule reads `generated_at` (recomputing age at eval
  time), not the stored `answer_age_s`. The F-GA-5 staleness
  threshold (`max(600s, 3×hook_interval + sync_cadence)`, pinned via
  D-GA-1) applies to the recomputed age (whether pull latency stays
  inside that formula now that `emitted_at` makes it computable is
  #1631's build-thread detail, not this doc's).
- **D-SC-5 — no structured gate-note schema is owed in S1.** The
  prose notes already reach the operator; no consumer parses them.
  If a future rule needs a machine-readable gate-failure class, that
  rule's slice owns the schema.

## Build slices filed

- **#1660** (p3, open-source) — record-schema additions: emit
  `gate.generated_at` from `box_snapshot.py` (surfaced from
  `_read_gate_status`, which parses it today and discards it), then
  carry `gate.generated_at` + `emitted_at` through `inventory.py`
  (D-SC-1, D-SC-2), with tests pinning the pass-through, the null
  cases, and the "age is recomputed, not stored" doc note. Unblocks
  #1631's amended acceptance (D-SC-4). Filed from this analysis.

## Honest summary

The collector's box-signal half works — per-field nulls, prose notes,
three-state `frozen` rendering — but it was built for human-readable
tables, not for rules. Two timestamps the box already emits never
reach the record (`emitted_at`, the hook file's `generated_at`), and
the one age the record does carry is frozen at emission time. Any
rule that needs to know "how stale is this box's gate answer *right
now*" — which is exactly what the fifth alert rule is — cannot be
built honestly on the current schema. The slice above adds the two
fields; the decisions pin what the nulls mean so every future rule
reads the same contract.

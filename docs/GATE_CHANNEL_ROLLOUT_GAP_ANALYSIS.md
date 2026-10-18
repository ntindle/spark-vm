# Gate-channel rollout remainders — gap analysis (2026-10-17, #1557)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `ff2ece425af88b32babbad5d5c455db1a8995d7d`
(2026-10-17 ~07:3x CDT). Issue/PR numbers are GitHub references as of
2026-10-17 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. No code ships in this analysis; nothing here deploys
anything.

This is the **box layer**: the #777 (G15/G18) rollout controller and
release-gate channel for the operator's own N-box fleet — release
documents, the box-side gate, the hook loop. It is NOT the tenant-plane
lane (#1261, `fleet/plane_deploy.py`): the #1261 wave machine assigns
waves for tenant *planes*; nothing in `fleet/` computes wave assignment
for boxes (`fleet/events.py:340` — `"rollout": None,  # G15 S2 assigns
waves`; `fleet/api.py` — `/fleet/waves` "unavailable until G15 S2").
Box rollout and tenant-plane rollout share vocabulary, not machinery.

**Non-overlap map (what this doc is not):**
- `docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` — the 2026-09-28 vision
  donor (G15–G18). Consumed, not replaced.
- `docs/ROLLOUT_CONTROLLER_CONVERGENCE_2026-10-11.md` + the
  `TENANT_PLANE_ROLLOUT_CONTROLLER_GAP_ANALYSIS.md` — the #1261
  tenant-plane lane. Distinct layer; its S2 wave machine is not this
  doc's G15 S2.
- #1557 — the in-issue remainder enumeration this analysis pins to a
  tree. Every remainder below was re-verified against `ff2ece42`; where
  #1557's enumeration stands verbatim it is cited, not re-argued.
- #1543 — the G15 S3 freeze-hold event producer; the separate tracker
  for that one emitter. **LANDED 2026-10-18** — `fleet/gate_publish.py`
  emits `kind: freeze-hold` on freeze flip/clear.
- The 20261017-0659 distribution turn's #1627 honesty fix + E2E —
  same fleet lane, plane layer; does not move any box-layer remainder.

## 1. The vision (#777, S1–S3, box layer)

A rollout controller publishes controller-signed `gate.json` release
documents; each box's hook caps its updaters at the max-permitted
version and fails closed (no signal = frozen). Build slices:

- **S1a** — gate publish/query/sync loop, `pending_range()` cap on the
  repo updater, freeze-drill test. SHIPPED via #830.
- **S1b** — the rest of the box side: hook-loop timer unit (60–120s,
  local status write), `toolset-update.sh` `_read_pin` cap, G17 S2
  mapping rows (`skipped-frozen` / `deferred-arc`) for the hook's log
  shapes, the fifth fleet alert rule (correlated gate-stale, read from
  the collector's answer-age field). Hook loop shipped via #1034; the
  other three slices did not.
- **S2** — operator tooling: `fleet freeze`/`unfreeze`/`promote`/`halt`
  writing through `gate_publish.py`, hook status file as a G16 collect
  artifact, key-rotation UX, multi-component registry UX, plus the
  computing-assignment half of the controller (waves; G15 S1's
  "controller wave assignment (canary → waves)" lives in code as
  reserved-to-S2).
- **S3** — hosted remainders: freeze-hold emitter (#1543 owned it;
  landed 2026-10-18),
  per-tenant gate documents, per-tenant waves (H11), hot-standby
  publisher, no-consent-gate (G13 §1/T4).

#777 closed 2026-10-05 with S1a + the S1b hook loop shipped. The rest
has no implementation and — until this analysis — no per-slice tracker.

## 2. Vision vs state (pinned 2026-10-17)

| Vision | Current state |
|---|---|
| The repo updater honors the release gate (`pending_range()` cap) | **SHIPPED (S1a, #830):** the repo updater is capped. |
| The toolset updater honors the release gate (`_read_pin` cap) | **UNBUILT.** `fleet/README.md:141` still names it a remaining S1b slice; `deploy/toolset-update.sh`'s only gate is the *idle* gate — no release-gate consultation. (Finding F-GR-1, filed as #1629.) |
| The hook loop keeps the gate answer fresh and visible | **SHIPPED (S1b, #1034):** `fleet/gate_hook.sh` writes the box's self-evaluated answer to `/var/lib/sparkvm/gate/status.json`. |
| Hook log shapes map into the G17 outcome vocabulary | **UNBUILT.** `fleet/events.py:102-103` declares `skipped-frozen` / `deferred-arc` as "S2/S3-forward outcomes with no legacy producer" — the vocabulary is reserved, no producer emits it. (Finding F-GR-2, filed as #1630.) |
| A fleet-wide gate-sync outage pages as one incident (correlated gate-stale, the fifth alert rule) | **UNBUILT.** `docs/UPDATE_EVENT_REPORTING.md` §4 holds rules 1–4 + rule-5 tail-discontinuity (#1006); the G18 §7-specified fifth rule never landed, and the G18 §7 "pointer comment on #777 — at ship" can never land on the closed issue. (Finding F-GR-3, filed as #1631.) |
| The operator sees gate staleness in `fleet status` | **UNBUILT.** `fleet/README.md:141` names it a remaining S1b slice; `fleet/console.py` contains no gate rendering at all. (Finding F-GR-4, filed as #1632.) |
| The operator drives releases through `fleet freeze`/`unfreeze`/`promote`/`halt` | **UNBUILT.** `gate_publish.py` carries the S1a document fields (`--freeze`, `key_id` dual-accept); the operator-tooling slice has no open tracker. (Finding F-GR-5, filed as #1633.) |
| The controller assigns waves (canary → waves) | **UNBUILT.** `fleet/events.py:340` (`"rollout": None,  # G15 S2 assigns waves`), `fleet/api.py`'s `/fleet/waves` "unavailable until G15 S2". Operator-estate wave assignment folded into #1633; the hosted per-tenant waves live on #1634 (F-GR-6). |
| Freeze flips emit `kind: freeze-hold` into the fleet journal | **LANDED 2026-10-18.** `fleet/gate_publish.py` emits `kind: freeze-hold` on freeze flip/clear into the fleet journal (`--journal`, default `events.jsonl` next to the gate document); the rows feed the status-page feed's §3.2 rollout rows (issue #1543). |
| Per-tenant gate documents, per-tenant waves, hot-standby publisher, no-consent-gate | **UNBUILT.** The S3 hosted remainders beyond the freeze-hold emitter; per-tenant waves cross-reference H11. #1634 owns the hosted per-tenant instantiation only — operator-estate wave assignment + tooling is #1633 (F-GR-5). (Finding F-GR-6, filed as #1634.) |

## 3. Findings

- **F-GR-1 — the toolset updater is not release-gated.** The S1a slice
  capped only the repo updater. `deploy/toolset-update.sh` gates on
  idle/lock/quiet-hours, never on the release document. Filed as #1629.
- **F-GR-2 — the G17 S2 mapping rows have no producer.** The outcome
  vocabulary was closed by design (§2: "closed"); the four outcomes
  with legacy producers are emitted; `skipped-frozen` ("the G18 gate
  said frozen") and `deferred-arc` await the hook leg. Any future
  collector inferring gate silence from these outcomes today would
  count only silence. Filed as #1630.
- **F-GR-3 — the fifth alert rule never landed.** UPDATE_EVENT_REPORTING
  §4's four rules + rule-5 tail-discontinuity (#1006) are the S1 alert
  set; the G18 §7 fifth rule (correlated gate-stale, read from the
  collector's gate answer-age field, NOT the event stream) is still
  design-only. The owed G18 §7 pointer comment ("on #777 — at ship")
  can never land on the closed issue; #1557's item 4 named it owed.
  The pointer comment was posted on #1557 at ship time:
  https://github.com/ntindle/spark-vm/issues/1557#issuecomment-6233989786
  (the G18 §7 pointer cannot land on the closed #777).
  Filed as #1631.
- **F-GR-4 — `fleet status` has no gate-stale line.** `fleet/console.py`
  returns zero hits for `grep -i gate` — there is no gate rendering at all.
  The hook writes answer + age + source to the box-local status file;
  the operator has no fleet-wide read surface for it.
  Filed as #1632.
- **F-GR-5 — G15 S2 has no owner.** Operator tooling
  (`freeze`/`unfreeze`/`promote`/`halt` through `gate_publish.py`,
  key-rotation UX, health gates on G17 events + G16 inventory) and the
  computing wave assignment for the operator's own estate both sit in
  S2. #1261 owns the tenant-plane template controller (plane layer);
  this issue owns the operator-estate wave assignment and tooling. The
  hosted per-tenant instantiation — per-tenant gate documents,
  per-tenant waves (H11), hot-standby publisher, no-consent-gate — is
  S3 and lives on #1634 (see F-GR-6), not here. Filed as #1633.
- **F-GR-6 — G15 S3 hosted remainders beyond the emitter have no
  tracker.** #1543 owned only the freeze-hold emitter (landed
  2026-10-18). Per-tenant gate
  documents, per-tenant waves (H11), the hot-standby publisher (G18 §8
  reserves it to S3 — the controller is a single point of *update*
  failure by design), and the no-consent-gate (G13 §1/T4) are unowned.
  Filed as #1634.

## 4. Decisions pinned

- **D-GR-1:** each unowned remainder above gets exactly one tracker
  (#1629–#1634; the freeze-hold emitter was #1543, landed 2026-10-18). The S2/S3
  split is pinned: #1633 owns operator-estate wave assignment +
  tooling; #1634 owns the hosted per-tenant instantiation (per-tenant
  gate documents, per-tenant waves under H11, hot-standby publisher,
  no-consent-gate) — no slice lives in two trackers. #1557 stays open
  as the lane umbrella — the acceptance it set ("each remainder either
  lands, or the design corpus records it as deferred with an explicit
  owner") is the exit criterion this analysis inherits.
- **D-GR-2:** the in-repo vocabulary is NOT reopened by this analysis.
  The `skipped-frozen` / `deferred-arc` reservation stands; #1630 is a
  producer-build issue, not a vocabulary issue.
- **D-GR-3:** the fifth alert rule, when built, reads the collector's
  gate answer-age field (per G18 §7), not the event stream — a
  fleet-wide sync outage is invisible in the event stream by design
  (G17 §3: the S1 canonicalizer infers nothing from gate silence).
- **D-GR-4:** S3's per-tenant waves cross-reference H11; S3's
  no-consent-gate cross-references G13 §1/T4. Both wait on their
  cross-referenced lanes, recorded on #1634 — not as reasons to leave
  the remainders untracked.

## 5. Closed since the 2026-10-16 enumeration

Nothing closed; #1557's enumeration stands verbatim, re-verified at
`ff2ece42`. The two design-doc footers already re-point at #1557/#1543
(the 20261016-0229 docs turn), so no footer work is owed in this
analysis. The only lane movement since the enumeration is the
20261017-0659 turn's #1627 (plane layer) — it does not move any
box-layer remainder.

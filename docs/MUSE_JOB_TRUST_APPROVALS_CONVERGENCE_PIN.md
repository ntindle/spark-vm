# Muse-job trust + approvals lane — convergence pin after #1394, #1396, #1430

Convergence pin, 2026-10-13, at main `e1737b8`. Lane: #1372 (muse-job
approvals operator surface), #1394 (live-job trust adoption), built on
#225/#789 (the `msp_approval` library module) and #227 (the supervise
path). This re-verifies
`docs/MUSE_JOB_APPROVALS_OPERATOR_SURFACE_GAP_ANALYSIS.md` (the #1397
analysis, pinned 2026-10-12 at `5778a76`) against the state after the
three ships that closed its open remainders: #1394 (trust voucher
grant, PR #1428), #1396 (listing through a supervisor-held session, PR
#1408), and #1430 (session-exited watch signal for dead muse processes,
issue #42). All claims verified by code read at the pin.

## What #1397 said (2026-10-12)

- **F-MSP-1:** #1372's three body items are all shipped — close the
  issue as shipped, don't hold it open for the remainders.
- **F-MSP-2:** the one explicitly-named remainder — listing through a
  supervisor-held session is not wired — filed as #1396 (this turn).
- **F-MSP-3:** live-job trust adoption is the only open trust-policy
  gap — #1394 (open, p3), already well-specified (operator-initiated,
  manager-side, journaled grant). No new trust-policy issues.
- **F-MSP-4:** the phone-approval loop is out of this lane's scope —
  #849 owns plane push → device; the muse-job lane ends at the
  operator's terminal.
- **D-MSP-1:** close #1372 via the analysis's Closes keyword.
- **D-MSP-2:** #1394 is the complete trust-policy remainder.
- **D-MSP-4:** trust prompts stay fail-closed by default (the #211
  incident's standing decision); any future widening of the
  `--trust-workspace` voucher's scope needs its own issue and opt-in.

## Verified state at main `e1737b8`

- **#1372 CLOSED** (as D-MSP-1 directed). **#1394 CLOSED** — the
  voucher-grant path shipped as PR #1428: `muse-job trust <slug>` (operator-initiated, manager-side, journaled
  via `method = "trust_workspace"`), the gate reads the grant, the
  README's standing trust-policy section documents the adoption ceremony.
  **#1396 CLOSED** — supervisor-mediated listing shipped as PR #1408
  (issue closed via the merge commit `850a8aa9`'s reference).
- **The trust gate is still fail-closed** (`muse-job/bin/muse-job`
  `_answer_trust_prompt`, line ~3092): `job.get("trust_workspace") is
  not True` → return False. A missing key (legacy records), `False`,
  the hand-edited `"false"` string (truthy but not `True`), and a
  missing/unreadable/corrupt record (the `load_job` try/except) all
  refuse. D-MSP-4 holds: no voucher-scope widening found; the scope is
  still the job's own workdir, re-derived from the slug.
- **#1430's session-exited signal covers the TUI watchdog path only.**
  `_pane_pid` + `_pane_tree_has_tui` walk the pane's process tree for a
  muse-family process; fail-closed (inconclusive reads keep the generic
  `tui-dead` signal). The MSP supervise path has no equivalent
  dead-session marking — see F-MSP-7.

## Findings

- **F-MSP-6 — the trust lane is complete, and #1427's premise is
  refuted.** #1394's grant closed the last named remainder (D-MSP-2
  confirmed, not re-derived). #1427 (p3) claimed the gate-side
  fail-closed read for legacy records has no regression test (its
  neuter — `== False` instead of `is not True` — fails open on
  key-less records, "no test catches it"). That premise is false at
  the pin: `muse-job/tests/test_trust_workspace_optin.py::
  test_answer_refused_when_key_missing` seeds a legacy record (no
  `trust_workspace` key) through the e2e gate test, asserts the gate
  refuses (`is False`) and sends no keys (`calls == []`) — and kills
  the neuter: on the `== False` copy the test goes red (verified by
  neuter run this turn — the neutered function proceeds past the
  guard and returns `True`). #1427's neuter demonstration ran only
  `test_trust_live_grant.py` (grant-path tests, which cannot see the
  gate check); the gate path was already covered. #1427's concrete
  ask is therefore already satisfied — closed as covered this turn
  with the neuter evidence in the pointer comment.
- **F-MSP-7 — NEW: the MSP request ledger has no dead-supervisor
  tombstone.** Ledger entries are removed only on decide/answer/refuse
  (`_msp_request_ledger_remove`, muse-job ~5905–5913; call sites ~6190,
  ~6231). `cmd_status` renders `"requested":
  _msp_request_ledger_read(slug)` (~4894) with **no supervisor-aliveness
  check**, while the direct paths fail loudly when the supervisor is
  dead: `approvals` raises "the supervisor may have died between the
  liveness check and the drain", `decide`/`answer` raise "the supervisor
  may have died ... the request stays queued". If the supervisor dies
  mid-turn with pending ledger entries, `status` advertises phantom
  "requested" approvals indefinitely — the operator can queue a decide
  that no live drain will ever execute. The `#1430` session-exited
  signal is the precedent for the fix direction: qualify `status`'s
  `requested` with `_msp_supervisor_alive` (~3879), or tombstone the
  ledger when the supervise loop exits with entries pending. →
  **filed as #1434** (this turn).
- **F-MSP-8 — F-MSP-4's boundary still holds.** No phone-loop drift into
  this lane; #849 still owns plane push → device.

## Decisions

- **D-MSP-5:** the ledger-staleness gap (F-MSP-7) is this turn's filing;
  nothing else from this lane.
- **D-MSP-6:** #1427 is closeable-as-covered (premise refuted by the
  existing neuter-sensitive gate test); the trust lane has no open
  items.

## Filed this turn

- #1434 (enhancement, area:muse-job, track:open-source, priority:p3):
  `muse-job status` shows stale MSP approval/user-input requests after
  the supervisor dies — ledger needs a dead-supervisor tombstone or
  `status` must qualify `requested` with supervisor aliveness (F-MSP-7).

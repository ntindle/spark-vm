# Muse-job approvals operator surface — vision vs state after #1372 slices 1–3

Gap analysis, 2026-10-12, pinned to main `5778a76` (PR #1395). Lane: #1372
(muse-job operator surface for MSP approvals), built on #225/#789
(the `msp_approval` library module) and #227 (the supervise path).

## The vision (what the issues asked for)

- **#1372 item 1:** `muse-job` grows `approvals`/`decide`/`answer`
  subcommands; `muse-job status` surfaces blocked approvals/inputs so the
  operator answers them "in one place" instead of entering tmux or using
  the raw smoke CLI (`msp_approval.py`) with a raw session id.
- **#1372 item 2:** the supervise path plugs `handle_approval_request` /
  `handle_user_input_request` into `MSPHost.set_request_handler` so prompts
  surface to the operator instead of stalling invisibly.
- **#1372 item 3:** a standing trust-policy opt-in whose shape is decided,
  not improvised — `--yolo` maps to `allowAll` for tool approvals, but
  trust prompts stay fail-closed per the recorded #211 decision (the
  workspace-trust prompt that blocked the #211 incident's unattended
  resume). The lane decided: `muse-job spawn --trust-workspace`, a
  spawn-time operator voucher covering the job's own workdir only.
- **The lane's outer boundary:** #849 owns the phone-approval loop
  (plane push → device). The muse-job lane ends at the operator's
  terminal.

## Verified state at main `5778a76`

All three #1372 slices are present and wired (verified by code read +
`muse-job --help` + local test run):

- **Slice 1 (subcommands):** `approvals` / `decide` / `answer` are real
  subcommands (`muse-job/bin/muse-job:6025-6057`; `cmd_approvals` at
  5274, `cmd_decide` at 5351, `cmd_answer` at 5408). `muse-job status`
  fetches pending approvals/user-inputs best-effort
  (`_msp_pending_for_status`, 5235; called from the status path at 4589)
  and the reader-thread callbacks keep a request ledger that `status`
  renders while the supervisor holds the session
  (`_msp_on_approval_requested` 5521, `_msp_on_user_input_requested`
  5546; ledger append/read at 5613/5633).
- **Slice 2 (supervise wiring):** the supervise command registers
  `approval/request` and `userInput/request` handlers **before**
  `host.open()` — the only race-free shape — with callbacks that journal
  a redacted signal and append the operator-safe shape to the ledger,
  never touching the transport (4205–4236; `_msp_host_for` 3602–3614).
  `decide`/`answer` route through the supervisor when it holds the
  session (queue-drain + result rendezvous,
  `_msp_decide_via_supervisor` 5929) instead of failing on MSP
  single-attach.
- **Slice 3 (trust opt-in):** `spawn --trust-workspace` records the bit
  in the job record (5978, 998); `_answer_trust_prompt` (2957) answers
  the gate only when the record carries the voucher, otherwise fails
  closed with a loud `blocked-trust` signal (2604–2616); the voucher's
  scope is pinned to the job's own workdir (2972–3014). Documented in
  `muse-job/README.md` § "Standing trust-policy opt-in" (line 255).
- **Tests:** 167/167 green locally on the four approval test files —
  `test_msp_approval.py`, `test_msp_approval_cli.py`,
  `test_msp_approval_supervise.py`, `test_event_trust.py` — at this pin.

## Findings

- **F-MSP-1 — #1372's three body items are all shipped.** Every
  acceptance criterion in the issue body is verifiably met at this pin
  (citations above). The issue is OPEN; it should be closed as shipped,
  not left to accrue unrelated work. (Its own p2 priority and the
  loop's merge history — slice 3 via PR #1393, merged as `e3f6fac7` —
  agree the lane was deliberate and complete.)
- **F-MSP-2 — the one explicitly-named remainder: listing through a
  supervisor-held session is not wired.** `muse-job approvals` fails
  with `_msp_supervisor_held_error` (5254–5272) — "Listing through a
  supervised session is not wired yet (issue #1396)". The operator
  composes `decide`/`answer` from `status` + the request ledger
  instead. This is a genuine sub-gap of #1372 item 1's "in one place"
  goal, worth its own issue rather than holding #1372 open: the
  supervisor owns the only session attach, so listing needs a
  supervisor-mediated read path (the decision path already has one).
  → **filed as #1396** (this turn).
- **F-MSP-3 — live-job trust adoption is the only open trust-policy
  gap.** `--trust-workspace` is spawn-time-only; legacy records read
  `trust_workspace: false`; adoption today is hand-answer-in-tmux or
  kill+respawn. This is #1394 (open, p3), already well-specified —
  operator-initiated, manager-side, journaled grant. No new filing.
- **F-MSP-4 — the phone-approval loop is out of this lane's scope.**
  #849 (hosted, p2) owns plane push → device; the muse-job lane ends
  at the operator's terminal. No filing from this lane; recorded as
  the boundary so a future gap turn doesn't re-derive it.
- **F-MSP-5 — no doc gap.** The README carries the trust-policy
  section; the subcommand help text carries the #1372 provenance; the
  operator-visible error message is the one place that must re-point
  to the new issue (fixed in the shipping PR).

## Decisions

- **D-MSP-1:** Close #1372 via this analysis's Closes keyword — the
  three body items are verifiably shipped. The remaining listing leg
  (F-MSP-2) is filed as its own issue; the held-session error message
  re-points to it.
- **D-MSP-2:** #1394 (voucher grant) is the complete trust-policy
  remainder; no new trust-policy issues from this turn.
- **D-MSP-3:** The muse-job lane's "one place" is `muse-job status` +
  the ledger → `decide`/`answer`. Listing-through-supervisor joins
  that set in the follow-up issue; the ledger is the interim
  operator-safe shape (redacted ids + titles, never answers).
- **D-MSP-4:** Trust prompts stay fail-closed by default (the #211
  incident's standing decision). Any future expansion of the
  `--trust-workspace` voucher's scope (beyond the job's own workdir)
  needs its own issue and its own opt-in shape — never a silent widen.

## Filed this turn

- #1396 (enhancement, area:muse-job, track:open-source, priority:p3):
  `muse-job approvals` cannot list on a supervisor-held session —
  needs a supervisor-mediated listing path (F-MSP-2).

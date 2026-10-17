# Endpoint-wiring gap analysis: the #849 buzz lane's endpoint-driven leg

Pinned to main `52722cc3` (2026-10-17, post-#1612 merge). Analysis, not a
commitment. Code-state claims below were verified against the repo tree at
that commit and the live GitHub issue state (2026-10-17). Issue/PR numbers
are GitHub references as of 2026-10-17 (not code-verifiable from the
tree). Honesty rules apply (`docs/POSITIONING.md`): this describes current
state and work to do, not promises. Nothing here sends a push.

**Non-overlap map (what this doc is not):**
- `docs/PUSH_LANE_PLANE_PORT_GAP_ANALYSIS.md` (2026-10-16) — the port
  plan for the sweep/sender/GC chain (filed #1565–#1568). It kept the
  endpoint-driven mappings on their "existing tracker" (#1492) — which
  has since closed. This doc owns that orphaned half; it does not
  re-decide the port strategy (F-PP-2 async rewrite stands).
- `docs/HOSTED_OWNER_ALERTING.md` (2026-10-14) — the owner-facing
  alerting contract that pins the two mappings as "caller unwired
  (#1492)". This doc consumes it; the issue-pointer refresh is D-EW-4.
- `docs/PUSH_LANE_CONVERGENCE_2026-10-14.md` — the lane's remaining-build
  list (§3); the two new gaps below join it.

## 1. Vision

The #849 phone-approval loop in one line: the agent files → the owner's
phone buzzes → two taps → the agent unparks. Six mapping functions in
`hosted/push_events.py` (one per taxonomy §2 event, #969/#1062) turn
plane-side events into pages. Four are sweep-driven (reminders, digests,
heartbeat-stale, token-expiry-warning — the D9 sweep drives them; the
sweep's plane port is #1566). Two are **endpoint-driven**: they must be
called from the plane worker's HTTP request path — `on_approval_filed`
from the #952 filing endpoint after the #872 record write, `on_box_revoked`
from the revoke endpoint after stamping `revoked_at`. The approval-filed
page is the core buzz of the whole loop: without it, no page fires when
an approval is filed, and the loop degrades to a polling dashboard.

## 2. Vision vs state (pinned 2026-10-17)

| Leg | State |
|---|---|
| Endpoint mapping policy (sync) | SHIPPED (#1062): `on_approval_filed` / `on_box_revoked` in `hosted/push_events.py`, tested, caller obligations documented (terminal-aid exclusion upstream of the filing write; D65 keyless-grandfathered exclusion) |
| Endpoint mapping policy (async) | SHIPPED (PR #1608, merged `52881616`): `hosted/push_events_async.py` — async ports with the async boundary injected, stdlib-only, 24/24 tests green, neuter-verified |
| The async `enqueue_page` boundary | **OPEN, UNOWNED:** named by the #1492 module docstring ("the async-boundary port slice's deliverable") and the STACKING NOTE; no issue owns it (see F-EW-2) |
| The two endpoint call sites | **OPEN, UNOWNED:** the #952 filing endpoint and the revoke endpoint are deployed-worker code with no in-repo source; neither calls the async ports |
| Owner-alerting contract pointers | STALE: `docs/HOSTED_OWNER_ALERTING.md` (§1 table, §2, §7, O6) and the CHANGELOG #1608 bullet both say the wiring is "still open on #1492" — #1492 is CLOSED (see F-EW-1) |
| Sweep-driven four | Owned by #1566 (in flight; S2-a/S2-b1 merged) |

## 3. Findings

- **F-EW-1 — #1492 closed with unbuilt acceptance.** PR #1608 carried
  `Closes #1492`, so the issue closed on merge. The issue's own pointer
  comment (id 6230458989, same day) says "This issue stays OPEN: the
  plane-side endpoint wiring (the #952 filing endpoint and the revoke
  endpoint calling these, plus the async `enqueue_page` boundary they
  need) is still unbuilt." The automation beat the intent: the in-repo
  slice genuinely shipped, but the acceptance it carried (plane endpoint
  wiring + async boundary) has no owner. Two independent documents on
  main now dangle: the CHANGELOG #1608 bullet ("still open on #1492")
  and `docs/HOSTED_OWNER_ALERTING.md`'s pin-test-guarded "caller unwired
  (#1492)" rows. The pin test (`test_unwired_mappings_stay_marked_unwired`)
  guards the *claim*, not the *pointer* — it cannot catch the dangling
  issue number.
- **F-EW-2 — the async boundary is named but unowned.** The #1492 module
  docstring pins the contract (`await enqueue_page(db, *, event_kind,
  owner_principal, box_id, key_material, now=None) -> result with
  .disposition`) and the STACKING NOTE forbids vendoring before the
  boundary lands. The 2026-10-16 plane-port analysis filed sweep
  (#1566), sender-loop (#1567→#1569–#1571), GC (#1568), and schema (#1565)
  ports — but no async-boundary port of `hosted/push_enqueue.py`'s
  `enqueue_page`. The sweep's port carries its own async DB access; the
  endpoint-driven mappings need a separate, request-path boundary (per
  call, not per-minute cron), and nothing files it.
- **F-EW-3 — the call sites are worker-only.** The #952 filing endpoint
  (`POST /v1/boxes/{box_id}/approvals/file`) and the revoke endpoint
  (`POST /v1/boxes/{box_id}/revoke`) live in the deployed
  `sparkvm-control` worker, whose source is fetched live at deploy time —
  there is no in-repo copy to wire. Acceptance of the wiring slice needs
  the worker checkout plus a live tick against api.sparkvm.dev (the S4a
  live re-verification precedent: deployed-bytes checks + test-row
  cleanup). An in-repo-only PR cannot close this.
- **F-EW-4 — ordering is a chain, not a pile.** #1565's live D1 migration
  (the four push tables + D57 page-once index) must land before any
  enqueue path writes real rows; the boundary must land before either
  endpoint calls it (the STACKING NOTE); the two call sites are
  independent of each other once the boundary exists. The boundary is
  independently testable in-repo against a contract-faithful async `_D1`
  stub — #1492's tests already inject `enqueue_page`, so the boundary's
  contract is consumer-pinned before it is built.
- **F-EW-5 — the caller obligations are the trap, not the code.** The
  sync docstrings pin two obligations the call sites must obey:
  (a) `on_approval_filed`: never call for an aid whose #872 record is
  already terminal — filing *is* the plane's own write, so there is no
  gate-1 re-read on this path; a terminal aid filed here pages
  spuriously. The check is upstream of the write. (b) `on_box_revoked`:
  D65 — never for the keyless-grandfathered path. A wiring slice that
  places the calls without the obligations ships two silent
  false-page sources. The wiring issue's acceptance must assert both
  negatively.

## 4. Decisions

- **D-EW-1 — one follow-up issue owns both halves** (boundary +
  call sites): the boundary alone has no acceptance without callers,
  and callers without the boundary are dead code. Filed as #1614 below
  (p2, enhancement, track:hosted-product).
- **D-EW-2 — the boundary reuses the sync decision table verbatim.**
  D10 budget, D57 page-once dedup, D54 digest coalescing live at the
  boundary by construction (O6) — policy is not re-decided, only the
  DB-API boundary is ported, following the #1492 precedent (injected
  boundary, stdlib-only, no sibling imports).
- **D-EW-3 — live acceptance required.** The slice's acceptance is a live
  tick: file a test approval + revoke a test box against
  api.sparkvm.dev, observe `queued` dispositions, then delete the test
  rows. No in-repo-only close.
- **D-EW-4 — the owner-alerting doc's pointers refresh separately.** A
  small docs delta retargets "caller unwired (#1492)" to the new issue;
  the pin test still guards the claim. Out of this slice's scope; filed
  as a p3 follow-up so the dangling pointer doesn't linger.
- **D-EW-5 — #1492's closure stands; the fix is a new issue, not a
  reopen.** The in-repo half genuinely shipped and was reviewed; the
  pointer-comment trail (6230458989 + the new issue's comment) records
  the premature-close lesson for the audit trail. Reopening would
  conflate two slices the loop deliberately separated.

## 5. Gaps filed this turn

- **#1614 (p2)** — Hosted product: plane endpoint wiring for the
  endpoint-driven push mappings (the #1492 plane half). Async
  `enqueue_page` boundary against the worker's async `_D1` (D-EW-2),
  `on_approval_filed` called from the #952 filing endpoint with the
  terminal-aid upstream check, `on_box_revoked` called from the revoke
  endpoint with the D65 exclusion, live acceptance (D-EW-3). Blocked on
  #1565 (schema live migration) for the live half only.
- **#1615 (p3)** — docs pointer refresh: retarget
  `docs/HOSTED_OWNER_ALERTING.md`'s "caller unwired (#1492)" rows and the
  CHANGELOG #1608 bullet to the new wiring issue (D-EW-4).

Pointer comments: on #1492 (premature-close trail + link to the new
wiring issue), on #849 (endpoint leg's remaining-build status).

## 6. Non-goals

- The sweep-driven four mappings (reminders, digests, heartbeat-stale,
  token-expiry-warning): owned by #1566; not re-examined here.
- The sender loop (#1567 epic → #1569–#1571), subscriptions (#968),
  digest assembly (#1064), GC (#1568): unchanged trackers.
- Re-deciding the port strategy: F-PP-2 (async rewrite) stands; the
  #1492 async-port pattern is its first application, not a revision.

## 7. Remaining-build table (the #849 buzz, post-this-turn)

| Build | Owner | State |
|---|---|---|
| D1 schema live migration | #1565 (open) | Blocks the live half of everything below |
| Async `enqueue_page` boundary | #1614 (filed this turn) | Unowned before this turn |
| Filing/revoke endpoint wiring | #1614 (filed this turn) | The core buzz; live acceptance |
| Owner-alerting pointer refresh | #1615 (filed this turn, p3) | Docs delta |
| D9 sweep port | #1566 (in flight) | S2-a/S2-b1 merged; live tick pending |
| Sender loop | #1567 → #1569–#1571 (open) | Design done; build open |
| Subscriptions | #968 (open, operator-blocked) | Needs the worker-secret data key |
| Digest assembly | #1064 (open) | — |
| GC port | #1568 (open) | — |

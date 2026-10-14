# Live-machine-control convergence: the #47 vision vs state (2026-10-14)

**Vision vs state for the #47 live-machine-control lane** — pinned to
main `7152489a` (2026-10-14 ~01:1x CDT) for all in-repo claims; every
in-repo claim below was verified against that tree this turn. Issue/PR
numbers are GitHub references as of 2026-10-14 (not code-verifiable from
the tree). Doc-first; honesty rules apply (`docs/POSITIONING.md`):
everything below is **current state and work to do**, not promises. The
hosted product is not live, and no tenant has ever controlled a box
through a #47 surface.

**Non-overlap map (what this doc is not):**
- `docs/LIFECYCLE_PARITY_AUDIT_2026-09-20.md` (C16) — the #47-vs-scorecard
  audit that filed #177–#180. This doc consumes it; it does not re-audit
  the vendors.
- `docs/STREAM_OWNERSHIP_DESIGN.md` (F2 / #178) — the stream-ownership
  answer. This doc consumes it; it re-analyzes nothing there.
- `docs/SUSPEND_WAKE_RESEARCH.md` — the suspend/wake mechanics research
  behind #177's memory semantics. This doc consumes it.
- `docs/DESKTOP_SFU_GAP_ANALYSIS.md` (#854),
  `docs/TERMINAL_STREAMS_ARTIFACTS_GAP_ANALYSIS.md` (#853),
  `docs/TERMINAL_STREAM_WIRE_PROTOCOL.md` (#919),
  `docs/DESKTOP_SESSION_PLANE_DESIGN_AHEAD.md` (#935) — the desktop and
  terminal legs. This doc consumes them; it does not re-pin their state.
- `docs/PROVISIONING_LANE_CONVERGENCE_2026-10-09.md` (#851) — the
  provisioning lane. This doc starts where provisioning ends: a running,
  paired box that nobody can yet control.

## 1. The vision (#47 — verbatim acceptance)

> A live control surface for hosted Spark VMs: see each machine's state
> in real time and take actions (start, stop, pause/resume, restart,
> snapshot, open terminal/desktop) from a web UI instead of SSH.
>
> The hosted product needs a user-facing way to manage machines. This is
> the core "it feels alive" surface for hosted.
>
> Acceptance:
> - [ ] Authenticated tenant sees only their own machines
> - [ ] Start / stop / restart / snapshot act through the provider interface
> - [ ] State updates live, no page refresh
> - [ ] Every action is audited
> - [ ] Works against boat.dev; Fly.io fallback path not broken
>
> Scope notes: parity rule (self-hosted gets anything implementable
> there); provider-agnostic control interface; tenancy first (H11
> precedes implementation on shared control paths); prefer event-driven
> live state over polling loops.

The C16 children add four asks the acceptance does not yet carry:
**#177** — name pause/resume in the acceptance + define
memory-preservation semantics (disk guaranteed; memory resume
shape-dependent; boat.dev pause conditional on the open verification;
restart = stop+start, in-place, not "warm"). **#178** — define
desktop/terminal stream-ownership semantics (stream count, view-only
viewers, interactive hold/handoff; session-scoped auth binding).
**#179** — define the idle lifecycle policy model (defaults per state,
per-tenant control, what "idle" means for a Muse-owned box; H13 owns
detection). **#180** — decide the per-state surface (what works in
stopped/paused/archived states) + whether file browsing is in scope.

The pipeline in one line: **a tenant opens a web UI, sees only their
own boxes live, and starts/stops/pauses/restarts/snapshots them and
opens terminal/desktop — every action audited — through a
provider-agnostic interface that works against boat.dev and Fly.**

## 2. Vision vs state (pinned 2026-10-14)

| Vision element | State |
|---|---|
| Authenticated tenant sees only their own machines | **Unbuilt.** The shipped dashboard (`hosted/dashboard/`) is owner-key authed (paste an owner API key, kept in tab sessionStorage, `Authorization: Bearer` on every call) — the owner sees every box. No tenant concept exists in the dashboard. #69 (per-tenant approval routing, p1) is the tenancy blocker; #281 (cred-ui auth) is the localhost half. |
| Start / stop / restart / snapshot act through the provider interface | **Contract exists; verbs missing; no driver.** `harness/provider_iface.py` defines `ProviderDriver` (provision, status, list_boxes, suspend, dial, ssh_info, destroy, attest_network_isolation, snapshot) — **no start, stop, restart, or resume method** (F-LMC1). No driver implements it (no Fly, no boat.dev). The dashboard has no start/stop/restart/snapshot/file controls at all — only push-registration rows, box cards, and approvals. |
| Pause/resume (#177) | **Semantics researched, acceptance never amended.** The contract's `ProviderState` carries SUSPENDED/WAKING/STOPPED and `MemoryResume` (FULL / COLD_ONLY / NONE) per #177's shape-dependent rule, and `suspend()` + `dial()`-wake exist — but #47's acceptance checkboxes still do not name pause/resume (verified against the live issue body this turn), and restart's stop+start meaning is unpinned anywhere. |
| State updates live, no page refresh | **Polling, not live.** The dashboard refreshes on a 30-second `setInterval(refreshAll, …)` (`hosted/dashboard/dashboard.html`). No event-driven state channel exists — the #847 phone-home socket carries commands/acks, not state pushes; the provider-events API #47's scope note wants is unverified on either provider. |
| Every action is audited | **No actions to audit yet.** The fleet event journal (`fleet/events.py`) is update-event reporting (G17), not a control-action audit; approval records (#872) audit decisions, not box actions. The audit schema for control actions is downstream of the actions existing. |
| Works against boat.dev | **Nothing.** No boat.dev code anywhere (research/competitor mentions only). #47 asserts boat.dev's API verbs; no verification pass has ever read boat.dev's own docs for them (F-LMC2 → #1456). |
| Fly.io fallback path not broken | **Contract only.** The Fly driver is #905 (open); the H4 live-API clearance has never been consumed. Nothing to break yet. |
| Stream ownership (#178) | **Designed, not built.** `docs/STREAM_OWNERSHIP_DESIGN.md` answers it (single-driver desktop invariant, view-only watchers, per-session terminals, handoff protocol, session-scoped auth binding). No implementation; the session plane is #935, the SFU binding waits on the operator-provisioned app. |
| Idle policy (#179) | **Unanswered.** No idle-policy design exists. H13's idle detector is research-only (control-plane work, gated on H11 per the suspend/wake research) — detection ownership is settled, the policy model (defaults, per-tenant control, the "idle" definition) is not. |
| Stopped-state surface + file browsing (#180) | **Unanswered.** No decision doc exists. No file-browsing surface exists anywhere (dashboard or otherwise); the stopped-state surface is undefined — the contract's STOPPED state ("provider/operator stopped outside the suspend path; `dial()` wakes") is the only pin. |
| Snapshot | **Verb without semantics.** `snapshot(vm_id, label) -> str` exists on the contract; what it captures/restores/retains/costs was explicitly deferred by C16 ("needs its own survey pass") and never surveyed (F-LMC3 → #1455). |

## 3. Findings

- **F-LMC1 — The provider contract cannot express three of #47's five
  verbs.** `ProviderDriver` (verified method list at main `7152489a`:
  provision, status, list_boxes, suspend, dial, ssh_info, destroy,
  attest_network_isolation, snapshot) has no `start`, `stop`,
  `restart`, or `resume`. `suspend` + `dial()`-wake cover pause/resume;
  start-after-stop, stop, and restart have no method and no mapping
  pin. A #47 build cannot be written against this contract as-is —
  the verbs must be added or explicitly mapped (D-LMC3).
- **F-LMC2 — boat.dev is asserted, never verified.** #47 names boat.dev
  as the primary provider target and asserts eight API verbs
  (stop/snapshot/resume/fork/delete/files/commands/events/desktop).
  The repo contains no boat.dev code and no verification pass; the
  competitor watch's recurring boat.dev/pricing-404 note is about
  pricing pages, not the API. Until #1456 lands, "works against
  boat.dev" is an unchecked claim, not an acceptance criterion with
  evidence behind it.
- **F-LMC3 — Snapshot semantics were deferred and never came back.**
  C16 scoped snapshot out of its own audit; no later turn surveyed it.
  The contract's `snapshot()` returns an opaque `str` — no capture,
  restore, retention, billing, or lifecycle semantics. #1455 owns the
  survey.
- **F-LMC4 — The shipped dashboard polls.** 30-second
  `setInterval(refreshAll)` is the only live-state mechanism. #47's
  scope note prefers event-driven state; the gap between polling and
  the preference is unowned — no issue tracks "event-driven dashboard
  state", and this doc does not file one (the channel question belongs
  to the #47 build once a provider-events API is verified by #1456).
- **F-LMC5 — The dashboard is an owner surface, not a tenant surface.**
  Owner-key auth, all boxes visible. #47's first acceptance checkbox
  needs #69's tenant routing + a tenant auth story; neither exists.
  The dashboard's current shape is correct for its operator use —
  this is a scope statement, not a defect in the dashboard.
- **F-LMC6 — #177/#179/#180 have been unanswered for 24 days.**
  Filed 2026-09-20 from C16; no answering doc exists for any of the
  three (verified: only the audit, the docs index, and the
  stream-ownership doc's sibling-mention reference them). #178 is
  answered-but-unbuilt. The #47 lane's open-question half is not
  moving.
- **F-LMC7 — The idle detector is research, gated on H11.**
  `docs/SUSPEND_WAKE_RESEARCH.md` settles detection ownership
  (control-plane work) and gates H13 on H11. The #179 policy model
  (defaults, per-tenant control, the "idle" definition) has no owner
  and no design — it is not H13's detection build, and no issue
  separates the two. #179 stays the tracking issue; this doc does not
  split it.
- **F-LMC8 — The transports are designed; the control UI does not
  exist.** Desktop (SFU gap analysis + session-plane design-ahead),
  terminal (streams analysis + #919 wire protocol), and stream
  ownership (#178) are all designed-not-built. The dashboard offers
  no control action of any kind — #47 has no UI yet, only
  prerequisites.
- **F-LMC9 — File browsing has no surface and no decision.**
  #180's second ask (is file browsing in #47's scope?) has no answer
  anywhere, and no file-browsing surface exists. The stopped-VM file
  ops AgentComputer demonstrates (cited in #180) show the shape; the
  decision is still open.

## 4. Decisions

- **D-LMC1 — #47's acceptance stays the vision; this doc does not amend
  it.** The pause/resume amendment is #177's ask and rides an edit to
  #47's issue body (owner/maintainer action), not a doc. This doc
  records the amendment as outstanding, it does not perform it.
- **D-LMC2 — The stream-ownership design stands as #178's answer.**
  `docs/STREAM_OWNERSHIP_DESIGN.md` is not re-litigated here;
  implementation stays on the #178 / #935 / #936 / #937 lanes.
- **D-LMC3 — The start/stop/restart verb gap is #905-build scope.**
  The #905 Fly-driver build owns the contract amendment: add the
  verbs, or pin the explicit mapping (start = `dial()`-wake from
  STOPPED, stop = suspend-vs-terminate decision, restart = stop+start
  sequence per #177's F5 note) — decided by that build with its
  reviewers, not here. The mapping must be explicit either way: a
  driver that silently maps "stop" to "suspend" would falsify #47's
  stop semantics.
- **D-LMC4 — Polling is the interim, not the target.** #47's
  event-driven preference stands. The 30-second poll stays until a
  verified provider-events channel exists (#1456's events-API ask);
  no interim "live enough" redefinition.
- **D-LMC5 — #179 and #180 remain OPEN decisions; this doc invents no
  defaults.** No idle timeout, no per-state surface table, no
  file-browsing verdict is pinned here — those are product decisions
  with billing and tenancy consequences, and inventing them in a
  convergence doc would be exactly the overclaim the honesty rules
  forbid. The decisions stay on their issues.

## 5. Filed gaps (genuinely new — no duplicates among open issues)

- **#1455** (p2) — #47 snapshot semantics survey: capture (disk /
  disk+memory, per shape), restore path, retention/billing, the
  returned handle's lifecycle. C16 deferred it; nothing has covered it
  since.
- **#1456** (p2) — #47 boat.dev API verification: verb-by-verb
  confirmation against boat.dev's own docs (verbs, suspend/idle
  semantics, events API, auth/tenancy/rate limits); docs-insufficiency
  counts as a finding.

Everything else #47 needs is already filed: #177/#178/#179/#180,
#69 (tenancy), #281 (cred-ui auth), #905 (Fly driver), #906 (the
orchestrator that makes boxes exist to control), #935/#936/#937
(desktop), #920/#921/#1035 (terminal streams/viewer), #1047/#1048
(metering, for the idle/billing half). #47 stays OPEN (vision
tracker).

## 6. What this doc does not claim

- No tenant has controlled a box through a #47 surface — the vision's
  every acceptance checkbox is unmet, and the honest remaining-build
  list is §2's right column.
- Plane-side facts inherit the pinned reads recorded in the cited
  docs — no fresh plane read this turn. If the plane moved since
  those pins, this doc's plane statements are stale with them.
- The dashboard claims were verified against
  `hosted/dashboard/dashboard.html` at main `7152489a` (30-second
  poll, owner-key auth, no control buttons); the contract claims
  against `harness/provider_iface.py` at the same tree.
- This doc files exactly the two issues in §5 and changes no code.

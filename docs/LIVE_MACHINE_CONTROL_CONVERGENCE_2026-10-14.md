# Live-machine-control convergence: the #47 vision vs state (2026-10-14)

**Vision vs state for the #47 live-machine-control lane** — pinned to
main `7152489a` (2026-10-14 ~01:10 CDT) for all in-repo claims; every
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
restart = stop+start per the C16 audit's F5, carried by #177, in-place,
not "warm"). **#178** — define
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
| Authenticated tenant sees only their own machines | **Unbuilt.** The shipped dashboard (`hosted/dashboard/`) is owner-key authed (paste an owner API key, kept in tab sessionStorage, `Authorization: Bearer` on every call) — the owner sees every box. No tenant concept exists in the dashboard. AgentID agent sign-in exists plane-side (#1225, closed; dashboard half #1199, open draft) — read-only agent sessions, not tenant auth. #69 (per-tenant approval routing, p1) is the tenancy blocker; #281 (cred-ui auth) is the localhost half. |
| Start / stop / restart / snapshot act through the provider interface | **Contract exists; verbs missing; no driver.** `harness/provider_iface.py` defines `ProviderDriver` (provision, status, list_boxes, suspend, dial, ssh_info, destroy, attest_network_isolation, snapshot) — **no start, stop, restart, or resume method** (F-LMC1). No driver implements it (no Fly, no boat.dev). The dashboard has no start/stop/restart/snapshot/file controls at all — only push-registration rows, box cards, and approvals. |
| Pause/resume (#177) | **Semantics researched, acceptance never amended.** The contract's `ProviderState` carries SUSPENDED/WAKING/STOPPED and `MemoryResume` (FULL / COLD_ONLY / NONE) per #177's shape-dependent rule, and `suspend()` + `dial()`-wake exist — but #47's acceptance checkboxes still do not name pause/resume (verified against the live issue body this turn), and restart's stop+start meaning is unpinned anywhere. |
| State updates live, no page refresh | **Polling, not live.** The dashboard refreshes on a 30-second `setInterval(refreshAll, …)` (`hosted/dashboard/dashboard.html`). No event-driven state channel exists — the #847 phone-home socket is contracted to carry commands/acks, not state pushes. The live channel splits two ways (D-LMC4): the plane→browser push channel (#1458, not gated on provider verification) and the provider-events feed (gated on #1456). |
| Every action is audited | **No actions to audit yet.** The fleet event journal (`fleet/events.py`) is update-event reporting (G17), not a control-action audit; approval records (#872) audit decisions, not box actions. The audit schema for control actions is downstream of the actions existing. |
| Works against boat.dev | **Nothing.** No boat.dev code anywhere (research/competitor mentions only). The competitor analysis (`docs/COMPETITOR_ANALYSIS.md`, Boat row) has read boat.dev's API docs and summarizes coverage (stop/archive, resume, fork, delete, desktop streaming, retention API) — what has never happened is a check of **#47's asserted nine-verb list verb-by-verb** (snapshot/files/commands/events unexamined; suspend/idle/events/auth semantics unverified). #1456 owns that check. |
| Fly.io fallback path not broken | **Contract only.** The Fly driver is #905 (open); the H4 live-API clearance has never been consumed. Nothing to break yet. |
| Stream ownership (#178) | **Designed, not built.** `docs/STREAM_OWNERSHIP_DESIGN.md` answers it (single-driver desktop invariant, view-only watchers, per-session terminals, handoff protocol, session-scoped auth binding). No implementation; the session plane is #935, the SFU binding waits on the operator-provisioned app. |
| Idle policy (#179) | **Unanswered.** No idle-policy design exists. H13's idle detector is research-only (control-plane work, gated on H11 per the suspend/wake research) — detection ownership is settled, the policy model (defaults, per-tenant control, the "idle" definition) is not. |
| Stopped-state surface + file browsing (#180) | **Unanswered.** No decision doc exists. No file-browsing surface exists anywhere (dashboard or otherwise); the stopped-state surface is undefined — the contract's STOPPED state ("provider/operator stopped outside the suspend path; `dial()` wakes") is the only pin. |
| Snapshot | **Verb without semantics.** `snapshot(vm_id, label) -> str` exists on the contract; what it captures/restores/retains/costs was explicitly deferred by C16 ("needs its own survey pass") and never surveyed (F-LMC3 → #1455). |

## 3. Findings

- **F-LMC1 — The provider contract cannot express #47's
  start/stop/restart verbs.** `ProviderDriver` (verified method list at main `7152489a`:
  provision, status, list_boxes, suspend, dial, ssh_info, destroy,
  attest_network_isolation, snapshot) has no `start`, `stop`,
  `restart`, or `resume`. `suspend` + `dial()`-wake cover pause/resume;
  start-after-stop, stop, and restart have no method and no mapping
  pin. (Snapshot has a verb — its missing piece is semantics, F-LMC3.)
  A #47 build cannot be written against this contract as-is —
  the verbs must be added or explicitly mapped (D-LMC3).
- **F-LMC2 — boat.dev is asserted, never verified verb-by-verb.** #47 names boat.dev
  as the primary provider target and asserts nine API verbs
  (stop/snapshot/resume/fork/delete/files/commands/events/desktop — the
  list as the C16 audit records it, from the ticket author's reading;
  #47's acceptance itself does not enumerate them).
  The repo contains no boat.dev code. The competitor analysis HAS read
  boat.dev's API docs (Boat row: stop/archive, resume, fork, delete,
  desktop streaming, retention API) — what has never happened is a check
  of #47's asserted list verb-by-verb: snapshot/files/commands/events
  are unexamined, and suspend/idle/events/auth semantics are unverified.
  Until #1456 lands, "works against boat.dev" is an unchecked claim,
  not an acceptance criterion with evidence behind it.
- **F-LMC3 — Snapshot semantics were deferred and never came back.**
  C16 scoped snapshot out of its own audit; no later turn surveyed it.
  The contract's `snapshot()` returns an opaque `str` — no capture,
  restore, retention, billing, or lifecycle semantics. #1455 owns the
  survey.
- **F-LMC4 — The shipped dashboard polls.** 30-second
  `setInterval(refreshAll)` is the only live-state mechanism. #47's
  scope note prefers event-driven state. The live channel splits two
  ways (D-LMC4): the plane→browser push channel is now tracked by
  #1458 and is NOT gated on provider verification; the
  provider-events feed is gated on #1456.
- **F-LMC5 — The dashboard is an owner surface, not a tenant surface.**
  Owner-key auth, all boxes visible. #47's first acceptance checkbox
  needs #69's tenant routing + a tenant auth story; neither exists.
  The dashboard's current shape is correct for its operator use —
  this is a scope statement, not a defect in the dashboard.
- **F-LMC6 — #177/#179/#180 have been unanswered for 24 days.**
  Filed 2026-09-20 from C16; no answering doc exists for any of the
  three. Other mentions (the H4 failover-router design, pricing
  thinking, the competitor analysis/watch) cite #177/#179/#180 as
  inputs without answering them. #178 is
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
- **D-LMC3 — The start/stop/restart contract amendment is #47-lane
  owned; #905 proposes and implements.** `ProviderDriver` is the
  provider-agnostic contract every driver consumes, so a single
  provider's build must not pin its semantics: the #905 Fly-driver
  build proposes the mapping from Fly evidence and implements it once
  decided, but the amendment lands in the #47 lane with cross-provider
  review informed by #1456 (boat.dev is the primary provider per #47,
  so the fallback's build must not pin shared stop/restart semantics
  before the primary's verbs are even verified). The mapping brief
  must address two conflations: (a) `suspend()` is H13's *idle*
  primitive — user-pause-via-suspend erases the pause reason (user vs
  idle) that audit, #179 policy, and metering need, so the mapping
  must say where the reason lives; (b) start-via-`dial()` inherits
  `dial()`'s `BinaryIO` stream side effect — start must not require
  holding a stream open, or the control plane must own that stream's
  lifecycle. Candidate mapping (for the amendment, not pinned here):
  start = `dial()`-wake from STOPPED, stop = suspend-vs-terminate
  decision, restart = stop+start sequence per the C16 audit's F5
  (carried by #177). The mapping must be explicit either way: a
  driver that silently maps "stop" to "suspend" would falsify #47's
  stop semantics — and stop is a product/billing/tenancy decision
  (C15 retention, #908 spend, #179 policy, audit semantics), not a
  driver detail.
- **D-LMC4 — Polling is the interim, not the target; the live channel
  splits two ways.** (a) Plane→browser push (SSE/WebSocket carrying
  the plane's own `status()` transitions) is tracked by #1458 and is
  explicitly NOT gated on #1456 — the plane can push its own state
  with zero provider events. (b) The provider-events feed IS gated on
  #1456's verification. #47's event-driven preference stands; the
  30-second poll stays until (a) lands; no interim "live enough"
  redefinition.
- **D-LMC5 — #179 and #180 remain OPEN decisions; this doc invents no
  defaults.** No idle timeout, no per-state surface table, no
  file-browsing verdict is pinned here — those are product decisions
  with billing and tenancy consequences, and inventing them in a
  convergence doc would be exactly the overclaim the honesty rules
  forbid. The decisions stay on their issues.

## 5. Filed gaps (genuinely new — no duplicates among open issues)

- **#1455** (p2) — #47 snapshot semantics survey: capture (disk /
  disk+memory, per shape) incl. the C16 stopped-only lead (verify the
  THIRD-PARTY claim that snapshots require a stopped box — it
  constrains snapshot UX and interacts with #180); restore path;
  access control / tenancy / storage isolation / encryption;
  retention/billing consuming the existing `RetentionInfo`/`RetentionKind`
  (C15) surface with snapshot storage flagged as a #908 ledger input
  (no parallel model); the returned handle's lifecycle. C16 deferred
  it; nothing has covered it since.
- **#1456** (p2) — #47 boat.dev API verification: verb-by-verb
  confirmation of #47's nine-verb list against boat.dev's own docs
  (verbs, suspend/idle semantics, events API, auth/tenancy/rate
  limits); docs-insufficiency counts as a finding. Precision: the
  competitor analysis has read boat.dev's API docs — what is missing
  is the #47-specific check.
- **#1458** (p2) — #47 plane→browser push channel for live dashboard
  state: SSE/WebSocket carrying the plane's own `status()` transitions,
  explicitly NOT gated on #1456; polling stays as the degraded path.

Everything else #47 needs is already filed: #177/#178/#179/#180,
#69 (tenancy), #281 (cred-ui auth), #905 (Fly driver), #906 (the
orchestrator that makes boxes exist to control), #935/#936/#937
(desktop), #920/#921/#1035 (terminal streams/viewer), #1047/#1048
(metering, for the idle/billing half). #47 stays OPEN (vision
tracker).

## 6. What this doc does not claim

- No tenant has controlled a box through a #47 surface — every
  substantive acceptance checkbox is unmet (the Fly-fallback checkbox
  is vacuous, not unmet: nothing exists to be broken yet), and the
  honest remaining-build list is §2's right column.
- Plane-side facts inherit the pinned reads recorded in the cited
  docs — no fresh plane read this turn. If the plane moved since
  those pins, this doc's plane statements are stale with them.
- The dashboard claims were verified against
  `hosted/dashboard/dashboard.html` at main `7152489a` (30-second
  poll, owner-key auth, no control buttons); the contract claims
  against `harness/provider_iface.py` at the same tree.
- This doc files exactly the three issues in §5 and changes no code.

# Lifecycle parity audit: #47 vs the live-control scorecard (C16, 2026-09-20)

**Audit window:** 2026-09-20 ~19:55–20:15 CDT. **Strategy loop, competitor
archetype.** Evidence conventions: VERIFIED = read on a vendor's own
page/doc/repo (inline link); THIRD-PARTY = third-party reporting or
ecosystem docs; INFERRED = my characterization, labeled as such.

**Scope:** the control-plane-visible lifecycle only — pause/resume, stop,
start, restart — plus the two columns the deep-scan left unscored (file
browsing, restart), closed here. Explicitly out of scope per the C16
mandate: snapshot semantics (needs its own survey pass), Daytona's
archive storage backend (substrate-conditional), and anything below the
control plane.

## §1 What #47 says today

Ticket [#47](https://github.com/ntindle/spark-vm/issues/47) (Live machine
control, `track:hosted-product`):

- **What:** "A live control surface for hosted Spark VMs: see each machine's
  state in real time and take actions (start, stop, pause/resume, restart,
  snapshot, open terminal/desktop) from a web UI instead of SSH."
- **Acceptance (checkboxes):** tenant-scoped visibility; "Start / stop /
  restart / snapshot act through the provider interface"; live state, no
  refresh; every action audited; works against boat.dev, Fly.io fallback
  not broken.

**The What-vs-Acceptance mismatch is the audit's headline finding:**
pause/resume, terminal, and desktop are promised in What but absent from
Acceptance. §3 files the gaps.

## §2 Coverage matrix

| Lifecycle surface | #47 What | #47 Acceptance | Best-provider parity evidence | Verdict |
|---|---|---|---|---|
| start | ✓ listed | ✓ listed | All six providers (VERIFIED in deep-scan) | covered |
| stop | ✓ listed | ✓ listed | All six; Daytona stop/archive/delete (VERIFIED) | covered |
| restart | ✓ listed | ✓ listed | Daytona: no distinct restart verb — restart = stop+start (THIRD-PARTY, see §4) | under-specified |
| pause/resume | ✓ listed | ✗ absent | E2B paused-session model, Daytona VM pause/resume (VERIFIED in deep-scan); SUSPEND_WAKE_RESEARCH.md contract | **absent from acceptance (F1)** |
| snapshot | ✓ listed | ✓ listed | survey deferred to snapshot pass | covered-as-verb (semantics out of scope) |
| terminal | ✓ listed | ✗ absent | AgentComputer ConnectRPC exec, Fly sprite console, E2B SDK terminal, Daytona Web Terminal STARTED-only (VERIFIED in deep-scan) | **absent from acceptance (F4 context)** |
| desktop/stream | ✓ listed | ✗ absent | E2B one-stream-at-a-time limit; Daytona VNC; AgentComputer VNC (VERIFIED in deep-scan) | **ownership undefined (F2)** |
| file browsing | ✗ not in #47's What or Acceptance (scope notes list boat.dev's `files` verb) | ✗ | AgentComputer file ops on stopped VMs, no charge; Daytona file nav via Web Terminal STARTED-only (VERIFIED in deep-scan) | **scope undecided (F4)** |
| idle auto-policy | ✗ | ✗ | Fly ~30s auto-pause; Daytona 60-min auto-pause default + auto-stop/auto-archive/auto-delete; E2B autoPause→pause-or-kill; CodeSandbox hibernate; TermSquad always-on (VERIFIED in deep-scan / SUSPEND_WAKE) | **absent (F3)** |
| stopped-state billing | ✗ | ✗ | AgentComputer cold storage; E2B running-only billing; Fly hibernate = storage-only (VERIFIED in deep-scan) | owned by C15 |

## §3 Findings → filed sub-items

### F1 — Pause/resume is promised but not accepted; memory semantics are unspecified

#47's What names pause/resume; its acceptance checkboxes don't. Three
corpus facts make the spec language non-trivial:

1. The provider-agnostic contract must NOT promise memory preservation
   (`docs/SUSPEND_WAKE_RESEARCH.md`): Runloop suspends disk-only; Fly's
   memory suspend caps at ≤4 GB and the H3 reference shape (8 vCPU / 15 GB
   RAM) exceeds it, so on Fly the reference box's "pause" degrades to a
   cold stop. Memory resume is shape-dependent, never guaranteed.
2. boat.dev — the ticket's primary provider target — has **unverified**
   suspend/idle semantics (`SUSPEND_WAKE_RESEARCH.md`, "Open
   verification": "boat.dev: suspend/idle behavior — relevant to the
   Fly-vs-boat fallback evaluation"). The ticket asserts boat.dev's API
   verbs (stop/snapshot/resume/fork/delete/files/commands/events/desktop);
   it must not assert memory-pause until the verification pass runs.
3. The recommended wake contract is already specified in the research:
   H4's `suspended`/`waking` states + async `dial()` wake, with wake-on-SSH
   as control-plane code (no surveyed provider offers wake-on-SSH natively
   — `SUSPEND_WAKE_RESEARCH.md`).

**Filed as #47 sub-item:** name pause/resume in the acceptance
checkboxes, reference the H4 contract, and write the provider-agnostic
semantics (disk guaranteed; memory resume shape-dependent; boat.dev pause
conditional on the open verification).

### F2 — Stream ownership is undefined

The deep-scan's "Stream concurrency/ownership" gap stands unaddressed: E2B
documents a one-stream-at-a-time limit (VERIFIED); no other vendor in the
set publishes a concurrency policy; #47 says nothing about stream count,
concurrent view-only viewers, or interactive-control holding and handoff
(who owns the mouse when a Muse and a human both open the desktop?).

This is also an approvals-model question: confirmd today approves
*discrete requests*, not long-lived sessions (deep-scan scorecard gap). A
live desktop is a session. The session-scoped bearer/expiry/revocation
binding is designed inside #47 — its own spec surface — built on H9's
identity primitives (cert/bearer issuance) and informed by H11's isolation
answer; the approvals-model evolution it implies (discrete approvals →
long-lived session grants) belongs to H10's confirmd multi-tenant scope,
not to H9/H11.

**Filed as #47 sub-item:** define stream-ownership semantics (stream-count
limit, view-only viewers, interactive hold/handoff, session-scoped auth
binding designed inside #47 on H9's identity primitives; approvals-model
evolution routed to H10).

### F3 — No idle lifecycle policy model

Every surveyed provider except TermSquad (always-on) has an idle story,
and they disagree on defaults: Fly Sprites auto-pauses after ~30s idle;
Daytona defaults to a 60-minute auto-pause when neither auto-pause nor
auto-stop is set, plus auto-stop/auto-archive/auto-delete; E2B's default
timeout action is *kill* unless the lifecycle is configured to pause;
CodeSandbox hibernates. #47 has no idle policy at all — no defaults, no
per-tenant control, no definition of what "idle" means for a box a Muse
owns (the H13 idle-detector ownership question: control-plane work,
per `SUSPEND_WAKE_RESEARCH.md`).

The policy model is also the billing model: E2B bills running time only,
AgentComputer publishes a cold tier, Fly stops compute billing on
hibernate. F3 and C15 (stopped/cold cost tier) are the same decision
made twice if #47 doesn't own the lifecycle model. Direction: #47/H13
define the lifecycle states; C15 prices retained resources per state —
the cross-link is informational, not a dependency.

**Filed as #47 sub-item:** define #47's idle lifecycle policy model
(defaults per state, per-tenant control, H13 idle-detector ownership,
cross-link to C15's stopped billing).

### F4 — Stopped-state surface and file-browsing scope are undecided

Two linked unknowns:

- **Stopped-state surface:** Daytona's Web Terminal works STARTED-only
  (VERIFIED in deep-scan) — terminal while stopped is a design choice,
  not a default. AgentComputer does file operations on *stopped* VMs
  without starting and without runtime charge (VERIFIED) — a stopped
  surface exists and is priced. #47 says neither.
- **File browsing:** not in #47 at all. The deep-scan left the column
  unscored; §4 closes the evidence here. The decision is scope-bearing:
  a file browser is a meaningful control-plane surface for a Muse's box,
  and AgentComputer's stopped-VM file ops show the shape it can take.

**Filed as #47 sub-item (decision item):** decide the per-state surface
(what works in stopped/paused/archived states) and whether file browsing
is in #47's scope or a follow-up ticket.

### F5 — Restart semantics: recommend, don't file (doc-only)

Daytona surfaces no distinct restart verb — restart is stop+start
(THIRD-PARTY: ecosystem wrapper docs, "Stop the sandbox. The sandbox can
be restarted later — files and state persist"). Recommended #47 spec
language, for whoever writes the acceptance amendment: **restart =
stop+start sequence (in-place, not a reprovision; disk and configuration
survive; in-memory process survival follows the same shape-dependent
rules as pause/resume (F1)).** Not "warm": in the corpus vocabulary warm
means memory retained, and on the H3 reference shape stop+start is cold.
No separate issue — the F1 sub-item carries it.

Audit note for the future snapshot survey (not filed): one ecosystem doc
claims Daytona can only capture a snapshot while the sandbox is *stopped*
(THIRD-PARTY) — if true, it constrains snapshot UX (stop→snapshot→start);
verify in the snapshot-semantics pass.

## §4 The unscored columns, closed (file browsing, restart)

Per the deep-scan's scope note ("flag as a gap for the C16 audit to
close"), the evidence the scan omitted:

**File browsing / file ops:**

| Provider | Evidence this pass |
|---|---|
| AgentComputer | VERIFIED (deep-scan): file operations on stopped VMs without starting, no runtime charge |
| Daytona | VERIFIED (deep-scan): file navigation/view/edit via Web Terminal; STARTED state only, org members only |
| E2B | THIRD-PARTY: ecosystem/compatible SDK surfaces document `files.*` ops (list/read/write/mkdir/remove/rename/watchDir); e2b.dev's own filesystem docs not re-read this pass — no VERIFIED claim made |
| Fly.io Sprites | No vendor evidence found |
| TermSquad | No vendor evidence found |
| Docker Sandboxes | VERIFIED (deep-scan): mountless workspace persists across stop/restart; host-mounted workspace remains on the host |

**Restart:**

| Provider | Evidence this pass |
|---|---|
| Daytona | THIRD-PARTY: no distinct restart verb surfaced; restart = stop+start ("files and state persist" per ecosystem docs) |
| E2B | No vendor evidence found for a restart verb |
| Fly Machines | `stop` + `start` are the verbs (VERIFIED in SUSPEND_WAKE research); restart not separately named |
| AgentComputer / TermSquad / Docker | Not surveyed for restart semantics this pass |

## §5 Honesty notes

- **boat.dev lifecycle honesty:** #47 names boat.dev's API verbs
  (stop/snapshot/resume/…) from the ticket author's reading; the pause and
  idle semantics behind those verbs are unverified (open verification in
  `SUSPEND_WAKE_RESEARCH.md`). This audit treats boat.dev pause as
  *conditional*, and F1's sub-item says so. Do not market pause/resume
  against boat.dev until the verification pass runs.
- **Design intent vs shipped product:** everything #47-side is spec, not
  product; the parity comparison is unshipped design against shipped
  vendor product. The wins stay bets, the lags stay real gaps — same
  framing as the deep-scan.
- **Dated vendor facts:** all vendor claims carry the deep-scan's
  2026-09-20 survey window except the §4 delta checks, dated today in
  this doc. Vendor behavior changes; re-verify before building against
  any of it.

## §6 Filed sub-items

- F1: [#177](https://github.com/ntindle/spark-vm/issues/177) — #47: name pause/resume in acceptance + define memory-preservation semantics
- F2: [#178](https://github.com/ntindle/spark-vm/issues/178) — #47: define desktop/terminal stream-ownership semantics
- F3: [#179](https://github.com/ntindle/spark-vm/issues/179) — #47: define the idle lifecycle policy model
- F4: [#180](https://github.com/ntindle/spark-vm/issues/180) — #47: decide stopped-state surface + file-browsing scope

## Sources

- `docs/COMPETITOR_LIVE_CONTROL_DEEP_SCAN_2026-09-20.md` (2026-09-20 survey)
- `docs/SUSPEND_WAKE_RESEARCH.md` (2026-09-19 survey; H4 contract)
- Ticket [#47](https://github.com/ntindle/spark-vm/issues/47)
- §4 delta checks, 2026-09-20 ~20:00 CDT: E2B-compatible filesystem API
  surface via computesdk/aliyun-fc ecosystem docs (THIRD-PARTY):
  https://github.com/computesdk/computesdk/blob/HEAD/docs/getting-started/quick-start.md,
  https://github.com/aliyun-fc/fc-docs/blob/HEAD/docs/en-US/01.FC%20Agent%20Sandbox/07.Developer%20Reference/01.E2B%20SDK-compatible%20API%20List.md;
  Daytona stop/start/pause/archive verbs via mirrored vendor docs
  (THIRD-PARTY mirror of daytona.io docs):
  https://github.com/codecaine-ai/gamecube-decomp-harness/blob/HEAD/ai_docs/daytona_docs/www.daytona.io_docs_en_sandboxes.md.md

# Stream-ownership semantics for live machine control (F2 / #178)

**Status:** designed, not built. Resolves #178 — "define desktop/terminal
stream-ownership semantics" — filed from the C16 lifecycle parity audit
(`docs/LIFECYCLE_PARITY_AUDIT_2026-09-20.md`, F2) as a sub-item of #47 (live
machine control). The design half; implementation stays on the issue.

**The question:** #47 promises terminal and desktop streaming but says
nothing about stream count, concurrent view-only viewers, or
interactive-control holding and handoff — who owns the mouse when a Muse
and a human both open the desktop? This doc answers it: a single-driver
invariant for the desktop, first-class view-only watchers, per-session
terminal streams, an explicit handoff protocol, and the session-scoped
auth binding that makes any of it enforceable.

**What this doc does not re-litigate:**

- Transport choice — researched in `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md`
  (WebRTC-class bar, Selkies-GStreamer first, TURN relay required for hosted).
  This doc consumes that research's integration sketch (per-box streamer,
  capturing Xvfb `:98`; signaling vs media paths) as its deployment shape —
  with the research's explicit correction honored: the bind address is an
  open decision (the tailnet interface behind ACLs or a tailnet-side
  forwarder), not "localhost-only".
- The idle policy model (#179) and the stopped-state surface + file-browsing
  scope (#180) — sibling F-findings with their own tickets. Where this doc
  touches them (streams need a started box), it states the dependency and
  stops.

---

## 1. Corpus facts this design stands on

1. **E2B documents a one-stream-at-a-time limit** for desktop streaming
   (VERIFIED in the deep-scan — "There can be only one stream at a time",
   "Creating multiple streams at the same time is not supported"); its SDK
   also exposes view-only URLs on the single stream via
   `get_url(view_only=True)`. No other surveyed vendor publishes a
   concurrency policy. We match the observed limit but as a *stated
   decision*, not a silent inheritance — see D1.
2. **confirmd approves discrete requests, not long-lived sessions**
   (transport research §5, 'Auth' item 3). A live desktop is a session.
   There is no confirmd session to reuse as a stopgap. The C16 audit's
   correction stands: the session-scoped auth binding is **designed inside
   #47's own spec surface**, built on H9's identity primitives and informed
   by H11's isolation answer; the approvals-model evolution it implies
   (discrete approvals → long-lived session grants) belongs to **H10's**
   confirmd multi-tenant scope — not to H9/H11, not to this doc's build
   slices.
3. **Every stream session start/stop writes an audit line** (transport
   research §5, item 3 ('Auth') — the same discipline as the swap proxy's
   audit log). D6 makes the handoff events audited too.
4. **H11 multi-tenancy audit shipped** (2026-09-24): shared control paths
   are audited before they are shared. Stream endpoints are shared control
   paths; nothing here ships without H11's scoping.

---

## 2. Decisions

### D1 — One interactive driver per desktop stream

A desktop stream has exactly one **driver** — the principal whose input
reaches the guest — and zero or more **watchers** (D2). Two principals
typing into one desktop is input corruption, not collaboration. A second
interactive claim while the seat is held does not multiplex, queue behind,
or silently preempt — it goes through the handoff protocol (D4).

**Enforcement split (control plane owns state, streamer enforces it):**
signaling and media are two different paths (transport research §5.2) —
WebRTC media flows browser↔streamer directly, 100% via the hosted TURN
relay, never through the control plane. A control plane that never touches
the media path cannot police input arriving over a direct peer data
channel, so the split is:

- The control plane owns lease **state** — who holds the seat, who is
  parked, what the grace timers say.
- The streamer **enforces** it: its single input channel is bound to the
  current lease-holder's session bearer, and on every lease transition the
  control plane sends the streamer a revocation signal — the old bearer's
  input channel is cut, the new holder's is armed. Watchers' peer
  connections carry no input channel at all.

"Streamer stays dumb" means it makes no policy decisions — but it honors
control-plane lease state on the input channel, and it fails closed: if a
revocation signal is undeliverable, the streamer drops all input channels
(closes the session) rather than leaving a stale driver armed.

**Races:** all lease transitions are atomic single-writer control-plane
operations (compare-and-swap on the seat state). The loser of a racing
claim or takeover gets an explicit "seat now held by \<principal\>"
refusal, audited (D6). A forced takeover landing during a parked-request
grace window cancels the parked queue (the forcer takes the seat; parked
requesters are notified and may re-claim).

### D2 — View-only watchers are first-class

Watchers see the same pixels the driver sees and have **no input path** —
no mouse, no keyboard, no clipboard in either direction (read or write:
the watcher's client never receives clipboard content). A watcher may
request the driver seat (→ D4). Watchers are the answer to "can the human
watch while the Muse drives": yes, without touching anything.

Cap: **8 concurrent watchers per box**, explicitly **provisional** — the
rationale is TURN-relay cost (each watcher is media the relay carries, and
the transport research requires the TURN relay to be costed and designed
before the prototype claims "works on hosted"), but the number is not yet
derived from a per-watcher bitrate × $/GB model. The cap gets its
derivation when the TURN costing lands; until then it is a placeholder
that will be re-litigated, not a fossil. Self-hosted operators configure
their own cap; the default ships at 8.

### D3 — Terminal streams are per-session, not shared

Each terminal tab is its **own pty session** with its own input — there is
no shared-driver contention to resolve, because a pty's input belongs to
its session. Multiple concurrent terminal sessions are allowed, each
opened under the session-scoped auth binding (D5) and each audited (D6).
The operator knob is a per-box session cap (default: the box's own
process limits decide; the control plane documents the knob, it does not
invent a small number).

The desktop is the special case, not the terminal: only the desktop has
one shared mouse.

### D4 — Driver handoff is explicit; silent takeover never happens

The driver seat is a **lease with liveness**, not a flag:

- **Claim:** a principal requests the driver seat. Granted immediately if
  free.
- **Held:** if the seat is held, the claim parks as a *handoff request*.
  The holder sees a "handoff requested by <principal>" notice and gets a
  **30-second grace window** to yield or keep. The grace timer is
  **server-side** — never client-acknowledged. No response inside the
  window → the handoff proceeds. Parked-request entries are tied to the
  requester's session bearer: if the requester's session closes while
  parked, the entry is dropped with an audit line and the next entry is
  considered — a dead queue entry is never granted to a vanished
  principal.
- **Yield:** the holder releases explicitly; a parked request is granted
  in FIFO order.
- **Liveness:** the lease is tied to the holder's media-session liveness
  (the D1 input-channel binding gives this almost for free) plus a
  control-plane heartbeat backstop. A holder whose client dies — with or
  without a parked request waiting — forfeits the seat: it returns to free
  (or to the FIFO head), with a notice to watchers and an audit line. The
  box's owner is never locked out by a hung client, including in S1 (see
  §3).
- **Forced takeover:** the **box owner's principal** (or owner-delegated
  principals) may take the seat immediately — the "take control"
  affordance in the web UI. This is an owner-*role* power over the owner's
  box, not a human-vs-Muse class privilege: any other human goes through
  the parked-request flow like everyone else, and the control plane
  rejects unauthorized takeover attempts with an audit line. A forced
  takeover is never silent: the displaced driver is demoted to watcher
  (the demotion always succeeds — the D2 8-viewer cap applies to *new*
  watcher joins; a displaced driver takes priority over the cap), both
  sides get a notice, and the takeover writes an audit line naming who
  took from whom (D6).

**Tie-break rule:** human-interactive claims and the tenant Muse's
programmatic claims are *equal principals* — no class preempts the other
through the claim path. First holder keeps the seat until yield,
grace-expiry, liveness-forfeit, or owner forced takeover. The tenant
Muse's automation never auto-preempts a live human session; it claims
through the same handoff flow.

**Rejected alternative:** last-claimer-wins silent preemption. Nobody in
the surveyed set documents it, and it manufactures "who moved my mouse"
incidents that no audit line can untangle afterward. The lease makes every
transition attributable.

### D5 — Session-scoped auth binding (designed in #47, built on H9)

Every stream session — driver or watcher, desktop or terminal — carries a
**session-scoped bearer** issued by the control plane after tenant
identity verification, with expiry and revocation. Revocation events:
session close, tenant offboard, and operator-initiated kill. The binding
is designed inside #47's spec surface on H9's identity primitives; it is
not confirmd's job today, and confirmd's discrete-approval model evolves
to long-lived session grants under H10 (not this doc, not #47's build
slices — named here so the dependency is visible).

Until H9's identity service exists, the prototype may mint session bearers
from the operator's existing auth (documented as the interim, same as the
transport research's interim notes) — the *shape* (scoped, expiring,
revocable) is the commitment, not the issuer. The interim honors
session-close, expiry, and operator-initiated kill; tenant-offboard
revocation binds when H10 lands (it has no meaning in the pre-H10
single-operator prototype, so the interim does not overclaim it).

### D6 — Audit: every transition is attributable

Stream session start/stop, driver claims/grants/yields, handoff requests,
grace-expiry handoffs, forced takeovers, and watcher joins/leaves each
write an audit line carrying the acting principal and the affected
session. Tenant attribution rides H10's attribution when it lands; until
then, lines are operator-scoped. The audit line is the whole reason D4
rejects silent preemption: a takeover nobody can attribute is a takeover
nobody can review.

### D7 — Streams need a started box

A stream session requires the box in a started state. Suspending or
stopping the box closes all sessions with a notice to connected clients;
the streamer needs a running Xvfb, so the streamer is start-only (Daytona's
Web Terminal is likewise STARTED-only — the pattern is ordinary, not a
limitation to apologize for). Whether an *active* stream session counts as
activity that blocks an idle-suspend is #179's call, not this doc's; D7
only defines what happens when suspend/stop proceeds. What a stopped box
*can* still do is #180's decision, not this doc's; this doc only requires
that whatever #180 decides, the streamer stays out of the stopped surface.

### D8 — #47 acceptance amendment (proposed wording)

The C16 audit found #47's acceptance omits terminal/desktop/stream
entirely. Proposed checkbox additions for the ticket owner (the F1
pause/resume amendment is carried by #177; these are the F2 lines):

- [ ] Desktop: one interactive driver at a time; view-only watchers
      allowed; driver handoff is explicit (claim / yield / server-side
      30s-grace takeover with notice to the holder, owner-only forced
      takeover) — stream-ownership semantics decided in the design doc
- [ ] Terminal: per-session streams, each under the session-scoped auth
      binding and audited
- [ ] Every stream session start/stop and every driver handoff writes an
      audit line

The amendment itself is the ticket owner's edit — this doc proposes the
wording; the pointer comment on #178 carries it.

---

## 3. Build slices

- **S1 — control-plane primitives:** the single-driver invariant, the
  watcher list with the provisional 8-viewer cap, session-bearer issuance
  with expiry/revocation, the streamer input-channel binding + revocation
  signal with the fail-closed rule, lease liveness (media-session binding
  + control-plane heartbeat backstop) and the owner forced-release
  primitive — so a hung driver can never strand the box owner even before
  any handoff UX exists. Audit lines for session start/stop. No handoff
  UX yet: a held seat with a live holder simply refuses the second claim
  with "held".
- **S2 — handoff UX:** claim/yield, the parked-request queue (tied to
  session bearers, dropped on session close), the server-side 30s grace
  window with holder notices — including the delivery channel by which a
  parked-request notice reaches a *programmatic* (headless Muse) holder,
  which the prototype must define rather than assume — forced takeover
  with demote-to-watcher and audit, displaced-driver notices. This is
  where the web UI's "take control" affordance lands.
- **S3 — H10 session-grant integration:** confirmd's long-lived session
  grants replace the interim bearer issuer; per-tenant audit attribution
  on every D6 line. Gated on H10 — not started before it.

## 4. Open questions

- **Q1:** Is 30 seconds the right grace window, or should it be shorter
  for Muse-to-Muse handoffs (no human in the loop to read the notice)?
- **Q2:** Should the tenant Muse's programmatic claims auto-yield when a
  human opens the desktop, or is the parked-request notice enough? (D4
  says notice; prototype UX may revise.)
- **Q3:** Self-hosted default watcher cap — keep 8, or scale it to the
  box's own bandwidth? The hosted cap is a cost decision; the self-hosted
  default wants an operator story, not a copy-paste.

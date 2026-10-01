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
  localhost-only, capturing Xvfb `:98`; signaling vs media paths) as its
  deployment shape.
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
   research §5, item 5 — the same discipline as the swap proxy's audit log).
   D6 makes the handoff events audited too.
4. **H11 multi-tenancy audit shipped** (2026-09-24): shared control paths
   are audited before they are shared. Stream endpoints are shared control
   paths; nothing here ships without H11's scoping.

---

## 2. Decisions

### D1 — One interactive driver per desktop stream

A desktop stream has exactly one **driver** — the principal whose input
reaches the guest — and zero or more **watchers** (D2). The invariant is
enforced by the control plane, not by streamer politeness: two principals
typing into one desktop is input corruption, not collaboration. A second
interactive claim while the seat is held does not multiplex, queue behind,
or silently preempt — it goes through the handoff protocol (D4).

The streamer itself stays dumb: it accepts one input channel. Multiplexing
policy lives above it, where it can be audited.

### D2 — View-only watchers are first-class

Watchers see the same pixels the driver sees and have **no input path** —
no mouse, no keyboard, no clipboard write. A watcher may request the
driver seat (→ D4). Watchers are the answer to "can the human watch while
the Muse drives": yes, without touching anything.

Cap: **8 concurrent watchers per box** on the hosted product (TURN-relay
cost sanity — each watcher is media the relay carries; the hosted TURN
requirement is named as open infrastructure in the transport research, so
the cap is a cost decision, not a protocol limit). Self-hosted operators
configure their own cap; the default ships at 8.

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

The driver seat is a **lease**:

- **Claim:** a principal requests the driver seat. Granted immediately if
  free.
- **Held:** if the seat is held, the claim parks as a *handoff request*.
  The holder sees a "handoff requested by <principal>" notice and gets a
  **30-second grace window** to yield or keep. No response inside the
  window → the handoff proceeds. The box's owner must never be locked out
  by a hung client.
- **Yield:** the holder releases explicitly; a parked request is granted
  in FIFO order.
- **Forced takeover:** a human operator may take the seat immediately
  (the "take control" affordance in the web UI). This is not silent: the
  displaced driver is demoted to watcher, both sides get a notice, and the
  takeover writes an audit line naming who took from whom (D6).

**Tie-break rule:** human-interactive claims and the tenant Muse's
programmatic claims are *equal principals* — no class preempts the other.
First holder keeps the seat until yield, grace-expiry, or forced takeover.
The tenant Muse's automation never auto-preempts a live human session; it
claims through the same handoff flow.

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
revocable) is the commitment, not the issuer.

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
limitation to apologize for). What a stopped box *can* still do is #180's
decision, not this doc's; this doc only requires that whatever #180
decides, the streamer stays out of the stopped surface.

### D8 — #47 acceptance amendment (proposed wording)

The C16 audit found #47's acceptance omits terminal/desktop/stream
entirely. Proposed checkbox additions for the ticket owner (the F1
pause/resume amendment is carried by #177; these are the F2 lines):

- [ ] Desktop: one interactive driver at a time; view-only watchers
      allowed; driver handoff is explicit (claim / yield / 30s-grace
      takeover with notice) — stream-ownership semantics decided in
      the design doc
- [ ] Terminal: per-session streams, each under the session-scoped auth
      binding and audited
- [ ] Every stream session start/stop and every driver handoff writes an
      audit line

The amendment itself is the ticket owner's edit — this doc proposes the
wording; the pointer comment on #178 carries it.

---

## 3. Build slices

- **S1 — control-plane primitives:** the single-driver invariant, the
  watcher list with the 8-viewer cap, session-bearer issuance with
  expiry/revocation, and audit lines for session start/stop. No handoff
  UX yet: a held seat simply refuses the second claim with "held".
- **S2 — handoff UX:** claim/yield, the parked-request queue, the 30s
  grace window with holder notices, forced takeover with demote-to-watcher
  and audit, displaced-driver notices. This is where the web UI's "take
  control" affordance lands.
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

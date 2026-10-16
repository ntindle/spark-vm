# cua-bridge observability gap analysis

**Vision vs current state for the bridge's own records** — pinned to main
`5d4f5388` for all in-repo claims. Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work to
do**, not promises.

The cua-bridge (`cua/bin/cua-bridge.py`) is the self-hosted control
surface that lets a localhost panel inject input into the desktop: clicks
at coordinates (`/api/click`), typed text (`/api/type`), single
keystrokes with modifiers (`/api/key`), and process spawns
(`/api/launch`), plus a mutating `?probe=1` variant of `/api/status` that
spawns xev, hops focus, and injects an XTEST key (gated since #1574).

**The vision:** the operator can reconstruct, from the box itself, what
the bridge was asked to do to the desktop — when, through which
endpoint, aimed at which window, and whether it worked — without ever
recording keystroke or typed content.

**The state:** the bridge keeps no records of its own activity at all.
`Handler.log_message` is `pass` (L1302), so there is no access log — not
even request counts, not even rejected attempts. What the panel drove the
desktop to do is unknowable after the fact, and what failed is
undiagnosable from the box.

## 1. The observability inventory, verified at main `5d4f5388`

| Surface | What exists today | Verdict |
|---|---|---|
| Mutation audit (click/type/key/launch) | Nothing. No per-request record anywhere. | **Gap → F-CBA-1** (already filed as #1576; this doc does not re-file it) |
| Server-side error trace | None. `do_GET`/`do_POST` catch `Exception` and answer `{"error": str(e)[:300]}` with a 500; the client gets a truncated exception string, the box keeps nothing. | **Gap → F-CBA-2** |
| Rejected auth/CSRF attempts | `_check_csrf` answers 403 `{"error": "forbidden"}` and returns; no record is written. | **Gap → F-CBA-3** |
| Audit sink | Exists by accident: the keepalive runs `cua-bridge.py ... >>"$HOME/.cache/cua-bridge.log" 2>&1` (`cua/bin/cua-keepalive.sh` L82–85), and the bridge already prints `WARNING:` lines there (focus re-assert, singleton lock). Unbounded append, no rotation, no permission pin. | **Gap → F-CBA-4** |
| Request timing / correlation | Nothing — no durations, no request IDs; a hung click has no server-side story. | Noted as F-CBA-5, advisory (out of the build path's scope for now) |
| Driver-call seam | `call(tool, args)` spawns the cua-driver subprocess per mutation; the request's outcome reaches only the panel's response. | Covered by F-CBA-1/F-CBA-2's "result" field |
| Read endpoints (`/api/windows`, `/api/screenshot`, `/api/status`) | Unlogged, deliberately: reads are not mutations, and `/api/screenshot` is high-volume by design. | Non-goal, stated |

## 2. Findings

- **F-CBA-1 — no mutation audit log.** The finding stands as #1576
  (found by the 2026-10-16 arch deep-read): no mutation — click, type,
  key, launch — is recorded anywhere. Referenced here for completeness;
  not re-filed.
- **F-CBA-2 — unhandled 500s leave no server-side trace.** The two
  `except Exception` handlers (do_GET, do_POST) translate every
  unexpected failure into a client-side truncated string. The operator
  on the box cannot see that a 500 happened, let alone why — while the
  panel, running on the same localhost, receives raw exception text
  (truncated, but still the exception). The asymmetry is backwards:
  information flows to the caller and not to the machine's own records.
  #1583's non-numeric-Content-Length 500 is one instance of this class;
  the class itself has no owner.
- **F-CBA-3 — rejected CSRF/host attempts are invisible on the box.**
  `_check_csrf` enforces the `Host`-allowlist + `X-CUA` header contract
  (hardened by #1574's probe-GET gate and the window-shape filter work),
  but a refusal is a 403 with no record. The threat model those checks
  exist for — a hostile page on the operator's own machine probing the
  bridge — produces no signal the operator can ever see. You cannot
  distinguish "nobody is probing me" from "I am being probed constantly".
- **F-CBA-4 — the audit sink is unshaped.** stderr→`~/.cache/cua-bridge.log`
  is a usable channel (the bridge already WARNINGs into it), but it is
  an unbounded `>>` append with default umask permissions and no
  rotation. That is fine while the log is near-empty; it stops being
  fine the moment F-CBA-1's audit lines land: window titles (email
  subjects, document names, URLs) become a permanent,
  default-permissions record, and a long-lived box slowly fills its disk
  with it. The sink's shape (rotation, permissions) must be pinned
  **before** the first audit writer lands, not after.
- **F-CBA-5 — no request timing or correlation (advisory).** Nothing
  records how long a mutation took or correlates the panel's request
  with the driver's subprocess outcome. Useful for diagnosing slow
  input (cf. #784's keepalive-vs-slow-driver incident), but it is a
  second-order observability want behind the audit/error/reject gaps —
  noted, not filed.

## 3. Decisions

- **D-CBA-1 — the mutation audit rides stderr (adopts #1576).** One line
  per mutating request (`/api/click`, `/api/type`, `/api/key`,
  `/api/launch`, `/api/status?probe=1`): timestamp, endpoint, resolved
  target window (pid + title from the bridge's own resolution — never
  client-supplied strings), and result (ok / error-class). **Targets,
  never content:** typed text and keystrokes are never logged, ever —
  this is a hard pin on the audit format, not guidance. stderr is the
  channel because the keepalive already captures it; no new plumbing.
- **D-CBA-2 — 500s log server-side as single-line events; the client
  contract does not change.** The `except Exception` handlers gain one
  timestamped stderr line per failure: exception type + condensed,
  newline-escaped frame summary — not a multi-line traceback, which
  would break the one-line-per-event sink discipline D-CBA-1 and
  D-CBA-3 assume (and whose frames can themselves contain the string
  `WARNING`). The client still receives the truncated `str(e)[:300]`
  shape — this turn does not widen the client error contract; it only
  gives the box its own copy. **Content rule (extends D-CBA-1's hard pin
  to the error stream):** no request bodies, no typed text, no raw
  driver-stderr blobs — `call()` raises `RuntimeError(p.stderr.decode()
  [:500] ...)`, i.e. opaque driver stderr that may echo the text it
  failed to inject, so the event logs a short error-class label
  instead. Exception text is request-content-bearing today; the "never
  content" pin governs.
- **D-CBA-3 — rejected CSRF/host checks log one line at the same sink.**
  Timestamp, source, reason class (`bad-host` / `missing-csrf-header`).
  No secret values, no request bodies, no response reading. One line per
  refusal, at WARNING level so it is greppable apart from the audit
  stream. **Volume-bounded:** first occurrence per reason-class per
  window, then periodic count summaries — a hostile page probing in a
  loop must not be able to grow the (pre-rotation) log at will or drown
  the very probing-detection signal the logging exists to create.
- **D-CBA-4 — the sink shape is pinned before the first writer, and the
  mechanism is pinned with it.** Rotation: size-capped (a bounded number
  of rotated generations; exact cap chosen by the implementing turn).
  Permissions: 0600 — the audit names window titles, which are
  operator-sensitive by construction. **Constraint:** the bridge holds
  the keepalive's `>>` file descriptor for its entire lifetime, so
  rename-based rotation of `~/.cache/cua-bridge.log` leaves the bridge
  writing to the renamed inode — growth stays unbounded, the exact
  failure this decision exists to prevent. The mechanism class is one
  of: (a) bridge-side size-capped rotation (the bridge owns the log fd;
  the keepalive's `>>` redirect is retired), or (b)
  keepalive-coordinated rotate-then-restart. Not open-ended "rotation."
  The audit line format itself is a contract between the bridge
  (writer) and the keepalive/operator tooling (rotator/consumer); it is
  documented where it is defined, not spread across READMEs.
- **D-CBA-5 — reads stay out of the audit (non-goal restated).**
  `/api/windows`, `/api/screenshot`, plain `/api/status` are not
  audited. If a future turn wants read-audit for forensics, it is a new
  decision with its own content rules — the screenshot path in
  particular must never imply pixel content is being retained.

## 4. Build slices (dependency order)

**#1588 is a blocking prerequisite of every writer slice.** The sink
shape must land before the first line is written to it — including
#1576's audit writer, which predates this doc and could otherwise land
its mutation-audit lines into the unshaped sink first. This ordering is
recorded on #1576 itself (not just in this doc).

1. **S3 — sink rotation + permissions pin.** Per D-CBA-4: mechanism-class
   rotation of `~/.cache/cua-bridge.log` + 0600. Owns F-CBA-4. → filed
   as #1588. **Lands first; gates S1, S2, and #1576.**
2. **S1 — server-side 500 logging.** One-line stderr event per unhandled
   exception in `do_GET`/`do_POST` per D-CBA-2; client responses
   unchanged. Owns F-CBA-2. → filed as #1586.
3. **S2 — CSRF/host reject logging.** Volume-bounded WARNING lines per
   `_check_csrf` refusal per D-CBA-3. Owns F-CBA-3. → filed as #1587.

#1576 stays the mutation-audit build (D-CBA-1 adopts its recommended
shape) and may land only after #1588 — the pointer comment on #1576
records this doc as the lane's design ahead and #1588 as the blocking
prerequisite of the audit-writer slice.

## 5. What this analysis does not do

- It does not change the bridge's trust model (localhost-only,
  CSRF-header contract, the #1574 probe-GET gate all stand).
- It does not add an audit transport (no syslog, no journal daemon,
  no new file) — stderr, captured by the keepalive, is the whole
  channel (D-CBA-1).
- It does not promise the hosted product anything: the bridge is the
  self-hosted CUA control surface. Whatever the hosted lane later
  needs (centralized audit, signed streams) is a separate design with
  its own content rules.

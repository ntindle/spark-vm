# S4b remaining-builds gap analysis: the socket gap-hold wedge (#1143) and the road to #960

**Vision vs current state.** Statuses pinned to this repo at main
`8c65a0f` (2026-10-07) and to the base analysis
`docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md` (written 2026-10-04, §2/§5 refreshed 2026-10-07, pinned to main
`7b20178`), the wire spec `docs/PHONE_HOME_WIRE_PROTOCOL.md` §3.3 with
the D-MAL1 policy (#1118, 2026-10-07) and the S4b-2a implementation pin
(#1001, adopted 2026-10-07). Plane-side facts carry forward from the
base doc's §2 — no plane re-read this turn; nothing below claims a
fresh deployed checkout. Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work
to do**, not promises.

## 1. The remaining S4b vision

#958's plane half is decomposed (S4b-1–S4b-4, base doc §5): S4b-4
journal sink and S4b-1 hello/identity/generation fence shipped and
deployed; S4b-2's emit half (2a) is pinned in the wire spec and
partially landed in the deployed worker checkout; S4b-2b (socket
`command_ack` consume-half) and S4b-3 (ping/alarm revocation re-verify
+ hibernation) are open under #1001/#1002; #960 (S6) is the
integration gate. The lane's standing degradation contract, from the
wire doc: a carrier failure degrades to **fetch-path latency, never
loss** — the every-minute HTTPS cron ingest (`spark-pair.py ingest`,
#874, `* * * * *`) is the liveness backstop for the whole queue.

This doc answers what the base doc left open: the box-side
sequence-gap guard now interacts with the S4b-2a re-drive's D-MAL1
skip, and the interaction wedges the socket's live delivery. #1143
filed the finding; this doc pins the design decision and the remaining
builds.

## 2. Current state — what moved since the base doc

| Element | Current state |
|---|---|
| Malformed-row policy (D-MAL1) | **Shipped — #1118 (2026-10-07), both carriers.** The box skips a malformed `command` frame loudly in `_handle_socket_command` — never executed, never acked, never holding the per-session `_acked_prefix`. The HTTPS carrier's cursor advances past the malformed row instead of acking it. |
| S4b-2a emit-half wire-spec pin | **Adopted — #1001 slice 2a (2026-10-07, PR #1141).** Wire spec §3.3 now pins: re-drive on every (re)bind and on the D15 wakeup RPC reads the acked watermark (`MAX(seq)` over `state='acked'`), emits `command` frames in seq order for current-epoch rows with `seq > watermark`, leases stamped exactly as the HTTPS path; malformed rows skipped (never emitted), journaled LOUDLY as `phone_home.redrive_malformed`; every re-drive pass journals `phone_home.redrive`. The emit-half code is in the deployed worker checkout (in-flight #1001 work); the consume-half (2b) stays open. |
| Box-side sequence-gap guard | **Shipped, with a documented residual — #976 S5b.** `pairing/spark_pair.py`: `_PhoneHomeSession` keeps a per-session `_acked_prefix`; a `command` frame with `seq > _acked_prefix + 1` is held ("gap after acked prefix … waiting on the re-drive") — not acked, not executed. The class docstring already names the residual: a DO-skipped malformed *row* surfaces to this guard as a sequence gap, and the guard holds later frames on it — "live delivery degrades to the cron path until reconnect or plane repair". The HTTPS cron path itself always flows past the bad row. |
| The wedge (#1143) | **Filed 2026-10-07 (arch, p2).** Scenario: prefix 4 acked; row 5 malformed (DO skips per D-MAL1, never emits); rows 6, 7 valid. Frames 6, 7 hit `6 > 4 + 1` → held; the hold never heals within the session — the re-drive will never emit 5. The durable queue never wedges (the cron backstop), but the socket — the fast path — degrades to a dead session on any malformed row once a prefix is established. Four candidate designs named (a)–(d). |
| Gap-hold test contract | `pairing/test_phone_home.py::test_socket_command_gap_holds_prefix` pins the hold: seq 3 is not stamped until the missing seq 2 arrives via re-drive. |

## 3. Findings

- **F-S4b-8 — #1143's scenario is real in the shipped code (validated
  this turn against main `8c65a0f`).** The gap guard
  (`_handle_socket_command`, `seq > self._acked_prefix + 1` → hold,
  loud log, no ack) cannot distinguish "row 5 is malformed and will
  never be emitted" from "row 5 is missing and the re-drive will send
  it" — under the S4b-2a pin, a malformed row *becomes* a permanently
  missing row (skipped on re-drive, never emitted), and the guard has
  no signal that tells the two apart. The wedge is live-delivery-scoped
  only: the durable queue keeps flowing through the cron backstop
  (D-MAL1 cursor advance); the socket fast path degrades to a dead
  session for the session's whole remaining life. A hostile plane can
  also induce it (malformed frame with a valid int seq, then higher
  seqs forever) — but a hostile plane has strictly worse options, so
  the plane-data-bug case is the realistic threat.
- **F-S4b-9 — the wire doc's "aligned" claim overstates D-MAL1's
  carrier alignment.** The D-MAL1 paragraph (§3.3) says "socket and
  HTTPS carriers are aligned on malformed rows". They are aligned on
  *skip-and-log* (neither executes nor acks a malformed row); they are
  **divergent on delivery degradation**: the HTTPS carrier flows past
  the bad row (the cursor advances, later rows execute on schedule);
  the socket carrier holds every later frame for the session's
  remaining life. The alignment claim needs the bounded-degradation
  caveat, or the next reader will misread "aligned" as "behaves the
  same".
- **F-S4b-10 — the gap hold is unbounded within a session.** The only
  heals today are reconnect (transport death / restart — the 90 s
  pong-timeout → hibernate rule that would bound sessions is itself
  unbuilt S4b-3 scope) or plane repair of the row. There is no
  time bound and no frame-count bound on the hold. The lane's own
  degradation contract ("fetch-path latency, never loss") assumes a
  bounded degradation; an unbounded hold is a live-delivery
  regression against it, not a faithful instance of it.
- **F-S4b-11 — candidate (b) (book malformed frame seqs, skip booked
  gaps) cannot cover the actual case.** Validated against the
  S4b-2a pin: a DO-skipped malformed *row* never produces a frame, so
  there is nothing to book — the late-arrival hole the issue flags
  (a well-formed frame arriving on a booked seq must execute out of
  order, never take the re-ack-without-execution path) is mechanism
  for a case that cannot occur, and the fix weakens the ordering
  guarantee the guard exists to enforce. (b) is rejected, not
  deferred — its marginal coverage is zero and its cost is the
  ordering guarantee.

## 4. Decisions pinned (namespaced D-GH series)

- **D-GH1 — adopt (c): cursor fast-forward as the #1143 build; the
  build lives on #1143 itself.** When the gap guard would hold, it
  consults the shared durable cursor (`commands_cursor.json`, the
  cron ingest's cursor — advanced past malformed rows per D-MAL1 on
  the `* * * * *` tick): if `shared_cursor > _acked_prefix` **and**
  the cursor's epoch equals the session's current epoch, fast-forward
  `_acked_prefix` to `shared_cursor` (loud log) and process the
  frame. *Soundness:* every seq in `(prefix, shared_cursor]` was
  either executed in order by the cron, ack-and-logged as an unknown
  kind by the cron (the socket treats unknown kinds identically —
  ack-and-log — so fast-forwarding over them produces zero behavioral
  divergence), or skipped per D-MAL1 by the cron — the socket skipping
  execution of those seqs is exactly D-MAL1, and the `(box_id, seq)`
  idempotency backstops absorb any socket/cron race on the boundary. *Read discipline:* the cursor
  read goes through the non-blocking `.ingest.lock` (the #976/#1117
  precedent — `_write_private` is O_TRUNC in-place, not temp+rename,
  so an unlocked concurrent read can see torn JSON); on lock
  contention or parse failure the guard keeps the hold — degrade,
  never wedge. *Epoch gate:* fast-forward only when the shared
  cursor's epoch equals the session's epoch (the #947 contract the
  session already honors in `_save_socket_ingest_state`); a moved
  epoch is the #848/#958 stale-epoch case, not a fast-forward case.
  *Bounding:* the hold is now bounded by ~one cron tick and
  self-heals without reconnect.
- **D-GH2 — (a) document-and-accept is the interim posture until the
  D-GH1 build ships** (already documented in the code's residual
  note and §2 above); it is not the end state — F-S4b-10's unbounded
  hold is a regression against the lane's degradation contract, not
  a faithful instance of it.
- **D-GH3 — (d) wire tombstones (`command_tombstone{seq,epoch}`)
  deferred with reasons, not adopted.** Tombstones carry exact
  information (the DO knows which rows it skipped), but they need a
  plane change (out-of-repo deploy), a box change, and a wire-doc
  change for a marginal gain over D-GH1: the degradation under (c)
  is already bounded to ~one cron tick and self-healing. Revisit
  triggers: a box without the every-minute ingest cron, or
  tombstones serving another lane's need.
- **D-GH4 — the D-MAL1 "aligned" claim gets a bounded-degradation
  caveat (F-S4b-9).** The D-GH1 build PR amends §3.3: the carriers
  are aligned on skip-and-log; they diverge on delivery degradation
  — the socket holds later frames on a DO-skipped malformed row
  until the cursor fast-forward (≤ ~1 cron tick) or reconnect, while
  HTTPS flows past. No separate issue: the amendment rides the
  #1143 build.
- **D-GH5 — test contract for the #1143 build.**
  `test_socket_command_gap_holds_prefix` keeps its contract (a true
  missing row still holds); a new test pins the fast-forward (shared
  cursor advanced past the gap by the cron → the held frame
  processes, loud log emitted); a third pins the epoch gate (cursor
  from a moved epoch does NOT fast-forward). All toggle-verified
  non-vacuous per the loop's test discipline. No new test file —
  the existing `pairing/test_phone_home.py` owns it.

## 5. Remaining builds (build order)

| Build | Issue | State after this doc |
|---|---|---|
| S4b-2b socket `command_ack` consume-half (hoisted shared ack helper) | #1001 | Open — unchanged by this doc; independent of D-GH1 (box-side only). |
| S4b-3 ping/alarm revocation re-verify + hibernation (D17/D18) | #1002 | Open — unchanged; its 90 s pong-timeout rule is the other bound on session life. |
| Gap-hold wedge → cursor fast-forward build | #1143 | **Design pinned (D-GH1–D-GH5); build-ready.** Box-side only, one slot, in-repo, testable — lands in any order relative to 2b/3. |
| S6 live acceptance | #960 | Open — consumes all of the above. |

No new issues filed: the one genuinely-new gap (F-S4b-8) already has
its item (#1143), and F-S4b-9's wire-doc caveat rides the #1143 build
(D-GH4). Pointer comments on #1143 (the D-GH decision record) and
#958 (lane tracker).

## 6. Explicit non-scope

Stream/input frame classes (#853/#919), approval decisions (#873 — the same durable queue on both carriers, not a socket-exempt channel; not re-litigated here), any write to liveness (§8 —
the socket never touches it), the S6 live acceptance itself (#960),
and the push lane's sender loop (#1094 — a different D-series).

# Phone-home lane convergence, 2026-10-20 (#847)

**Status: analysis, not a commitment.** Code-state claims verified against
the repo tree at main `7a86bb13` (2026-10-20 ~09:3x CDT). Plane-side facts
are pinned to the loop's GitHub record (the plane worker source is not in
this repo); issue/PR numbers are GitHub references as of 2026-10-20.
Honesty rules apply (`docs/POSITIONING.md`): this describes current state
and work to do, not promises. Nothing here deploys anything.

This document re-pins the #847 vision-vs-state 18 days after
`docs/PHONE_HOME_GAP_ANALYSIS.md` (2026-10-02) and 9 days after
`docs/PHONE_HOME_S6_READINESS_2026-10-11.md`, against everything that
shipped since: S4b-2/3 deployed live (2026-10-09), #976 S5b box-side
command frames (PR #981), #1338's wire-protocol contradiction fixes
(resolving the S6 doc's F-S6-7 follow-up #1320), and the #1489
phone-home-events gap (filed 2026-10-15).

**Non-overlap map (what this doc is not):**
- `docs/PHONE_HOME_GAP_ANALYSIS.md` — the 2026-10-02 vision-vs-state that
  opened the lane. Consumed: every G47.x gap below is dispositioned.
- `docs/PHONE_HOME_WIRE_PROTOCOL.md` — the S3 contract (#941); §11 is the
  S6 acceptance checklist. This doc does not edit the contract.
- `docs/PHONE_HOME_S6_READINESS_2026-10-11.md` — the S6 pre-acceptance
  pin. This doc confirms it is still current; it does not re-derive it.
- `docs/S4B_SOCKET_REMAINING_BUILDS_GAP_ANALYSIS.md` — the S4b
  decomposition. Consumed (all slices closed).

## 1. Lane state (pinned 2026-10-20)

| Slice | State |
|---|---|
| S1 — #846 plane half (rotate/revoke) | Shipped |
| S2a — #864 interim HTTPS heartbeat sender | Closed |
| S3 — wire protocol contract (#941) | Shipped |
| S4 — plane DO per box (#958 + S4b-1..4 #999–#1002) | **Build-complete, deployed live** to `sparkvm-control` (S4b-2/3 closed 2026-10-09). Issue #958 still OPEN — see F-20-1. |
| S5 — box WSS client (#959 S5a) + socket command frames (#976 S5b) | Shipped (`pairing/spark_pair.py`, stdlib-only RFC 6455; 101 box-half tests) |
| S6 — live acceptance (#960) | **OPEN — the lane's only remaining build.** Blocked on owner-provisioned prerequisites (two disposable test boxes, owner key, human pairing approval); the loop cannot self-provision these. |

## 2. G47.x disposition (2026-10-02 gaps → 2026-10-20 state)

- **G47.1 (no box-side long-lived process)** — RESOLVED. The persistent
  `phone-home` daemon lives in `pairing/spark_pair.py` (S5a); the
  process-shape decision was taken with the S5 slice as the gap analysis
  prescribed.
- **G47.2 (plane has no WebSocket surface)** — RESOLVED. S4 built the DO
  class, upgrade handler, binding, and migration in the plane workspace;
  deployed live.
- **G47.3 (socket auth story)** — RESOLVED. Upgrade handshake verifies
  `sha256(token)` at handshake time; `token_expires_at` and `revoked_at`
  re-verified on reconnect/resume (S4b-3).
- **G47.4 (wire protocol design)** — RESOLVED. S3 contract shipped (#941).
- **G47.5 (one-DO-per-box addressing)** — RESOLVED. Stub name derived via
  `idFromName` from the token's `box_id`; URL `{id}` is a routing hint
  only (S4a, live-verified 101/401/426 paths).
- **G47.6 (stdlib-only WSS client)** — RESOLVED as option (a): hand-rolled
  stdlib-only RFC 6455 framing in `spark_pair.py` (S5a). No new
  dependency; the brittle surface (framing/handshake) is covered by the
  101 box-half tests.
- **G47.7 (fleet journals)** — RESOLVED. DO-side liveness events land in
  the fleet event journal via the S4b-4 sink (#999).
- **G47.8 (WSS↔HTTPS fallback + liveness precedence)** — RESOLVED. The
  #864 heartbeat remains the ONLY liveness signal (wire spec §8); the
  socket client never writes `last_heartbeat.json`. Socket loss falls back
  to HTTPS heartbeats; the journal/status precedence rule is pinned in
  the S5a header comment.

## 3. Findings

- **F-20-1 — #958 is build-complete but still open.** Every S4/S4b slice
  is closed and the DO is deployed live, yet #958 (the S4 build issue)
  remains OPEN on GitHub. The S6 readiness doc already treats S4 as
  closed. Recommendation: a repo turn closes #958 (or records why it
  stays open as a tracker). This turn does not close it — issue closure
  outside the turn's own scope belongs to the repo lane.
- **F-20-2 — stale "plane half not built yet" comments shipped in the
  box client.** `pairing/spark_pair.py` carried the claim in two places:
  the S5a/S5b header note and the `phone-home` subparser help text (the
  operator-facing one, shown by `spark_pair phone-home --help`). Both
  said "the plane half (#958, one Durable Object per box) is not built
  yet — expect `upgrade failed` retries". That was true when S5a shipped;
  S4 deployed live 2026-10-09. An operator reading `upgrade failed`
  retries today would misdiagnose a live-plane failure as "not built
  yet." Fixed in this turn (comment-only, both occurrences): the notes
  now state the plane half is deployed and point at #960 for live
  acceptance.
- **F-20-3 — no new build gaps.** The only open work is S6 (#960), whose
  prerequisites are owner-provisioned (S6 readiness §4). #1489 (owner
  alert on phone-home human-attention class, filed 2026-10-15) keys off
  this lane's `phone_home_events` journal but is a separate p3 alerting
  item, not a lane blocker.

## 4. What remains

Exactly one item: **#960 S6 live acceptance**, executing the §11
checklist harness-first then live, per the 2026-10-11 readiness pin.
This turn confirms that pin is still current: the one contract change
since it was written — #1338's wire-protocol contradiction fixes
(2026-10-11), resolving that doc's own F-S6-7 follow-up (#1320) — is
aligned with the pin's per-item verdicts (the §11 revoke-during-socket
item and the S6 doc's Item 2 now agree on the corrected behavior), so
no per-item verdict is invalidated. Its prerequisites are the
standing user-infra set: two disposable test boxes (not the user's real
hardware), an owner key, and human pairing approval. Until those exist,
the lane is correctly parked, not stalled.

## 5. Decisions

- **D-20-1** — This doc is the lane's convergence pin; the next
  re-pin is due only when S6 executes or a new lane gap is filed.
- **D-20-2** — #958's open state is flagged (F-20-1) but not changed
  here; closure is a repo-turn action.
- **D-20-3** — The S6 readiness doc needs no update; its §4
  prerequisites and D-S6-1..6 run decisions stand. Its intro sentence
  ("One doc-accuracy follow-up filed as #1320") is now historical —
  #1320 was resolved by #1338 — but the operative per-item content is
  unchanged.

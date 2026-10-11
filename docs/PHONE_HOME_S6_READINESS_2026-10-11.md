# Phone-home S6 readiness, 2026-10-11: the #847 lane's acceptance pre-check (#960)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `2cd2c4d` (2026-10-11 ~09:4x CDT).
Issue/PR numbers are GitHub references as of 2026-10-11 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. No phone-home
code ships in this analysis; nothing here deploys anything or touches the
live plane.

This document is the pre-acceptance pin for #960 (the #847 S6 live
acceptance). It maps each item of the S3 contract's §11 checklist
(`docs/PHONE_HOME_WIRE_PROTOCOL.md` §11) against what the shipped tree
already proves and what only the live run can prove, so the turn that
executes S6 starts from a verified map instead of re-deriving it. It files
no new issues: every remaining unknown below is already inside #960's
explicit scope.

**Non-overlap map (what this doc is not):**
- `docs/PHONE_HOME_WIRE_PROTOCOL.md` — the S3 contract (#941): §11 is the
  vision; this doc is the readiness map against it, not a contract edit
  (one parenthetical location fix, §7, noted in F-S6-7).
- `docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md` — the 2026-10-04 pre-build
  decomposition (F-S4b-1–F-S4b-7, D14–D18, filed #999–#1002). Consumed:
  all four slices are closed.
- `docs/PHONE_HOME_GAP_ANALYSIS.md` — the 2026-10-02 vision-vs-state that
  opened the lane. Consumed.
- `docs/DURABLE_COMMANDS.md` — the #848/#873/#947 command-queue contract
  (epochs, leases, cursor discipline) the checklist items 3 and 6 rest on.

## 1. Lane state (pinned 2026-10-11)

| Slice | State |
|---|---|
| S3 contract (#941) | Shipped — the §11 checklist is the acceptance vision |
| S4 plane DO: S4a (#958), S4b-1 (#1000), S4b-2 (#1001), S4b-3 (#1002), S4b-4 journal sink (#999) | All closed; S4b-2/3 closed 2026-10-09; deployed live to `sparkvm-control` |
| S5 box client (#959) + S5b socket command frames (#976) | Closed |
| S6 live acceptance (#960) | **OPEN — this doc's subject** |

Structural fact for the S6 executor (F-S6-1): the plane worker source is
not in the public repo — the public tree holds the contract, the box
client (`pairing/spark_pair.py`), and the box-side tests. The S6 method's
"harness-first" step therefore runs the *real* `worker.py` from the
operator's checkout against a sqlite-backed D1 stub (the
`hidden_files/harness_958_s4a.py` pattern from #846/#848/#952) — that
harness is the only pre-live verification of plane behavior. In-tree
`pairing/test_phone_home.py` (54 tests) covers the box half against a
contract-faithful plane stub.

## 2. Per-item readiness (§11 checklist)

### Item 1 — Two boxes, distinct stubs, no cross-talk
- **Already proven (tree):** route-by-token — the DO stub is
  `idFromName("phone-home:" + box_id)` derived from the *token's*
  `box_id`; the URL id is a routing hint only (S4a, live-verified
  101/401/426 paths). "A DO binds exactly one box: the handshake identity
  at first connect. It never routes a frame to another stub." (wire §7).
  Box side: a `welcome` naming another `box_id` exits without reconnect
  (`test_bad_welcome_box_id_exits_no_reconnect`).
- **Live-only:** two real test boxes; a command enqueued for A must never
  produce a `phone_home.redrive` row for B nor execute on B (observed via
  the owner journal read path `GET /v1/boxes/{id}/phone-home/events`,
  S4b-4). The "stub-id assertion" is the per-box journal attribution —
  the stub identity is deterministic from the token, so box_id-keyed
  journal rows *are* the stub binding evidence.
- **Verdict: READY.** No new gaps.

### Item 2 — Revoke-during-socket
- **Already proven (tree):** plane re-verifies the bound credential's
  stored hash on every inbound frame and on the 10-minute alarm wake:
  `revoked` → `close`/`revoked` + `phone_home.revoked_kill` journal
  (S4b-3, deployed). Box: `revoked` → exit 1, no reconnect
  (`_phone_home_close_action`, `test_revoked_no_reconnect_loop`); the
  message prints the re-pair path, and the separate #864 heartbeat cron's
  401 prints the same guidance (`pairing/spark_pair.py`: "this box token
  is dead (expired, revoked, or never valid) — re-pair the box
  (`request` + `redeem`)").
- **Live-only:** revoke A's token mid-socket via the owner revoke
  endpoint (#846); observe `close`/`revoked`, the journal row, daemon
  exit with the re-pair message, no reconnect (daemon stays down), and
  the cron's 401 guidance. **Bound honesty:** ≤ 30 s for a compliant
  (pinging) box — the 30 s box ping is re-verified per frame; ≤ 10 min
  for a silent socket (alarm wake). The S6 run must use a pinging box
  for the tight bound and budget the worst case.
- **Verdict: READY.** Run last (D-S6-3): revocation destroys the test
  token.

### Item 3 — Reconnect-resume clean
- **Already proven (tree):** generation claim is crash-safe
  (persist-before-use, never reuses: `_phone_home_claim_generation`);
  every fresh connect claims last+1, so a `kill -9` + restart binds
  generation N+1 and the old socket gets `superseded-generation`
  (the surviving old daemon would exit 1 fail-closed on it — the
  token-theft signal). Re-drive on every (re)bind and on the D15
  Worker→DO wakeup RPC: unacked current-epoch rows in seq order, lease-
  stamped exactly like the HTTPS fetch path, journaled
  `phone_home.redrive` (S4b-2 pin). Box dedupes redelivery by
  `(box_id, seq)`; the socket `command_ack` feeds the same watermark
  the re-drive reads (S5b; `test_socket_command_redelivery_deduped`,
  gap-hold/fast-forward tests).
- **Live-only:** kill -9 A's daemon with a command unacked, restart with
  the generation file intact (plain restart — no epoch bump, D-S6-5),
  observe the N+1 bind, the re-driven command, and exactly-once execution
  (one stamp in the box's `consumed/` store; at-least-once is the
  contract, dedupe is the box's).
- **Verdict: READY.** Runbook caution (F-S6-6): this item needs a *plain*
  restart. Deleting the generation file is the counter-loss path — that
  bumps the epoch and legitimately expires the pending commands, which is
  item 6's test, not this one.

### Item 4 — Stale-generation fence
- **Already proven (tree):** handshake-level fence live-verified
  2026-10-05 (stale `hello` → `close`/`stale-generation` carrying
  `last_generation`; the 12/12 live-smoke run). Box recovery: adopt
  `last_generation + 1`, bump epoch (counter loss is a reboot-equivalent
  per §5), reconnect (`test_stale_generation_adopts_and_bumps_epoch`).
  Frame-level rule in the contract: `generation < last_generation` →
  drop + journal `phone_home.generation_fence` (S4b-1).
- **Live-only:** the frame-level drop + journal. The box client never
  emits stale frames, so S6 needs a raw-frame probe: complete a hello at
  generation M on a test box token (transient — never persisted), then
  send any frame with generation M−1 and assert the drop plus the
  `phone_home.generation_fence` journal row (`seen_generation` = M−1,
  `generation` = M, the kept one) via the owner read path.
  `test_phone_home.py`'s frame encode/decode helpers are the probe's
  starting point.
- **Verdict: READY**, with a probe-building step.

### Item 5 — Fallback honored
- **Already proven (tree):** the heartbeat is independent of phone-home
  (`test_heartbeat_untouched_by_phone_home`); reconnect backoff is
  1 s → 60 s ±25% jitter with the attempt counter persisted across
  restarts (no storm, no tight loop); daemon failures are loud exits.
  Liveness authority is the heartbeat alone (§8) — the socket must never
  refresh it.
- **Live-only:** with A's daemon running, block its egress —
  `iptables -m owner --pid-owner <daemon-pid> -A OUTPUT -p tcp
  --dport 443 -j DROP` (per-process, so the cron's HTTPS is untouched;
  there is no in-repo WSS-only kill switch — the ws URL derives from the
  control URL). Assert: heartbeats keep 200ing, an enqueued command
  executes via the cron fetch-execute-ack ingest (#874 loop), and the
  dashboard staleness chips stay heartbeat-true. Then remove the rule
  and assert WSS recovery at generation+1 with no storm.
- **Verdict: READY.** The iptables owner-match is the runbook's
  contribution (F-S6-3); it is test tooling, not a product gap.

### Item 6 — Epoch untouched by reconnect
- **Already proven (tree):** plain reconnects never bump epoch
  (`test_plain_reconnect_leaves_epoch_alone`); counter loss bumps epoch
  (box side); `?epoch=` is claimed on every `/commands/pending` fetch
  and omitted when the box has no epoch yet (#947).
- **Live-only AND UNVERIFIED:** the plane half — "claiming a new
  incarnation expires every pending/leased command of older epochs: they
  are never delivered again" and the racing-lower-claim `409`
  (`docs/DURABLE_COMMANDS.md`, #848/#958 scope). The plane source is not
  in the public tree (F-S6-1) and no live epoch-bump test is recorded
  anywhere. S6 must: enqueue a command for A, force an epoch bump
  (delete the generation file → counter-loss path, or the owner epoch
  reset), and assert the old-epoch command is never delivered; then
  attempt a racing lower `?epoch=` claim and expect `409`. If the plane
  does not implement either half, that is a genuine gap to file against
  #848's scope — it is inside #960's checklist, not a new issue.
- **Verdict: NOT VERIFIED — the highest-uncertainty item.** It should be
  the live run's first probe (D-S6-6): everything after it assumes the
  epoch contract holds.

## 3. Findings

- **F-S6-1** — Plane source is operator-side, not in the public repo
  (verified: no `worker.py` anywhere in the tree at main `2cd2c4d`).
  Consequence: the harness-first step (real worker.py + sqlite D1 stub,
  the `harness_958_s4a.py` pattern) is load-bearing, not optional — it
  is the only pre-live check of plane behavior. Not a product gap; the
  deployment model is deliberate (deployed-bytes SHA pinned at deploy
  time).
- **F-S6-2** — Item 6's plane half (epoch expiry + 409) is the least-
  verified slice of the lane. Contract-documented, never live-proven.
- **F-S6-3** — No in-repo way to block WSS egress alone (ws URL derives
  from the control URL). The iptables owner-match runbook step covers
  it; test tooling, not a product gap.
- **F-S6-4** — The revocation bound is honest but asymmetric (≤30 s
  compliant / ≤10 min silent). S6 must run item 2 on a pinging box.
- **F-S6-5** — Item 1's "stub-id assertion" reduces to per-box journal
  attribution: the stub name is deterministic from the token's box_id,
  so `phone_home.*` rows keyed by box_id are the binding evidence.
- **F-S6-6** — Items 3 and 6 need opposite restart disciplines (plain
  restart vs counter-loss restart). Mixing them up makes each test
  vacuously pass or spuriously fail.
- **F-S6-7** — Docs accuracy: the wire-protocol §7 S4b-1 note cites
  `control-plane/live_smoke_1000.py`, which is not in the public tree
  (verified by search at main `2cd2c4d`). Fixed in this turn with a
  parenthetical "(operator-side script, not in the public tree)" —
  editorial only, no contract change.

## 4. Decisions for the S6 executor

- **D-S6-1** — Harness-first, then live. Extend the `harness_958_s4a.py`
  pattern (real worker.py, sqlite D1 stub) with per-item plane-logic
  checks before touching `api.sparkvm.dev`.
- **D-S6-2** — Two disposable test boxes, enrolled via the pairing flow
  (owner approves `request` + `redeem`). Every test row — boxes, tokens,
  journal rows, commands — is deleted afterwards; real boxes' heartbeats
  must be unaffected (the #952 hygiene).
- **D-S6-3** — Item order: 6 (epoch probe first — everything assumes the
  contract), 1, 3, 4, 5, 2 last (revocation destroys the token).
- **D-S6-4** — The executor needs an owner key (revoke endpoint, journal
  read path, owner-decide enqueue, test-row cleanup). This analysis
  creates no credentials.
- **D-S6-5** — Item 3 uses `kill -9` + restart with the generation file
  intact; item 6 uses generation-file deletion (counter-loss). Never the
  reverse.
- **D-S6-6** — If any probe contradicts the contract (notably the epoch
  expiry / 409), the executor files the gap against the owning slice's
  scope and stops the acceptance — a failed probe is a finding, not a
  retry loop. #960 stays open until all six pass.

## 5. What S6 closes

#960 is the last open slice of #847 (S3/S4/S5 all shipped and closed).
When all six checklist items pass — harness-first, then live E2E with
test-row cleanup — #960 closes, and #847 (the phone-home vision issue)
closes with it. #849's approval loop and the #853/#854 lanes are separate
visions and are unaffected.

# Provisioning-lane convergence: the #851 hosted-provisioning vision vs state (2026-10-14)

**Vision vs state for the #851 hosted-provisioning lane** — pinned to
main `c4d4c24` (2026-10-14 ~19:42 CDT) for all in-repo claims; every
in-repo claim below was verified against that tree this turn. Issue/PR
numbers are GitHub references as of 2026-10-14 (state verified via
direct GET this turn for every lane issue named). Doc-first; honesty
rules apply (`docs/POSITIONING.md`): everything below is **current
state and work to do**, not promises. The hosted product is not live,
and no hosted box has been provisioned by this lane.

**Non-overlap map (what this doc is not):**
- `docs/PROVISIONING_LANE_CONVERGENCE_2026-10-09.md` (#851) — the
  previous convergence pin, pinned to main `03ac6cf`. This doc
  supersedes its §"remaining" list; the G51.1–G51.5 gap records stand.
- `docs/BOX_PROVISIONING_GAP_ANALYSIS.md` (2026-10-03, #851) — the
  original decomposition; still the vision's home. This doc does not
  re-file its gaps.
- `docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md` (#851/#908/H12)
  — spend-cap + metering decomposition; consumed, not re-analyzed.
- `docs/FLY_DRIVER_DESIGN_AHEAD.md` (landed as `0fedc76` via #1206) —
  the #905 build's input contract; the build still owns it.
- `docs/ORCHESTRATOR_ATTESTED_PAIRING_GAP_ANALYSIS.md` (#906/#907) and
  `docs/ATTESTATION_TOKEN_CRASH_WINDOW_GAP_ANALYSIS.md` (#907/#1209) —
  consumed, re-analyzed only where stated (§2, #1489).

## 1. The vision (#851 — verbatim acceptance)

> Waitlist → invite → provision: turning a signup into a running box.
> Covers the provisioning path (Fly Machines initially, within the
> $5/run / $25/month caps for loop-provisioned machines), initial
> pairing, and handoff to the dashboard.
>
> Acceptance:
> - Invited user gets a box **without manual operator steps**.
> - Box **auto-enrolls via the pairing flow** and appears in the dashboard.
> - **Spend caps enforced.**

Unchanged since the 10-09 pin. None of the three acceptances has been
exercised end to end.

## 2. What the lane gained since 2026-10-09

- **The /data contract is pinned (#1205 closed, PR #1230).**
  `docs/DATA_VOLUME_CONTRACT.md` + the image's `data-prep.sh` lay out
  the pinned data-volume subdirs (pairing, approvals, confirmd, ssh)
  with contract owners; sshd host-key paths symlink onto the volume.
  Issue closed as completed by the owner 2026-10-09.
- **Pairing runtime runs as the `sparkpair` box-service user (#1219
  closed, #1395 / `5778a76`).** The recipe bakes the user (locked
  password, no login, home `/home/sparkpair`); the identity-seed hook
  (root) enrolls into `/home/sparkpair/.config/spark-pair` and hands
  off; `pair-heartbeat`, `pair-rotate`, `pair-phone-home` run as
  `sparkpair` under supervisord. The golden-image README cites
  **#1220 Option B (decided 2026-10-12)** — the split-user shape landed
  in-image, but #1220 stays OPEN: the store-access decision (#1363)
  that the ingest + upload-filings legs need is still the gate.
- **The healthy-box contract is shipped (#1273 closed, #1488 /
  `c4d4c24`).** `pairing/README.md` "Verification (healthy box) —
  provisioned image (supervisord)" pins expected `supervisorctl` states
  per program (FATAL-as-page + exit-1-human-attention EXITED), the
  tick-failure signal map (the pair-* log-path correction from the
  golden-image README A1 note), the heartbeat-only liveness pin, and
  the pre-redeem vs post-redeem split. Honesty carried verbatim:
  **ingest and upload-filings are NOT wired on the image yet (#1363
  owns the store-access design)**, so the contract checks three pairing
  programs, not five; `commands_cursor.json` joins with the ingest leg.
- **The image now runs the H14 push worker (#1267, #1268).**
  `deploy/golden-image/supervisord.conf` carries `[program:push-worker]`
  (mirrors `confirm/push-worker.service`; the H14 retry half, fed by
  the #1282 plane-push signal). The provisioned image's program set is
  no longer pairing-only.
- **Host-key attestation decisions advanced (#1204 still OPEN, PR #1210
  merged).** PR #1210 pins "env persistence as the sole host-key
  fingerprint stability guarantee"; the golden-image README carries the
  driver contract for the #905 build: machine-config env persists
  across cold stops (verified against the Fly stop/start model), keys
  live on `/data` (D-V3), and the driver MUST read back
  `/run/sparkvm/ssh_host_key.status` (`source=env` + fingerprint
  equals the minted one) or the receipt is decorative.
- **Plane cron-trigger contract (#1385; #1069/#1298)** — the D9 sweep
  family now has a documented cron home; relevant to the #1214 and
  #1489 alert legs below (a plane-side job needs a place to run).
- **Housekeeping:** VERSION 0.8.0 (#1270), IMAGE_TAG separator fix
  (#1271/#1272).

## 3. New gap filed this turn

**#1489 (p3) — owner-visible alert when `pair-phone-home` enters the
human-attention class while the heartbeat keeps flowing.** The #1488
contract made the supervisord grammar precise — EXITED exit-1
the valid-token subset of the human-attention class (superseded-generation, identity-mismatch, protocol errors) is the
human-attention class, never a restart target — but on a provisioned
box there is no human watching `supervisorctl`, and the heartbeat keeps
200ing through the still-valid-token closes: verified this turn,
`cmd_heartbeat` sends only `_status_body` (box_id, sent_at, client,
uptime_s, load_1, token_expires_at), and the dashboard renders liveness
purely off `heartbeat_at` (5 min silence = stale) with no phone-home
state. A box whose phone-home channel died looks fully healthy on the
dashboard while the plane has no way to reach it except HTTPS polling.
Not covered by #1214 (never-paired only) or S6 item 2 (revoked only,
where the heartbeat 401s too). The plane-side signal exists — #999's
`phone_home_events` DO journal — so the build keys a plane-side job off
terminal closes for valid-token + fresh-heartbeat boxes (dashboard
chip and/or a new push-taxonomy paging event type); the no-restart
design stays; only the no-reconnect-after-close window should page.
Pointers will ride the #851 and #958 bodies.

## 4. Remaining (re-verified 2026-10-14)

- **#905** (Fly driver build — FLY_DRIVER_DESIGN_AHEAD is its input
  contract; build order in its §4; D-D3's host-key contract above is
  new since the design-ahead landed).
- **#906** (claim→provision orchestrator), **#907** (plane-attested
  pairing), **#908**'s spend-cap slices (**#1074**–**#1077**),
  metering (**#1047**/#1048 + emission worker), **#1089**
  (provision-record store), **#1107**–**#1110** (claim-binding,
  record lifecycle, plane-owner placement).
- **#1204** (host-key attestation mechanism — the D-D3 contract is
  decided and pinned in-image; the driver build owns it).
- **#1209** (attestation-token plaintext custody — open; the #905
  build's custody design).
- **#1214** (never-paired alert — open; shares the plane-side job
  home with #1489).
- **#1220** (pairing state root-owned — open; Option B landed in
  image, #1363 gates the rest).
- **#1489** (filed this turn; phone-home human-attention alert).

Closed since the 10-09 pin: #1203 (identity-seeding hook, closed
before), **#1205** (this window, PR #1230), **#1219** (this window,
PR #1395), **#1273** (this window, PR #1488). #851 stays OPEN
(provisioning vision tracker).

## 5. Dated amendments

- **2026-10-14:** the 10-09 pin's "remaining" list is superseded by §4
  above. The #1488 honesty note (ingest/upload-filings not wired on
  the image) is the current state of the #849 lane's S4 box-side leg
  as seen from provisioning — the #1363 store-access decision is now
  the single named gate for two lanes (approvals ingest + filing
  upload) and the image's program set.
- **2026-10-14:** the pairing README's "Known rough edges" was
  already corrected by #1488 (failure logs are 1 MiB-capped per
  D21/#1020) — no stale "unbounded logs" claim survives on the lane.

## 6. What this doc does not claim

- No hosted box has been provisioned by this lane; the vision's first
  acceptance has never been exercised end to end, and the H4 live-API
  clearance has never been consumed by the loop.
- Plane-side facts inherit the pinned reads recorded in the cited docs
  — no fresh plane read this turn. If the plane moved since those
  pins, this doc's plane statements are stale with them.
- The #905 driver is still a design-ahead: every driver-shape claim
  above (env persistence, D-D3, the read-back contract) is the
  decided contract, not shipped behavior.

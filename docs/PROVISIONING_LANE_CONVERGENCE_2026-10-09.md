# Provisioning-lane convergence: the #851 hosted-provisioning vision vs state (2026-10-09)

**Vision vs state for the #851 hosted-provisioning lane** — pinned to
main `03ac6cf` (2026-10-09 ~08:10 CDT) for all in-repo claims; every
in-repo claim below was verified against that tree this turn. Issue/PR
numbers are GitHub references as of 2026-10-09 (not code-verifiable from
the tree). Doc-first; honesty rules apply (`docs/POSITIONING.md`):
everything below is **current state and work to do**, not promises. The
hosted product is not live, and no hosted box has been provisioned by
this lane.

**Non-overlap map (what this doc is not):**
- `docs/BOX_PROVISIONING_GAP_ANALYSIS.md` (2026-10-03, #851) — the
  original G51.1–G51.5 decomposition. This doc supersedes its §2 state
  table, its §4 standing-blocker note (see §5), and its G51.4 tracking
  pin (see D-D8 in §5); the G51.1–G51.5 gap records stand.
- `docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md` (#851/#908/H12)
  — the 2026-10-06 convergence pass (spend-cap + metering
  decomposition, F-P1–F-P3, D-P1–D-P4). This doc consumes it and does
  not re-file its gaps; it adds what moved on 2026-10-07 through
  2026-10-09.
- `docs/FLY_DRIVER_DESIGN_AHEAD.md` (landed as `0fedc76` via #1206; internal pin `48a8030`) — the
  #905 build's input contract (F-D1–F-D12, D-D1–D-D8). This doc consumes
  it; the build still owns it.
- `docs/ORCHESTRATOR_ATTESTED_PAIRING_GAP_ANALYSIS.md` (#906/#907, O
  series, D-O1–D-O5) and
  `docs/ATTESTATION_TOKEN_CRASH_WINDOW_GAP_ANALYSIS.md` (#907/#1209,
  D-TW series) — the orchestrator + attestation legs. This doc consumes
  them; it re-analyzes nothing.

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

The pipeline in one line: **an invite claim becomes a running, paired,
metered box with no operator steps — the orchestrator provisions it,
first-boot identity seeding binds it to the plane, plane-attested
pairing enrolls it, and the spend ledger attributes its burn.**

## 2. What the lane gained since 2026-10-03

The 2026-10-03 analysis filed #905–#908 and stopped. Since then:

- **The golden image has a producer and a gate (#1087 closed
  2026-10-07; #1176 closed 2026-10-08).** `deploy/golden-image/` ships
  the recipe (`Dockerfile`), the build driver (`build-image.sh`:
  refuses dirty trees, never pushes — registry credentials stay
  operator-owned), the sshd first-boot wrapper (host keys generated on
  first boot, never baked), supervisord (`supervisord.conf` tini +
  supervisord), and image-manifest tooling. The per-build gate
  (`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`) is wired into the release
  workflow and runs on release tags. F-P1's "gate but no producer" is
  closed; the 2026-10-06 convergence's F-P1 re-scope ("#905 narrows to
  the driver + exec-install path") is now the standing division of
  labor: #905 consumes the image, it does not build it.
- **Claim-binding idempotency is in the contract (#1107's contract half
  on main; #1107 stays open).** `harness/provider_iface.py` carries
  D-O1: the fail-closed key `(tenant_id, claim_id, attempt_n)` on
  `ProvisionSpec`, `provision()`'s dedupe contract (same-key retry
  returns the existing box — never a second box, never an error), and
  `list_boxes()` with `BoxIdentity`. The driver-side dedupe behavior is
  #905's build scope. O1's "double-provision window" is closed at the
  contract level.
- **The attestation-token wire contract is specified (#1108, open).**
  256-bit random base64url, minted by the plane at provision-record
  creation; the owner-auth create endpoint returns the plaintext once;
  the plane stores only the hash (D-P2); the plaintext transits exactly
  twice (plane→orchestrator, orchestrator→box env). TTL, consume
  semantics, and replay behavior are #1108's build scope — the driver
  carries the opaque value.
- **The provision-record store is pinned (#1089, open).** Plane D1,
  plane-readable for the G51.3 token validation; one record, two
  consumers (G51.3 validation, #1074 ledger ingestion). F-P3's writer
  credential dependency is settled by D-O4: the orchestrator never
  writes D1 — it creates records through the plane's owner-auth endpoint
  and holds an owner key; the write credential (and its custody) is the
  trust root.
- **G51.4's golden-image leg is shipped (#1203 closed 2026-10-09; merge
  `22677c1`).** `deploy/golden-image/identity-seed-hook.sh` is a
  supervisord one-shot (fail-closed on absent/empty/whitespace-only
  `SPARKVM_BOX_ID` / `SPARKVM_PLANE_URL` / `SPARKVM_ATTESTATION_TOKEN`
  — no enroll, loud log, never an invented identity), skips when
  enrolled or in-flight (the single-use token is never re-presented —
  plane 403s replays), regenerates an orphan `box.key`, and runs
  `init` + `request` with the token in the child env only (never on
  argv, never logged). `pairing/spark_pair.py`'s `request` gained
  `--attestation-token` (`SPARKVM_ATTESTATION_TOKEN` env fallback);
  `auto_approved` skips the human ceremony and records inert
  `attested:true`. 31 hook + client tests, toggle-verified
  non-vacuous. Redeem completion is #907's box-side half; cold-stop
  state persistence is #1205's /data contract.
- **The host-key attestation mechanism is decided, not built (#1204,
  open).** D-D3: at provision, the driver mints a per-machine ed25519
  host keypair and injects the private key via machine-config env
  (`SPARKVM_SSH_HOST_KEYS`, alongside the D-D6 identity vars); the
  image's first-boot wrapper gives env-provided keys precedence and
  keeps `ssh-keygen -A` for non-hosted use; hosted provision fails
  closed when the driver cannot mint. Attestation holds by construction —
  `ssh_info()` reports the fingerprint of the key the driver minted,
  over the authenticated provision channel. Load-bearing: machine-config
  env persistence across cold stops is the sole stability guarantee —
  the #1204 build-time verification is not optional.
- **The /data volume-mount contract is filed (#1205, open).** The
  inventory of box state that must persist on `/data` across cold stops
  (ephemeral-rootfs reference shape) vs the image — provision-time write
  targeting rides it.
- **The attestation crash windows are designed (#1209 answered;
  analysis shipped 2026-10-09 as `bec22c7`).**
  `docs/ATTESTATION_TOKEN_CRASH_WINDOW_GAP_ANALYSIS.md` walks the
  mint→pair pipeline and pins the crash between token mint and
  `provision()`: the plaintext exists in exactly one place (the dead
  orchestrator's memory) and cannot be recovered by construction —
  so the answer is reconcile-driven **supersede to attempt_{n+1}**
  (fresh token, claimant-invisible, no #1214 alert for superseded
  attempts; orchestrator-side plaintext persistence and a plane re-issue
  endpoint both rejected with reasons). No box-side change; placement
  independent.
- **A never-paired alert is filed (#1214, p3).** Security's suggestion
  from the #1203 review: the plane should alert on
  provisioned-but-never-paired boxes.
- **The orchestrator leg is decomposed (O series, #1107–#1110).**
  #1107 (claim-binding idempotency), #1108 (attestation wire contract),
  #1109 (provision-record lifecycle + supersede + sweeper),
  #1110 (orchestrator placement + record creation via the plane
  owner-auth endpoint). D-O4 (orchestrator never writes D1; in-repo cron
  placement) and the supersede mechanic (#1109, refined by the crash
  analysis) stand.
- **Spend-cap and metering decompositions stand, unbuilt.** #908 →
  #1074 (spend-ledger D1 schema + provision-record ingestion), #1075
  (pre-provision cap-check hook + projected-cost function; interim
  static size→cost table until #905's driver-owned model lands per
  D-D4), #1076 (destroy-on-breach worker + pre-destroy notice), #1077
  ([POLICY] cap catalog). Metering: #1047 (box-local producer), #1048
  (plane ingestion), and the 2026-10-06-filed emission worker
  (spool → plane, fail-open).

## 3. Vision vs state (pinned 2026-10-09)

| Vision element | State |
|---|---|
| Waitlist → invite | **Ships.** `site/waitlistd.py` + `site/waitlist_invites.py` (invite waves, claim POST, `claimed` funnel event); landing live at `sparkvm.dev/waitlist`. Unchanged since 2026-10-03. |
| Invite → provision trigger | **Nothing.** No claim→provision orchestrator anywhere in the repo. G51.2 rides #906 (open); placement + record-creation leg is #1110 (open). |
| Provision (provider driver) | **Contract only.** `harness/provider_iface.py` is executable (D-O1 idempotency, `list_boxes()`/`BoxIdentity`, dedupe contract) — verified this turn. **No driver implements it** (no Fly driver on main; the build-input contract is `docs/FLY_DRIVER_DESIGN_AHEAD.md`). Open as #905. |
| Golden image | **Ships.** Producer + per-build gate (#1087, #1176). The driver's digest-pinned image ref is operator config (D-D5). |
| First-boot identity seeding | **Ships — golden-image leg only.** #1203 (closed): the hook reads the D-D6 machine-config env, fails closed, never re-presents the token. The exec-install `/data` leg stays deferred with the F1b alternative per D-D2 (see D-D8, §5). |
| Host-key attestation | **Decided, unbuilt.** #1204 (open): driver mints + env-injects per-machine ed25519; image prefers env keys; env persistence across cold stops is the unverified stability assumption. |
| Attestation wire contract | **Specified, half-built.** #1108 (open) pins the token lifecycle; the box presentation half is shipped (#1203's `--attestation-token`); the plane validate-and-consume half rides #907. |
| Auto-enroll approval | **Design in progress.** #907 (open): single-use token, validated and atomically consumed against the D1 provision record, `approved_by='provision-orchestrator'` bound to the record id; crash-window recovery pinned (D-TW series: supersede to attempt_{n+1}). |
| Provision-record store | **Decided, unbuilt.** #1089 (open): D1 schema contract; orchestrator writes via the plane owner-auth endpoint (D-O4). |
| Appears in the dashboard | **Mechanics exist.** #845/#954 shipped the authenticated dashboard; the row comes from the pairing/enrollment record. No provision-time registration path — deliberately not built: the orchestrator's job is to make pairing→enrollment complete (G51.2/G51.3). |
| Spend caps enforced | **Decomposed, unbuilt.** #908 → #1074/#1075/#1076/#1077 (all open). The driver owns the size→cost model (#1075 consumes it, D-D4). The $5/run / $25/month loop-provisioned caps stay policy, not mechanism; the hosted path has no cap check, no ledger, no destroy worker yet. |
| Metered | **Decomposed, unbuilt.** #1047 (box-local), #1048 (plane ingestion), the emission worker (fail-open). |
| Never-paired alert | **Filed.** #1214 (p3): provisioned-but-never-paired plane-side alert. |

## 4. The lane's build order (dependency order for the queue)

D-P4's 2026-10-06 order, refreshed with the 2026-10-07–09 gains.
D-P4's parallelism stands: the numbers below mark dependency groups,
not a serial start-after order — a build may start once it has
consumed the decided design contracts, and the build slices of the
design issues proceed in parallel.

1. **#1089** (provision-record schema contract) — before #906's
   record-store wiring and #1074's provision-record ingestion, since
   both consume the schema.
2. **#1108** (attestation wire contract) — the contract is decided and
   consumed by #905's build; the box presentation half is shipped
   (#1203); the plane validate-and-consume half is #907's build scope
   (see item 7).
3. **#1205** (/data contract) — the #905 provision path must know where
   provision-time writes land.
4. **#1204** (host-key attestation) — #905's `ssh_info()` build scope;
   carries the build-time env-persistence verification.
5. **#905** (Fly driver) + **#1203** (image hook, shipped) — a machine
   that boots, seeds, and presents a token; first smoke provision is
   #905's first slice (H4 live-API clearance is granted). The F-D12
   handoff branch ((a) machine-exec disabled at handoff vs (b)
   operator-signed §6 invariant-5 revision) is named by the driver's PR.
   #905 may start now: it consumes the decided contracts (#1089 D1
   schema, #1108 wire contract, #1204 env-persistence design, #1205
   /data contract) and carries #1204's build-time env-persistence
   verification.
6. **#906** (claim→provision orchestrator) — consumes the claim stream,
   calls `provision()` with the fail-closed claim key (D-O1), the
   #1089 record store, the #1108 token, and the #1075 cap-check hook
   (interface decided; built in parallel — #906's first cut ships
   behind the H4 policy caps until the hook lands).
7. **#907** (plane-attested pairing) — validate + atomically consume the
   token (the #1108 plane half), approve with the typed reason.
8. **#1074 → #1075 → #1076** (spend-cap), **#1077** ([POLICY]);
   **#1047 → F-P2/#1088 → #1048** (metering).

## 5. Dated amendments (supersession notes)

- **D-D8 (2026-10-09, recorded in FLY_DRIVER_DESIGN_AHEAD):** the
  2026-10-03 G51.4 pin — "G51.4 rides #905 (the driver issue); relates
  to #134 (open)" — is superseded for the golden-image leg only — the hook is
  image-side (`deploy/golden-image/`), re-tracked to #1203 (closed).
  The exec-install `/data` leg stays deferred with the F1b alternative
  per D-D2.
- **F-D8 (2026-10-09):** `FLY_DRIVER_RESEARCH.md`'s `parked` language is
  stale against the shipped contract (`provider_iface.py` adjudication:
  driver-requested suspend always surfaces as `suspended`; warm-vs-cold
  rides `memory_resume` / `wake_kind`). The #905 build follows the
  contract; the research doc's dated supersession note rides the #905
  build's PR — recorded here so no turn re-litigates it.
- **2026-10-09 freshness note on the 2026-10-03 analysis's §4 standing
  blocker:** the loop's own dev-box SSH to the hosted box failing
  host-key verification no longer constrains the tenant path —
  D-D3's attested `ssh_info()` design removed loop→box SSH from the
  trust chain (attestation holds by construction from the provision
  channel). The operator/loop access path itself stays standing
  NEEDS_USER-owned (2026-10-05: Tailscale node identity is the trust
  root; re-pin on rotation, never re-raise). The §4 substance ("the
  loop must not auto-accept host keys") is unchanged; only the blast
  radius narrowed.

## 6. What this doc does not claim

- No hosted box has been provisioned by this lane — the vision's first
  acceptance ("invited user gets a box without manual operator steps")
  has never been exercised end to end, and the H4 live-API clearance
  has never been consumed by the loop.
- Plane-side facts inherit the pinned reads recorded in the cited docs
  (2026-10-02 provisioning read; 2026-10-05 metering read) — no fresh
  plane read this turn. If the plane moved since those pins, this doc's
  plane statements are stale with them.
- This doc files no new issues and changes no code. Everything the
  2026-10-07–09 verification pass surfaced was already filed; #851
  stays open (provisioning vision tracker) alongside #905–#908,
  #1074–#1077, #1047/#1048, #1089, #1107–#1110, #1204, #1205, #1209
  (answered, open), and #1214.

# Orchestrator + attested-pairing gap analysis (#906 / #907)

**Vision vs current state for the claim→provision→attested-pair leg** —
pinned to main `2a4669c` for all in-repo claims. This is the
design-ahead pass over `docs/BOX_PROVISIONING_GAP_ANALYSIS.md` (G51.2,
G51.3 — 2026-10-03) and `docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md`
(F-P3, D-P2, D-P4 — 2026-10-06): what the #906 orchestrator and the #907
attestation protocol still need pinned before either can be built.
Plane facts inherit the pinned reads those docs record (no fresh plane
read this turn); the plane's pairing endpoints are pinned to
`docs/CONTROL_PLANE_API_REFERENCE.md` at this commit.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live.

## 1. The vision, restated for this leg

An invite claim becomes a running, **paired** box with no operator
steps: the orchestrator consumes the claim, the Fly driver provisions a
machine from the golden image, first-boot identity seeding binds the box
to the plane, **plane-attested pairing enrolls it without a human
click**, and the dashboard row appears. #906 owns the wiring; #907 owns
the auto-approval design. Acceptance (from the issues): an invite claim
becomes a running paired box in the dashboard with no operator steps;
the approval record names the provision record, not a human.

## 2. What the lane gained since 2026-10-03

- **The approval-record vocabulary #907 consumes is shipped.**
  `POST /v1/pairing/{id}/approve` carries typed reasons; the plane
  records `approved_by` (the #844 ship record: `approved_by='bootstrap'`
  for the fresh-database first-claim path; `pairing/README.md` §First-owner-key
  bootstrap). #907's attested approval reuses the shape with
  `approved_by='provision-orchestrator'` — it no longer has to invent it.
- **The pairing-request wire shape is pinned.**
  `POST /v1/pairing/request` is **unauthenticated** and takes
  `{name, pubkey(b64), fingerprint}` → `{pairing_id, code, expires_at}`
  (`docs/CONTROL_PLANE_API_REFERENCE.md`, Pairing endpoints table).
  The server computes the fingerprint from the submitted pubkey itself
  (the client value is ignored — the fingerprint-spoof hole is closed).
  Pairing codes carry a 15-minute lazy expiry; at most 50 pairings may
  be pending (429 beyond). The attestation token rides this
  unauthenticated endpoint as a new field — the token *is* the
  auto-approval credential, which is why its consume must be atomic
  and single-use (finding O2).
- **The golden-image producer is closing.** F-P1's gap (#1087) is closing:
  the pinned-Dockerfile build driver with dirty-tree-refusing builds
  (`deploy/golden-image/build-image.sh`) and the supervisord daemon set
  are merged; the digest-pin recorder
  (`harness/pin_image.py` → `deploy/golden-image/pinned-image.json`)
  ships in PR #1106 — **not yet on main** at the pinned commit — and
  will give #906's driver call an image to pin and a record the #905
  driver consumes as its operator-set pin
  (`docs/FLY_DRIVER_RESEARCH.md` §F3b) once merged.
- **The provision-record home is pinned (D-P2).** #1089's contract:
  the provision record (claim id, invite, box id, attestation-token
  hash, tenant binding) lives in plane D1 — one record, two consumers
  (G51.3 token validation, #1074 spend-ledger ingestion). Token stored
  as hash, never plaintext.
- **The retry/lineage rule exists (D-C5).**
  `docs/SPEND_CAP_ENFORCEMENT_GAP_ANALYSIS.md` D-C5: failed provision
  attempts share the retry-chain lineage; ingestion is idempotent. The
  orchestrator's re-provision story consumes it (finding O3).
- **The commit→emit lesson is in the claim path.**
  `site/waitlist_invites.py --reconcile-claimed` (#898): the claim row
  is committed *before* `claimed` is emitted; the dangerous window the
  orchestrator must survive is its own mirror image (finding O1).

### 2026-10-07 refresh — F-P1 / #1087 closed (post-#1106)

The §2 "golden-image producer is closing" bullet and the §5
"golden-image producer (#1087, closing)" line were written at the pinned
commit `2a4669c`, when PR #1106 was open but unmerged. PR #1106 merged
2026-10-07 (commit `506ff48`); the digest-pin recorder
(`harness/pin_image.py` → `deploy/golden-image/pinned-image.json`) is now
on main. The producer is **closed, not closing**:

- Slice 1 (PR #1100) shipped the producer: pinned-Dockerfile recipe,
  dirty-tree-refusing build driver baking the exact commit + release tag
  into the manifest, the supervisord daemon set.
- Slice 2 (PR #1106) shipped the publish pin: the fail-closed writer
  records the digest-pinned ref only for a completed gate pass on the
  exact baked SHA, only the `registry.fly.io` host the driver contract
  names, only a digest-pinned ref (a bare tag is never launchable);
  re-pinning the same SHA to a different digest needs `--force`.
  `read_pin()` / `pin_image_ref()` raise `PinnedImageError` on a
  missing or invalid record, so the future #905 driver cannot provision
  from an unpinned image. The record is validated, not tamper-evident —
  the trust root is the operator who ran the pin and the reviewed
  pinning commit (`deploy/golden-image/README.md` §"Publish + pin
  (operator)" documents the operator flow).

Net for this lane: F-P1's "the golden image has a gate but no producer"
is now fully closed — the lane has a producer (recipe + build driver)
and the pin machinery (fail-closed writer + `read_pin()` /
`pin_image_ref()`, the record the #905 driver's §F3b contract names as
its operator-set pin); no image has been built or pinned yet —
publishing remains an operator step per
`deploy/golden-image/README.md` §"Publish + pin (operator)". Issue
#1087 closed via #1106's `Closes`. What remains is unchanged by this
refresh: #905 (driver), #906 (orchestrator), #908 (spend-cap mechanism),
#1089 (provision-record store), the O-series findings (filed as
#1107–#1110), and decisions D-O1–D-O5.

§2's other bullets were re-verified against main `c9b9f84` (2026-10-07)
and show no drift: the pairing-request wire shape still matches
`docs/CONTROL_PLANE_API_REFERENCE.md`; the #1089 provision-record
contract is open and unchanged; `docs/SPEND_CAP_ENFORCEMENT_GAP_ANALYSIS.md`
D-C5 is unchanged; `site/waitlist_invites.py --reconcile-claimed` still
commits the claim row before emitting `claimed` (#898 is closed, the
code claim still holds); the `approved_by` pairing vocabulary is
unchanged since #844.

## 3. Findings: genuinely-new gaps (O-series)

Gaps already filed (#905, #906, #907, #908, #1074–#1077, #1047, #1048,
#1087, #1088, #1089) are not re-filed. These pin what G51.2/G51.3 and
F-P3/D-P2 left open:

- **`[BLOCKER]` O1 — claim-binding idempotency is still unpinned.**
  G51.2 named the gap ("claim-binding (an idempotency key on
  ProvisionSpec or driver-level dedupe keyed by claim id)") but pinned
  no contract. Verified at this commit: `harness/provider_iface.py`
  `ProvisionSpec` (L222–254) carries **no** idempotency key and **no**
  claim reference — `tenant_id` is the only identity on the spec. The
  dangerous window is real: the orchestrator calls
  `driver.provision()` (money spent, machine exists), crashes before
  recording, retries, and provisions a **second box** — the exact
  mirror of the #898 window, except the leaked resource bills by the
  minute. The orchestrator's startup reconcile also needs a driver-side
  read: list machines and match them against unconsumed provision
  records before issuing new provisions. The driver must therefore tag
  what it creates and remember in-flight keys across its own restarts.
- **`[DESIGN]` O2 — the attestation token's wire contract is unpinned.**
  G51.3 pinned the mechanism (single-use token, seeded via
  machine-config env, validated and consumed at the plane pairing
  endpoint, typed approval). Unpinned: the request field name, the
  token format, the TTL between provision and first-boot pairing, the
  consume semantics, replay behavior, and the fallback when the token
  is absent or expired. Because `POST /v1/pairing/request` is
  unauthenticated by design (the box has no credential yet), anyone
  reaching the endpoint can *present* a token — the security of the
  whole leg rests on the token being unguessable, bound, and
  atomically consumable. The machine-config env is operator-visible
  (Fly machine config is readable by the operator), so the token's
  pre-consumption window is a forgery window by construction — it must
  be bounded, not wished away.
- **`[DESIGN]` O3 — the provision record has no lifecycle past pairing.**
  #1089 pins the schema; D-C5 pins retry lineage; #1074 ingests the
  records for the spend ledger. Unpinned: the record's state machine
  and who transitions it. A box that never pairs (token TTL lapses), a
  box destroyed on cap breach (#1076), a re-provision that supersedes
  an earlier attempt — each leaves the record in a state the ledger
  must attribute correctly and the pairing endpoint must enforce
  (a superseded token must not auto-approve a second box). Today the
  record has no terminal states and no sweeper.
- **`[DESIGN]` O4 — F-P3's unexamined dependency is still unexamined.**
  F-P3 named it honestly: "who authenticates the orchestrator's D1
  writes — the orchestrator writes operator-trusted records consumed
  by both G51.3 validation and the #1074 spend ledger, so the write
  credential (and its custody) is the actual trust root, not the store
  choice. That credential design rides with #1089's schema contract."
  #1089 shipped the schema without pinning the writer's credential.
  G51.2's placement decision (1) is also still open: the claim store
  today lives in `WAITLIST_DATA` rows.jsonl in-repo, while the
  production claim POST targets the control-plane origin; the plane
  worker has no scheduled/cron path (documented in the D9 analysis),
  so a plane-resident orchestrator has nowhere to tick.

## 4. Decisions pinned (D-O series)

- **D-O1 — idempotency key = `(tenant_id, claim_id, attempt_n)`, required
  on `ProvisionSpec`.**
  Fail-closed at construction, like `tenant_id`: a spec without a
  claim binding is rejected, not honored. The driver dedupes on the
  full key and returns the existing `vm_id` on retry of the same
  attempt — never an error, never a second box. Scoping the attempt
  into the key is load-bearing: D-O3's re-provision writes `attempt_n`
  with a fresh token, and a claim-scoped key would return attempt_1's
  `vm_id` (whose env holds the now-superseded token) for attempt_n's
  provision — a box that can never auto-pair while the orchestrator
  believes attempt_n is in flight. The driver's in-flight
  key→vm_id map must survive driver restarts (for the Fly driver: the
  key rides machine metadata at create so a fresh driver process can
  rebuild the map by listing). The orchestrator's startup path is
  **list → match → then provision**: reconcile driver-listed machines
  (matched by the metadata key) against unconsumed provision records
  before issuing any new `provision()` call. Supersede includes
  old-machine teardown: the orchestrator destroys attempt_{n-1}'s
  machine (when it still exists) as part of the supersede transition,
  before attempt_n's provision is issued — a superseded machine is
  never left running with a dead token. This closes the crash window
  in both directions — the driver never double-provisions, and the
  orchestrator never orphans a provision it forgot it made.
- **D-O2 — the attestation token is a bound, TTL'd, atomically-consumed
  bearer token**
  - Format: 256-bit random, base64url, opaque. Minted by the plane at
    provision-record creation — D-O4's owner-auth create endpoint
    returns the plaintext once, over the already-authenticated channel;
    the plane stores only the hash (D-P2). The plaintext transits
    exactly twice: plane→orchestrator in the create-record response,
    orchestrator→box in the machine-config env. At rest it exists in
    the machine-config env and the box's first-boot memory (plus
    transiently in the orchestrator's memory between the two hops).
  - Enrolled identity: the plane enrolls the **presenting pubkey**. It
    cannot verify the presenter is the minted `box_id` on an
    unauthenticated endpoint, so "a token minted for box X enrolls only
    box X" is unenforceable as stated. What the token *does* bind is
    the approval: auto-approval fires only against the provision record
    whose token hash matches, and the approval is bound to that
    record's `(tenant_id, claim_id, box_id)` — a token-holder can only
    ever enroll under the same tenant and claim, never cross-tenant or
    cross-claim. The same-tenant substitution residual (a config-reading
    operator presenting the token from another machine) is accepted:
    the only party that can read Fly machine config is the operator,
    who already holds the owner key and the Fly token — against an
    adversarial operator nothing in this leg holds.
  - Threat model: the token defends against *leakage* (logs, API audit
    trails, shoulder-surfed config), not against the operator. For
    leakage, 24 h TTL + atomic single-use consume + 403-and-audit on
    replay is defense-in-depth; the TTL bounds the window a leaked
    token stays useful.
  - Wire: new optional field `attestation_token` on
    `POST /v1/pairing/request`. The box's first-boot hook presents it
    on the pairing `request` call (`pairing/spark_pair.py request`
    gains the flag; the human path never sets it).
  - Consume: the plane validates the token hash against a
    `pending`-state provision record and consumes it **atomically** —
    the same UPDATE that NULLs the token hash flips the record out of
    `pending` — then approves with
    `approved_by='provision-orchestrator'` bound to the provision
    record id. No token, wrong token, or non-`pending` record → the
    request falls through to the human ceremony (code shown, never
    auto-approved). Replay of a consumed token → 403 + plane-side
    audit row (the endpoint is unauthenticated; the audit row is the
    only signal).
  - TTL: 24 h from provision **(tunable — a first pin, not a researched
    constant; the rationale is the bounded-window argument below, and the
    value should move with first-boot latency data once the leg runs).**
    The pre-consumption window is bounded, not zero — the machine-config
    env is operator-visible by construction (G51.4's only plane→box
    channel), so a leaked token stays useful for the TTL. Lapsed tokens
    are never honored late.
  - Why this doesn't reopen G51.3's forgery hole: auto-approval fires
    **only on token presentation**, never on recognition; the human
    fingerprint ceremony was unverifiable for hosted boxes anyway
    (no tenant-readable screen), so attestation from the provisioning
    party is the sound trust root; BYO/self-hosted boxes keep the
    human ceremony.
- **D-O3 — provision-record lifecycle: `pending → paired | expired |
  destroyed`, plus `superseded`.**
  The pairing endpoint transitions `pending→paired` on token consume
  (D-O2). The in-repo cron's reconcile pass (D-O4) sweeps `expired`
  past the 24 h TTL for records never paired, via the owner-auth record
  endpoint — the plane worker has no scheduled path today, so the
  sweeper's driver is the same in-repo clock, not a plane-side cadence;
  D9's option-(b) scheduled plane worker is the named future home for
  the loop and the sweeper. The destroy worker (#1076)
  stamps `destroyed`. Re-provision for the same claim writes a new
  attempt row (D-C5 lineage: `attempt_n`, `supersedes attempt_{n-1}`);
  **supersede invalidates the old token immediately** — the old
  record flips to `superseded` at supersede time, not at TTL, so a
  stale first-boot hook racing a re-provision can never auto-approve
  the dead box. Re-provision fires only on terminal, operator-visible
  failure — never on a timer and never because a first-boot is slow:
  the trigger is the token TTL lapsing with no pairing, or the destroy
  worker's (#1076) health verdict. An aggressive trigger (superseding a
  live-but-slow box) would leave a running machine that can never pair,
  so supersede requires the old attempt known-dead, not merely slow.
  #1074 ingests every terminal transition
  (`paired`/`expired`/`destroyed`/`superseded`), commit→emit at the
  plane per the #898 lesson.
- **D-O4 — the orchestrator never writes D1 directly.**
  Provision records are created through a **plane owner-authenticated
  endpoint** (the plane writes D1 itself); the orchestrator holds an
  owner key and calls the endpoint. This answers F-P3's trust-root
  question with machinery that already ships: the plane's owner-key
  auth (#843) is the write credential — no new D1-write credential.
  The cron's owner key lives in the existing in-repo secret custody
  (the same store the loop's operators already use for plane owner
  keys), so F-P3's custody question is closed by naming it, not by
  inventing a new story. Orchestrator placement follows: the
  claim→provision loop runs as an **in-repo supervised cron one-shot**
  (flock-serialized, loud failure — the #864/#953 discipline), reading
  claims from the in-repo claim store today and from the plane's claim
  surface when the control-plane claim POST deploys. The plane worker
  has no scheduled path, so a plane-resident orchestrator has nowhere
  to tick — in-repo is not a compromise, it is the only place with a
  clock (D9, `PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md`, already chose a
  future scheduled-plane-worker home for the sweep — the orchestrator's
  loop and the D-O3 sweeper migrate there when it exists; in-repo is the
  only clock today, not the forever home). The driver itself stays
  behind `provider_iface`; the orchestrator calls the driver directly
  (same process) and the plane for record creation.
- **D-O5 — tenant_id sourcing: claim→tenant link, fail-closed.**
  G51.2's decision (2) is answered for the MVP: the orchestrator
  derives `tenant_id` from an explicit claim→tenant link record
  (written at claim time or by the operator). No link → no provision,
  loud. The orchestrator never invents a tenant. H3's identity model
  later replaces the link table, not the fail-closed contract.

## 5. Explicitly NOT new gaps (already owned)

- Fly driver build + exec-install path (#905), golden-image gate
  (exists), first-boot hook (rides #905/G51.4), golden-image producer
  (#1087 — closed 2026-10-07; see the refresh in §2), meter envelope emission (#1088), provision-record
  schema (#1089), spend-cap slices (#1074–#1077), meter_agent (#1047),
  plane metering endpoint (#1048), H4 live-API clearance (granted),
  the human pairing ceremony (ships — #844), token rotation (#846),
  heartbeat (#864), dashboard (#845/#954), the plane-side pairing
  endpoint implementation (plane workspace work follows the in-repo
  contract, per the #846 precedent).

## 6. Gaps filed

- O1 → #1107: claim-binding idempotency key on `ProvisionSpec` +
  driver dedupe contract + claim→tenant fail-closed sourcing (#906
  slice).
- O2 → #1108: attestation-token wire contract — request field,
  atomic consume, 24 h TTL, replay rules, human-ceremony fallback
  (#907 slice).
- O3 → #1109: provision-record lifecycle states + supersede
  invalidation + sweeper + #1074 ingestion shape (#1089/#1074 slice).
- O4 → #1110: orchestrator placement (in-repo cron) +
  provision-record creation via the plane owner-auth endpoint, no
  direct D1 writes — answers F-P3 (#906 slice).

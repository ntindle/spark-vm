# Attestation-token crash-window gap analysis (#907 / #1209)

**Vision vs current state for the attestation token's crash windows** —
pinned to main `22677c1` for all in-repo claims. This is the design-ahead
pass over #1209 (filed 2026-10-09 by the arch deep-read of
`docs/FLY_DRIVER_DESIGN_AHEAD.md` F-D5,
`docs/ORCHESTRATOR_ATTESTED_PAIRING_GAP_ANALYSIS.md` D-O1/D-O2, and
`harness/provider_iface.py` D-O1): what happens when the orchestrator
crashes — or the driver call fails — **after** the plane mints the
attestation token and **before** any machine exists. The plane stores
only the token hash (D-P2) and cannot re-issue it; the token's plaintext
exists in exactly one place — the dead orchestrator's memory.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live. The create-record endpoint that mints the token (#1089's build
scope) does not exist yet — this design is pinned **before** the build,
so the orchestrator's recovery contract is settled when the endpoint
lands.

## 1. The pipeline this leg walks

For the crash analysis, the mint→pair pipeline has six hops (the
decisions each hop already pins are named):

1. Orchestrator calls the plane's owner-auth create-record endpoint
   (D-O4: the orchestrator never writes D1; it holds an owner key).
2. Plane mints the 256-bit base64url token, stores **only the hash**
   (D-P2), returns the plaintext once over the authenticated channel
   (#1108, D-O2).
3. Orchestrator calls `driver.provision(spec)` with the fail-closed
   idempotency key `(tenant_id, claim_id, attempt_n)`; the key rides
   machine metadata at create so a fresh driver process can rebuild
   the in-flight map by listing (D-O1).
4. Driver creates the Fly machine; the token enters machine-config env
   (D-D6); the orchestrator records the `vm_id`.
5. First-boot hook presents the token on the pairing `request` call
   (`--attestation-token`; #1203 shipped the box half — skip-if-enrolled,
   skip-if-inflight, never re-presented).
6. The plane validates the hash, **atomically consumes** it (same UPDATE
   NULLs the hash and flips the record out of `pending`), and approves
   with `approved_by='provision-orchestrator'` bound to the provision
   record id (#1108, D-O2). Replay of a consumed token → 403 + audit.

## 2. The crash windows, enumerated

| Window | State at crash | Recoverable today? |
|---|---|---|
| **W0** — post-mint (hop 2), pre-`provision()` (hop 3) | Plaintext only in dead memory; plane holds hash + `pending` record; **no machine exists** | **No.** Nothing owns the recovery — this is #1209's gap. |
| W1 — `provision()` in flight | Machine may or may not exist | Yes — D-O1: driver dedupes on the attempt key and returns the existing `vm_id` on retry; reconcile does list→match→then-provision. |
| W2 — post-provision, pre-record (hop 4) | Machine exists, token already in its env | Yes — reconcile finds the machine by the metadata key; no plaintext needed. |
| W3 — machine exists, never pairs (TTL lapses / box dead) | Record `pending`, token hash valid, machine live or dead | Yes — D-O3 sweeper stamps `expired` past the TTL; the destroy worker (#1076) stamps `destroyed`. |
| W4 — consumed token replayed | Record consumed | Yes — 403 + plane-side audit row (D-O2, #1108). |

W1–W4 are owned. W0 is the only window where the attempt is
**unrecoverable as specified**: the reconciler's list→match finds an
unconsumed `pending` record with no matching machine and re-issues
`provision()` — but the orchestrator no longer holds the token
plaintext and the plane cannot return it. Re-issuing the provision is
specified but unprovisionable.

## 3. Findings: what W0 pins open

- **F-TW1 — the D-O1 crash-window analysis has a pre-machine hole.**
  D-O1's window is "provision() succeeded, orchestrator crashed before
  recording" — the mirror image. The pre-`provision()` window (minted
  token, zero machines) is unexamined: D-O1's reconcile (list→match→then
  provision) assumes the token is still in hand, which holds only when
  the reconciler is the minter's own process — never across restarts of
  the flock-serialized cron one-shot (D-O4).
- **F-TW2 — no party can recover the plaintext by construction.**
  D-P2 (hash-only) and #1108 (plaintext-once) are deliberate custody
  decisions, not oversights. Any recovery that re-issues the token
  contradicts one of them. The only consistent recoveries are (a) the
  orchestrator durably persists the plaintext, or (b) the attempt is
  superseded with a fresh token — one of them must be chosen, and the
  choice composes with the D-O3 lifecycle, not against it.
- **F-TW3 — the W0 case is distinguishable from every other window by
  the machine listing.** `pending` record + no machine carrying the
  attempt's metadata key + flock-serialized sole-writer reconciler =
  the token is gone and no live machine can be orphaned by supersede.
  This is a stronger precondition than D-O3's "known-dead, never
  merely slow" — there is no machine at all.

## 4. Decisions pinned (D-TW series)

- **D-TW1 — W0 recovery is reconcile-driven supersede to
  attempt_{n+1}.** (This answers #1209.)
  The reconciler treats "pending record + no machine matched by the
  attempt metadata key" as a failed attempt: it flips the old record
  `pending → superseded` (the old token invalidated at supersede time —
  #1109's rule extends to pre-machine attempts; F-TW3's "no machine"
  precondition satisfies D-O3's "known-dead, never merely slow"), then
  proceeds with attempt_{n+1} (fresh create-record call → fresh token).
  This composes with D-O1's attempt-scoped idempotency (the new attempt
  has its own key, so the dead attempt's machine — which does not exist
  — can never be returned for the new attempt) and with D-C5's
  retry-chain lineage (`attempt_n`, `supersedes attempt_{n-1}`).
- **D-TW2 — rejected (a): orchestrator-side plaintext persistence.**
  It reintroduces the exact plaintext-custody problem D-P2 was designed
  to avoid: a second secret store with its own custody story, its own
  TTL/cleanup semantics, and an unpinned home (the orchestrator's
  placement is still #1110's open question). The custody principle —
  the plaintext transits exactly twice (plane→orchestrator,
  orchestrator→box env) and exists at rest only in the machine-config
  env — stays intact only if the orchestrator never durably holds it.
- **D-TW3 — rejected (b): a plane re-issue/rotate endpoint.**
  It contradicts #1108's plaintext-once contract and widens the forgery
  window the single-use design bounds: a re-issue endpoint turns the
  single-use invariant from a structural property (hash NULLed on
  consume) into a policy the endpoint must enforce on every call. The
  #1108 contract is not amended.
- **D-TW4 — the supersede trigger's three gates.** The reconciler
  supersedes only when (1) the record is `pending`, (2) no
  driver-listed machine carries the attempt's metadata key, and (3) the
  attempt is older than the driver's create-settle bound (tunable,
  minutes — belt-and-suspenders for listing lag; with the flock-serialized
  sole writer of D-O4, no concurrent orchestrator exists, so an
  unlisted machine means it was never created). The 24 h token TTL is
  **not** a gate here: the record is unrecoverable *now* — waiting out
  the TTL would stall the claim for a full day for a box that was never
  born, and D-O3's "never supersede merely-slow" caution does not apply
  because there is no machine to orphan. The D-O3 sweeper's
  `expired` path stays for the distinct post-machine case (W3).
- **D-TW5 — the join key.** The reconciler joins provision records to
  driver machines on `(claim_id, attempt_n)` — the D-O1 idempotency key
  minus `tenant_id` (the record already carries the tenant binding per
  #1089's contract; `tenant_id` is in the machine metadata key and is
  checked, not joined on). D-C5's retry-chain lineage already names
  `attempt_n` / `supersedes attempt_{n-1}`; the #1089 schema build must
  materialize `attempt_n` as a column (it is the reconciler's match key),
  and the create-record endpoint's response must echo it so the
  orchestrator's own bookkeeping and the record agree.
- **D-TW6 — #1214's alert does not fire on superseded records.**
  Supersede is a normal, audited transition (`pending → superseded`),
  not an anomaly. #1214's scope — a TTL-lapsed `pending` record with no
  pairing and no box — explicitly excludes superseded records; the
  supersede's own audit row (D-TW7) is the signal that the attempt was
  deliberately replaced.
- **D-TW7 — the supersede writes a plane-side audit row naming the
  cause** (`w0-no-machine`), so #1074's ledger ingestion and #1214's
  alert can distinguish a deliberate W0 supersede from a TTL expiry.
  Precedent: #1108's consume-time audit on replay.
- **D-TW8 — no box-side change.** #1203's hook never sees a token in W0
  (no machine booted) and its never-re-present rule is unaffected. A
  superseded attempt's hook can never exist, so there is nothing for the
  hook to reconcile against.
- **D-TW9 — placement independence.** The W0 rule rides the reconciler,
  not the placement: today the reconciler is the D-O4 in-repo cron
  one-shot; if placement ever moves to a plane-resident orchestrator,
  the trigger (machine-listing + flock-equivalent sole writer) moves
  with it unchanged.

## 5. Explicitly NOT new gaps (already owned)

- The attestation-token wire contract (#1108, open), the provision-record
  store (#1089, open), the orchestrator build (#906, with #1107 claim
  binding + #1110 placement filed), the provision-record lifecycle +
  sweeper (#1109, open — D-TW1/D-TW4 refine its supersede scope, noted by
  pointer comment, not re-filed), the never-paired alert (#1214, open),
  the box-side hook (#1203, shipped), the idempotency key (D-O1, #1107),
  the 24 h TTL pin (#1108/D-O2 — "a first pin, not a researched
  constant"; the create-settle bound in D-TW4 gets the same treatment),
  #1074's ledger ingestion of terminal transitions.

## 6. Honest open items

- **The create-settle bound value is unresearched** (D-TW4): "minutes"
  is a first pin, not a measured constant — it should move with the
  Fly driver's actual create-listing latency once the leg runs.
- **The create-record endpoint is #1089's build scope** (open): D-TW5's
  "echo attempt_n in the response" is a contract requirement for that
  build, not a behavior that exists.
- **The D-O3 sweeper's W3 path is unchanged by this analysis** — a
  `pending` record *with* a machine that never pairs still waits out
  the TTL before the supersede/expire decision; only the no-machine
  case supersedes immediately.

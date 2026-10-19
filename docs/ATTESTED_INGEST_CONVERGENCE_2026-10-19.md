# Attested-ingest lane convergence, 2026-10-19: the #775 S3 slices vs state

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `2e33ceca` (2026-10-19, PR
#1765's merge — four slots after the S3 ingest landed). Issue/PR
numbers are GitHub references as of 2026-10-19 (not code-verifiable
from the tree). Honesty rules apply (`docs/POSITIONING.md`): this
describes current state and work to do, not promises. Nothing here
authorizes an update on any box.

This document converges the #775 (G13 trust-model implementation)
lane's third slice: the 2026-10-15 convergence pin
(`docs/TRUST_MODEL_CONVERGENCE_2026-10-15.md`) left S3 filed-but-
unbuilt as #1516; the 2026-10-19 0659 feature turn shipped the S3
ingest half (PR #1762, merge `c9254d0a`, unanimous SHIP IT —
Security/Engineering/Architecture/QA, CI 13/13 on the reviewed head
`0b7542bd`, merged tree byte-identical to the reviewed head). This
turn re-verifies every S3 disposition against what actually landed.

## 1. The vision (#1516's scope, verbatim)

1. **The signed box→plane event channel mechanism** (the "G17 S3
   remainder"): how a box proves its identity on the event. For tenant
   fleets this is required from day one (§3 T2: the operator estate
   may start without attestation; the hosted tenant fleet may not).
2. **Attested ingestion in `fleet/events.py`:** replace the
   `attested: False` stub — verify the channel signature at ingest,
   set `attested` true only on verified rows, keep the `attested:
   False` path for legacy/log-only rows (the schema must stay able to
   represent both).
3. **The T2 consume-gate rule as a pinned acceptance:** every
   consuming gate filters `attested == true`; unattested rows may be
   logged, never gate-consumed. (Until the G15 controller exists, the
   rule is pinned at the ingest + documented for the first gate
   builder.)

## 2. The state (verified at `2e33ceca`)

**Scope 1 — mechanism SHIPPED, producer half explicitly the
follow-up.** `fleet/attest.py` (400 lines): ed25519 box-identity keys,
canonical envelope `{"box_id", "row"}` (signature covers the raw row
bound to box_id; the `attestation` member itself is outside the
envelope), write-once `<store>/box-keys.json` registry
(`pin_box_key` — idempotent same-key re-pin, fail-closed on a
different key, temp-file + os.replace + fsync under the store lock),
fail-closed `verify_attestation` (malformed/missing-key/bad-signature
all yield `attested=False`; a bad signature on a claiming row is the
forgery signal — loudest collector note). The box-side contract is
`format_attested_row` (canonical `json.dumps` with
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`).
`fleet/test_attest.py`: 33 tests. The operator CLI exists and works —
`python3 fleet/inventory.py box-key pin/show` (verified live on a
scratch store this turn: pin prints the `SHA256:` fingerprint, show
reads it back). The module docstring names the producer half as the
G18/producer lane's follow-up: wiring the deploy agent to sign rows
at emit time is NOT in this slice. The #844 pairing key is explicitly
disqualified as a signing key (guest-resident, tenant-exfiltratable);
an operator-estate box signs with its provisioned key; the mechanism
is key-agnostic.

**Scope 2 — attested ingestion SHIPPED.** `canonicalize_audit_rows`
(`fleet/events.py`) verifies every object row's attestation claim
*before* the shape gates (events.py:408) — a forged signature on a
claiming row produces the loud forgery note even when the row's shape
is unknown or local-only. Valid signatures stamp `attested: True`;
everything else stays `attested: False`. The legacy path is intact:
`fleet/test_events.py:149` still pins unsigned rows to `attested is
False` — that test is the legacy-path pin, not a stale stub.

**Scope 3 — T2 rule pinned as code + documented for the first gate
builder.** `attest.gate_consumable_events` is the filter every
consuming gate reads through (`test_attest.py:477` pins the filter);
`docs/ROLLOUT_CONTROLLER_DESIGN.md` (§204 area) and
`docs/UPDATE_EVENT_REPORTING.md` (§S3) pin the rule for the G15 gate
builder. No in-repo consumer violates it today — verified this turn:
`fleet/gate_publish.py`'s freeze-hold rows are controller-origin
(`"source": "controller"`, `"trigger": "manual"` — the pin's
"controller's own authority" carve-out, and their `attested: False`
stamp is honest); `evaluate_gate_stale_alerts` (#1631) reads the
collector-local gate snapshot, not box events; the relay auto-driver
only *appends* tick notes to the journal (never consumes box events
as gate input).

## 3. Findings

**F-AI-1 — the producer lane has no owner (genuinely new).** The
deploy agent stamping rows at emit time — with the custody
acceptance that the hosted tenant signing key is held in the layer
below (provisioner/host agent), never guest-side — is named as a
remaining item in `attest.py`'s docstring and
`docs/UPDATE_EVENT_REPORTING.md` §S3, but no open issue owns it
(searched open issues for producer/emit/sign-at-emit/layer-below —
only #1516 itself matches). Filed this turn as a p2 build issue
(track:hosted-product, area:fleet): acceptance is a box emitting
signed rows at emit time with the hosted-tenant key provably
tenant-inaccessible.

**F-AI-2 — the box-key rotation ceremony has no owner (genuinely
new).** No rotate/unpin path exists for `box-keys.json` — deliberate
for slice 1 (no production keys are pinned) — and no open issue owns
it. #1407 (operator-key re-encryption) and #1515 (operator pin
rotation design owner) orbit the *operator* key, not box keys. Filed
this turn as a p3 (track:hosted-product, area:fleet): under T2 key
compromise is an expected event, so rotation must land before the
first tenant gate consumes attested rows.

**F-AI-3 — the hosted plane-side key source has no owner (genuinely
new).** Where the tenant plane pins box keys (D1/worker config),
which plane identities can read/write them, and how the pin itself
is attested — named as remaining item (2) in
`docs/UPDATE_EVENT_REPORTING.md` §S3, owned by no open issue. Filed
this turn as a p2 (track:hosted-product, area:fleet): the in-repo
`box-keys.json` registry is the operator-estate surface; the hosted
plane needs its own pin store design.

**F-AI-4 — F-TM3 residuals carried (not new, all still open):**
#1515 (operator pin rotation design owner, p3), #1407 (operator-key
re-encryption, p3), #778 (G19 retention GC + tenant read path, p2),
#776 (G14 scheduler suspend-awareness, p2). None block the S3
remainders.

**F-AI-5 — the F-TM2 trap frame still holds.** There is still no
consuming gate today, so "never gate-consumed" is still vacuous by
absence — and the T2 acceptance now rides on the G15 gate build
inheriting `gate_consumable_events` rather than re-deriving the
rule. #1516 stays open for the producer half + the first gate's T2
inheritance; its shipped acceptance (mechanism + ingest + T2 pin) is
done.

## 4. Decisions

- **D-AI-1:** the three remainders are filed as build issues, not
  folded back into #1516. #1516's shipped acceptance (mechanism +
  ingest + T2 pin) is complete; the producer lane, rotation
  ceremony, and plane-side key source are distinct builds with
  distinct owners and acceptance criteria.
- **D-AI-2:** rotation lands before the first tenant gate (T2's
  "key compromise is an expected event"), but after the producer
  lane — rotating keys nobody has pinned is ceremony without a
  subject.
- **D-AI-3:** the plane-side key source is the tenant plane's build
  (its own pin store, e.g. D1/worker config), not an extension of
  the operator's `box-keys.json` CLI — the operator registry stays
  the operator-estate surface (both-supported: same primitives,
  separate pin stores).

## 5. What this doc does not claim

Not the S3 build (shipped, #1762); not the producer lane, rotation
ceremony, or plane-side key source builds (the filed issues own
those); not the G15 controller build (G15 #606 is closed on design,
its implementation lives outside the trust lane); not a
re-verification of the #1762 review record (unanimous SHIP IT on the
final head — see the slot entry, not here). #775 stays OPEN (S3
remainders + F-AI-4 residuals).

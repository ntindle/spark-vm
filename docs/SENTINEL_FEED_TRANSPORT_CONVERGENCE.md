# Sentinel-feed transport leg convergence, 2026-10-20: #1349 vs state

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `b497aa8d` (2026-10-20, PR
#1807's merge). Issue/PR numbers are GitHub references as of
2026-10-20 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to
do, not promises. Nothing here authorizes an update on any box.

This document converges the G25 sentinel-feed transport leg (issue
#1349, filed 2026-10-11 by the gap turn behind
`docs/FLEET_CONSUMPTION_G25G26_GAP_ANALYSIS.md`, which pinned
decisions D-25-1–D-25-3). Nine days later: nothing of the leg's
three build items has been built, but the lanes around it moved —
the signing half got a mechanism, the fleet journal gained a new
record family, and the producer half of the attested channel got
its own issue. This pin re-verifies every #1349 disposition against
what actually landed and names the one genuinely new cross-lane
gap.

## 1. The vision (#1349's scope, verbatim + the D-25 series)

D-25-1 — operator-provisioned = operator-attested (tamper-evident,
not tamper-proof; the D-OP2 credential proves the voice, not the
bytes). D-25-2 — one shipment channel, `kind`-discriminated
(`meter` | `event`) on the D-OP2 envelope channel. D-25-3 — seq gaps
are fail-visible, always: per-surface monotonic counters with
restart epochs on the shipper; the operator-plane intake raises a
seq-gap alert on any discontinuity.

#1349's three build items: (1) the tenant-plane shipper (which
records, per-surface seq counters with restart epochs, fail-visible
gap semantics); (2) the envelope-channel record kind (`kind: event`
vs `kind: meter`, or the case for a separate channel — D-25-2's
honest limit says the spec may overturn the one-channel call with
reasoning); (3) the operator-plane intake (where shipped records
land, the seq-gap alert, the tamper-evidence story, replay
protection, fail-closed-on-seq-regression). Explicit non-goal: the
sentinel-side rule engine (a later #799 slice).

## 2. The state (verified at `b497aa8d`)

**Item 1 — shipper: NOTHING.** No shipper code exists in the tree
(grep for `shipper|shipment|ship_` across control-plane, fleet, box
equivalent dirs: zero hits). No per-surface seq counters exist
(A2's prescription from `docs/SENTINEL_TELEMETRY_SURFACES.md` is
still design paper — no `restart epoch` / per-surface monotonic
counter in any Python source).

**Item 2 — envelope channel: NOTHING in code.** D-OP2 lives only in
`docs/OPERATOR_PLANE_BUILD_PATH_GAP_ANALYSIS.md` and the G25/G26
doc. The `envelope` hits in `fleet/` are unrelated: the G15
*rollout* envelope (`fleet/api.py`, `fleet/events.py` — a different
concept with the same word) and `fleet/attest.py`'s canonical
signing envelope (the box→tenant-plane attested channel, G13 — the
other half of the wire, not this one). #1350 (the meter-envelope
record schema) is still open; the one channel the schema would ride
has no code. #1258 (envelope auth — the D-OP2 credential class,
rotation/revocation, the #798 operator-declared mapping) is still
open; #906's orchestrator (whose install step would plant the
credential) is still open.

**Item 3 — intake: NOTHING.** #1048 (plane-side metering ingestion)
is still open with zero comments. The operator-plane intake
placement was decided in #1257 (closed), but no intake code exists.
D-25-3's seq-gap alert therefore has no raiser — and, per §4, no
named surfacing either.

**What DID move since 2026-10-11:**

- **G13 mechanism shipped** (PR #1762, 2026-10-19): `fleet/attest.py`
  (400 lines — ed25519 box-identity keys, canonical signing
  envelope, write-once box-key registry, fail-closed verification)
  plus `fleet/test_attest.py` (33 tests). This is the box→plane
  *signing* half (the #1516 S3 slice; #775 is the G13 umbrella), not the tenant-plane→
  operator-plane transport half — the two must not be conflated.
  Consequence for #1349: the shipper (item 1) now has a box-side
  provenance story to aggregate — `attested: true` rows from the
  fleet journal become the highest-trust records it ships. But
  #1767 (filed 2026-10-19, still open) names the producer half
  unbuilt: no box signs at emit time yet, so `attested: true` is
  currently unreachable in production. The transport leg's "highest
  trust" record class is a future input, not a present one.
- **The fleet journal gained a record family:** #1630's
  `skipped-frozen` legacy producer shipped (PR #1807,
  `fleet/events.py` — `("check", "fleet-freeze") →
  ("check", "skipped-frozen")` mapping with its comment at L127,
  L216–222); #1808 (the `deferred-arc` producer) is filed and open.
  The S1 record set #1349's spec consumes therefore changed after
  the filing: freeze-verdict rows now exist in the journal the
  shipper must aggregate. (Disposition: pointer note on #1349, not a
  new issue — the record set is already inside #1349's scope.)
- **The metering envelope grammar exists as design:**
  `docs/USAGE_METERING_DESIGN.md` §3 pins the canonical envelope
  (`v`, `seq`, `epoch`, `ts_ns`, `tenant`, `source`, `event`,
  `trust`, allowlisted `attrs`, `mac` reserved). Per D-26-1, #1350's
  schema EXTENDS this grammar with `kind: event` — the transport
  leg's records ride the same envelope, one channel per D-25-2.
  Nothing here is code; it is the spec the spec issues build on.
- **Issue comment silence:** #1349 (0 comments), #1048 (0), #1258
  (0), #799 (1 — the D-25 pointer comment), #1350 (1 — the pointer
  comment). Nine days, zero build comments. The lane is filed and
  frozen, not worked.

## 3. Decisions: re-confirmed, one open question carried

- **D-25-1 (operator-attested = tamper-evident) STANDS.** Nothing
  built touches it; the G13 mechanism sharpens rather than
  threatens it (attested rows are the tamper-evident story's
  strongest future input).
- **D-25-2 (one channel, `kind`-discriminated) STANDS.** The honest
  limit invited the #1349 spec to overturn it with reasoning; the
  spec does not exist yet, so there is nothing to overturn with.
  Noted for the spec author: the metering consumer (`kind: meter`)
  and the sentinel intake (`kind: event`) have different retention
  appetites — the alerting taxonomy question (§4) is the first
  concrete place a one-channel strain would show.
- **D-25-3 (seq gaps fail-visible) STANDS**, and this convergence
  extends it one step: the intake alert needs a named owner-facing
  surface (§4).
- **Open question (no issue yet — see §4).**

## 4. The genuinely new gap

- **GAP-1 — The D-25-3 seq-gap alert has no surfacing owner.**
  D-25-3 says the intake raises a seq-gap alert on any discontinuity
  and on unaccounted epoch resets. `docs/HOSTED_OWNER_ALERTING.md`'s
  alert taxonomy (the #1629 lane) has no seq-gap / transport-health
  class: the class table lists approval filed/reminder, hourly
  digest, heartbeat stale, box revoked, token-expiry warning,
  provisioned-never-paired (#1214), phone-home-died (#1489) — no
  row for "the sentinel's trail has a hole". When #1349's intake
  ships, its loudest signal — the trail is incomplete — fires into
  a taxonomy with no slot for it: no dashboard chip, no push
  mapping, no digest row. Filed as a new issue this turn.

Two pointer notes (existing-issue scope, not new issues):

- On **#1349**: the shipped record set changed after filing —
  `skipped-frozen` verdict rows now exist in the fleet journal
  (PR #1807), `deferred-arc` rows are filed (#1808); the spec's S1
  record census must include both families, and the shipper's
  per-surface seq story must cover them.
- On **#1349**: the both-supported question — in self-hosted mode
  the operator plane is local/absent, so the envelope channel
  collapses to the local estate read path (the G21 pattern); the
  spec should name the collapse explicitly rather than leave
  self-hosted operators guessing whether D-OP2 applies to them.

## 5. Remaining build order (unchanged from 2026-10-11, now sharper)

1. #1350 (envelope schema) — the record contract #1258 and #1048
   both reference; unblocks the channel definition.
2. #1258 (envelope auth) + #906's install step — the credential
   the voice authenticates with.
3. #1349 (transport spec) — shipper, record kind, intake; consumes
   #1350/#1258; the S1 record set must carry the §4 pointer notes.
4. #1048 (plane-side ingestion) — the intake's other half.
5. #799 (sentinel spec S1) — the record set + verification contract
   the feed finally serves.
6. GAP-1 (new issue) — the seq-gap alert's owner-facing surfacing;
   can land any time before the intake ships, must land before or
   with it.

## 6. Honest limits

- This turn shipped no code, no shipper, no channel: the lane is
  still 100% design paper. The convergence's value is the re-pin,
  not progress.
- The `attested: true` record class the shipper would most want is
  currently unreachable (#1767) — the transport leg's trust story
  is designed against a producer that does not exist yet.
- D-25-2's one-channel call remains a review-economics judgment
  until the #1349 spec either ratifies or overturns it with a
  worked reason.

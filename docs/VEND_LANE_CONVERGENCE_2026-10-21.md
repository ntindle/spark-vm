# Vend-lane convergence, 2026-10-21 (#850)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `b70610f9` (2026-10-21, PR
#1876's merge). Issue/PR numbers are GitHub references as of
2026-10-21 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. Nothing here vends a credential — the plane
(`sparkvm-control`) still has no vend endpoint; the contract remains
the plane's build spec.

This document continues
`docs/CREDENTIAL_VEND_LANE_STATE_2026-10-16.md` (pinned to main
`a368262`), which superseded the 2026-10-02 gap-analysis state rows and
filed #1553/#1554. One build has landed since: **PR #1817 closed
#1405** (2026-10-20) — the contract's §2.2 "rate-limits mints per box
(`429`)" sentence finally has a mechanism.

## 1. What moved since the 10-16 pin

- **#1405 → #1817 (merged 2026-10-20, `21f4f41d`).** `hosted/vend_rate_limit.py`
  (153 lines): D1-backed token bucket, per `box_id`, capacity 10 mints /
  300 s (D105), one atomic single-statement UPDATE take (the #990
  single-statement lesson — no CTE), D106 first-mint INSERT race
  handling, fail-closed typing, advisory `retry_after_s`, D2 trust
  posture (caller passes the #844-resolved `box_id`; the module grants
  no identity), and the No-DELETE invariant. `hosted/vend_rate_limit_async.py`
  is the async plane port against the worker's async `_D1`,
  "droppable into `worker.py` verbatim" (the D-PP-1/D-PP-2 pattern).
  Conformance: `test_vend_rate_limit_async.py` (5 tests) runs every
  scenario against both the sync truth and the async port over a
  worker-faithful `_D1` shim and asserts identical outcomes — the
  sync/async divergence risk is test-pinned, verified on current main.
  Contract §2.2 now names the mechanism (D105/D106, the 429 +
  `Retry-After` shape, the #890 endpoint's emission duty); §2.4's D1
  schema names the `vend_rate_limit` table (with the No-DELETE
  invariant); `hosted/README.md` documents the module.
- Nothing else in the lane moved: #890, #891, #906, #1178, #1365,
  #1404, #1406, #1407, #1500, #1553, #1554 are all still open
  (verified via API 2026-10-21); #1269 stays closed.

## 2. Slice state (contract §11, at `b70610f9`)

| Slice | State |
|---|---|
| S1 tenant-scoping (#280) | **Shipped** — contract §1 stands; no drift found on re-read. |
| S2 vend contract | **Shipped, amended** — §2.2 gains the D105/D106 rate-limit mechanism (#1817); §5 gains the batching discipline and §10 gains item 14 (this turn, F-VC15/F-VC16). |
| S3 plane vend endpoint (#890) | **Open, p2** — not built. Body (last touched 2026-10-16) predates #1817: no reference to the D105 integration (wire `try_take_async` ahead of the mint path; denied → 429 + `Retry-After`) — pointer comment this turn (F-VC17). The #1178 retention pin still gates its D1 migration (D-VR-1, re-verified open). |
| S4 box-side swapd fetch (#891) | **Open, p2** — not built. Body (2026-10-08) predates #1817 and pins no batching discipline — pointer comment this turn (the new §5 bullet is the discipline its fetcher must implement). |
| S5 H19 reconcile → vend bootstrap | **Open** — rides #906 per D-VR-4 (pointer comment on #906 stands; #906 still open). |
| S6 acceptance (#1553) | **Open, p2** — tracks the contract's §10 verbatim; inherits the new item 14 automatically (pointer comment this turn). |
| Data key (#1554) | **Open, p2** — operator-owned (NEEDS_USER); unchanged. |
| Pre-build gates on #890 | **All still open**: #1404 (placement build half — contract half landed via #1453), #1406 (atomicity — contract §2.1a pinned), #1407 (key-rotation re-encryption), #1500 (`vend_audit.actor` free-text), #1365 (first-manifest-write actor). |

## 3. Genuinely-new findings (this turn)

- **F-VC15 — D105's "never touches legitimate traffic" claim assumed
  batched mints; the contract pinned no batching discipline.** The
  bucket is per `box_id` (10 takes / 300 s). The contract's §2.2
  sentence read "the legitimate cadence is already ~1 mint per 300 s
  per name, so no legitimate box is throttled" — but with per-name
  mints (one POST per name, the natural reading of §5's "re-checks
  each lease … and refreshes any lease"), a box with 11+ names at the
  §2.3 minimum TTL (300 s) issues 11+ takes per 300 s and eats 429s on
  legitimate traffic; first boot is worse (N names, zero leases → N
  immediate mints; a 64-name manifest converges over ~6 windows,
  ~30 min, instead of one batched request). The 64-name cap enables
  batching but nothing required it — verified by grep: no batching
  requirement in the contract, and #891's body (2026-10-08) is
  batching-silent. **Fixed in-turn:** §5 now pins the discipline —
  the fetcher collects all due names each re-check cycle into one
  mint POST (first boot: `ceil(N/64)` requests) — and the §2.2 /
  module-docstring / README phrasing is corrected to "~1 mint
  request per 300 s per box (all due names batched)". Decision
  D-VC15: the per-box bucket shape is kept (a per-(box,name) bucket
  would let 64 names × 10 mints defeat the D1 write-amplification
  bound #1405 was filed for); batching is the client-side half of
  the design.
- **F-VC16 — §10's acceptance checklist never learned about the
  rate limiter.** The 13 items predate #1817; #1553 tracks §10
  "verbatim", so the S6 slice silently dropped the 14th behavior
  (denied take → 429 + `Retry-After`; batched legitimate cadence
  never throttled). **Fixed in-turn:** §10 gains item 14; #1553's
  verbatim tracking inherits it (pointer comment posted).
- **F-VC17 — #890's body omits the D105 integration** (same class as
  the 10-16 turn's F-VR-3): the contract's §2.2 names the #890
  endpoint's emission duty (wire `try_take_async` ahead of the mint
  path via the async port; denied → 429 + advisory `Retry-After`;
  the caller resolves the bearer token to `box_id` per the D2 trust
  posture), but #890's body (2026-10-16) never mentions it. Pointer
  comment posted this turn — no new issue; the duty belongs on the
  build issue.

## 4. Documented residuals (checked, not findings)

- **Denied-take read amplification is unbounded.** #1405's gap was D1
  *write* amplification (a `vend_audit` row + a decrypt op per mint);
  the limiter bounds *allowed* mints, and denied takes never reach
  the decrypt or the audit write. A hostile box can still loop denied
  takes (up to ~4 read statements each, plus the bearer check) at
  whatever rate D1 reads sustain. Cheap reads vs. the bounded
  writes — the stated gap is closed; the residual is documented here,
  not filed.
- **`# pragma: no cover` comment imprecision (verified non-issue).**
  Both modules comment the row-None path "the row was INSERTed
  above" — in the INSERT-loses path the row pre-existed rather than
  being inserted above. The code is correct either way (the path
  requires a concurrent DELETE, which the No-DELETE invariant
  forbids); the comment is merely imprecise. Not filed.
- **D2's caller contract dangles until #890.** Both modules document
  that the caller must pass the #844-resolved `box_id` and reject a
  box-asserted identity upstream — that caller does not exist yet.
  It is #890's build scope (covered by the F-VC17 pointer comment),
  not a new issue.

## 5. Decisions

- **D-VC15 — batching is the client-side half of D105.** The fetcher
  (§5, #891) batches all due names into one mint POST per re-check
  cycle; the per-box bucket keeps its 10/300 s shape. A per-name
  minting client is non-conformant as of this pin.
- **D-VC16 — §10 item 14 is the rate limiter's acceptance home.**
  #1553 inherits it via its verbatim-§10 tracking; no separate
  rate-limit acceptance issue.
- **D-VC17 — the D105 integration duty lives on #890** (pointer
  comment), following the F-VR-3 precedent — build duties belong on
  build issues, not in third trackers.

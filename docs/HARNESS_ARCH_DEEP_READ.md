# harness/ — architecture deep-read (2026-10-01)

Deep-read of `harness/` — the pre-seeded harness tooling (R2): the
golden-image manifest and its preflight, the provision-time injector,
the gate fixture and its teardown, the baked-secrets gate scan, the
provider-agnostic H4 contract, and the SSH-key-as-account identity
stack (S1 stateless primitives + S2/S2.5/S3 registry with rotation and
the claim protocol). Read in full: `key_identity.py`,
`key_registry.py`, `provider_iface.py`, `proxy_match.py`,
`inject-provision-state.sh` (steps 1–8), `scan-baked-secrets.sh`,
`README.md`; tests sampled for contract coverage.

## Structural strengths

The component is in good shape where it counts:

- **The injector is genuinely fail-closed.** Every step asserts
  positively (manifest preflight against the pinned SHA, echo teardown
  verified with the proxy's own matching semantics, real-key assertion
  via blind not-dummy compare, CA presence, probe gate) and any refusal
  blocks box-live. The ordering invariants are load-bearing and stated
  (smoke scoping list before the hosts.allow append).
- **Path-level TOCTOU is pinned by fd, not by comment.** Step 5 (tenant
  identity) and step 6 (tenant record) open source and destination with
  `O_NOFOLLOW`, re-validate the exact installed bytes, and set modes on
  the open fds — the #258 class was found and fixed here, not papered
  over.
- **The registry fails closed on corruption** (never silently resets),
  publishes atomically (mkstemp + rename), serializes on an atomic
  lockdir with stale-holder reclaim, and the claim protocol stores only
  hashes. The docstrings name their trust boundaries honestly (rotate
  assumes local-caller attestation; the claim protocol owns the
  network-caller case).
- **Echo detection cannot diverge from enforcement** — `proxy_match.py`
  imports the proxy's own matcher (#261), with the non-canonical
  loopback spellings (#259) and mapped-loopback forms (#269)
  fail-closed.

## Fixed in this run

1. **Crash-orphaned registry tmp files (#824).** `_save()` publishes via
   mkstemp + rename; a writer killed between the two left a
   `registry.json.tmp.*` orphan that no path ever swept (verified on
   main). `_locked()` now sweeps orphans older than 1h — the same rule
   fleet's #716 fix uses — never touching live-writer tmps.
2. **Unaudited `remove()` (#825).** Deleting an account left zero trace —
   "registered and deleted" was indistinguishable from "never
   registered". `remove()` now appends to a bounded `deletions` journal
   (cap 1000, oldest-first eviction like `rotations`), copying the
   deleted record's lineage context (`rotated_to`/`rotated_at`,
   `claimed_at`/`claimed_by`) plus `deleted_at`; new `deletions()`
   accessor; pre-#825 stores normalize on load.
3. **Stale S1 manifest policy text (#826).** `first_connect_manifest`'s
   policy map still said rotation was "not-implemented" and the claim
   story was a "later slice" — both shipped (S2.5 rotate, S3 claim). The
   policy strings now describe the shipped mechanics; the module
   docstring points at `key_registry.py` for the stateful slices.

Tests: 120/120 in `test_key_registry.py` + `test_key_identity.py`
(9 new: stale/fresh tmp sweep, prefix sweep, concurrent-reclaim safety,
deletion journaling with lineage, unknown-remove journaling nothing,
journal bound, cross-reload persistence, pre-#825 store normalization,
misshapen-journal fail-closed; plus the manifest policy text is now
asserted in `test_manifest_shape_and_fields`). The sweep and journal
tests were verified non-vacuous against the pre-fix code.

## Filed as issues (out of this run's ~45 min scope)

- #827 — `inject-provision-state.sh` §3a: crash-orphaned
  `.smoke-hosts.*` tmps are never swept (same class as #824/#716; the
  8c fragment tmp has trap discipline, the 8b tmp doesn't). Per the
  architecture review: the fix is trap **plus** an age-thresholded
  stale-sweep at injector start (a trap alone doesn't close the
  SIGKILL/OOM hole) — caveat appended to the issue.
- #814 — pre-existing, same class for fleet journals: unbounded growth,
  no rotation/bounding policy (still open).

## Residuals noted, not filed

- `scan-baked-secrets.sh` skips unreadable files loudly but
  fail-open (documented in its own header; the gate runs as root which
  moots it on a healthy image).
- Material introduced between the 5b re-scan and the snapshot is
  unscanned — the gate doc's own honest residual ("snapshot promptly
  and touch nothing after 5b").
- `ProviderState` has STOPPING/STOPPED with no `stop()` verb — deliberate:
  they exist only for provider-initiated stops, `dial()` routes them
  through the wake path. Contract choice, not a gap.

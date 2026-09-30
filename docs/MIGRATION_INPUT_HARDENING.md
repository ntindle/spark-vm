# Migration-tooling input hardening (G20 / #661)

**Status:** designed (the hardening bar), not built. Resolves G20
(#661), the residual of the G13 trust-model design
(`TENANT_UPDATE_TRUST_MODEL.md` §3 T3 / §5). Closes the last open
G-number of the update-channel series: G11/G12 shipped; G13/G14/G15/
G16/G17/G18/G19 designed; G20 designed here.

**The question (§13's leftover):** the reimage path runs migration from
the *new* image's tooling, forward-only (G11). Tenant *code* does not
execute during the maintenance window — but the migration's *input* is
tenant *data*, and the tenant holds root inside the guest (H11). What
is the hardening bar for migration tooling that processes
attacker-influenced input?

## 1. What the earlier designs already decide (bounds, not repeated)

- **G11** (`UPDATE_CHANNEL_POLICY.md`): rolling reimage with tenant-state
  migration is the single renewal path. Migration runs from the *new*
  image's tooling, forward-only. G11's S2 deferred three contract items
  here: the migration contract must define version-skipping (N→N+2),
  failed-migration semantics, and snapshot-retention policy. This doc
  answers the first two; snapshot-retention policy stays with G11's S2.
- **G12** (`UPDATE_CHANNEL_POLICY.md` §2): the failure code is
  `maintenance-failed` — a maintenance that breaks the box is a broken
  box, on the record. The enter/exit/failure writes belong to the
  control-plane update scheduler — never the provider driver, never the
  Muse, and never the migration tooling itself: the migration emits a
  result-report; the scheduler consumes it and owns the status
  transition.
- **G13** (`TENANT_UPDATE_TRUST_MODEL.md` §3 T3): the threat is named —
  the tenant poisons the migration. Its trust ruling stands: this is
  defense-in-depth, not a trust hole. The execution boundary is named
  there and is *part of the bar here*: migration executes inside the
  *new guest* only — never on the provisioner host.
- **The golden-image gate** (`GOLDEN_IMAGE_GATE_PROCEDURE.md`): the
  migration tooling ships *in the image*, so it is gate-checked like
  every other image content. The migration manifest (§2) is part of
  what the gate reviews.
- **G19** (`UPDATE_AUDIT_RETENTION_AND_ACCESS.md`): the migration
  outcome lands in the control-plane journal — the `reimage` record's
  `migration outcome` field (named in G13 §2) is where it is attributed
  and retained.

## 2. The hardening bar

A migration is shippable only if it meets every rule below. The rules
are checkable at the image gate — most reduce to "the migration
manifest declares X" plus a harness behavior.

### Inputs: parse, don't trust

- **B1 — every migration input has a declared schema, validated before
  use.** Tenant data is parsed and validated against a declared schema
  (field types, allowed values, size bounds) — never trusted raw, never
  branched on before validation. The schemas are declared in the image's
  migration manifest (§6 S1), reviewed at the gate like code.
- **B2 — parser discipline.** Migration tooling processes hostile
  input with non-evaluating parsers only: no `eval`, no template
  expansion, no plugin/config-hook loading out of tenant data. Parsers
  are bounded — max input size, max nesting depth, max wall-clock —
  declared in the manifest, so a hostile payload can fail the migration
  but cannot hang or OOM the maintenance window into an unbounded one.
- **B3 — the layout-version marker is validated first.** The claimed
  state-layout version is itself attacker-controlled. It is validated
  against the set of source layouts the new image declares it can
  migrate *from* before anything else reads tenant data. An unknown or
  future version fails closed — the migration never attempts a
  guess-migration from a layout it does not know.
- **B4 — version skipping is declared, not improvised.** The manifest
  declares exactly which N→M jumps the migration supports. An
  undeclared jump (N→N+2 with no direct path) fails closed rather than
  attempting a two-hop guess. The supported-jump set is
  gate-checkable: a release whose manifest cannot cover the fleet's
  actual N spread fails the gate before it ever reaches a wave.

### Failure: fail closed, never half-migrate

- **B5 — two-phase migration: validate-all-then-commit.** Phase 1
  validates every input against its schema with *zero writes* to tenant
  state. Phase 2 applies the transform. A failure in either phase —
  validation, transform, or crash — lands the box in
  `maintenance-failed` with a `detail` reason, never in a
  half-migrated state. The G11 rollback primitive (reimage to the
  previous gate-checked image + snapshot restore) is the recovery, not
  a blind retry of the failed transform.
- **B6 — no double-apply.** Migration steps are idempotent or
  guarded: re-running a migration against already-migrated state is a
  no-op or a detected-refusal, never corruption. A retry of a failed
  migration starts from the pre-migration snapshot (B5), not from the
  half-written output.
- **B7 — execution boundary.** Migration runs inside the *new guest*
  only — never on the provisioner host (G13 §3 T3). Migration tooling
  processing attacker-influenced tenant data on the provisioner host
  would be the privilege-boundary crossing the trust model forbids. The
  network surface is closed during the maintenance window; the only
  provisioner channel is the declared result-report (success/failure +
  attested box identity). Unattested result-reports may be logged,
  never consumed — the same rule G13 §3 T2 sets for gate events.

### Blast radius: stated, not assumed

- **B8 — the blast-radius argument, made explicit.** A poisoned
  migration breaks the tenant's own box only. The tenant already owns
  that box (they hold root — H11); the reimage primitive is
  provisioner-side and per-box, so there is no path from a poisoned
  migration to another tenant's box or to the control plane. This is
  why the whole bar is defense-in-depth: hardening converts "tenant
  bricks their own box with hostile data" from a fleet-wide incident
  into a per-box `maintenance-failed` the operator can reimage or roll
  back. A design that treated migration hardening as the trust boundary
  would be upside down — the boundary is the per-box primitive; the
  hardening is the honesty layer on top of it.

### Supply chain and hygiene

- **B9 — the manifest is gate content.** The migration manifest
  (declared schemas, supported jumps, resource bounds) ships in the
  image and is reviewed at the golden-image gate. A release whose
  migration tooling is undeclared — schemas missing, jumps unlisted,
  bounds absent — fails the gate. This is G11's forward-guard family
  (the timer-exclusion guard): the day an undeclared migration lands in
  an image, the no-guess-migration decision dies silently.
- **B10 — no tenant data in logs.** Validation failures log the input
  class, the reason, and the offending *field name* — never the
  offending bytes. Tenant data stays tenant data; the operator's
  failure diagnosis does not need it.

## 3. Failure classes and what each one does

| Failure | Detection | Outcome |
|---|---|---|
| Input fails schema validation (B1) | Phase-1 validator | Abort before any write; `maintenance-failed: migration: validation:<class>` |
| Layout version unknown/future (B3) | Marker check, first | Abort before any read beyond the marker; `maintenance-failed: migration: unknown-layout` |
| Undeclared N→M jump (B4) | Manifest lookup | Abort; `maintenance-failed: migration: unsupported-jump` |
| Transform failure mid-Phase-2 | Harness | Abort; pre-migration snapshot intact (B5); `maintenance-failed: migration: transform:<step>` |
| Crash mid-migration | Result-report absent at watchdog | Watchdog (G14's bounded-`maintenance` family): treat as transform failure; `maintenance-failed: migration: crashed` |
| Resource bound exceeded (B2) | Parser/harness limits | Abort; `maintenance-failed: migration: resource-bound` |
| Result-report lost/unattested (B7) | Scheduler timeout / attestation check | Unattested: logged, never consumed; the box does not advance — it stays `maintenance` until the watchdog fires, then `maintenance-failed` |

Every row ends the same way: the box is broken *on the record*
(G12), the control-plane journal's `reimage` record carries the
migration outcome with attribution (G13 §2, G19 retention), and
recovery is G11 rollback — reimage to the previous gate-checked image
plus snapshot restore. The tenant Muse sees its own box's outcome
through the G19 read surface, never a box-side journal.

## 4. Sibling relationships (no re-litigation)

- **G11** — owns the mechanics and the snapshot-retention policy
  (still owed by its S2); this doc consumes the reimage primitive and
  answers the migration-contract halves G11 deferred (version-skipping,
  failed-migration semantics).
- **G12** — owns the `maintenance-failed` code and the producer rule;
  the migration's result-report is the *input* the scheduler consumes
  to write the code, not a status write itself.
- **G13 §3 T3** — the threat; this doc is the bar it filed for. The
  trust ruling (defense-in-depth, per-box primitive) is not re-argued.
- **G14** — the bounded-`maintenance` watchdog is the crash-detection
  backstop in §3's last rows; this doc adds no new clock semantics.
- **G17/G18** — the result-report's attested-identity half is their
  lane; this doc names the requirement (B7) without designing the
  transport. Whether the result-report reuses the G17/G18 attested
  event channel or is a separate narrow channel is Q5.
- **G19** — migration outcomes land in the control-plane journal's
  `reimage` record and inherit its retention tiers and tenant read
  path; no second audit design is owed.
- **H11** — the layer split (tenant root in guest, operator below) is
  the premise B7 and B8 stand on.

## 5. Open questions

- **Q1 — the concrete input inventory.** This doc defines input
  *classes*; the first migration's S1 must name the concrete
  tenant-data surfaces (which paths, which stores) and their declared
  schemas. Is there a standing registry of migratable state, or does
  each release declare its own?
- **Q2 — retry semantics.** Is a failed migration ever re-run in
  place (operator-declared retry of the same reimage), or is rollback
  to the previous image the only recovery, with the fixed migration
  arriving as a new release? The doc leans rollback-first; the
  implementers confirm.
- **Q3 — schema evolution.** Strict-reject on unknown fields, or
  readers-ignore-unknown (the G1 versioning-rule family)? Strict is
  safer against smuggled semantics; lenient is kinder to additive
  changes. The bar needs one answer before S1.
- **Q4 — resource-bound defaults.** Per-image manifest values, or a
  global floor the manifest may only tighten? A floor prevents a lazy
  manifest from declaring absurd bounds.
- **Q5 — the result-report channel.** Reuse the G17/G18 attested event
  transport, or a separate narrow migration-result channel? Named as a
  requirement here (B7); designed in the G17/G18 lane.

## 6. Build slices (for the feature/distribution track, not this doc)

1. **S1 — migration manifest + contract.** The declared-schema manifest
   format (schemas, supported N→M jumps, resource bounds), shipped in
   the image, consumed by the golden-image gate (B9). Answers Q1 and
   Q4's manifest half.
2. **S2 — hardened migration harness.** The two-phase
   validate-then-commit runner that image migrations plug into;
   implements B1–B7 and B10, emits the declared result-report, refuses
   double-apply (B6).
3. **S3 — scheduler integration.** Consume the result-report, write
   `maintenance-failed` per the G12 producer rule, wire G11 rollback
   on failure, land the outcome in the control-plane journal (G19).

**Both-supported note:** the same manifest, harness, and failure
semantics serve the self-hosted operator's N-box estate — the
hardening bar is identical with the operator as the only actor. The
hosted delta is the attested result-report (B7) and per-tenant
journal scoping (G19); the bar degrades gracefully to the
single-operator case without a second design.

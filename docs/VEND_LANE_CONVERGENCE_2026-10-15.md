# Vend-lane convergence, 2026-10-15: the #1401–#1407 gates vs state (#850)

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `9923003` (2026-10-15, PR #1499's
merge). Issue/PR numbers are GitHub references as of 2026-10-15 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. Nothing here
vends a credential.

This document pins the #850 credential-vending lane's state after the
2026-10-13 post-arch pin (`docs/VEND_LANE_POST_ARCH_CONVERGENCE_2026-10-13.md`,
at main `0dd9e9e`). Seven things moved since that pin — six vend-lane
PRs plus one cross-lane audit-landing:

1. **PR #1409 merged** (2026-10-13) — "dual-mode credential-source seam
   for the ingest (#948)": `SVM_CRED_MODE` (`local` default / `vend`),
   latched per-run via `credential_mode.json` (F-VC4, carried forward).
2. **PR #1443 merged** (2026-10-13) — the 10-13 pin itself.
3. **PR #1453 merged** (2026-10-14T05:42:49Z) — "security: pin
   parameterized placement shape in vend contract (#1404)": the
   contract's §2.1a now names the parameterized `placement` value shape
   (`["bearer_header", {"custom_header": "X-Api-Key"}]`), citing #1404.
   F-VC6's **contract half is landed**; the build halves remain.
4. **PR #1486 merged** (2026-10-14T23:34:06Z) — "contract: pin
   current-only token-state gate for vend issuance (#1402)": §2.1b
   "Token-state gate for issuance" and the §2.1 mint-row sentence —
   mint and refresh require a `current` box token; a `grace` token mints
   nothing and reads `401` with a rotation-naming message.
5. **PR #1498 merged** (2026-10-15, `ddecc5a8`) — "security: pin
   vend-contract #1401/#1402/#1403 decisions + acceptance items": the
   contract's §10 acceptance checklist gains items 10/11/12 (denial-worded,
   each citing its issue) and `scripts/test_credential_vend_contract.py`
   gains 7 machine pin tests for the three decisions. #1401, #1402, and
   #1403 are now CLOSED (via Closes keywords; evidence close-out
   comments posted, naming #890 as the build-time verification carrier).
6. **Cross-lane: PR #1499 merged** (2026-10-15, `9923003`) — "#775 S1:
   control-plane update journal": `fleet/update_journal.py` journals
   registration / wave_assignment / promotion / reimage / maintenance /
   freeze-halt-unfreeze-promote / deferred-skipped with **fail-closed
   attribution** — `--tenant` required with no default, `--actor-fingerprint`
   normalized to the repo's canonical `SHA256:<base64>` form (the
   `pairing/ed25519.fingerprint()` shape; bare names rejected), every
   other rollout record referentially chained to a journaled registration
   under the store lock. This is the loop's standing audit discipline;
   F-VC12 below applies it to the vend lane's own audit table.
7. **PR #1408 merged** (2026-10-13, `850a8aa`) — recorded in the 10-13
   pin; carried forward for completeness (no-oracle `401`, AES-128-GCM).

**Non-overlap map (what this doc is not):** not the S3/S4 build notes
(`docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md` owns those — §1 and D-V2
amended in this same PR, see F-VC11); not a re-verification of the
10-13 pin's F-VC2–F-VC5 (carried forward, with the closures above); not
#890's build. This doc's job is narrow: pin the post-#1498 state,
record the two genuinely-new findings (F-VC11, F-VC12), and refresh the
remaining-build list for #890/#891.

## 1. The vision (#850, verbatim acceptance)

Boxes authenticate with their box Bearer <redacted> and receive narrow,
short-lived credentials from the plane; revocation propagates; every
vend is server-side audited. Unchanged.

## 2. Findings

### F-VC11 — the design-ahead still prescribes the losing side of #1402

The 10-13 pin's README row states "D-VD11: mint requires `current`,
superseding the design-ahead's current+grace line" — but the
design-ahead itself was never amended. `docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md`
§1 still says the box "presents its box Bearer <redacted> bearer
(current+grace classes per §2/D-V2) at the plane's vend endpoint", and
D-V2 (line 159) still reads "The vend endpoint honors current+grace
bearer <redacted>". Both contradict the settled contract (§2.1b, §10
item 11), the merged #1486, and the closed #1402. A builder reading
only the design-ahead — which is the document that points at #890 —
would implement the losing inheritance. Fixed in this PR: §1 carries a
dated amendment to current-only for the mint path (citing D-VD11 /
#1402 / #1486 / §2.1b), D-V2 is superseded-in-place by the same
amendment, and the §2 #952-filing-endpoint bullet (current+grace for a
non-secret-issuing route) is left untouched — it was and remains
correct.

### F-VC12 — `vend_audit.actor` is free-text where the S1 journal is canonical

The contract's §2.4 DDL (line 333–341) defines
`vend_audit.actor TEXT /* 'box' | owner-key id */`, with `tenant_id`
"reserved, NULL in the per-tenant-box shape". The #775 S1 journal that
landed in the same merge window demands fail-closed attribution:
tenant required, actor as the canonical `SHA256:<base64>` fingerprint
of the pinned provisioned operator key (`pairing/ed25519.fingerprint()`
shape; bare names rejected), referential chaining under the store lock. The vend lane's audit row —
"the audit a tenant can't tamper with" (§2.5) — carries less identity
than the rollout journal does, and a free-text `'box'` actor carries no
key-level identity of its own — correlating it to the box key fingerprint
the plane recorded at #844 pairing requires joining `box_id` back to the
plane's pairing records. Filed as a new
pre-build gate on #890 (issue #1500, priority:p3, arch, track:hosted-product): `vend_audit`
should inherit the S1 journal's attribution discipline (canonical
fingerprint for box actors, owner-key id for owner actors, no bare
'box'), before #890 writes the DDL for real.

### F-VC13 — the design-ahead's §10 count is stale (fixed in this PR)

The design-ahead §1 also says "Acceptance is the contract's §10
ten-item checklist." §10 has had twelve items since #1498. Fixed in
this PR ("twelve-item checklist"). A two-word fix, but the checklist is
the contract the acceptance tests pin — a stale count is how a future
reader misses items 10–12.

### F-VC6 (updated) — #1404's contract half is landed; the build halves remain

#1453 pinned the parameterized `placement` value shape in §2.1a/§2.2.
#1404 stays OPEN — correctly: §2.1a (line 142) still tells #891 that a
multi-entry array "fails closed as malformed" at the proxy and that
#891 "MUST translate the array to the proxy's single-placement shape"
(line 153–160), and #890 must validate each placement entry's shape at
write time. Those are build halves, not decision halves. Zero comments
on the issue; no linked progress beyond #1453.

### F-VC7 — #1405 (the 429 with no mechanism) is unaddressed

Contract §2.2 (line 234) still claims per-box mint rate limiting
("`429` — precedent: the pairing 50-pending cap in
`CONTROL_PLANE_API_REFERENCE.md`"). The cited precedent is a count cap,
not a rate limit, and no rate-limiting mechanism exists anywhere in
the plane worker. Zero comments, zero linked progress. The contract
must gain a real mechanism or drop the claim before #890 builds against
it.

### F-VC8 (updated) — #1406 is a contract-text amendment gate; the mechanism is prescribed

Unchanged from the 10-13 pin: the manifest write spans `vend_manifest`
**and** `vend_values` with no pinned atomicity unit; the design-ahead
§2 already prescribes "D1-batch-portable atomic statements (#990)".
Contract-text amendment before #890 builds. Zero comments, zero linked
progress.

### F-VC9 — #1407 (key-rotation code path) is unaddressed

Unchanged from the 10-13 pin: contract §3's "Key rotation is an
operator procedure" means manual D1 surgery with the data key in a
human's hands — the procedure the custody section (§3) exists to avoid.
The decrypt-with-old / encrypt-with-new sweep needs an execution path
before the first rotation is ever needed. Zero comments, zero linked
progress.

### F-VC14 — the seven are pristine

#1404–#1407 carry zero comments and zero linked PRs/commits between
their filing (2026-10-13 ~01:39 CDT) and this pin. #1401–#1403 are the
only arch findings with movement (contract halves → pins → closed).
No other turn has started on the remaining four; nothing here
double-counts in-flight work.

## 3. Decisions

- **D-VD12.** The design-ahead's current+grace prescription is amended
  in this PR (F-VC11) — dated amendment, D-D8 pattern — rather than
  filed as an issue: the contradiction sits between two repo docs and
  the fix is a two-line text change with no design question left open.
  #890's build inputs are now internally consistent: mint requires
  `current`; `grace` stays on non-secret-issuing box routes.
- **D-VD13.** `vend_audit` inherits the S1 journal's attribution
  discipline (F-VC12): canonical `SHA256:<base64>` box fingerprints
  (the `pairing/ed25519.fingerprint()` shape) and owner-key ids — no
  bare `'box'` strings; `tenant_id` reserved-column revisited when the
  plane model does. Filed as a pre-build gate on #890, not bundled into
  this PR: it is a schema decision the #890 builder must own.
- **D-VD14.** One new issue filed this turn (F-VC12, #1500). The
  #1401–#1407 seven stay on the pre-build gate list (none dropped, none
  double-filed); #1500 joins them as the eighth.

## 4. Remaining-build list (#890 S3 / #891 S4)

| # | State |
|---|---|
| #1401 (no-oracle 401) | CLOSED 2026-10-15 — §10 item 10 + pin tests (#1498). Build half: #890 inherits the §2.1 convention. |
| #1402 (grace mint gate) | CLOSED 2026-10-15 — §2.1b + §10 item 11 (#1486, #1498). Build half: #890 gates mint on `current` only; design-ahead amended here (F-VC11). |
| #1403 (AES-128-GCM) | CLOSED 2026-10-15 — §3 + §2.4 DDL + §10 item 12 (#1408, #1498). Build half: #890 vendors the AES-128-GCM from `hosted/push_crypto.py`; data-key custody (Worker secret) is #890's. |
| #1404 (placement shape) | OPEN — contract half landed (#1453). Build halves: #890 validates each entry at write time; #891 translates the array to the proxy's single-placement shape (§2.1a). |
| #1405 (429 mechanism) | OPEN — unaddressed. Contract claims a rate limit with no mechanism. |
| #1406 (two-table atomicity) | OPEN — unaddressed. Contract-text amendment gate; mechanism prescribed (D1-batch-portable, #990). |
| #1407 (rotation path) | OPEN — unaddressed. Needs an execution path, not an operator procedure. |
| #1500 (F-VC12: vend_audit attribution) | OPEN — filed this turn. Pre-build gate on #890. |
| #890 (S3 plane vend endpoint) | OPEN — build slices per the design-ahead, now with consistent inputs. |
| #891 (S4 box plane-fetch) | OPEN — consumes `SVM_CRED_MODE` (#1409); placement translation (§2.1a). |
| #850 (vision tracker) | OPEN — as ever. |

## 5. Appendix — claim ledger

Every code-state claim in §2 was re-verified at main `9923003` by this
turn: §10 items 10/11/12 present at `docs/CREDENTIAL_VEND_CONTRACT.md`
lines 560–582; §2.1b at lines 179–196; §2.2 `429` at line 234; §2.1a
placement at lines 124–160; `vend_audit` DDL at lines 333–341;
design-ahead §1 line 23 and D-V2 line 159 (pre-amendment) at
`docs/CREDENTIAL_VEND_S3S4_DESIGN_AHEAD.md`. Issue states re-verified
via the GitHub API 2026-10-15 ~02:1x CDT: #1401/#1402/#1403 closed,
#1404–#1407 open with zero comments, #890/#891/#850 open.

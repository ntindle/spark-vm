# Trust-model lane convergence, 2026-10-15: the #775 slices vs state

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `f538f54` (2026-10-15, PR #1514's
merge — #775 S2). Issue/PR numbers are GitHub references as of
2026-10-15 (not code-verifiable from the tree). Honesty rules apply
(`docs/POSITIONING.md`): this describes current state and work to do,
not promises. Nothing here authorizes an update on any box.

This document pins the #775 (G13 trust-model implementation) lane's
state after S2 landed: `docs/TENANT_UPDATE_TRUST_MODEL.md` closed the
G13 design half in 2026-10; S1 and S2 are now shipped; the vision's
third slice has no build owner.

## 1. The vision (#775, verbatim §6 slices)

1. **S1 — control-plane update journal + schema:** the §2 JSONL journal
   with the attribution fields, per-tenant scoping, and
   registration-ref chaining. The journal exists before the scheduler
   does — decisions auditable from day one.
2. **S2 — registration CLI + operator identity:** `fleet register`
   binds the registering operator's identity (the pinned provisioned
   operator key from §2's attribution rules, fingerprint in every
   record — the same provisioned trust root
   `ROLLOUT_CONTROLLER_DESIGN.md` §5 names).
3. **S3 — attested event ingestion:** box-identity attestation on the
   events gates consume (§3 T2); unattested events logged, never
   gate-consumed. This S3 also owns the G17 S3 remainder: the signed
   box→plane channel mechanism itself.

Both-supported: the same primitives serve the self-hosted operator's
N-box estate with the operator as the only actor; the hosted delta is
tenant scoping + attestation.

## 2. The state (verified at `f538f54`)

**S1 — shipped** (PR #1499, 2026-10-15): `fleet/update_journal.py` —
`append` requires `--tenant` (no default) and `--actor-fingerprint`
(normalized to the canonical `SHA256:<base64>` form; bare names
rejected), `--record` choices over the §2 record types,
`registration_ref` generated-never-accepted with referential chaining
under the store lock; `read` filters by `--tenant`/`--record`/`--since`
and warns on malformed lines (skipped, never gate-consumed).
`docs/UPDATE_JOURNAL_OPERATOR_REFERENCE.md` is the operator surface.

**S2 — shipped** (PR #1514, 2026-10-15): `fleet/register.py` —
`init` pins the provisioned operator key's fingerprint per store
(write-once; different-digest fails closed), `register` journals the
`registration` record under the pinned identity (no
`--actor-fingerprint` flag — the human path cannot self-attest a
different identity), `show-identity` reads the pin. Exit 2 for
usage/validation, exit 1 for runtime/integrity (corrupt pins are
integrity errors).

**S3 — not built, and nothing owns it.** `fleet/events.py` is the
box-event pipeline; `canonicalize_audit_rows` stamps every row
`"attested": False,  # S1/S2: false, always` (line 342), and
`fleet/test_events.py:149` asserts exactly that. The trust doc's §3 T2
names "the G17/G18 implementers' lane" for the attestation mechanism —
but G17 (#608) and G18 (#609) are both closed on design, and no issue
anywhere owns the S3 build. The #775 issue body names S3 in prose; no
filed issue existed for it (searched `attested event` / `G17` / `attest`
in open titles and bodies, 2026-10-15). Filed this turn as #1516.

## 3. Findings

**F-TM1 — the S3 slice is an ownerless vision item (genuinely new).**
Three things the vision promises have no build home: (a) the signed
box→plane event channel mechanism (the "G17 S3 remainder"); (b)
attested ingestion replacing the `attested: False` stub in
`fleet/events.py`; (c) the §3 T2 consume-gate rule enforced at a real
gate. Filed this turn as #1516 (the S3 build issue; "Part of #775"). Its
acceptance carries the T2 rule verbatim: unattested events may be
logged, never gate-consumed — the ingested-row schema keeps the
`attested` flag, and every consuming gate filters on it.

**F-TM2 — the T2 rule is currently vacuous by absence, and that is the
trap.** There is no consuming gate today at all — the G15 controller is
designed but unbuilt — so nothing can violate "never gate-consumed"
yet. The risk is not present abuse but a sibling turn building the
promotion gate (G15/#606 follow-on) and consuming `fleet/events.py`
output as trusted input because every row *looks* journaled and
canonical. The S3 issue carries the T2 rule as an acceptance item so
the first gate build inherits the attestation requirement rather than
re-deriving it.

**F-TM3 — residuals carried (not new, all filed):** #1515 (re-pin
design owner, p3 — the `init` refusal names #1407 as the
rotation-design owner), #1407 (key-rotation re-encryption, p3), #778
(G19: retention GC + tenant read path, p2), #776 (G14 implementation,
p2). None of these block S3; #1515/#1407 orbit the pin lifecycle, #778
the journal's read side.

**F-TM4 — the `show-identity` vs `read --record registration`
distinction holds.** S2 added no registry query surface of its own —
and none is needed: the release registry *is* the journal store, and
`update_journal.py read --record registration` is the deployability
lookup the controller consumes (registration records carry
`release_id`/`channel`/`policy_ref`). No gap here; recorded so a later
turn does not file one.

## 4. Remaining-build table

| Slice | State | Owner |
|---|---|---|
| S1 update journal | shipped (#1499) | — |
| S2 registration CLI + identity pin | shipped (#1514) | — |
| S3 attested event ingestion | **filed this turn** (#1516) | #775 |
| Re-pin design owner | filed (#1515, p3) | — |
| Key-rotation re-encryption | filed (#1407, p3) | — |
| G19 retention + tenant read path | filed (#778, p2) | — |
| G14 scheduler suspend-awareness | filed (#776, p2) | — |

## 5. Non-goals (what this doc is not)

Not the S3 build (the filed issue owns that); not the G15 controller
build (G15 #606 is closed on design, its implementation lives outside
the trust lane); not the G17/G18 transports (closed on design);
not a re-verification of the S1/S2 review records (both merged with
unanimous SHIP IT on their final heads — see their slot entries, not
here). #775 stays OPEN (S3 + residuals).

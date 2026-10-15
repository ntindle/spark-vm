# Update journal — operator reference (S1, #775)

The control-plane update journal is the authoritative "what happened"
record for fleet update decisions. This doc is the **how** — the CLI,
the record vocabulary, the attribution rules, the failure taxonomy. The
**why** — the threat model, the trust root, who may authorize what —
lives in `TENANT_UPDATE_TRUST_MODEL.md`; the build slices (S2's `fleet
register` CLI, S3's attested ingestion) and the retention/tenant-read
story (G19, #660) live in that doc's §5 and §6.

Pinned to `fleet/update_journal.py` as merged on main `861b8ce`
(2026-10-15). If the module's behavior drifts from this doc, the
module wins and this doc needs a correction, not the other way around —
every behavior claim below was exercised against the shipped CLI in a
scratch store.

## 1. What it is

One append-only JSONL file per store, `<store>/update-journal.jsonl`,
on the **control plane** — never on a tenant box. The tenant holds root
inside the guest (H11), so any audit line written to a box is forgeable
by the tenant's own agent; this journal lives where the operator (or
their control plane) does.

It records update *decisions* — release registrations, wave
assignments, promotions, reimages, maintenance windows, freeze/halt
overrides — and, just as importantly, the `deferred`/`skipped` lines
that prove a box was *not* updated and why. There are no phantom
entries: a silent absence can never read as success.

This is a different journal from the fleet event stream
(`UPDATE_EVENT_REPORTING.md` — box-emitted outcomes, where box clocks are
never trusted) and from inventory's `journal.jsonl` in the same store
(observation records must not share provenance with authorization
records); the full provenance argument is in
`fleet/update_journal.py`'s docstring.

## 2. The CLI

Stdlib only. No server, no daemon — two subcommands.

### `append` — validate and journal a record

```
update_journal.py append --store DIR --tenant T --actor-fingerprint FP \
    --record TYPE --data '{...}' [--ts 2026-10-15T08:07:30Z]
```

`--tenant`, `--actor-fingerprint`, `--record`, `--data` are required;
`--ts` defaults to now (UTC, ISO-8601). `--record` is constrained to
the eleven §3 record types. On success, exit 0; a `registration` also
prints its generated `registration_ref` to stdout (that ref is the
handle every later record in the rollout must cite).

The walk-through below is the canonical rollout lifecycle in four
lines. The `--actor-fingerprint` is the provisioned operator key's
fingerprint (the pinned identity the trust model §2 requires) in the
canonical form (§4), passed as a shell variable here:

```console
$ FP="SHA256:..."  # your provisioned operator key's fingerprint
$ update_journal.py append --store /var/lib/sparkvm/fleet --tenant acme \
      --actor-fingerprint "$FP" --record registration \
      --data '{"release_id":"2026.10.1","channel":"stable","policy_ref":"pol-77"}'
reg-dfabf8f59e1fc7d6
$ update_journal.py append --store /var/lib/sparkvm/fleet --tenant acme \
      --actor-fingerprint "$FP" --record wave_assignment \
      --data '{"box_id":"box-9","wave":0,"canary":true,"manifest_version":"mv-204","registration_ref":"reg-dfabf8f59e1fc7d6"}'
$ update_journal.py append --store /var/lib/sparkvm/fleet --tenant acme \
      --actor-fingerprint "$FP" --record reimage \
      --data '{"box_id":"box-9","image_from":"2026.09.4","image_to":"2026.10.1","wave":0,"migration_outcome":"success","registration_ref":"reg-dfabf8f59e1fc7d6"}'
$ update_journal.py append --store /var/lib/sparkvm/fleet --tenant acme \
      --actor-fingerprint "$FP" --record freeze --data '{"reason":"canary regression signal"}'
```

Nothing is journaled on any validation failure — the CLI fails loud
(exit 2, the reason on stderr) instead of journaling a half-true line.

### `read` — dump the journal

```
update_journal.py read --store DIR [--tenant T] [--record TYPE] [--since TS]
```

One JSON object per line on stdout, `sort_keys` order. The three
filters compose (`read --store DIR --tenant acme --record reimage
--since 2026-10-01T00:00:00Z` answers "which acme boxes were reimaged
this month"). A missing journal file reads as empty (exit 0, no
output) — an estate that has never journaled is not an error.

Malformed lines are **reported, never gate-consumed**: `read` prints a
stderr warning `update_journal: warning: N malformed line(s) skipped
(never gate-consumed)` and drops them from the result. A corrupt line
is missing evidence, never evidence. Note that the reader stays
unlocked (§5), so a partial last line written by a racing append shows
up in that same skip count.

## 3. The record vocabulary

Eleven types, schema-exact: unknown fields are rejected, not dropped.
Every record carries the four common fields `ts`, `record`,
`tenant_id`, `actor_fingerprint`; every type except `registration`
and the release-independent `freeze`/`unfreeze` additionally carries
`registration_ref` citing the authorizing registration (see §4). Types
marked `[C]` in the table must cite a registration; the `registration`
type generates it; `freeze`/`unfreeze` must not carry it.

| Record | Required fields | Optional | Enums | Chaining |
|---|---|---|---|---|
| `registration` | `release_id`, `channel`, `policy_ref` | `advisory_ref` (mandatory when `channel` is `security`) | `channel` ∈ {stable, security} | generates `registration_ref` |
| `wave_assignment` [C] | `box_id`, `wave`, `canary`, `manifest_version` | — | `canary` must be a real bool (not 0/1 — bool≠int is enforced) | cites ref |
| `promotion` [C] | `from_wave`, `to_wave`, `gate_evidence_refs` | — | `gate_evidence_refs` is a non-empty list of non-empty strings | cites ref |
| `reimage` [C] | `box_id`, `image_from`, `image_to`, `wave`, `migration_outcome` | `g17_outcome_ref` | `migration_outcome` ∈ {success, failed} | cites ref |
| `maintenance` [C] | `box_id`, `transition`, `arc` | — | `transition` ∈ {enter, exit} | cites ref |
| `freeze` | `reason` | — | — | **must not** carry a ref |
| `unfreeze` | `reason` | — | — | **must not** carry a ref |
| `halt` [C] | `release_id`, `wave`, `reason` | — | — | cites ref |
| `promote` [C] | `release_id`, `to_wave`, `reason` | — | — | cites ref |
| `deferred` [C] | `box_id`, `reason` | — | — | cites ref |
| `skipped` [C] | `box_id`, `reason` | — | — | cites ref |

Field-type rules beyond the obvious: non-empty strings (an empty
`reason` is a validation failure, not a journaled silence), `int`
fields reject booleans, and **the CLI-level common fields never live
inside `--data`** — `ts`, `record`, `tenant_id`, or `actor_fingerprint`
in `--data` is rejected, because a CLI-level vs data-level pair silently
shadowing each other is an attribution hazard in both directions.
`registration_ref` is the one common field that does travel in
`--data`: required there on every chained type, rejected on
`registration` and on `freeze`/`unfreeze` (see §4).

## 4. Attribution — the rules that make it auditable

- **`tenant_id` is required and has no default.** The journal is
  per-tenant by construction; a missing tenant is a fail-loud exit 2,
  never a "global" bucket.
- **The fingerprint is structural, not decorative.** There is no
  `--actor-name` flag — a bare name like `operator` cannot be
  journaled by accident. Accepted forms: the repo's `SHA256:` base64
  fingerprint (as emitted by `pairing/ed25519.fingerprint()`;
  whitespace/padding tolerant, prefix case-insensitive) or the same
  32-byte digest as 64 lowercase hex chars. Both normalize to one
  canonical journal form (`SHA256:` + unpadded base64), so the
  cross-restart identity the trust model requires compares
  byte-for-byte. Anything else — including a perfectly plausible
  operator name — is rejected:
  `actor_fingerprint 'operator' rejected: fingerprint is not a
  32-byte SHA-256 digest — a bare name cannot be journaled as an
  identity`.
- **`registration_ref` is generated, never accepted.** On
  `registration` the CLI computes `reg-` + the first 16 hex chars of
  SHA-256 over the authorization-bearing inputs (release, channel,
  policy, advisory, moment, canonical fingerprint) and prints it; a
  caller-supplied ref is rejected (the design rationale is in
  `fleet/update_journal.py`'s docstring). The ref hashes the
  authorization-bearing inputs *including* the timestamp, so a
  re-registration reproduces the same ref only when `--ts` is pinned to
  the identical timestamp. Without an explicit `--ts`, `now()` produces
  a fresh ref — re-running a registration is a new registration, not an
  idempotent replay.
- **The chain is checked at append time.** Every record that cites a
  `registration_ref` must cite a registration already in this store
  under the same tenant — a reimage citing `reg-deadbeef` journals
  nothing and exits 2. Registrations earlier in the same batch count,
  so a register-then-chain sequence in one call works. Tenant scoping
  crosses the chain too: a ref registered for tenant A is dangling
  for tenant B.
- **`freeze`/`unfreeze` carry no ref.** They are operator-level,
  release-independent actions (the trust model's §2 — the rationale is
  in `fleet/update_journal.py`'s docstring), so a
  `registration_ref` on one is rejected, not ignored.

## 5. Store layout and write discipline

The store is a directory. The journal is one file in it:
`<store>/update-journal.jsonl`, one newline-terminated JSON object
per line, keys sorted. The write discipline — one line per single
`write()` under line buffering, O_APPEND positioning, fsync before
return (an append that exits 0 survives an OS crash), all appends
under the store-scoped journal lock with a bounded wait — is documented
in `fleet/update_journal.py`'s docstring. Two facts matter to the
operator directly:

- **The lock is host-local.** It serializes processes on this machine
  only. A store shared across hosts needs its own design (G26's fleet
  event stream is the named future); this journal claims no
  cross-host exclusion.
- **Readers stay unlocked.** A reader racing a writer may observe a
  partial last line — that lands in the read skip count with a loud
  warning (§2), never in the results, never in a gate decision.

## 6. Failure taxonomy

Exit codes are a contract:

- **0** — success. (Plus the `reg-…` ref printed on registration.)
- **2** — usage/validation error: bad fingerprint, unknown record
  type, missing or misshaped field, dangling `registration_ref`,
  ref on freeze/unfreeze. Fail-loud — **nothing is journaled** —
  with the reason on stderr. This is an input problem: fix the
  command, don't retry it into the store.
- **1** — runtime error: the store directory cannot be created, the
  journal cannot be appended, the lock cannot be acquired. An
  environment problem: safe to investigate and retry the same
  command.

Malformed data on disk is not an error class the writer can produce:
the module deliberately has **no prune** — retention and the tenant
read path are G19 (#660). The `read` command exists so the operator
can answer "what happened" directly from the journal; if a line is
corrupt, `read` says so loudly and skips it, and that skip is never
consumed by any gate. (The G17 alert-rule machinery that *does*
gate on fleet events reads the event stream, not this journal —
the two records have different trust stories, §1.)

## 7. The self-hosted operator's estate

The both-supported default applies: the same primitives serve the
self-hosted operator's N-box estate — registration, the journal, the
freeze — with the operator as the only actor and the estate name as
`--tenant`. The hosted delta is tenant scoping (one journal per tenant
plane) and the attestation requirement on the ingest path (S3,
#775's remaining half).

## 8. What this doc is not

- **Not the retention policy.** How long records are kept and who
  may read them — G19 (#660), `UPDATE_AUDIT_RETENTION_AND_ACCESS.md`.
- **Not the registry.** S2's `fleet register` CLI and operator
  identity model are #775's next slice, not shipped yet.
- **Not the attested ingest.** S3's signed box→control-plane event
  channel is #775's remaining half.
- **Not a gate.** Nothing here is consumed by an automated gate
  today; the journal exists *before* the scheduler does so that when
  the scheduler arrives, its decisions are auditable from day one.

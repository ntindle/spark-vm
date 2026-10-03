# Credential-vending contract: vend spec + tenant-scoping decision (#850, S1+S2)

**Status.** Design contract, pinned to this repo at merge `35485f1` (PR
#930). Plane-side facts are pinned to `docs/CONTROL_PLANE_API_REFERENCE.md`
and the loop's 2026-10-03 reads of the `sparkvm-control` worker — the plane
lives outside this repo, so plane-side rows below are the contract the
plane must implement, not a description of what it does today. Doc-first;
honesty rules apply (`docs/POSITIONING.md`): everything below is the
**agreed design and the work to do**, not a promise.

**Place in the slice plan** (`docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md`
§4): this doc lands **S1** (the #280 tenant-scoping decision — G50.3 says
land it *with* the vend contract, not after it) and **S2** (the vend
contract spec). S3 is #890 (plane vend endpoint, follows this contract);
S4 is #891 (box-side swapd fetch path, parallelizable with S3 once this
pins). S5 is the H19 reconcile; S6 is the acceptance checklist (§10).

**Vision tracker:** #850. Implementation items: #890, #891.

## 1. S1 — the tenant-scoping decision (#280)

#280's three options, evaluated:

| Option | Shape | Verdict |
|---|---|---|
| A. Tenant field in the registry | One host, N tenants, flat store gains a `tenant` column | **Rejected.** Vends credentials into a shared secret universe — exactly what G50.3 forbids. A column does not fix A1. |
| B. Per-tenant secret dirs + registry files | One host, N tenants, N flat stores | **Rejected.** Inherits A1 whole: the proxy still trusts any local process, so a per-tenant dir is one `swap.log` away from a cross-tenant swap. (A4: all jails share one proxy today.) |
| C. Per-tenant box | One tenant per box; the store stays flat | **ADOPTED.** |

(The gap analysis's "per-tenant swapd" option folds into C — one box
implies one swapd.)

**Decision: C.** It follows from `docs/MULTI_TENANCY_AUDIT.md` §2 finding
1 rather than re-litigating it — the audit ADOPTED per-tenant box for
compute isolation; applying it to the credential stack is the new
decision G50.3 demanded, made here: *"per-tenant box is the vendor
consensus for mutually-untrusted tenants; the jail generalizes honestly
only if the weaker shared-kernel boundary is documented as such."* With C:

- The existing flat store (`/home/swapd/secrets/<name>`,
  `/home/swapd/credentials.json`) is **correct-by-construction per box** —
  no tenant key lands in `cred`, the registry, or the secrets dir. #280 is
  decided for the hosted track: the answer is *no tenant dimension in the
  box-side stack*.
- The vend contract's tenant dimension is **`box_id`**, 1:1 with the tenant
  in the hosted shape. The plane's per-box secret manifest (§2.4) is the
  tenant boundary; two tenants never share a manifest.
- The proxy's host-wide grants (A1) stay **benign in the hosted shape**:
  each box runs exactly one tenant's processes against its own proxy, so
  "any local process can spend any grant" spends only that tenant's
  grants.

**Boundaries (what this does NOT claim):**

- Cooperative same-household tenants sharing one self-hosted box keep the
  existing flat store with its documented limits — that shape is the
  self-hosted single-operator model, not hosted multi-tenancy. #339
  (per-tenant request auth on the proxy) remains the open improvement for
  that shape; it is decided *together* with vending per G50.4 but
  implemented separately (§7).
- The jail remains a cost optimization for cooperative tenants, never a
  security equivalence (audit §2 finding 1, quoted above).
- **"Two tenants never share a manifest" is an operator provisioning
  invariant, not a schema guarantee.** The D1 schema permits an owner
  to write identical secret values into two boxes' manifests; nothing
  in v1 detects or forbids it. The tenant boundary holds only while
  provisioning keeps the 1:1 box:tenant mapping.

## 2. S2 — the vend contract

### 2.1 Endpoints and auth

Two auth classes, same namespaces as the rest of the plane
(`CONTROL_PLANE_API_REFERENCE.md` §"Auth classes"): a box bearer presented
at an owner endpoint never matches; an owner key presented at a box
endpoint never matches. (#890 confirms routing conventions against
`worker.py` — owner-key approval records live under
`/v1/boxes/{box_id}/approvals`; the auth classes here stay explicit
regardless.)

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /v1/boxes/{box_id}/credentials` | **box bearer** (#844) | Mint: the box requests named credentials, receives short-lived values. `{box_id}` in the path must equal the token's box (else 403 — the token is valid, the identity is wrong). |
| `PUT /v1/owner/boxes/{box_id}/credentials/manifest` | **owner key** (#843) | Management: write/replace the box's secret manifest (metadata + source values, write-only). |
| `GET /v1/owner/boxes/{box_id}/credentials/manifest` | **owner key** | Management: read manifest **metadata only — never secret values** (values are write-only after set; see §3). |
| `DELETE /v1/owner/boxes/{box_id}/credentials/{name}` | **owner key** | Revoke: retains the manifest row as a tombstone and stamps `revoked_at` — a revoked name is never vended (mint lists it in `refused`); the stamp is cleared only by re-PUT with a fresh value. Propagation is bounded by §5. |

### 2.1a Manifest write schema and validation

Request body (`PUT /v1/owner/boxes/{box_id}/credentials/manifest`,
owner key, TLS):

```json
{ "secrets": [ { "name": "github-pat", "value": "<plaintext secret>",
  "ttl_seconds": 3600, "host_allowlist": ["api.github.com"],
  "placement": ["bearer_header"] } ] }
```

Write/replace is per-box and **atomic**: the posted array becomes the
box's entire manifest — names absent from the array have their values
deleted. Validation failures are `400`:

- `name`: 1–64 chars, `[A-Za-z0-9._-]` (the `aid` charset precedent in
  `CONTROL_PLANE_API_REFERENCE.md`); names appear in URL paths and D1
  keys, so anything else is rejected.
- `value`: 1–16384 bytes (the durable-command payload precedent); larger
  is rejected.
- `ttl_seconds`: within the §2.3 bounds.
- `host_allowlist`: non-empty array; every entry a bare DNS hostname
  (no scheme, port, path, or userinfo); wildcard entries rejected in
  v1. An empty or missing allowlist is a `400`, never a fail-open vend.
- `placement`: non-empty subset of
  `bearer_header | custom_header | query_param | url_path_segment`.
- `box_id`: must be an enrolled, non-revoked box; unknown box → `404`
  (no manifest rows for unenrolled boxes).

The `PUT` response echoes metadata only
(`{ok, box_id, names: [...], updated_at}`) — never values. The plaintext
`value` is encrypted into `vend_values` before the response is written
and must never appear in plane access logs, error logs, or `vend_audit`
rows (see §2.5, §3).

`GET /v1/owner/boxes/{box_id}/credentials/manifest` returns
`{ "secrets": [ { "name", "ttl_seconds", "host_allowlist", "placement",
"revoked_at", "updated_at", "updated_by" } ] }` — metadata only, never
values.

### 2.2 Mint request and response

Request (box → plane):

```json
{ "names": ["github-pat", "openai-key"] }
```

The box names only what it needs. The plane intersects with the box's
manifest: names in the manifest are vended; anything else is listed in
`refused` — never silently dropped, never vended. Names with
`revoked_at` set are likewise listed in `refused`, never vended.

**Mint vs refresh.** There is one mint endpoint; a refresh is a repeat
`POST` with the same names. The plane records `action='refresh'` in
`vend_audit` when it mints while an unexpired, unrevoked lease for that
`(box_id, name)` already exists, and `action='mint'` otherwise. The
response shape is identical either way.

`names` is capped at 64 entries (`400` beyond); the plane additionally
rate-limits mints per box (`429` — precedent: the pairing 50-pending cap
in `CONTROL_PLANE_API_REFERENCE.md`).

Response (plane → box), `200`:

```json
{
  "server_time": "2026-10-03T17:00:00Z",
  "credentials": [
    {
      "name": "github-pat",
      "value": "<the secret — returned in the mint response body only, never in any other endpoint or response>",
      "expires_at": "2026-10-03T18:00:00Z",
      "ttl_seconds": 3600,
      "host_allowlist": ["api.github.com"],
      "placement": ["bearer_header"]
    }
  ],
  "refused": ["openai-key"]
}
```

`host_allowlist` and `placement` carry the existing box-side discipline
into the hosted shape: the box-side swapd enforces the same rules it
enforces for human-filled secrets today (`hosts.allow` binding +
placement restrictions `bearer_header` / `custom_header` / `query_param` /
`url_path_segment` in `proxy/swap_addon.py`). The effective allowlist is
the manifest `host_allowlist` **intersected with** the box's own
`hosts.allow` — neither side widens the other; the box fails closed
(loud, no swap) on a mint response with a missing or empty
`host_allowlist`. The plane's manifest is the source of truth; the box
never widens it.

**Honest scope note (v1):** v1 vends *lease-wrapped source credentials* —
the short-lived property is enforced by lease expiry, refresh, and
revocation (§5), not by minting fresh upstream tokens per vend. Dynamic
upstream minting (STS-style per-vend tokens where the upstream supports
it) is a future extension, not v1. The contract's security properties
below hold for v1.

### 2.3 TTL bounds

STS-style, minutes-to-hours. Contract bounds, enforced at manifest-write
time (out-of-range manifest TTL → `400`):

- default `ttl_seconds`: 3600
- minimum: 300 (5 min)
- maximum: 86400 (24 h — matches the box-bearer lifetime, so no lease
  outlives the identity that fetched it)

`expires_at` is server-stated. The box treats a lease as expired 60 s
early (safety margin against clock skew); the #846 ±300 s clock window
applies to the bearer itself.

At the minimum 300 s TTL the re-check cadence (§5) equals the TTL, so
minimum-TTL credentials re-mint roughly every 300 s; manifest authors
wanting lower refresh load should prefer TTLs ≥ 900 s.

### 2.4 D1 schema (plane)

```sql
-- Per-box secret manifests: names, TTLs, per-secret allowlists.
-- Conspicuously no values.
vend_manifest(box_id TEXT, name TEXT, ttl_seconds INT,
              host_allowlist TEXT /* JSON array */, placement TEXT /* JSON array */,
              updated_at TEXT, updated_by TEXT /* owner-key id */,
              revoked_at TEXT /* NULL = active; set by DELETE; cleared
              only by re-PUT with a fresh value */,
              PRIMARY KEY (box_id, name));

-- Secret values: ciphertext only. Separate table so a manifest reader
-- can never trip over a value.
vend_values(box_id TEXT, name TEXT, ciphertext BLOB, nonce BLOB,
            alg TEXT /* 'aes-256-gcm' */, created_at TEXT, rotated_at TEXT,
            PRIMARY KEY (box_id, name));

-- Server-side vend audit (G50.6): every vend, refresh, revoke, and
-- manifest write. Never carries values.
vend_audit(id INTEGER PRIMARY KEY, at TEXT, box_id TEXT, name TEXT,
           action TEXT /* mint|refresh|revoke|manifest_write|manifest_read */,
           actor TEXT /* 'box' | owner-key id */,
           result TEXT /* ok | refused | revoked_box | error */,
           ttl_seconds INT, tenant_id TEXT /* reserved, NULL in the
           per-tenant-box shape — §7 */);
```

### 2.5 Server-side audit (G50.6)

`swap.log` keeps auditing box-side swaps, but the audit a tenant can't
tamper with is the server-side one: every mint, refresh, revocation, and
manifest write/read lands in `vend_audit`. The audit row carries
`box_id` — the tenant identity #280's per-tenant-box decision makes 1:1
with the tenant; box identity itself comes from the #844 box bearer.
It never carries a secret value.

**Read path.** `vend_audit` rows are readable only with an owner key
(S3: `GET /v1/owner/boxes/{box_id}/credentials/audit`, paginated,
owner-auth). They are never served to box-bearer callers and never
embedded in mint responses. A box reading another box's vend history
would be cross-tenant intel; the read path stays on the owner side of
the auth-class boundary (§2.1).

## 3. Custody: where secret values rest on the plane (G50.9)

The vision moves secret material off the box and onto the plane. Without
this answer the design is a trust relocation, not a trust improvement:

- **At rest:** encrypted. `vend_values.ciphertext` is AES-256-GCM with a
  random nonce per value. The data key lives as a **Cloudflare Worker
  secret** — never in D1, never in the repo, never in logs, never in an
  audit row. Key rotation is an operator procedure (re-encrypt
  `vend_values` under the new key; the old key is retained only for the
  rotation window).
- **In flight:** plaintext exists only in worker memory while assembling a
  mint/refresh response, over TLS, to the authenticated box.
- **Who can read a value:** exactly one API path — the box's own
  `POST /v1/boxes/{box_id}/credentials` with a valid box bearer. Owner
  keys manage (write/replace/revoke/list-metadata) but **cannot read
  plaintext values through the API** — `GET` on the manifest returns
  metadata only. Values are write-only after set; rotation means
  replace, not read-back.
- **What a D1-reading attacker gets:** manifests (names, TTLs,
  allowlists — metadata), ciphertexts (unreadable without the Worker
  secret), vend-audit rows (which credential, when, to which box — no
  values), key/token hashes (as today). They do **not** get any secret
  value, the data key, or a box token.
- **Honest limit:** the plane operator technically controls the worker
  and its secrets. There is **no claim of operator blindness** — H11's
  finding 4 (decided 2026-09-24) is explicit about this, and this contract
  inherits it. The design protects against *infrastructure-layer*
  exposure (Cloudflare-side, backups, mis-scoped service tokens), not the
  operator. Users wanting provider-blind infrastructure self-host.
- **No secret values in plane logs.** Mint/refresh response bodies are
  excluded from HTTP access logging; error paths (4xx/5xx bodies,
  exception traces, edge logs) must never echo a secret value or a full
  mint response. The only place a plaintext value may exist on the plane
  is worker memory during response assembly.
- **Key-rotation bound.** The old data key is destroyed ≤ 24 h after a
  rotation completes; during the window both keys decrypt (dual-key
  read). Fresh random nonce per encryption operation, including
  rotations — GCM nonce reuse is catastrophic. Stated plainly: one data
  key protects all tenants' values, so one key compromise exposes every
  vended value. That is why the key lives in a Worker secret and rotates
  as an operator procedure.
- **Scope.** Secret material delivered outside the vend path (e.g.
  smuggled as an opaque #848 durable-command payload, stored verbatim in
  D1) is outside this custody story — this section covers vended
  credentials only.

## 4. The outage rule (G50.2, reconciled)

Reconciled with the control-plane-outage principle
(`MULTI_TENANCY_AUDIT.md` — design for stale authorization, never assume
an outage degrades into bypassed identity):

- **No lease + plane configured but unreachable → fail closed.** No
  swap; loud log. (A box with no plane configured never reaches this
  rule — it takes the secrets-dir path per §6; "plane unreachable" here
  means configured-but-unreachable.)
- **Live lease + plane unreachable → TTL-bounded stale authorization.**
  The box keeps swapping until the lease expires, then stops. A lease is
  never extended past its `expires_at` — the box treats it as expired
  60 s early (§2.3).
- **Revocation** takes effect at the next successful refresh, bounded as
  §5 states (worst case one refresh cadence). A revoked name missing
  from the refresh response is evicted from the cache immediately
  (refresh-miss eviction). There is deliberately **never a post-expiry
  stale value** — expiry is a hard delete (§5).
- **Box-bearer revocation does not kill a live lease.** Revoking a
  box's bearer stops all new mints/refreshes (401), but a lease already
  in the box's RAM keeps swapping until its `expires_at` — up to the
  24 h TTL cap — per the outage rule above. There is no remote-kill of
  a live lease in v1. An operator revoking a box for cause must also
  rotate the affected upstream source credentials. #891 SHOULD route an
  owner-issued `credential_kill` through the durable-command queue
  (#848) so a live box wipes its RAM cache within one command-fetch
  cycle; until that ships, the TTL cap is the kill bound.
- **Bootstrap (S5):** at provisioning, the owner-side tooling writes the
  box's secret manifest (`PUT` manifest, §2.1a) — that is the plane-side
  half of the first mint, and it is also H19's credential half (§8). No
  lease is generated before a box bearer exists: per G51.4
  (`BOX_PROVISIONING_GAP_ANALYSIS.md`) there is no box-side credential
  install before pairing, and the mint endpoint's only auth is the
  post-pairing box bearer. The box's first fetch happens on first boot
  after pairing (or on first swap via fetch-on-miss, §5); until then the
  box holds an empty RAM cache and the no-lease fail-closed rule above
  applies — a hosted box starts life with a provisioned manifest and an
  empty cache, never with a pre-seeded lease.

## 5. Short-lived semantics (G50.5)

- **Refresh-before-expiry** (the Vault-Agent pole, not fetch-on-use):
  the box-side fetcher re-checks each lease every `max(300 s, ttl/3)`
  and refreshes any lease whose remaining TTL has dropped below
  `max(300 s, ttl/3)`. Fetch-on-use is rejected for the hot swap path
  (it would put plane latency on every credentialed request); a
  lease-miss at swap time triggers an immediate blocking refresh
  (fetch-on-miss).
- **Hard delete-on-expiry:** at expiry the value is wiped from memory. A
  subsequent swap request fails closed until a fresh lease lands.
- **RAM-only cache:** vended values are never written to the box
  filesystem — no secret bytes on disk, per #850's acceptance. RAM-only
  means never written via file I/O — but on a host with swap enabled,
  paged-out memory *is* disk. #891 must `mlock(2)` the cache pages (or
  platform equivalent) and suppress core dumps for the fetcher process,
  or the hosted box image must run swapless; otherwise acceptance item 4
  (§10) fails. This constraint is recorded here so the acceptance claim
  stays honest.
- **Revocation propagation bound:** one refresh cadence — worst case
  `max(300 s, ttl/3)` after the owner revokes, the box stops swapping
  (a revoke landing just after a re-check is seen at the next one).
  Owners who need faster revocation must rotate the upstream source
  credential itself — the vend layer bounds staleness, it does not push
  revocation.
- **Refresh-miss eviction:** a name present in the RAM cache but absent
  from a successful refresh response is hard-deleted from the cache
  immediately — revocation must not wait for lease expiry.

## 6. The dual-mode seam (G50.2)

Source selection is a **config-time decision**, not a runtime assumption:

- **Plane configured → vend path** (§2–§5, with the §4 outage rule).
- **Plane not configured → the secrets dir, exactly as today.** "Plane
  unreachable" is the self-hosted box's permanent state, and Q4 keeps
  human-filled secrets on the box disk by design.

The vend path never becomes the only path. A self-hosted box with no
plane configured behaves byte-identically to today.

**Mode latch.** The vend-vs-disk decision is read once at fetcher start
and latched for the process lifetime. A mid-run loss or change of the
plane configuration is treated as *plane unreachable* (§4: live leases
swap to expiry, then fail closed) — never as a silent switch to the
secrets dir. In vend mode the fetcher does not read
`/home/swapd/secrets` or `credentials.json` at all — dir files on a
plane-configured box are dead bytes, never swapped. Rationale: an
unlatchable mode bit is an audit-evasion switch — flipping to disk mode
would stop plane-side `vend_audit` mints (G50.6's tamper-evident trail)
while swaps continue. The fetcher logs its latched mode at startup
(box-side `swap.log`); S3 SHOULD treat "box heartbeating but never
minting" as an anomaly signal.

The vend-mode config (plane base URL + box bearer source) is pinned by
#891; this contract only requires the mode be a config-time, latched
decision.

## 7. Request identity: the #339 twin (G50.4)

Per-tenant box makes the proxy's host-wide grants benign **for the hosted
shape** — one tenant per proxy (§1). The hosted-track decision is landed
here (per-tenant request auth is unnecessary under per-tenant box); the
cooperative same-box shape stays open with #339, and `tenant_id` is
reserved in `vend_audit` rows (NULL in the per-tenant-box shape) so the
audit schema needs no migration when it lands.

## 8. H19's three elements route three ways (G50.7)

#134 is not a single credential-delivery shape; per-element routing:

- **Scoped sudoers for the tenant agent user** → reconciles against Q4's
  runtime-cell answer (tenant gets contained root-equivalent inside the
  cell; the operator never co-resides with a passwordless-sudo domain),
  not folded into vending.
- **Smoke-test credential install** → the vend bootstrap (S5): manifest
  write at provisioning, then vending takes over after pairing. This is
  the one element that is "do not build two credential-delivery shapes."
- **Echo-endpoint allowlist entry** → the smoke-bootstrap decision,
  riding with the credential half.

## 9. Honest limits (G50.8)

Stated plainly (the q5 research's point): **nothing fully protects
against root on the box.** The defense is blast-radius control — short
TTLs, narrow per-box scoping, audience-bound tokens where the upstream
supports them, injection at the proxy so workload process memory holds
placeholders. No marketing claim of operator blindness; the trust story
is already explicit in the H11 audit (§3).
- **Paging:** a RAM cache on a swapping host leaks secret bytes to the
  swap device — see §5. The "no secret bytes on disk" claim holds only
  with locked memory or a swapless host.

## 10. Acceptance (S6 — testable)

1. Two boxes, distinct manifests → distinct secret universes (S1).
2. Revoke mid-lease → the box stops swapping within one refresh cadence
   of the revoke (`max(300 s, ttl/3)` — §5), and a revoked name vanishes
   from the cache at the next refresh.
3. Unreachable plane + live lease → TTL-bounded stale swaps, then stop,
   loud; no-lease + plane-configured-but-unreachable box → no swap, loud
   (§4).
4. No secret bytes on the box filesystem (RAM-only cache) (§5).
5. The plane audit shows every mint, refresh, revocation, and manifest
   write/read (§2.5).
6. The self-hosted no-plane configuration works exactly as today (§6).
7. Owner `GET` on a manifest returns metadata only — never values (§3).
8. Revoked box bearer → no new mints/refreshes (401), but a live lease
   keeps swapping until expiry — documented behavior, not silent (§4).
9. A box bearer presented at any `/v1/owner/.../credentials/*`
   endpoint → 401 (auth-class namespace separation, §2.1).

## 11. What's next

- **#890 (S3):** the plane vend endpoint, D1 schema, mint/revoke,
  owner-gated management, and server-side audit — implemented against
  this contract in the plane workspace.
- **#891 (S4):** the box-side swapd fetch path — RAM cache, TTL refresh,
  the §4 reconciled outage rule, box-bearer auth, and the §6 dual-mode
  seam — in this repo.
- **S5:** the H19 reconcile per §8 (credential half → vend bootstrap).
- **S6:** the acceptance verification per §10.

Pointer comments on #850, #890, #891, and #280 carry this contract's
location. #280's hosted-track decision is recorded here in §1.

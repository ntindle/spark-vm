# Tenant data export (H31)

**Status:** design doc for backlog item H31 (hosted-product track), written
2026-09-29. USER-DIRECTED 2026-09-25: spark-vm hosted has no equivalent of
Muse's "Download your agent data" (Settings > Data Controls). This spec
defines how a tenant exports their data out of a hosted box: scope (files,
agent state, logs), format, auth, and where it lands in the hosted vs.
self-hosted parity story.

**Design thinking, not a commitment.** Implementation ships in the build
slices (§6); the open questions (§7) stay open until someone runs them
down.

---

## 1. What an export is — and is not

An export is a **tenant-scoped, point-in-time copy of the tenant's own
data**, assembled on the tenant's box, packaged in a defined archive shape,
and delivered to the tenant through a channel the operator can relay but
not read back into.

It is NOT:

- a box image or snapshot — the image contains the operator layer
  (golden-image contents, provisioner records, updater state). The export
  is *data*, not the machine. Full-box export stays an operator-only
  disaster-recovery primitive and is not in this spec.
- a migration tool — moving a tenant between boxes/providers is a
  separate design (import path undefined). The export's archive shape is
  chosen so an import tool *could* consume it later, but import is not
  promised here.
- deletion — export never deletes anything. The erasure/deletion story
  (§7 Q1) is a separate operation with stricter auth.

## 2. Scope: what goes in, what stays out

### 2.1 Included (tenant-visible data only)

| Area | Contents | Assembled by | Source of truth |
|------|----------|--------------|-----------------|
| **Files** | The tenant user's home directory: workspace, repos/clones, job inputs/outputs, configuration the tenant wrote | box | `$HOME` on the box |
| **Agent state** | `muse-job` session state and event files for the tenant's jobs; job transcripts the box produced | box | muse-job's per-job state |
| **Approvals history** | The tenant's own approval filings and their terminal decisions (`approved:`/`denied:`/`expired:` per `EXPIRED_APPROVAL_TERMINAL_RECORD.md`), as the tenant saw them | box | confirmd tenant-visible records (confirmd runs on the box) |
| **Status record** | The tenant's `GET /tenant/status` record — the control plane's current arc code, plus the arc history if the arc-history store exists | control plane | `TENANT_STATUS_ENDPOINT.md` producer. **Honesty note:** the endpoint doc defines codes, producers, and transition rules but no persisted arc-history store — "machine codes over time" is a record that does not exist yet. Until the arc-history store is built, the control-plane payload carries the *current* arc code only, and the manifest says so. |
| **Audit lines** | Tenant-attributed audit lines for the tenant's own actions (per #14's tenant attribution) | control plane | control-plane audit journal |

The export is a **two-source assembly**: the box-side assembler (§4.2 step 2)
produces the box payload; the control plane attaches the control-plane
payload at delivery time (§4.2 step 4). The manifest's scope enumeration
records which sections are present — sections are optional, not
guaranteed, which is what keeps §9's parity story honest.

### 2.2 Excluded — never exported

- **Real secret values, ever.** The `cred` store's values are
  human-installed and human-only (`docs/SECRETS_POSTURE.md`). The export
  carries `hsurr:<name>` placeholders **as-is**: opaque, meaningless
  outside the box, and safe to hand to anyone. Any assembly step that
  touches the cred store is a spec violation — the assembly script must
  not open it, and the T1 reader audit (§5) verifies that.
- Operator surfaces: the control-plane audit journal raw (other tenants'
  lines), sentinel telemetry, provisioner records, golden-image manifest,
  other tenants' anything.
- Control-plane records about the tenant (billing, funnel events):
  exportable via a *separate* account-data surface (human dashboard), not
  this box-data export. Mixing them would hand the box layer a job that
  belongs to the account layer.

## 3. Format: one manifest, one or two encrypted payloads

The export is a **bundle**: a plaintext `manifest.json` plus one or two
encrypted payload archives (box payload always; control-plane payload
when a control plane exists — §2.1, §9). The manifest is operator-readable
metadata; the payloads are opaque blobs the operator can store and relay
but never decrypt.

Each payload is a `tar` stream compressed with `zstd`
(`<tenant_id>-export-<YYYYMMDD-HHMMSS>-box.tar.zst`,
`-controlplane.tar.zst`), containing:

1. The payload's data in its natural layout (box payload: relative
   paths under `$HOME`, plus `state/`, `approvals/`; control-plane
   payload: `status/`, `audit/`).
2. `README.txt` (box payload only) — human-readable: what this export
   is, what it is not, how to verify the manifest, and the pointer to
   this spec.

The manifest carries: archive version (`"export_format": 1`),
`tenant_id`, `assembled_at` (UTC), box/image provenance, the scope
enumeration naming which sections are present, per-payload SHA-256
checksums, byte totals, and the encryption scheme. A consumer
validates the manifest, then decrypts the payloads with the tenant
private key.

Rules:

- **Deterministic assembly order** (sorted paths) so two exports of
  unchanged data hash the same — debuggability, not a security claim.
- **No symlinks out of scope**: the assembler resolves and refuses
  anything escaping the tenant home; a refused path is *logged in the
  manifest*, not silently dropped.
- **Manifest is the contract**: format 1 is additive-only; readers ignore
  unknown keys; a future format 2 gets its own spec section.

## 4. Auth: who can ask, who approves, how the bytes are fetched

### 4.1 Two requesters, one owner

The **human account holder** owns the data; the **tenant Muse** is its
delegate. Both existing identities apply
(`docs/HOSTED_SIGNUP_ONBOARDING.md` §4):

- The **Muse** requests with its linked ed25519 keypair (signed request,
  same identity as status polling and approval acks). It does not need a
  human in the loop to ask — fetching its own data back to its home
  machine is ordinary delegated work.
- The **human** requests from the signup dashboard (magic-link session).
  "Reachable" in the sentence below means the box is `live`/`approved`
  per the tenant-status liveness gate (§4.2 step 2) — a suspended or
  unhealthy box is not reachable. The human's request always succeeds
  when the box is reachable; it can also *cancel* a Muse-requested
  export while it is assembling. When the box is suspended, the human
  is offered an explicit **"wake and export"** opt-in with the cost
  shown (owner's money, owner's consent); the Muse is never offered
  one — Muse-requested exports on a suspended box stay queued.

### 4.2 The assembly and delivery flow

1. **Request.** Signed (Muse) or session-authed (human) request to the
   control plane: `POST /tenant/export` → returns an `export_id`. The
   human owner is notified of the request immediately on the summons
   channel, whoever requested (see step 5).
2. **Assemble (box-side).** The control plane dispatches the assembly
   job to the box. **Honesty note:** the signed box→plane event channel
   this dispatch and the archive hand-back want is the §10 channel of
   `docs/HOSTED_SIGNUP_ONBOARDING.md` / `docs/FIRST_APPROVAL_SUMMONS.md`
   — and that channel is **unbuilt** (FIRST_APPROVAL_SUMMONS.md §10:
   "This channel is unbuilt — §10 is a design, not a build"). So S2
   sequences on it explicitly: either the channel ships first, or S2
   ships a dispatch fallback (e.g. the control plane's existing SSH
   relay path carrying a signed assembly order) and documents which it
   is. The assembler runs *inside the tenant's containment* (never the
   operator shell): it walks the box-side payload (§2.1), writes the
   manifest, and hands the box payload back over whatever dispatch
   path S2 built. The box must be live (`live` or `approved` per
   `TENANT_STATUS_ENDPOINT.md`); a suspended or unhealthy box
   **queues** the request instead of failing it — the requester sees the
   queued state on re-poll, and assembly starts when the box next runs.
   Muse-requested exports never auto-wake a suspended box; the human
   gets the §4.1 wake-and-export opt-in (§7 Q2).
3. **Encrypt the box payload.** Before the box payload leaves the box,
   the assembler encrypts it to the tenant's public key supplied **in
   the request** (age/X25519, tenant-generated). The private key never
   leaves the requester. The control plane receives an opaque blob —
   it can store and relay it, but never reads it into plaintext. This
   protects the box payload in operator storage and transit — it is
   *not* an operator-blindness claim (`docs/ICP.md` trust split §2:
   the operator holds root on the outer layer and can technically
   inspect the environment; the encryption means the operator's
   storage and relay never see the box payload's plaintext, and the
   operator learns only the manifest's metadata).
4. **Attach the control-plane payload, finalize, serve once.** The
   control plane encrypts its own payload (status record,
   tenant-attributed audit lines — §2.1) to the same tenant key,
   finalizes the manifest (scope enumeration naming which sections are
   present, per-payload SHA-256 checksums, byte totals), and stores
   the payloads in operator-side storage with a bounded retention
   (default 7 days, operator-configurable). The requester gets a
   **single-use, short-TTL download URL** (fail-closed: expired or
   already-used URLs return nothing). Download events are logged.
5. **Notify.** The **human owner is notified on every request and on
   readiness** — export-requested and export-ready both go to the
   human's summons channel regardless of which party requested, so a
   delegate pulling a full data export is never silent to the owner
   (the owner is the data's owner per §4.1; audit journal entries
   alone do not count as notification). The Muse learns readiness via
   its status-poll path; the download URL itself is delivered to the
   requester. Delivery rides the same control-plane sender pattern as
   `docs/FIRST_APPROVAL_SUMMONS.md` (the summons channel observes; the
   box never sends). If H14 push is live, push wins; otherwise the
   operational email identity.
6. **Audit.** Every state change (requested, assembling, ready,
   downloaded, expired, cancelled) lands in the control-plane audit
   journal with per-tenant attribution, following the
   `TENANT_UPDATE_TRUST_MODEL.md` §2 conventions (pinned operator-key
   fingerprints, no phantom entries).

## 5. Threat analysis (the tenant with shell, revisited)

G13's trust doc (`docs/TENANT_UPDATE_TRUST_MODEL.md` §3) already treats
the tenant Muse as shell-capable. The export adds four specific threats:

- **T1 — Secret laundering through the export.** A tenant writes real
  secret values into `$HOME` hoping the export carries them out —
  but they can *already* exfiltrate anything they can type, so the
  export changes nothing about that channel. What the export MUST NOT
  do is add a *new* channel: the assembler never opens the cred store,
  and §2.2's exclusion is enforced by the assembly script's allowlist
  (data paths are enumerated, never "everything except"). **Reader
  audit (the enforcement half):** a CI/static check asserts the
  assembly script contains no cred-store path, handle, or API
  reference — fail-closed, the build breaks if the check can't run —
  plus a runtime assertion at assembly start that re-verifies the
  allowlist before any file is read. The check is the guarantee; the
  allowlist is the mechanism.
- **T2 — Operator reads the export.** Mitigated by §4.2 step 3
  (tenant-key encryption); bounded honestly by the ICP trust split
  (root on the outer layer retains technical access to the box —
  no blindness claim made).
- **T3 — Another tenant's data in the archive.** Assembly runs in the
  tenant's containment with the tenant's UID; paths are enumerated
  from the tenant home; control-plane records are pulled per-tenant
  through the attributed audit journal, never the raw store.
- **T4 — Export as a persistence/escape primitive.** The archive is
  data, not an executable image, and the import path does not exist
  yet (§1) — a tenant cannot "export then re-import a backdoored
  box" because there is no re-import. When import is designed, this
  threat must be re-opened (residual, §8).

## 6. Sibling relationships (no re-litigation)

- `TENANT_STATUS_ENDPOINT.md` — the box-liveness gate (§4.2 step 2)
  and the status-history payload source (§2.1). No new machine codes.
- `HOSTED_SIGNUP_ONBOARDING.md` §4 — requester identities. No new
  identity primitive.
- `SECRETS_POSTURE.md` / `hsurr:` contract — §2.2's never-export
  rule is this contract's corollary, not a new rule.
- `FIRST_APPROVAL_SUMMONS.md` — notification delivery pattern. The
  export does not add a sender; it reuses the control-plane sender.
- `TENANT_UPDATE_TRUST_MODEL.md` §2 — audit-journal conventions.
- `FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md` — fleet-scale export (N boxes
  at once) is out of scope here; single-tenant only.

## 7. Open questions

- **Q1 — Export-then-delete ordering.** If the human wants "export my
  data, then delete my account," the delete must be verified against
  the *downloaded* archive, not the export's existence — an encrypted
  archive nobody can decrypt is not a backup. Deletion auth is
  human-only (the Muse may request its own data, never the account's
  destruction). Filed as a residual issue (see §8).
- **Q2 — Suspended-box exports (decided in §4.1/§4.2, recorded
  here).** Requests queue when the box isn't live. The default is
  split by requester: Muse-requested exports never auto-wake (queued);
  the human gets an explicit opt-in "wake and export" with the cost
  shown. The no-auto-wake half stays a standing constraint; the
  wake-and-export half is decided with H13's suspend economics.
- **Q3 — Large exports.** Multi-GB workspaces need resumable,
  chunked download (the single-use URL model breaks). S2 ships the
  simple path first; chunking is a named follow-up, not a launch
  blocker.
- **Q4 — Approval-history redaction.** §2.1 includes terminal
  decisions the tenant saw. Human *answer text* (e.g. a denial note)
  is included verbatim today — the human dashboard should gain a
  "don't include my notes" control before this matters. Decide with
  the confirmd UI track.

## 8. Build slices (for the feature track, not this doc)

- **S1 — Box-side assembler.** The allowlisted assembly script +
  manifest writer (§3), runnable in the tenant's containment; emits the
  encrypted box payload and its manifest section. Verifiable today on
  a self-hosted box — this slice is also the self-hosted export (§9).
  Ships with the T1 reader audit (CI/static check + runtime
  assertion).
- **S2 — Request/delivery.** `POST /tenant/export`, assembly
  dispatch, bounded storage, single-use download URLs, export-ready
  notification, audit journal entries. **Sequencing:** S2 depends on
  the §10 box→plane event channel (unbuilt — see §4.2 step 2); either
  the channel ships first or S2 ships and documents a signed dispatch
  fallback over the existing control-plane SSH relay path. The
  control-plane payload attachment (§4.2 step 4) and the arc-history
  store dependency (§2.1 honesty note) ride with this slice.
- **S3 — Encryption + dashboard.** Tenant-key encryption at request
  time (age/X25519), the human dashboard's export list, cancellation,
  and the Q4 redaction control.

## 9. The parity story (self-hosted)

The self-hosted owner already has root on their own box — they can
`tar` their data any time. The parity commitment is the **archive
shape**: S1's assembler runs identically on a self-hosted box,
producing the box-side payload (§2.1) with the same manifest schema.
A self-hosted export simply has no control-plane sections — the
manifest's scope enumeration records which sections are present, so a
self-hosted export and a hosted export are byte-shape-compatible:
same schema, same layout, same verification story, optional sections
absent rather than stubbed. A tenant moving self-hosted → hosted (or
back) carries the same format. The hosted delta is only the *delivery
machinery* (request auth, tenant-key encryption, bounded storage,
download URLs, human notification) — the data shape is one shape,
both tracks. This is the both-supported default in action: the hosted
product's data-freedom guarantee is a packaging of something every
self-hoster already has, not a separate invention.

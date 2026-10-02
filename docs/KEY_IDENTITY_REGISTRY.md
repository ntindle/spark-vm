# Key identity registry — storage and lookup (GH #446, slice S2)

This note is the **storage-and-lookup half** of the #446 acceptance item
"Design note choosing the identity binding (fingerprint format, storage,
lookup)". The fingerprint format half shipped with slice S1
(`harness/key_identity.py`); this note records the S2 choice for the
registry that remembers first-connect keys on a box.

## What it is

`harness/key_registry.py`: a per-host registry mapping an SSH key's OpenSSH
`SHA256:` fingerprint to an account record — derived account id, key type,
`created_at`, `last_seen_at`, and `box_ref` (the box the account resumes
to). It is the storage foundation for "same key -> same box": the registry
remembers which keys have been seen and which box they bind to; the
connect-time wiring that registers on first connect and resumes on reconnect
is a later slice (#446).

## Storage choice: one JSON file, lockdir exclusion, atomic writes

- **One JSON file** (`registry.json` in the registry root) keyed by
  fingerprint string. Chose flat JSON over sqlite deliberately: no schema
  migrations at this scale, human-inspectable on the box, and the whole
  store is stdlib `json` — the module keeps S1's stdlib-only discipline so
  it runs unchanged on the self-hosted box, the hosted control plane, and
  the operator laptop.
- **Mutual exclusion is a lockdir** (`registry.lock.d/`, created with
  `os.mkdir`, which is atomic on POSIX). The lockdir also serializes
  threads inside one process, which fcntl locks do not; it works the same
  on the box and the operator laptop.
- **Writes are atomic**: temp file opened `O_EXCL`, then `os.replace`. A
  crashed writer can never leave a half-written store behind.
- **Stale locks are reclaimed**: the lockdir holds the holder's pid; if the
  pid is dead the lock is removed and recreated. (Pid-recycling can only
  make a waiter wait longer — a liveness miss, never corruption.)
- **Corrupt `registry.json` fails closed** (`RegistryError`), never silently
  reset or rebuilt. Identity misbinding is worse than downtime: the registry
  refuses to proceed, and the operator restores from backup (recovery runbook
  below).

Default root: `$XDG_STATE_HOME/spark-vm/key-registry`, falling back to
`~/.local/state/spark-vm/key-registry`. Override with `--registry-root`
(the test suites use tmp dirs; the store never touches the real root in
tests). The root dir is `0700`, the store `0600`.

## Lookup choice: exact fingerprint string, idempotent register

- The lookup key is the fingerprint string exactly as S1 produces it —
  `SHA256:` + 43 chars of unpadded base64. No normalization, no case
  folding: a malformed fingerprint (including the *padded* form S1 never
  emits — padded and unpadded twins derive different account ids) raises
  `KeyIdentityError` loudly rather than silently becoming a different
  record key.
- `register` is **idempotent**: a known fingerprint refreshes `last_seen_at`
  and returns the existing record. Registering with an explicit `--box-ref`
  rebinds the box; registering without one leaves the stored binding alone
  (absence of evidence is not evidence of unbinding). Routine reconnects
  should call `register` (or `touch`) *without* `--box-ref` so they never
  disturb the binding. An empty `--box-ref ""` is rejected — an empty
  string is provided-but-meaningless and must not silently clear a binding.
- `touch`, `bind_box`, and `remove` return `False` on unknown fingerprints
  instead of creating records — writes are explicit.
- `manifest <fingerprint>` emits the **registry-issued resume manifest**:
  the same field vocabulary as S1's first-connect manifest, with the
  `box_id` slot filled from the registry's box binding — the slot S1's
  README said this slice would fill. `vm_endpoint` stays null: the
  endpoint is connect-time knowledge (a later wiring slice); `claim_url`
  stays null until the connect-time wiring fills it — the claim protocol
  itself is slice S3 (#446) and is shipped (see "Claim protocol" below).
  `remove` is a deliberate
  deprovisioning operation (account teardown / key retirement), not an
  undo button — since #825 it appends to the bounded `deletions` journal
  (lineage context + `deleted_at`, capped at 1000, oldest-first
  eviction), so a deleted account stays distinguishable from a
  never-registered one; deleting a
  record means the same key re-registers as a new account on next connect.

## What is NOT stored

- **No secrets.** Records hold public fingerprints, one-way derived account
  ids (the derivation is irreversible: the fingerprint and key cannot be
  recovered from the id), and operator-visible metadata. Restrictive file
  modes are defense in depth, not the security model.
- **No key material.** The public key blob is never persisted — only its
  fingerprint. Re-registering the same key line derives the same record.

## Rotation and claim

**Rotation (slice S2.5, shipped).** `KeyRegistry.rotate(old_fp, key_line=new_line)`
is the operator-driven rotation path for a key the operator still holds
("I generated a new key and want this box to know it's me"). Per #446's
policy (and S1's): **a new key is a new account** — rotate registers the
new key as a NEW account id and *links* the accounts rather than
preserving the id. Atomically, under one lock and one store write:

- the old record is stamped `rotated_to` / `rotated_at` (rotation itself
  does not advance the record's `last_seen_at` — the rotation is recorded
  in `rotated_at`; liveness via `touch` or re-`register` still updates
  `last_seen_at` afterwards — rotation is lineage, not a ban);
  the old record is never deleted by rotate (deprovisioning stays a
  deliberate `remove`);
- the new key registers as a new account with the box binding inherited,
  so "same key -> same box" continuity survives the rotation;
- a lineage entry (`old/new fingerprint + account id, key type, box,
  timestamp`) appends to the `rotations` journal — scoped to rotation
  (deletions have their own bounded journal since #825, `deletions()`).
  The journal is bounded at
  1000 entries (oldest-first eviction); the per-record `rotated_to`
  pointer is never evicted, so lineage survives journal roll.

Preconditions fail loudly: unknown old fingerprint (rotation never
implicitly registers — a typo must not mint an account), already-registered
new key (rotation never merges two existing accounts — the silent-misbind
edge), already-rotated old key (rotate the *latest* key — the record
pointer and the journal must never diverge on who the current key is),
same-key (old == new), malformed input. The new key's public-key *line* is
required so rotate verifies the key parses, not just the
fingerprint's shape. Re-registering the old key afterwards is legal and
refreshes `last_seen_at` — rotation is lineage, not a ban.

Trust boundary: `rotate` performs NO cryptographic proof that the caller
holds the old key — attestation is assumed from the caller (the local
operator rotating their own key). A network caller must prove possession
before calling; the claim protocol (S3, #446) owns that decision, not
this slice.

**Lost-key rotation is NOT this slice.** If the operator no longer holds
the old key, there is nothing to attest with — that path needs the claim
protocol (slice S3, #446), which this module still records no state for.

**Claim protocol (slice S3, shipped).** `KeyRegistry.issue_claim` /
`KeyRegistry.redeem_claim` (+ CLI `claim-issue` / `claim-redeem`) are the
key-loss escape hatch #446 promised: an operator who no longer holds the
old key upgrades a key-only account to a claimed account by redeeming a
single-use claim code shown once at issue time.

- One live code per account; issuing a new code revokes the old one.
- Only SHA-256 hashes are ever stored (`"sha256:<hex>"` on the record's
  `claim` entry) — the plaintext code is returned once by `issue_claim`
  and cannot be recovered afterwards, so a stolen `registry.json` yields
  no live claim codes. The module's "no secrets" posture holds: the
  store holds hashes, never plaintext codes.
- Codes carry an expiry (default 7 days, `--ttl-hours` to set; must be
  positive) checked against the registry's own clock; expired codes are
  refused AND removed (self-cleaning). Redemption is single-use and
  atomic under the lock: the first redeem consumes the code and stamps
  `claimed_at` / `claimed_by` (operator label/email, optional); a racing
  second redeem fails.
- Like rotate, issue never implicitly registers — the fingerprint must
  already be known, and a rotated-out (`rotated_to`-stamped) record is
  refused: claiming superseded lineage would stamp a dead record, so
  claim the latest key. Redeeming an unknown code fails loudly; hash
  comparison is constant-time.
- Re-claiming an already-claimed account is allowed (restamps
  `claimed_at` / `claimed_by` — a label change is a feature, not an
  error). `claim` on a record describes the one currently-live code;
  `claimed_*` describe the most recent redemption.

**The operator's decision rule — claim vs rotate.** Both are box-local
CLI ops that trust the local caller, but they answer different
questions. `rotate` (S2.5) is for "I still control this box and I have
a new key": the new key registers as a NEW account, the old record
keeps a forward link, the box binding carries over — identity stays the
key, lineage is preserved. `claim` is for "I cannot prove key
possession": the operator lost the old key, or wants to bind the
account to a party (a human owner, an agent) who never held a key at
all. The operator — whoever holds local access to the registry, the
trust root of this protocol — mints a code and hands it to the
claimant OUT OF BAND (paste it into the agent's config, hand it to the
human, read it over the phone: the protocol is deliberately
channel-agnostic because the right channel differs between a
self-hosted box and the hosted control plane). The claimant redeems
it, and the SAME account is upgraded in place — same `acct_` id,
stamped `claimed_at` / `claimed_by` — instead of a new account with a
lineage link. Rotate is not delegable; a claim code is.

**What redemption buys at this slice.** Honestly: the stamps. No policy
reads `claimed_at` yet, `claim_url` is still null, and a new key is
still a new account (identity-is-the-key stands). What the slice
delivers is the record-level upgrade the wiring slices build on: a
lost-key account can be re-associated with its human without the old
key, and an operator can distinguish "key-only" from
"operator-vouched" accounts in `status` / `lookup` output. The escape
hatch is real; the consumers are later.

**"Claimed" is not "full account".** #446's target is a full account —
email, billing, recovery. "Claimed" is the trust state this slice
records: the operator vouched for the binding between this account and
this claimant. The full-account record (validated contact, billing,
recovery) is a later slice built on top of it; `claimed_by` is a
free-text label that MAY hold an email but is not validated as one, and
carries no billing semantics.

**`claim_url`, defined at last.** The resume/first-connect manifest's
`claim_url` will be the URL where the claimant redeems their code
without registry-local CLI access — an on-box or control-plane endpoint
that accepts the code and performs the same single-use, expiry-checked
redemption `claim-redeem` does. Filling it belongs to #446's
"connect-time wiring of the registry" slice (still open, tracked under
#446's later slices) — the third deferral now has a named owner, not a
bare "later slices".

Sequencing: this slice is the protocol. Filling the resume manifest's
`claim_url` slot and wiring claim issuance into the connect-time path
remain later slices; the manifest's vocabulary is unchanged.

## Operations

- CLI: `python3 harness/key_registry.py register --key-line
  'ssh-ed25519 AAAA...' [--box-ref <id>] [--registry-root <dir>]`
  (also `lookup`, `touch`, `bind`, `remove`, `rotate`, `claim-issue`,
  `claim-redeem`, `manifest`, `status`); data commands emit JSON. `--registry-root` may appear before or after
  the subcommand; if given in both positions, the after-subcommand value
  wins.
- `manifest` is how the onboarding path answers "what does this key
  resume?": it fills the `box_id` slot S1's README promised the registry
  slice would fill. `vm_endpoint`/`claim_url` stay null until the
  connect-time wiring (later slice) fills them — the claim protocol
  itself (S3) is shipped, see above.
- `claim-issue <fingerprint> [--ttl-hours N]` prints the single-use
  claim code ONCE (the store keeps only its hash — it cannot be recovered
  afterwards); `claim-redeem <code> [--claimed-by <label>]` consumes the
  code and stamps the account `claimed_at` / `claimed_by`. The code is a
  bearer credential: a positional code is visible in the process list
  (`ps`, `/proc/<pid>/cmdline`) and lands in shell history — on a
  multi-user host pass it via `claim-redeem --code-stdin` instead
  (Security review, round 1). Treat a printed code like a password: don't
  paste it into chat or tickets.
- **Rotate:** `key_registry.py rotate <old-fingerprint> --key-line
  '<new key line>'` — operator-held-key rotation (see Rotation above).
  Emits the old record, the new record, and the journal entry as JSON.
- **Recovery runbook (corrupt registry):** the registry fails closed, so a
  corrupt store blocks onboarding. Diagnose: `key_registry.py status`
  prints `error: registry is corrupt`. Fix: restore `registry.json` from
  backup, or delete it to start empty (all key-identity accounts then
  re-register on next connect as *new* accounts — same-key resume is lost,
  which is why restore-from-backup is the recommended path). Never hand-edit
  a live store: write through the CLI or the module so the lock and the
  atomic rename stay in the loop.

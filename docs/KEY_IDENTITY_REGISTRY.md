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
  README said this slice would fill. `vm_endpoint` and `claim_url` stay
  null: the endpoint is connect-time knowledge (a later wiring slice) and
  the claim protocol is slice S3 (#446). `remove` is a deliberate
  deprovisioning operation (account teardown / key retirement), not an
  undo button — it has no audit trail by design at this slice; deleting a
  record means the same key re-registers as a new account on next connect.

## What is NOT stored

- **No secrets.** Records hold public fingerprints, one-way derived account
  ids (the derivation is irreversible: the fingerprint and key cannot be
  recovered from the id), and operator-visible metadata. Restrictive file
  modes are defense in depth, not the security model.
- **No key material.** The public key blob is never persisted — only its
  fingerprint. Re-registering the same key line derives the same record.

## Rotation and claim (later slices)

Per #446's policy (and S1's): **a new key is a new account** — rotation
attestations, key linking, and the claim/upgrade escape hatch are later
slices. S2 records no claim state at all, so it cannot preempt S3's
claim-protocol decisions; the claim API will be designed as part of that
slice. The sybil question (multiple keys = multiple identities) stays
accepted-for-self-hosted, hosted-policy-TBD, per #446.

## Operations

- CLI: `python3 harness/key_registry.py register --key-line
  'ssh-ed25519 AAAA...' [--box-ref <id>] [--registry-root <dir>]`
  (also `lookup`, `touch`, `bind`, `remove`, `manifest`, `status`);
  data commands emit JSON. `--registry-root` may appear before or after
  the subcommand; if given in both positions, the after-subcommand value
  wins.
- `manifest` is how the onboarding path answers "what does this key
  resume?": it fills the `box_id` slot S1's README promised the registry
  slice would fill. `vm_endpoint`/`claim_url` stay null until the
  connect-time wiring (later slice) and the claim protocol (S3) land.
- **Recovery runbook (corrupt registry):** the registry fails closed, so a
  corrupt store blocks onboarding. Diagnose: `key_registry.py status`
  prints `error: registry is corrupt`. Fix: restore `registry.json` from
  backup, or delete it to start empty (all key-identity accounts then
  re-register on next connect as *new* accounts — same-key resume is lost,
  which is why restore-from-backup is the recommended path). Never hand-edit
  a live store: write through the CLI or the module so the lock and the
  atomic rename stay in the loop.

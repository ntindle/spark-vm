# Key identity registry — storage and lookup (GH #446, slice S2)

This note is the **storage-and-lookup half** of the #446 acceptance item
"Design note choosing the identity binding (fingerprint format, storage,
lookup)". The fingerprint format half shipped with slice S1
(`harness/key_identity.py`); this note records the S2 choice for the
registry that remembers first-connect keys on a box.

## What it is

`harness/key_registry.py`: a per-host registry mapping an SSH key's OpenSSH
`SHA256:` fingerprint to an account record — derived account id, key type,
`created_at`, `last_seen_at`, `box_ref` (the box the account resumes to),
and claim state. It is how "same key -> same box" is implemented: the first
SSH connect registers the key; every later connect looks the fingerprint up
and resumes the bound account.

## Storage choice: one JSON file, lockdir exclusion, atomic writes

- **One JSON file** (`registry.json` in the registry root) keyed by
  fingerprint string. Chose flat JSON over sqlite deliberately: no schema
  migrations at this scale, human-inspectable on the box, and the whole
  store is stdlib `json` — the module keeps S1's stdlib-only discipline so
  it runs unchanged on the self-hosted box, the hosted control plane, and
  the operator laptop.
- **Mutual exclusion is a lockdir** (`registry.lock.d/`, created with
  `os.mkdir`, which is atomic on POSIX). fcntl locks are not portable —
  the operator laptop may be macOS while the box is Linux — and the lockdir
  also serializes threads inside one process, which fcntl does not.
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
  `SHA256:` + unpadded base64. No normalization, no case folding: a
  malformed fingerprint raises `KeyIdentityError` loudly rather than
  silently becoming a different record key.
- `register` is **idempotent**: a known fingerprint refreshes `last_seen_at`
  and returns the existing record. Registering with an explicit `--box-ref`
  rebinds the box; registering without one leaves the stored binding alone
  (absence of evidence is not evidence of unbinding).
- `touch`, `mark_claimed`, `bind_box`, and `remove` return `False` on
  unknown fingerprints instead of creating records — writes are explicit.

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
slices. `mark_claimed` records the operator's claim decision for audit
purposes; it does not implement the claim protocol. The sybil question
(multiple keys = multiple identities) stays accepted-for-self-hosted,
hosted-policy-TBD, per #446.

## Operations

- CLI: `python3 harness/key_registry.py --registry-root <dir> register
  --key-line 'ssh-ed25519 AAAA...' [--box-ref <id>]` (also `lookup`,
  `touch`, `claim`, `bind`, `remove`, `status`); data commands emit JSON.
- The registry is what the onboarding path consults on connect; the box's
  SSH entrypoint should `register` before handing the agent its manifest.
- **Recovery runbook (corrupt registry):** the registry fails closed, so a
  corrupt store blocks onboarding. Diagnose: `key_registry.py status`
  prints `error: registry is corrupt`. Fix: restore `registry.json` from
  backup, or delete it to start empty (all key-identity accounts then
  re-register on next connect as *new* accounts — same-key resume is lost,
  which is why restore-from-backup is the recommended path). Never hand-edit
  a live store: write through the CLI or the module so the lock and the
  atomic rename stay in the loop.

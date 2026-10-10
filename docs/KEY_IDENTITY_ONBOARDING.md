# Key-identity onboarding — the first-run experience (GH #446)

This is the onboarding-surface doc for the last open #446 acceptance item
("Documented alongside the accounts plan"). The mechanism slices are all
shipped:

- **S1** — identity primitives + manifest vocabulary
  (`harness/key_identity.py`): fingerprint a public key, derive the account
  id, emit the first-connect manifest.
- **S2** — the registry (`harness/key_registry.py`): per-host store mapping
  an SSH key's OpenSSH `SHA256:` fingerprint to an account record
  (fingerprint, account id, key type, `created_at`, `last_seen_at`,
  `box_ref`). Design note: `docs/KEY_IDENTITY_REGISTRY.md`.
- **S2.5** — rotation: a new key registers a *new* account; lineage is
  recorded, not linking (`rotate`).
- **S3** — the claim protocol (`issue_claim` / `redeem_claim`): single-use
  claim codes, the key-loss upgrade path.

This doc pins the **first-run experience** the connect-time wiring slice
must deliver: the agent's first-connect walkthrough, the manifest UX, the
"same key -> same box" resume semantics, the human one-command path, the
rotate-vs-claim decision rule, the wiring slice's acceptance spec, and
where key-identity sits in the accounts plan.

## 1. The agent first-connect walkthrough

The agent-native onboarding story is "no signup form, no password, no API
key" — the SSH key *is* the account, the way `ssh railway.new` works:

1. **The agent generates its own keypair** (e.g. `ssh-keygen -t ed25519`)
   and keeps the private key. The public key is the identity; nothing
   secret is ever transmitted.
2. **First SSH connect with that public key** implicitly creates the
   account bound to the key's OpenSSH `SHA256:` fingerprint. There is no
   form to fill and no token to paste — first connect *is* registration.
3. **The wiring slice hands back the first-connect manifest** (JSON):
   the account id, the key fingerprint, the claim-link escape hatch, and
   the policy the agent must report back to its operator (§2).
4. **The agent reports `account_id` and `claim_url` to its operator** and
   persists them — the `claim_url` bookmark rule in §3 is the one part of
   this flow that cannot be skipped safely.
5. **Reconnects with the same key resume the same account** (§4) — the
   agent gets a resume manifest, not a fresh registration.

## 2. The manifest, verbatim

The first-connect manifest is built by `first_connect_manifest` in
`harness/key_identity.py`. The field vocabulary, quoted verbatim from the
code:

- `manifest_version` (currently `1`), `account_id` (one-way derived from
  the fingerprint), `key_fingerprint`, `key_type`, `issued_at` (UTC
  ISO-8601), `expires_at` (UTC ISO-8601 or `null` — key-identity accounts
  do not expire; claim-link validity is set by the claim/upgrade slice,
  not here), `vm_endpoint`, `box_id`, `claim_url`.
- `policy`, with three quoted values:
  - `rotation`: "lineage-recorded: a new key is a new account; the old
    record keeps rotated_to/rotated_at and the lineage is journaled
    (registry rotate)"
  - `claim`: "single-use claim codes (registry issue_claim /
    redeem_claim): key-loss upgrade path, 7-day default TTL"
  - `sybil`: "accepted for self-hosted: each key is its own identity;
    hosted policy TBD"

On reconnect the registry issues the **resume manifest** — the same field
vocabulary, distinguished by `"registry_issued": True` (verified against
`harness/key_registry.py`'s `_resume_manifest`): the `box_id` slot is
filled from the registry's box binding (the slot S1's README promised
this slice would fill); `vm_endpoint` and `claim_url` stay null — the
endpoint is connect-time knowledge for a later wiring slice, and the
claim protocol is S3. An agent can tell a resume from a fresh
registration by the presence of `registry_issued`.

## 3. Manifest UX: the claim_url bookmark rule

The manifest's `claim_url` is the agent's **only lifeline to a full
account** — and the claim codes behind it are deliberately
unrecoverable: the registry stores only the SHA-256 hash, and the
plaintext is shown once at issue time (`issue_claim`: "the plaintext is
returned once in the result and must be shown to the operator then,
because it cannot be recovered later"). An operator who no longer holds
the old key upgrades a key-only account to a claimed account by
redeeming the code — and that only works if the claim path survived the
session.

**The rule: the agent must persist the `claim_url` somewhere durable
outside the session — bookmark it.** A key-only account whose claim link
is lost *and* whose key is lost has no recovery path: there is no email,
no password reset, nothing to fall back on. Losing the bookmark turns a
routine key-loss into a dead account.

Until the wiring slice fills it, `claim_url` may be `null` (the resume
manifest carries it null by construction). The agent must distinguish
"no claim path yet — the slice hasn't wired it" from "claim path exists
— I have it bookmarked", and never treat a null `claim_url` as
"no upgrade path exists".

## 4. "Same key -> same box": resume semantics

The registry's core promise (`register`'s own docstring): registering an
already-known fingerprint refreshes `last_seen_at` and returns the *same*
account record — registration is idempotent, reconnects never fork a
second account.

- **Explicit rebind wins.** Passing `box_ref` on register (or the `bind`
  command) rebinds the box — the operator's explicit statement overrides
  the stored binding.
- **`box_ref=None` leaves the stored binding untouched.** Absence of
  evidence is not evidence of unbinding: a reconnect that says nothing
  about the box must not clear the binding.
- **An empty `box_ref` is refused loudly** — it would silently clear a
  binding while nothing downstream distinguishes "unbound" from "bound
  to empty".
- The resume manifest (§2) is how the agent learns it resumed: same
  `account_id`, `registry_issued: True`, and the `box_id` it last bound.

## 5. The human one-command path

The self-hosted story is one command -> working box, matching the
`ssh railway.new` bar #446 set out to meet:

```
ssh <box>          # first connect: key registers, manifest is printed
```

Everything after that is the registry CLI (`key_registry.py`, JSON-first
— the registry is an agent-operations tool, and JSON is the contract):

- `register` — register a key (or re-register to rebind the box);
- `lookup` / `status` — inspect; `touch` — mark seen;
- `manifest` — emit the resume manifest for a fingerprint;
- `rotate` — rotate to a new key (§6);
- `claim-issue` / `claim-redeem` — the S3 claim flow (§6).
  `claim-redeem` takes the code positionally or via `--code-stdin` —
  the code is a Bearer <redacted>: argv exposes it in the process list and
  shell history, so stdin is the safe path on multi-user hosts.

The human sees the same manifest the agent does — the operator is the
agent's persistence layer for the bookmark rule in §3.

## 6. Rotate vs claim: the decision rule

One key = one identity, so key changes come in exactly two flavors. Pick
by whether the agent still holds the old key:

- **Key still held (suspected compromise, hygiene rotation) → rotate.**
  `rotate` registers the new key as a *new* account; the old record keeps
  `rotated_to`/`rotated_at` and the lineage lands in the registry's
  rotations journal. Rotation never merges two existing accounts —
  identity is still the key.
- **Key lost (no longer held) → claim.** `claim-issue` mints a
  single-use code (7-day default TTL, shown once, SHA-256 hash only in
  the store); `claim-redeem` stamps the account `claimed_at` /
  `claimed_by`. A claimed account is still the key's account — **claim
  is the upgrade path, not a re-registration**.
- **Never implicitly.** Issuing a claim code requires a *registered*
  fingerprint — a typo must not mint an account. Registration happens on
  first connect, never as a side effect of claim or rotate.

## 7. The wiring slice acceptance spec

The connect-time wiring — registering on first connect, resuming on
reconnect, handing the manifests to the agent — is the unbuilt slice.
This doc is its acceptance spec. A wiring implementation is done when:

1. **First connect with an unknown key** registers it and emits the
   first-connect manifest (§2) — no form, no token, first connect is
   registration.
2. **Reconnect with a known key** refreshes `last_seen_at` and emits the
   registry-issued resume manifest (`registry_issued: True`, `box_id`
   filled from the binding) — reconnects never fork accounts.
3. **Explicit `box_ref` rebinds; absent `box_ref` preserves** the stored
   binding (§4); empty `box_ref` is refused.
4. **The manifest reaches the agent before any work starts**, and the
   agent's report-back includes the `claim_url` bookmark per §3.
5. **`expires_at` stays null** — key-identity accounts do not expire;
   claim-link validity is the claim/upgrade slice's business.
6. **Sybil posture is stated honestly**: multiple keys = multiple
   identities is accepted on self-hosted; the hosted sybil policy is
   still TBD (#446 open question) and must not be presented as settled.

## 8. Accounts-plan placement

"The accounts plan" is the multi-tenant plane model decision
(`docs/MULTI_TENANT_PLANE_MODEL_DECISION.md`, D-MT1: **one plane per
tenant** — each signup provisions its own `sparkvm-control` instance;
the shipped single-owner auth model is kept verbatim on every
instance). Key-identity's place in it:

- **Self-hosted and agent-created accounts:** key-identity is the
  onboarding story — one command, no signup form, no API-key issuance.
- **Hosted product:** key-identity is the *tenant-Muse side* of the
  per-tenant plane — the key-identified agent the per-tenant plane's
  owner keys bind to (the #1158 tenant-Muse identity binding). It
  complements the human-mediated enrollment-token flow
  (`docs/HOSTED_SIGNUP_ONBOARDING.md` §4): the signup form onboards the
  *human*, key-identity onboards the *agent* — different actors, same
  key-pair primitive (the tenant Muse's key is approved in the signup UI
  by fingerprint, exactly the fingerprint vocabulary this doc's manifest
  pins).
- **Credential-proxy complement:** the key identifies *who*; the swap
  proxy still brokers *what they may touch* (the #446 proposal's
  standing line).
- **Launch posture:** nothing here is launch-directed and there is no
  pricing-as-commitment copy — self-hosted/contributor surface, P3 gate
  unaffected (the #446 acceptance item's own words).

What stays open: the connect-time wiring slice itself (accepted above),
and the full-account record beyond claimed status. #446 stays open
until both land.

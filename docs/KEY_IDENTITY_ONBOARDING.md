# Key-identity onboarding — the first-run experience (GH #446)

**Status: design doc, not a commitment.** This is the onboarding-surface half
of #446 — what an agent (or a human) *experiences* when the SSH key is the
account. The mechanism halves are shipped: the identity primitives and
first-connect manifest vocabulary (`harness/key_identity.py`, slice S1), the
per-host fingerprint→account registry (`harness/key_registry.py` + slice S2),
operator-held rotation (S2.5), and the claim/upgrade protocol (S3). See
`docs/KEY_IDENTITY_REGISTRY.md` for storage, lookup, rotation, and claim
mechanics. The connect-time wiring that registers on first connect and
resumes on reconnect is a later #446 slice; this doc describes the
experience that wiring must deliver, so the wiring has a spec to satisfy.

**Non-overlap map (what this doc is not):**
- The hosted signup funnel stages are `docs/FIRST_RUN_ACTIVATION.md`
  (activation framework) and `docs/HOSTED_SIGNUP_ONBOARDING.md`
  (discover → signup → identity → provisioned box). Key-identity onboarding
  is the *agent-created-accounts* path inside the identity-linking stage of
  that funnel — no signup form, no password, no API key. It also stands
  alone on the self-hosted path, where it is the whole onboarding story.
- The claim protocol mechanics (code issuance, hashing, TTL, redemption)
  are in `docs/KEY_IDENTITY_REGISTRY.md` ("Claim protocol"); this doc
  covers only the human-facing UX of claiming.
- Pricing, trial terms, and launch copy are out of scope
  (`docs/PRICING_THINKING.md`; P3 marketing gate holds — this doc ships
  contributor-facing onboarding design only).

## 1. The promise

`ssh` with a key, get an account. First connect with a public key implicitly
creates the account bound to that key's fingerprint; reconnecting with the
same key resumes it. This is the onboarding bar #446 set from Railway's
`ssh railway.new` flow: agent-native by construction, because anything that
speaks SSH can provision itself — no separate API-key issuance flow for the
agent path, no signup form for the human path.

Two audiences, one mechanism:

- **The agent** (the primary audience): a coding agent whose operator told
  it "go get a spark-vm box." It has a keypair, an SSH client, and a way to
  report back. It does not have a browser, a human, or patience for forms.
- **The human operator** (self-hosted): the person who ran the one command
  and now owns a box. They hold the key, so rotation and recovery are their
  problems to solve with the tools in §5.

## 2. First connect — the agent walkthrough

What the agent does, in order. Every step is designed to need no human.

1. **Present the key.** The agent connects to the onboarding endpoint
   with its public key (the same key it will use for all future
   sessions). Endpoint discovery — how the agent learns *where* to
   connect in the first place — is the connect-time wiring slice's job
   (§6); this walkthrough starts at the moment the agent has an address
   and a key. There is nothing to fill in — the key *is* the credential
   and the identity.
2. **Receive the manifest.** On first connect the onboarding path hands the
   agent a JSON manifest — the same vocabulary `harness/key_identity.py`
   emits (`first_connect_manifest`), with the registry-filled slots from
   `harness/key_registry.py` (`manifest <fingerprint>`):
   - `manifest_version`, `account_id` (`acct_` + 16 hex, derived one-way
     from the fingerprint — the agent cannot recover the key from it),
   - `key_fingerprint` (`SHA256:` + 43 unpadded base64 chars),
     `key_type`, `issued_at`,
   - `box_id` — which box this key resumes to (filled by the registry;
     the slot S1 left for S2),
   - `vm_endpoint` — the box's canonical answer for where future
     sessions should connect (connect-time knowledge; null until the
     wiring slice fills it). The agent already knows what it dialed to
     get here; `vm_endpoint` is authoritative over that — what the box
     wants used going forward, which may differ from the dialed address
     (e.g. a relay or a stable hostname).
   - `claim_url` — where a key-loss claim is redeemed (null until the
     connect-time wiring slice fills it; the claim *protocol* is shipped,
     the URL that serves it is not — see KEY_IDENTITY_REGISTRY.md),
   - `expires_at` — null; key-identity accounts do not expire,
   - `policy` — the three rules the agent must internalize, quoted from
     the shipped vocabulary: rotation is lineage-recorded (a new key is a
     new account; the old record keeps `rotated_to`/`rotated_at`), claim
     is the key-loss upgrade path (single-use codes, 7-day default TTL),
     sybil is accepted for self-hosted (each key is its own identity;
     hosted policy TBD).
3. **Report back.** The agent's job on first connect is to persist the
   manifest — written next to its keypair, or wherever it keeps durable
   operator-facing state — and report it to its operator: account id,
   box id, the claim URL (when non-null), and the policy block. The
   operator needs the claim URL *before* key loss happens — a claim
   code is issued on demand, but the URL is the address the operator
   bookmarks. The manifest is re-fetchable from the box later
   (`manifest <fingerprint>`), so the bookmark rule survives an agent
   that loses its copy; but an agent that never reports the manifest at
   all has failed onboarding even if the account exists.
4. **Verify resume.** The agent reconnects once more in the same session.
   Same key must land on the same account and the same box, and the
   registry-issued resume manifest must show the same `account_id` with
   `box_id` filled. If it doesn't, onboarding is broken — this is the
   acceptance probe for the connect-time wiring slice.

Failure posture, stated plainly, per audience. A malformed key fails
loudly at step 1 (the S1 parser raises rather than guessing): the
connect is refused, no account row is registered, and the agent sees the
refusal naming the key — its correct next move is to report the verbatim
error to its operator, generate a fresh keypair, and retry (a new key is
a new account, per the §3 policy — retrying with a fresh key is
onboarding, not a workaround). A registry that cannot be read fails
closed: the connect is refused, no new account row appears, and the
registry file is left unmodified — the operator then restores from
backup (KEY_IDENTITY_REGISTRY.md recovery runbook), because a misbound
identity is worse than a refused connect. The agent's standing
instruction for any refused connect: report the refusal and the verbatim
error to its operator; never retry blindly more than once.

## 3. Reconnect — "same key, same box"

The resume semantic the whole design rests on:

- Reconnecting with a known key returns the existing account. No
  re-registration, no human involvement. `last_seen_at` advances;
  nothing else moves. The manifest is re-fetchable on demand from the
  box (`key_registry.py manifest <fingerprint>` — the registry-issued
  resume manifest, which carries `registry_issued: True` to distinguish
  it from the stateless first-connect manifest); reconnects never mint a
  new account, but they also never assume the agent still holds the
  first one.
- **A new key is a new account.** This is the sharp edge and it is
  deliberate: identity is the key, so key change is identity change.
  Rotation-as-new-identity is the documented #446 policy; the registry
  records lineage (the old record's `rotated_to` pointer, the bounded
  `rotations` journal) so the operator can follow the trail, but the new
  key never inherits the old account id.
- Removing a key's record (`remove`) is deprovisioning, not undo: the
  same key re-registers as a *new* account on next connect. The
  `deletions` journal keeps a deleted account distinguishable from a
  never-registered one.

What this means for the operator's key hygiene: the key is the account,
so the key's backup story *is* the account's backup story. Lose the key
with no backup and the only path back is the claim protocol (§5) — which
is why the agent must surface `claim_url` to the operator at first
connect, before anything is lost.

## 4. The human path — one command to a working box

On the self-hosted path the human experience is: generate a key (if they
don't have one), register it once (`key_registry.py register --key-line
'<key line>'`), `ssh` in. That is the whole signup form. The box's
onboarding surface — whatever presents the connect-time wiring — should
behave like a good host on that first session:

- Say what happened: "new key seen — account `acct_…` created" vs
  "known key — resuming account `acct_…`, box `<id>`." The human should
  never wonder whether they just made a second account by accident.
- Hand over the same manifest the agent gets (it is JSON; print it or
  point at it). The human needs the `claim_url` bookmarked and the
  rotation rule understood *now*, not after key loss. Until §6.4 is
  satisfied the surface must not present a null `claim_url` as a link —
  say "claim URL not provisioned yet" instead of rendering nothing.
- Point at the recovery story once: "if you lose this key, the claim
  path is `<claim_url>`; if you still have it, rotate with the registry
  CLI." One sentence each; links, not lectures.

## 5. Rotation and claim — the operator's decision rule

Both are box-local operations that trust whoever holds local access to
the registry, but they answer different questions. Stated as the rule the
operator memorizes:

- **"I have a new key and I still hold the old one" → rotate.**
  `key_registry.py rotate <old-fingerprint> --key-line '<new key>'`.
  The new key registers as a NEW account, the old record keeps a forward
  link, the box binding carries over — "same key → same box" continuity
  survives. Rotation is lineage, not a ban: re-registering the old key
  afterwards is legal. Rotation performs no cryptographic proof the
  caller holds the old key — attestation is assumed from the local
  caller.
- **"I can't prove I hold the old key" → claim.** The operator issues a
  single-use claim code (`claim-issue`), hands it to the claimant out of
  band, and the claimant redeems it (`claim-redeem` / the future
  `claim_url` endpoint). The SAME account is upgraded in place —
  `claimed_at` / `claimed_by` stamped — instead of a new account with a
  lineage link. Codes are single-use bearer tokens — whoever holds the
  code holds the authority — with a 7-day default TTL;
  only hashes are stored, so a stolen store yields no live codes.
- **"Claimed" is not "full account."** #446's target full account —
  validated contact, billing, recovery — is a later slice built on top
  of `claimed_at`/`claimed_by`. The claim protocol records the
  trust state ("the operator vouched for this binding"); the account
  record is future work.

The one mistake to prevent: an operator who lost the old key must not
"rotate" by registering the new key and assuming continuity — that mints
a new account and strands the old one's box binding. The onboarding
surface should say the decision rule verbatim when it offers either path.

## 6. What the connect-time wiring slice must deliver

This doc is the experience spec for the still-open wiring slice (tracked
under #446). The slice is done when an agent can run the §2 walkthrough
end to end against a fresh box:

1. First connect with an unseen key registers the fingerprint and returns
   the full first-connect manifest (§2 step 2), with `box_id` filled from
   the registry binding.
2. Reconnect with the same key resumes the account and box, and the
   resume manifest carries the same `account_id` (the §2 step-4 probe).
3. Resume is registry state, not in-memory: reconnecting from a new
   session/process still resumes the same account and box, and
   reconnecting never re-registers — no second account row appears and
   the record's `created_at` is unchanged.
4. `vm_endpoint` and `claim_url` are filled (today they are null; the
   claim protocol is shipped, the serving URL is not).
5. Failure is observable: a connect with a malformed key is refused, no
   account row is registered, and the agent sees the refusal naming the
   key; with a corrupt registry the connect is refused, no new account
   row appears, and the registry file is byte-identical afterwards.

Out of scope for the wiring slice (named so nobody smuggles them in):
the full-account record (validated contact / billing / recovery), the
hosted sybil policy, and any hosted-launch surface. The wiring serves
the self-hosted and agent-created-accounts path first; the hosted
control plane reuses the same modules unchanged (S1's stdlib-only
discipline is the portability contract).

## 7. Placement alongside the accounts/onboarding plan

This doc sits alongside the accounts/onboarding plan
(`docs/HOSTED_SIGNUP_ONBOARDING.md`) as the key-identity onboarding
surface: that doc's §4 (identity linking) covers the enrollment-token /
fingerprint-approval path for human-driven signup; this doc covers the
key-as-identity path for agent-created accounts and the self-hosted
one-command story. (The phrase "accounts plan" in #446's acceptance
item means this onboarding-plan doc set — there is no separate
accounts-plan document.) The mechanism docs —
`docs/KEY_IDENTITY_REGISTRY.md` (storage, lookup, rotation, claim
protocol) and the `harness/key_identity.py` / `harness/key_registry.py`
module docstrings — are the implementation companion; this doc is the
experience companion. `docs/FIRST_RUN_ACTIVATION.md` owns the hosted
funnel framework; key-identity onboarding feeds its identity-linking
stage and shares its funnel measurement (`docs/FUNNEL_MEASUREMENT.md`)
once the wiring slice lands.

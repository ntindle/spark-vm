# Golden-image round-trip gate — operator procedure

Implements `docs/FIRST_TEN_MINUTES_SPEC.md` §6.7 (item 7 of §6). The spec
requires the operator to verify **on every golden image** that the first
task files, the human can answer, the grant mints, and the task verifies
end-to-end, with the filing-count determinism check. This doc is the
procedure the operator actually runs per image. The tooling it drives is
the gate-fixture tooling (`harness/install-gate-fixture.sh`,
`harness/check-image-manifest.sh`, `harness/harness-auth-probe`); read
those scripts' headers before running this procedure the first time.

The §6.7 gate generalizes the pilot's §5.1 readiness gate
(`docs/RESEARCH_FIRST_RUN_PILOT.md` §5.1 — run the canonical task once,
confirm the filing appears in `APPROVALS/pending/`, the human can answer
it, the grant mints; do not run the cohort until it passes) from "per
pilot box" to "per golden image".

## Scope and honesty

- This procedure gates the **image**, at image-build time, before the
  image is published. It does not cover provision-time checks (the
  provision-time injector's preflight and `harness-auth-probe
  --mode provision` on the live tenant box) and it does not replace the
  pilot cohort's own §5.1 gate.
- At image-build time the first-run human does not exist yet, so the
  operator (or a designated stand-in) plays the human. The gate proves
  the round-trip **mechanics** — file → answer → grant minted → task
  verifies — not the signup-page UX.
- Until the spec's §6 item-6 interface lands (the client-visible pending
  signal the tenant Muse can park on — a §10 pre-launch build item, not
  shipped), the gate exercises the round trip **through confirmd
  directly** with the operator answering. That is still the §6.7 gate's
  core; it is not the minute-5–8 executable script. Record the interface
  gap in the gate record (step 6) rather than pretending it closed.
- The `policy-misfire` and `no-gated-action` codes are **operator-only**
  (spec §2/§4): a filing-count defect must never render on the signup
  page. Keep them in the gate record and defect tracker only.

## Prerequisites

- The image under test was built from a **clean checkout at a known
  commit** (the manifest generator refuses dirty trees — see below).
- Root on the image-build environment (the gate installs the fixture
  through the narrow writers, exactly as at build time).
- The canonical first-task text: the pilot's §5.1 canonical task, used
  identically on every image under gate. If a substitute task is used
  (pilot §5.1 allows substitution only when the task doesn't file), the
  substitute must be **identical across all images under gate**, or the
  results are not comparable.
- `image_version` (the full commit SHA the image was baked from).

## Step 0 — manifest preflight

Confirm the image's manifest names the code you think you're gating:

```bash
harness/check-image-manifest.sh <manifest.json> --expect-version <SHA>
```

Exit 0 means the manifest is well-formed (`sparkvm/golden-image-manifest@1`
schema, required fields present) and `image_version` matches the baked
commit. Any other exit is a **gate refusal, not a retry**: the image is
not what the manifest claims. Do not proceed; rebuild from a clean tree
(`harness/generate-image-manifest.sh` refuses dirty trees for exactly
this reason).

## Step 1 — install the gate fixture

```bash
sudo harness/install-gate-fixture.sh
```

The installer installs only the **public, non-secret** dummy inference
credential under the inference proxy's single fixed name `llm-api`
(`GATE-FIXTURE-DUMMY-NOT-A-SECRET` — it is baked into the repo on
purpose; it is not a credential), the loopback echo host in
`inference-hosts.allow` and in the inference proxy's own
`inference-ssrf.allow`, starts the echo fixture, and runs the probe in
gate mode to prove the fixture works. It is idempotent and runs as root
(the gate environment matches the image-build environment).

It **fails closed** — refuse and stop — if the secrets dir already holds
a real `llm-api` (a blind compare refuses any stored value that is not
the public dummy, so a real tenant key is never overwritten and its
value is never read). A gate that proceeds over a real key is a
**security incident**, not a passed gate: the fixture binding must never
coexist with a real credential.

## Step 2 — auth-path probe (gate mode)

```bash
harness/harness-auth-probe --mode gate
```

Exit 0 means: the image's model calls route through the inference proxy
on the image, the proxy swapped the placeholder for the dummy with the
exact `Authorization: Bearer <...>` wire shape, the placeholder never
reached the origin, and confirmd answers (the approvals path the first
task needs is up).

Failure classes are distinguishable by design — read the probe's header
before triaging:

- **Exit 3 (environment):** the CLI is missing, the fixture is absent,
  or the echo log is unreadable. The gate environment is broken; fix the
  environment, not the image.
- **Exit 1 (check failed):** an image-path problem — the CLI ignores the
  proxy env, the placeholder reaches the origin unswapped, the CLI
  vehicle hung, or the fixture is misinstalled. This fails the image.
- **Exit 2 (usage):** the gate was invoked wrong; fix the invocation.

The probe never handles a real secret — everything it names is an
`hsurr:<name>` placeholder, swapped at egress. Keep it that way in any
gate wrapper you write.

## Step 3 — the round trip (file → answer → grant mints → verify)

Run the canonical first task once, exactly as a tenant Muse would — a
single gated request type, single attempt (spec §6 item 2: "the first
task files exactly one approval" is a constraint on the task's request
pattern, not a policy guarantee):

1. **Files.** Confirm a file appears in `APPROVALS/pending/` for the
   gated request. If nothing files, stop — this is a `no-gated-action`
   outcome; the gate fails (step 4 classifies it).
2. **The human can answer.** The operator answers the pending request
   through confirmd. A pending request that cannot be answered is a gate
   failure ("a golden image that files but can't answer/mint fails the
   gate" — spec §6 item 7).
3. **The grant mints.** Confirm the consumed record carries
   `decision == "approve"` (denials land in `consumed/` identically — a
   denial does not prove minting).
4. **The task verifies end-to-end.** Re-run the gated action with the
   grant in place and confirm it succeeds (spec §6 item 3: "the Muse can
   observe the grant took effect"). An approval that mints but doesn't
   take effect fails the gate.

## Step 4 — filing-count determinism check

Count the filings the task produced:

- **Exactly 1 filing** — pass.
- **0 filings** — operator code `no-gated-action`. Gate fails. The task
  never attempted the gated action; the request pattern is wrong for the
  gate (per pilot §5.1, substitute a task that files — identically across
  all images under gate).
- **2+ filings** — operator code `policy-misfire`. Gate fails. The defect
  is in the task's request pattern (or the filing/coalescing path),
  filed as a proxy/confirmd-track defect, not waived: the gate exists to
  catch exactly this.

Record the count and the operator code in the gate record (step 6).
Neither code ever surfaces on the signup page.

## Step 5 — fixture teardown (pre-publish, mandatory)

The gate fixture must **never coexist with a real credential**.

**Ownership split — read before touching anything.** This procedure
(running as root on the build box, pre-publish) is the *sole* owner of
allowlist-line removal. The provision-time injector's step 2 is not a
second teardowner: it unbinds registry entries through the narrow writer
and then **refuses loudly** on any surviving echo exemption in the allow
files — it has no narrow path to remove allowlist lines (production
sudoers is append-only by design; see
`harness/inject-provision-state.sh` step 2). Skipping the image-build
teardown is not recoverable at provision time; it is a hard provision
refusal. A real tenant key landing on an image whose fixture was never
torn down is refused loudly by the installer — treat that refusal as the
safety net firing, then fix the image; never override it.

1. Unbind every `llm-api` → echo-host registry binding **through the
   narrow registry writer** (idempotent per entry — this is the one part
   of teardown that has a narrow path):

   ```bash
   sudo -u swapd cred-registry-set-inference remove-host llm-api <host>
   ```

   (same invocation the injector performs in
   `inject-provision-state.sh` step 2; the writer removes only exact
   lowercase host matches — if a binding survives the unbind, the image
   is pathological: rebuild it).

2. Remove the echo host from `inference-hosts.allow`
   (`/home/swapd/inference-hosts.allow`) **and** from the inference
   proxy's own `inference-ssrf.allow`
   (`/home/swapd/inference-ssrf.allow`). There is **no narrow path for
   this by design** — production sudoers grants only `tee -a`
   (append-only) on the allow files. Edit both files as root (this
   procedure's Prerequisites grant root on the image-build environment;
   the narrow writers are for tenant-scope operations, not for undoing
   the fixture). The injector cannot do this step for you — see the
   ownership split above.

3. Verify with the proxy's own matching semantics
   (`harness/proxy_match.py`, pinned to the real functions by
   `harness/test_proxy_match.py`'s drift tripwire) that **no effective
   echo binding remains** — loopback aliases included (`127.0.0.1`,
   `localhost`, `::1`; the fixture used `127.0.0.1` but a surviving
   alias is the same defect). This is the reference implementation from
   `inject-provision-state.sh` step 2 (`echo_bound_hosts` /
   `allowlist_echo_entries`); all three commands must return empty
   output with exit 0:

   ```bash
   cat /home/swapd/inference-registry.json \
     | KEY_NAME=llm-api python3 harness/proxy_match.py echo-bound-hosts
   python3 harness/proxy_match.py allowlist-echo-entries hosts /home/swapd/inference-hosts.allow
   python3 harness/proxy_match.py allowlist-echo-entries ssrf  /home/swapd/inference-ssrf.allow
   ```

   Non-empty output is a gate failure. So is an unverifiable teardown:
   an unreadable registry (exit 2) or an unparsable allow file (exit 1)
   must never read as "entry absent" — treat them as refusals and fail
   the gate. The image does not publish until all three read empty.

## Step 6 — record the gate outcome

Record, alongside the image's manifest, one gate record per image:

- `image_version` (SHA), `schema`, and the manifest file used
- date, operator, and the gate environment (image-build vs provision)
- probe result (mode, exit code) and fixture install result
- the round-trip record: approval id, human answer outcome,
  grant-minted confirmation, end-to-end verification result
- **filing count** and operator code (`ok`, `no-gated-action`, or
  `policy-misfire`)
- the §6 item-6 interface-gap note (while unlanded: "round trip
  exercised through confirmd directly; pending-signal interface not yet
  shipped")
- the final verdict: **gate / no-gate**

A gate failure must name the defect tracker entry (request-pattern
defect → proxy/confirmd track; image-path defect → harness tooling;
fixture-survival → the build gate). A gate record without a verdict is
not a gate; an image without a gate record does not publish.

## Cadence

Run this procedure **once per golden image** — every rebuild, every
base-layer change, every change to the proxy, inference proxy, swap
writers, confirmd, or the fixture tooling itself. A manifest whose
`image_version` predates a component change is a gate that never ran.

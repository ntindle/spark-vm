# Golden-image round-trip gate — operator procedure

Implements `docs/FIRST_TEN_MINUTES_SPEC.md` §6.7 (item 7 of §6). The spec
requires the operator to verify **on every golden image** that the first
task files, the human can answer, the grant mints, and the task verifies
end-to-end, with the filing-count determinism check. This doc is the
procedure the operator actually runs per image. The tooling it drives is
the gate-fixture tooling (`harness/install-gate-fixture.sh`,
`harness/check-image-manifest.sh`, `harness/harness-auth-probe`,
`harness/echo-fixture.py`, `harness/proxy_match.py`,
`proxy/with-proxy`, `proxy/cred-store-set`,
`proxy/cred-registry-set`, `proxy/cred-store-delete`,
`proxy/grant-writer`, `confirm/confirmd.py`); read those files' headers
before running this procedure the first time.

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
- The gate's round trip (steps 2–3) exercises the **real filing path**:
  the gated request goes through the main credential-swapping proxy,
  which refuses the out-of-scope request and files the approval itself;
  the operator answers through confirmd; the grant mints through
  `grant-writer`; the re-run swaps the real (dummy) value through the
  proxy. No test vehicle files on the task's behalf — the proxy's own
  `_file_approval` path is what the gate exercises.
- Until the spec's §6 item-6 interface lands (the client-visible pending
  signal the tenant Muse can park on — a §10 pre-launch build item, not
  shipped), the gate answers **through confirmd directly** with the
  operator tapping Approve, and the task runs as an explicit command
  rather than through the minute-5–8 activation script. That is still
  the §6.7 gate's core. Record both interface gaps in the gate record
  (step 6) rather than pretending they closed.
- The `policy-misfire` and `no-gated-action` codes are **operator-only**
  (spec §2/§4): a filing-count defect must never render on the signup
  page. Keep them in the gate record and defect tracker only.

## Prerequisites

- The image under test was built from a **clean checkout at a known
  commit** (the manifest generator refuses dirty trees — see below).
- Root on the image-build environment (the gate installs fixtures
  through the narrow writers and edits the allow files as root, exactly
  as at build time).
- The canonical round-trip task (step 2): a fixed, versioned,
  deterministic gated request — **identical across all images under
  gate**, or the results are not comparable. The spec's canonical
  first-task text is still pilot-gated and not adopted
  (`FIRST_TEN_MINUTES_SPEC.md` says so explicitly); until it lands, this
  procedure's fixed task is the canonical task for the gate. Record its
  verbatim brief in the gate record (step 6).
- `image_version` (the full commit SHA the image was baked from).

## Step 0 — manifest preflight

Confirm the image's manifest names the code you think you're gating:

```bash
harness/check-image-manifest.sh <manifest.json> --expect-version <SHA>
```

The `<manifest.json>` is the artifact `harness/generate-image-manifest.sh`
produced at image-build time (stdout, or `--out <path>`); it is the same
manifest the provision-time injector preflights. Name the exact file in
the gate record.

- **Exit 0** means the manifest is well-formed
  (`sparkvm/golden-image-manifest@1` schema, required fields present)
  and `image_version` matches the baked commit.
- **Exit 1** is a **gate refusal**: the image is not what the manifest
  claims. Do not proceed; rebuild from a clean tree.
- **Exit 2** is an **invocation error** (bad arguments, bad flags):
  fix the command and re-run — it is not a verdict on the image.

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

### Reading the installer's probe output (triage, not a re-run)

The installer's embedded gate-mode probe run **is** the auth-path check
— do not run `harness/harness-auth-probe --mode gate` standalone
afterward. The installer owns the ephemeral echo fixture's lifecycle
(it is killed on installer exit) and the `PROBE_*` environment the
probe needs; a standalone run outside that context is meaningless.
Triage a failed installer run from its captured output:

- **Probe gate mode, exit 3 (environment):** the CLI is missing, the
  fixture is absent, or the echo log is unreadable. The gate environment
  is broken; fix the environment, not the image.
- **Probe gate mode, exit 1 (check failed):** an image-path problem —
  the CLI ignores the proxy env, the placeholder reaches the origin
  unswapped, the CLI vehicle hung, or the fixture is misinstalled. This
  fails the image.
- **Installer exit 2 (usage/setup):** a narrow writer, the fixture, or
  the probe is not executable, or a required tool is missing. The
  image-build environment is wrong, not the image: fix the environment,
  never the image, and never bypass the check.
- **Installer exit 3 (fixture startup):** the echo fixture failed to
  start. Diagnose from the captured stderr the installer prints; do not
  proceed without the fixture.

Any nonzero installer exit is **no-gate**: the gate did not run. But the
classes differ — environment/setup failures are fixed and the gate
re-run; image-path failures fail the image. Route from the captured
stderr, not from the exit code alone.

The probe never handles a real secret — everything it names is an
`hsurr:<name>` placeholder, swapped at egress. Keep it that way in any
gate wrapper you write.

## Step 2 — round-trip setup (gate-only, torn down in step 5)

The gate's canonical round-trip task is a single deterministic gated
request through the **main** credential-swapping proxy: one `POST` to a
model-call-shaped path on a gate-only echo origin, carrying the
`hsurr:gate-test` placeholder. The credential `gate-test` is bound to
the echo host with static limits `GET` + `/v1/models` only, so the
`POST /v1/chat` request is out of scope and the proxy files exactly one
approval. This is the real `_file_approval` path — the same one a tenant
task's out-of-scope request takes.

1. **Start the round-trip echo fixture** (plain HTTP; gate-scratch,
   never a service — killed in step 5):

   ```bash
   ECHO_FIXTURE_LOG=/tmp/gate-roundtrip-echo.log ECHO_FIXTURE_PORT=18099 \
     harness/echo-fixture.py > /tmp/gate-roundtrip-port 2>&1 &
   # Wait for the readiness signal (same 10s deadline pattern as the
   # installer's fixture start — a bare grep here races the bind):
   deadline=$((SECONDS + 10))
   while [ $SECONDS -lt "$deadline" ]; do
     grep -q '^PORT=18099' /tmp/gate-roundtrip-port 2>/dev/null && break
     sleep 0.2
   done
   grep -q '^PORT=18099' /tmp/gate-roundtrip-port   # readiness
   ```

   If port 18099 is taken on the build box, pick another free port and
   use it consistently below.

2. **Install the gate test credential** (public dummy — never a secret)
   on the **main** proxy and bind it to the echo host with narrow
   static limits:

   ```bash
   printf 'GATE-FIXTURE-DUMMY-NOT-A-SECRET' \
     | sudo -u swapd cred-store-set gate-test
   sudo -u swapd cred-registry-set add-host gate-test 127.0.0.1
   sudo -u swapd cred-registry-set add-method gate-test GET
   sudo -u swapd cred-registry-set add-path gate-test /v1/models
   ```

3. **Exempt the echo host on the main proxy** (gate-only lines, removed
   in step 5). There is no narrow path for these by design — production
   sudoers grants only `tee -a` (append-only) on the allow files, so the
   operator appends as root on the image-build environment:

   ```bash
   printf '127.0.0.1\n' | tee -a /home/swapd/hosts.allow
   printf '127.0.0.1\n' | tee -a /home/swapd/ssrf.allow
   ```

   The proxy hot-reloads the store, registry, hosts, and ssrf files per
   request (mtime-checked) — no restart needed.

4. **Clear stale gate filings.** If `/home/swapd/approvals/pending/`
   holds any `gate-test` item from an aborted run, resolve or remove it
   first — a stale item coalesces with the new filing and the count
   check (step 3.2) cannot distinguish them.

## Step 3 — the round trip (file → answer → grant mints → verify)

### 3.1 The task files

Run the canonical task's single gated request exactly as a tenant Muse
would — one request type, one attempt:

```bash
with-proxy curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  http://127.0.0.1:18099/v1/chat \
  -H 'Authorization: Bearer hsurr:gate-test' \
  --data-binary '{"model":"gate-round-trip"}'
```

Expected: `200` from the echo fixture. The proxy sees the placeholder
for a bound credential, finds the `POST /v1/chat` request outside the
static `GET` + `/v1/models` limits with no covering grant, **refuses the
swap, files one approval** (`method-not-allowed`), and lets the request
through with the placeholder untouched. The echo log for this run shows
`Bearer hsurr:gate-test` — that is correct here; the swap is what the
grant will later enable.

If the curl itself fails (connection refused, proxy not listening),
that is an **environment failure, not a gate verdict** — fix the
environment and re-run. A gate verdict needs the request to have
reached the proxy.

### 3.2 Filing-count determinism check

Count the gate's filings in `pending/` (time-ordered; the newest
`gate-test` item is this run's):

```bash
count=0
for f in $(ls -t /home/swapd/approvals/pending/*.json 2>/dev/null); do
  jq -e 'select(.credential=="gate-test")' "$f" >/dev/null 2>&1 \
    && count=$((count+1))
done
echo "$count"
```

- **Exactly 1 filing** — pass. Record its id:

  ```bash
  for f in $(ls -t /home/swapd/approvals/pending/*.json 2>/dev/null); do
    AID=$(jq -r 'select(.credential=="gate-test") | .id' "$f")
    [ -n "$AID" ] && break
  done
  echo "$AID"
  ```

- **0 filings** — operator code `policy-misfire`. Gate fails. The task
  took the gated action (the curl reached the proxy) and the proxy
  filed nothing: the filing path is defective. File a proxy/confirmd
  defect; do not waive it. (`no-gated-action` is reserved for a task
  variant that never sent the request at all — with this canonical
  task it cannot occur; if the curl never ran, that is an environment
  failure, step 3.1.)
- **2+ filings** — operator code `policy-misfire`. Gate fails. Either
  the task's request pattern double-files or the filing/coalescing path
  is defective. File a proxy/confirmd defect; do not waive it: the gate
  exists to catch exactly this.

Neither code ever surfaces on the signup page.

### 3.3 The human can answer

The operator answers the pending request through confirmd (the human
side; the tenant signup UX is out of scope for the gate). Open the
confirmd page — `https://<tailnet-ip>:8443` (`CONFIRM_BIND` /
`CONFIRM_PORT`; tailnet-identity auth) — find the pending item by the
`AID` from step 3.2, and tap **Approve**. The page mints the per-item
CSRF nonce itself; there is no manual nonce handling.

A pending request that cannot be answered is a gate failure ("a golden
image that files but can't answer/mint fails the gate" — spec §6
item 7).

### 3.4 The grant mints

Confirm the consumed record carries `decision == "approve"` (denials
land in `consumed/` identically — a denial does not prove minting) and
that `grant-writer` lists an active grant for the exact tuple:

```bash
jq -r '.decision' /home/swapd/approvals/consumed/"$AID".json   # "approve"
/home/swapd/grant-writer list | grep "$AID"
# <AID> gate-test 127.0.0.1 POST /v1/chat <job> (active)
```

The grant row must show `gate-test 127.0.0.1 POST /v1/chat` and status
`active`. Anything else is a gate failure.

### 3.5 The task verifies end-to-end

Re-run the identical gated request with the grant in place and confirm
the swap took effect (spec §6 item 3: "the Muse can observe the grant
took effect"):

```bash
with-proxy curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  http://127.0.0.1:18099/v1/chat \
  -H 'Authorization: Bearer hsurr:gate-test' \
  --data-binary '{"model":"gate-round-trip"}'
tail -1 /tmp/gate-roundtrip-echo.log | jq -r '.authorization'
```

Pass criteria: `200`, and the echo log's `authorization` is
`Bearer GATE-FIXTURE-DUMMY-NOT-A-SECRET` with **no `hsurr:` token**
anywhere in the record. An approval that mints but doesn't take effect
fails the gate.

## Step 4 — filing-count verdict

Step 3.2 is the determinism check; this step is its verdict. Record the
count and the operator code (`ok`, `policy-misfire`) in the gate record
(step 6). `no-gated-action` cannot occur with the canonical task (step
3.2); if a future task variant never sends the gated request, that code
means the request pattern is wrong for the gate — substitute a task
that files, identically across all images under gate (pilot §5.1).

## Step 5 — fixture teardown (pre-publish, mandatory)

The gate fixtures must **never coexist with a real credential**.

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

**Inference-fixture teardown:**

1. Unbind every `llm-api` → echo-host registry binding **through the
   narrow registry writer** (idempotent per entry — this is the one part
   of teardown that has a narrow path):

   ```bash
   sudo -u swapd cred-registry-set-inference remove-host llm-api 127.0.0.1
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

3. Delete the inference dummy credential file itself
   (`/home/swapd/inference-secrets/llm-api`) as root — there is no
   narrow delete writer for the inference store, and a surviving dummy
   file wedges the installer's next gate run (a present file with no
   echo-only binding reads as "not this fixture"). The blind compare
   and the injector's refusal remain the backstop regardless.

**Round-trip-fixture teardown (main proxy):**

4. Remove the gate test credential entirely — registry entry and store
   file — through the narrow writers:

   ```bash
   sudo -u swapd cred-registry-set remove gate-test
   sudo -u swapd cred-store-delete gate-test
   ```

5. Remove the `127.0.0.1` gate lines from the main proxy's
   `/home/swapd/hosts.allow` **and** `/home/swapd/ssrf.allow` as root
   (no narrow path exists; same ownership split as above).

6. Kill the round-trip echo fixture (gate-scratch, never a service) and
   remove its log:

   ```bash
   pkill -f 'echo-fixture.py'   # only the gate's fixture runs on the build box
   rm -f /tmp/gate-roundtrip-echo.log /tmp/gate-roundtrip-port
   ```

**Verification — the image does not publish until every check reads
empty.** Verify with the proxy's own matching semantics
(`harness/proxy_match.py`, pinned to the real functions by
`harness/test_proxy_match.py`'s drift tripwire) that **no effective
echo binding remains** — loopback aliases included (`127.0.0.1`,
`localhost`, `::1`; the fixture used `127.0.0.1` but a surviving alias
is the same defect). This is the reference implementation from
`inject-provision-state.sh` step 2 (`echo_bound_hosts` /
`allowlist_echo_entries`); all commands must return empty output with
exit 0:

```bash
cat /home/swapd/inference-registry.json \
  | KEY_NAME=llm-api python3 harness/proxy_match.py echo-bound-hosts
python3 harness/proxy_match.py allowlist-echo-entries hosts /home/swapd/inference-hosts.allow
python3 harness/proxy_match.py allowlist-echo-entries ssrf  /home/swapd/inference-ssrf.allow
cat /home/swapd/credentials.json \
  | KEY_NAME=gate-test python3 harness/proxy_match.py echo-bound-hosts
python3 harness/proxy_match.py allowlist-echo-entries hosts /home/swapd/hosts.allow
python3 harness/proxy_match.py allowlist-echo-entries ssrf  /home/swapd/ssrf.allow
```

And confirm the credential files are gone:

```bash
test ! -e /home/swapd/secrets/gate-test \
  -a ! -e /home/swapd/inference-secrets/llm-api \
  && echo TEARDOWN-CLEAN
```

Non-empty output is a gate failure. So is an unverifiable teardown:
an unreadable registry (exit 2) or an unparsable allow file (exit 1)
must never read as "entry absent" — treat them as refusals and fail
the gate.

## Step 6 — record the gate outcome

Record, alongside the image's manifest, one gate record per image:

- `image_version` (SHA), `schema`, and the manifest file used
- date, operator, and the gate environment (image-build vs provision)
- probe result (mode, exit code) and fixture install result
- **canonical round-trip task**: task id and the verbatim gated-request
  brief (method, path, credential name, static limits, echo origin)
- the round-trip record: approval id, human answer outcome,
  grant-minted confirmation (grant row), end-to-end verification result
  (swapped `Authorization` observed at the echo origin, no `hsurr:`)
- **filing count**, the count method, and operator code (`ok` or
  `policy-misfire`)
- **teardown attestation**: each removal performed (registry unbinds,
  allowlist-line removals, credential-file deletions, fixture kill) and
  the verification command results
- the §6 item-6 interface-gap note (while unlanded: "round trip
  exercised through confirmd directly; pending-signal interface not yet
  shipped") and the activation-script gap note (while unlanded: "task
  run as an explicit command, not through the minute-5–8 script")
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

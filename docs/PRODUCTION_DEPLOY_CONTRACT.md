# Production deploy contract (hosted control plane)

Standing contract for every loop-executed production deploy to the hosted
control plane (`sparkvm-control` Worker + its D1 database). Proposed by the
33rd rotation audit (P114) after the first two loop-executed production
deploys improvised it well but left nothing standing; adopted 2026-10-02 by
this docs turn (track: hosted-product).

## What "production" means

The hosted control plane is the only production the loop touches. Deploys
outside the loop (owner's own terminal, main chat) are not covered by this
contract but must still be recorded: the next loop turn that discovers an
out-of-loop deploy enters it into the loop's run log (kept in the
improvement-loop goal's working state) using the same entry shape.

## Code homes

The deployed Worker code is **not in the spark-vm repo** — it lives in a
separate, non-version-controlled workspace directory
(`<loop-goal>/../sparkvm-dev-website-v2-cloudflare-management-infra/control-plane/worker.py`),
so the repo alone cannot pin what is running. For every loop-executed
deploy, the record pins the deployment id **and the SHA-256 of the deployed
`worker.py` bytes**. The loop's existing convention of keeping a
pre-deploy copy of the worker under the improvement-loop goal's
`hidden_files/` (e.g. `worker.py.bak-pre-<issue>-plane-<timestamp>`)
remains the working backup; the SHA is the audit pin.

## The gate: no deploy without all of these

1. **Unanimous routed-role SHIP IT on the exact final head (the code being
   deployed).** Roles are routed per the playbook's routing table — plane
   code routes Security + Engineering + Architecture (the security-sensitive
   row + the credentials/network/auth default). No round cap; no shipping
   over an unresolved substantive objection. **Ratchet:** a SHIP IT given on
   an earlier head is stale the moment a later fix touches code the role
   already cleared — the role re-confirms on the final head before the
   deploy proceeds (precedent: slot 20261002-1129, Security + Architecture
   round-3 re-confirms on the final head).
2. **A test harness run against the exact final head (the code being
   deployed).** The D1 binding may be a stub in the harness — the stub's
   differences from production must be documented per deploy, and any known
   stub-blind class gets an explicit compensating check. Precedent: at
   #848 the harness ran a real worker against a sqlite D1 stub and the
   NULL-column-as-JsNull proxy class (e.g. `json.dumps` 500s in
   `_cmd_row`; the same class misreported a guard-blocked revoke as 200
   in #846) was compensated by injecting fake JsNull proxies and
   asserting NULLs serialize as JSON null. See "The two precedent
   deploys" for why this clause exists.
3. **No deploy inside a turn that cannot finish verification.** Deploy and
   live-verification are one unit of work; a turn that can ship the code
   but not verify it does not deploy (the loop's no-incomplete-turns
   hygiene). Deferral is not a drop: a deferred deploy is pick-up-able by
   a later run. Worst case is a one-run deferral — an unverified
   production deploy is the worse outcome.
4. **Credential provenance is decided before the deploy.** The deploy
   records whose credential and which surface executed it (see "Records").
   The contract covers authorization, not just mechanics — an unowned
   credential is a gate failure. (The operator-configured Cloudflare
   tooling on the shared loop box counts as operator-owned provenance;
   this clause bars nobody's tooling.) A gate failure defers the deploy
   and is escalated through the playbook's `NEEDS_USER.md` path — it
   never stalls the loop.

## Schema migrations: forward only

- D1 DDL is applied **one statement at a time**. The `/batch` route on the
  D1 tooling 404s (standing tooling note, 2026-10-02) — batch execution is
  not a retry loop, it is a dead path.
- Every migration statement is verified live afterwards (pragma / schema
  read-back on the production database).
- Before applying a migration, capture a D1 backup/export — or confirm the
  time-travel restore window — and record the restore path in the deploy
  record. "Forward-fix" without a restore path is fiction for destructive
  ALTERs; a bad migration on the production user registry with no backup
  is the catastrophic failure this contract exists to prevent.
- Migrations are **forward-fix only**: there are no down-migrations for
  production D1. The forward-fix plan for a bad migration is written down
  *at deploy time*, not improvised after the failure; for a destructive
  migration the plan names the restore first.
- Non-idempotent `ALTER`s are flagged in the record so a re-run is a
  conscious, reviewed decision, never an accident.

## Worker deploys

- A deploy produces a **deployment id**; the id goes in the deploy record
  along with the SHA-256 of the deployed `worker.py` bytes (see "Code
  homes").
- **Rollback is redeploying the previous deployment id.** At deploy time,
  read the current live deployment id from the Cloudflare tooling and use
  *that* as the rollback target, logging any mismatch against the last
  recorded id — an out-of-loop deploy can silently invalidate a recorded
  target, and rollback must never start with a discovery step.
- **Rollback is a reviewed state by reference.** Redeploying the rollback
  target named in the deploy record does not re-trigger gate 1 (the code
  was already reviewed and shipped); it still requires the run-log record
  update and live verification. An emergency rollback must never hit a
  review wall.
- Edge propagation is not instant: the first precedent took ~60 seconds
  before the new code answered. Live-verification probes start after the
  propagation window; a transient 404-then-401 sequence inside the window
  is expected, not a failure signal — persisting beyond the propagation
  window is.

## Scheduled plane jobs

The push sender loop (`hosted/push_send_loop.py`, #1094) runs as a
scheduled job against the plane's D1 store. The loop has no leader
election and no claim lease (the frozen schema, #988, rules out a claim
column) — so the scheduler owns singleton-ness, and this section is
the interim claiming mechanism:

- **Ticks MUST NOT overlap.** Exactly one sender tick per D1 store at a
  time. Two overlapping ticks SELECT the same `'queued'` rows and both
  POST: the owner's phone buzzes twice for one page (page-once is the
  lane's core promise — a double-buzz cannot be un-rung by any
  downstream dedup), and on the release path both ticks run the
  terminal transaction, double-decrementing the D10 budget counter
  (floored at zero) so one page can consume another page's budget unit.
- **A tick overrunning the schedule interval is a double-buzz incident**,
  not a performance note: shorten the tick's work (`max_claims`) or
  lengthen the interval before ticks can overlap.
- **Handoff:** this rule retires when the Durable-Object singleton
  claim build ships — the claim design is pinned in
  `docs/PUSH_SENDER_CLAIM_DESIGN.md` (D56a, #1121); its input gate is
  what turns overlapping ticks into queued ones instead of concurrent
  sends. Until then, this section is the entire claiming mechanism.

## Live verification checklist

Run after the deploy, against production, before calling it done:

1. **Health probe** — the plane answers on the public endpoint.
2. **Auth taxonomy** — the error classes the deploy touches are exercised
   live: unauthenticated → 401, wrong token → 401/403, missing resource →
   404, stale/conflicting state → 409. The auth gate precedent
   (slot 20261002-1129) verified enqueue/fetch/epoch-reset without auth →
   401 and fetch with a bogus token → 401, and wrote no test rows.
3. **Test-row hygiene** — every test row created for live E2E is deleted
   afterwards, and the production registry is verified clean (the
   precedent: pairing approved/redeemed with test rows, then the test box
   + pairing deleted, registry verified to contain only the real
   production box).
4. **What cannot be exercised live is stated explicitly** — covered by the
   harness instead, with the reason recorded. Precedent: token revocation
   was not exercised live because minting an owner key would permanently
   close the live bootstrap window; the harness covered it against the
   exact deployed code, and the record says so.
5. **Pre-existing production observations are recorded, not mutated.**
   A deploy that notices an unhealthy box records it as an observation
   for the ops lane/owner; it does not plane-mutate its way around a
   box-side problem (precedent: the 04:04 CDT stale heartbeat on the sole
   production box was recorded as a box-side observation — no plane
   mutation made or needed).

## Records

Every deploy lands in the loop's RUNLOG as a deploy entry carrying:

- the deployment id (Worker) and the SHA-256 of the deployed `worker.py`
  bytes (see "Code homes"); the live deployment id read at deploy time
  as the rollback target, with any mismatch against the last recorded id
  logged;
- the review verdicts (roles, rounds, what each round cleared);
- the harness result (counts, stub caveats, compensating checks);
- the live-verification results, including test-row deletion proof and
  the registry-clean verification;
- the exact D1 migration statements, the pre-migration restore path
  (backup/export or time-travel window), and the forward-fix plan
  (restore-first for destructive migrations);
- the credential provenance (whose credential, which surface);
- anything the deploy deliberately did not do, with the reason.

Repo-side: protocol-level changes ship a docs PR with the public protocol
spec and a reader-facing CHANGELOG entry (precedent: `docs/DURABLE_COMMANDS.md`,
PR #867).

## The two precedent deploys

Both executed 2026-10-02 by the loop worker using the operator-configured
Cloudflare tooling on the shared loop box. Both met the
review/harness/live-verification discipline this contract codifies — and
one of them is why gate 2 exists in its written form:

- **#846 plane half** (rotating box Bearer <redacted> + revoke): Worker deployment
  `db44225c2db14359b2652ee913401490` (2026-10-02T16:25:10Z); D1 migration 3
  ALTERs + 2 indexes; 10/10 live E2E with the real pairing client, test rows
  deleted, registry clean; Security + Architecture + Engineering unanimous
  final SHIP IT (2 rounds, ratchet clean). It met gates 1 and 3 — but
  **not gate 2 as written**: its harness recorded no stub differences and
  no compensating check for the NULL-column-as-JsNull class, and it shipped
  the live bug (a guard-blocked revoke re-read misreported as 200), fixed
  post-deploy. The fake-JsNull injection precedent belongs to #848 alone.
- **#848 plane half** (durable commands): Worker deployment
  `c10b0f4212104a2481ba1b038eb2e682` (2026-10-02T17:05:12Z); D1 migration 2
  ALTERs + commands table + index; live auth-gate verification, no test
  rows; Security + Architecture + Engineering unanimous final SHIP IT
  (3 rounds, ratchet re-confirms on the final head); harness 54/54 with
  fake-JsNull injection for the same stub-blind class gate 2 exists to
  catch; docs PR #867.

Gate 4's provenance record is new with this contract: P114(g) postdated
both deploys, and neither deploy's RUNLOG entry records "whose credential,
which surface" — the tooling sentence above is reconstruction, not a
record. The pre-deploy SHA-256 pin is likewise new; the precedent rows
carry no code hash.

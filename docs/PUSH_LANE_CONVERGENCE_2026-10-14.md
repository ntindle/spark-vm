# Push-lane convergence pin: the #849 vision vs state (2026-10-14)

**Vision vs state for the #849 phone-approval buzz leg** — pinned to
main `27793e8` (2026-10-14 ~06:50 CDT) for all in-repo claims; every
in-repo claim below was verified against that tree this turn. Issue/PR
numbers are GitHub references as of 2026-10-14 (not code-verifiable from
the tree). Doc-first; honesty rules apply (`docs/POSITIONING.md`):
everything below is **current state and work to do**, not promises.
The hosted product is not live, and no tenant has ever received a
phone-approval page through this lane.

**Non-overlap map (what this doc is not):**
- `docs/PUSH_LANE_CONVERGENCE_2026-10-10.md` — the prior pin, refreshed
  in place 2026-10-12 to post-#1058 / post-#1368 state (commit
  `a473708`). This doc consumes it and re-verifies it at today's main;
  it does not re-derive the whole lane.
- `docs/PUSH_SUBSCRIPTION_WIRE_CONTRACT.md` (#968 / GP2, #1391) — the
  subscription wire contract. This doc consumes it; it re-analyzes
  nothing there except the two holes §2 names.
- `docs/PUSH_SENDER_SCHEMA_CONTRACT.md` (#988, as amended by #1061 and
  the D45 retirement) — the D1 store, custody, and VAPID lifecycle.
  This doc consumes it.
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` (D-MT1) — the
  one-plane-per-tenant model. This doc consumes it; the plane-home
  question §2 answers falls out of D-MT1, not out of new analysis.
- `docs/LIVE_MACHINE_CONTROL_CONVERGENCE_2026-10-14.md` (#47) — the
  live-control lane, pinned today. Separate lane; this doc does not
  touch it.

## 1. What moved since the 10-12 refresh

| Change | State at today's main |
| --- | --- |
| Subscription dashboard half (#1391) | **MERGED** 2026-10-13 (`29c0ede`): `docs/PUSH_SUBSCRIPTION_WIRE_CONTRACT.md` (D98–D102) + dashboard "Push notifications" section + `hosted/dashboard/sw.js` + 6 push tests in `test_dashboard.py`. |
| Subscription plane half (#1392) | **FILED** 2026-10-13 (open, p2): the four wire-contract endpoints on the private `sparkvm-control` worker + serve `sw.js` at `/sw.js` (D102). Gates on the operator data key (D45). |
| Digest suppression double-representation (#1423) | **SHIPPED** (`bbd7072`, PR #1440): a budget-suppressed digest no longer coalesces into the current window's count. |
| Digest no-refire guard (#1424) | **SHIPPED** (`d8ce7d8`, PR #1426): enqueue-side refusal of digest refire for already-fired windows — the guard no longer lives only in the sweep scan. |
| Digest D53 pin + past-window text (#1425) | **SHIPPED** (`727f02e`): D53 fast-path pinned for `approval_filed` (digest attempt rows carry real box ids per D56c/D89, so the D53 claim stays unfaithful for digests); late-fired past-window digests no longer claim "this hour" about the previous hour's pages. |
| D45 one-data-key claim | **RETIRED** (`ad88197`, #1375): under D-MT1 the data key is one per tenant plane's Worker (the D-VD3 shape); one key protects one tenant's secrets. The NEEDS_USER data-key entry already carries the matching D-MT1 amendment (per-plane provisioning at plane deploy time, orchestrator-owned, #906/#905 territory). |
| `_utcnow` hardening (#1384) | **SHIPPED** (`642ee4e`): non-finite/out-of-range epoch floats rejected in `push_send_loop.py` / `push_sweep.py`. Hardening only; no lane-state change. |
| Deploy-contract slice (#1385) | **SHIPPED** (merged 2026-10-12, `c6cc64d1`): `deploy/plane-cron/` — the plane-workspace cron-trigger contract: the exact `wrangler.toml` `[triggers]` declaration (per-minute D9 sweep, `30 3 * * *` daily 03:30 UTC retention GC), the scheduled-handler dispatch contract, #1013-pattern manual ops triggers (`POST /v1/ops/push/sweep`, `POST /v1/ops/push/gc` — owner-key only, box token refused), and `verify_plane_cron.py` post-deploy verification (26 hermetic tests). Issues stay open: the operator's live tick (#1069) and the plane-side trigger registration. |

Nothing else in the lane moved since the 10-12 refresh: #1094, #1064,
#967, #968 stay open with unchanged scope (re-verified §3); #1069 and
#1298 stay open with reduced residual — their in-repo contract slices
shipped in #1385 (see §3).

## 2. The subscription leg, deep-read at today's main

This is where the movement is, so this is where the pin looks closely.

**Shipped and verified (dashboard half).** The #1391 dashboard surface
does what the wire contract requires of a conforming client:
capability gate (`dashboard.html:590` — no service worker or
PushManager → a plain-language "can't receive" notice, never a dead
button); list via the existing owner-auth `api()` helper
(`dashboard.html:597`); 404/501 on the list endpoint renders the
muted "push notifications aren't enabled on this control plane yet"
notice (`dashboard.html:603`–`609` — the known not-yet state, never a
raw error); dead-410 rows render a warning chip plus their own
"Re-register" button (`dashboard.html:337`–`341`); the no-wipe guard
scopes the 30 s auto-refresh (`dashboard.html:628`); the DOM never
holds secrets (device labels + statuses only — pinned by
`test_push_row_html_xss_and_no_secret_render`). Six push tests cover
the surface (row states, XSS/no-secret render, register paths +
device charset, unsubscribe URL shape, dead/empty/capability gate,
404 degradation). The wire contract's §2 client checklist is met in
full by the shipped code.

**Plane-home question — answered, not a gap.** A plausible misread of
#1392 ("implement ... on the private `sparkvm-control` worker") is
that subscriptions would live on an operator plane while D-MT1 says
they live on the tenant plane. D-MT1 resolves it: every hosted signup
provisions a dedicated `sparkvm-control` instance — `sparkvm-control`
is the *name* of each tenant plane's worker (own Worker, own D1, own
VAPID identity), not a single operator plane. #1392's target is the
tenant-plane worker; the operator plane holds no subscription rows.
No filing needed; this paragraph is the record so the misread does
not get re-litigated.

**F-PUSH-14-1 — per-signup VAPID keypair issuance is unowned.**
Filed as **#1475** (p2). Three settled statements do not compose:
D48a (VAPID generation is operator-run, offline — "never on the
plane, never in CI"); D-MT1 (every signup provisions a dedicated
plane with its own VAPID identity; per-plane VAPID/secrets issuance
is a named provisioning cost); #906's acceptance ("no operator
steps"). #906's scope ("run seeding + H19 credential install") names
no VAPID issuance — and H19 is the *box-side* credential install
packet (#134), not plane VAPID issuance. The data key had the same
shape and got its D-MT1 carve-out (orchestrator deploy-time
generation under operator Cloudflare credentials, recorded in
NEEDS_USER.md); VAPID got no parallel carve-out. Until decided,
#1392's `GET /v1/push/vapid-pubkey` has no key to serve on a
signup-provisioned plane, and the subscription leg cannot complete
there. The decision is (a) orchestrator-generates at deploy time
(amend D48a; the data-key carve-out is the template) or (b) every
signup waits on a manual operator VAPID step (amend #906's
acceptance). #1475 owns the decision + the home (#906 scope
amendment or a follow-up build).

**F-PUSH-14-2 — D102's sw.js byte-pin has no enforcement mechanism.**
Filed as **#1476** (p3). D102 says the plane serves
`hosted/dashboard/sw.js` at `/sw.js`, "byte-pinned to the reviewed
file" — but no mechanism enforces the pin: no deploy-time hash
check, no drift test, nothing in #1392's scope, and the loop cannot
verify the private worker's served bytes. The precedent proving the
class is real is #1299 (dashboard inline-copy drift): the plane
worker's inlined `dashboard.html` already drifts from the repo copy.
Failure mode is silent: the plane keeps serving a stale worker after
the dashboard's `sw.js` evolves, and notifications render through
the outdated fallback. #1392 (or its follow-up) should carry a pin
check (deploy-time hash, or serve-from-repo-at-deploy) or D102
should be downgraded from "byte-pinned" to "served from the plane
bundle; redeploy with the dashboard".

**Issue-hygiene notes (pointer comments, not new issues).**
- **#968** — body still describes the combined pre-split scope
  (plane endpoints + dashboard in one issue). Pointer comment
  records the split: #1391 shipped the dashboard half; #1392 owns
  the plane half; #1475 owns the VAPID issuance question. #968
  stays open for the plane half.
- **#1064** — body still says "Unbuilt: nothing reads the coalesced
  rows and composes the digest body, nothing delivers it through
  the sender loop, and nothing resets `push_digest_state` after
  delivery." All three have shipped (D87 reset, D76/D77 sweep
  passes, #1423/#1424/#1425). Pointer comment records the
  corrected remaining scope: the D88 adjudication only —
  count-scoped body (shipped) vs per-box breakdown (unbuilt; needs
  a schema change per D89 since digest pages enqueue with
  `box_id` NULL). #1064 stays open for D88.
- **#1392** — pointer comment recommends the plane build carry
  conformance tests against the wire contract (D99 validation
  matrix, D98 read-path secrecy, D100 upsert, D101 delete, D102
  serving): the loop cannot verify the private worker, and the
  #952/#873 plane halves set the harness precedent. #1476
  (sw.js pin check) belongs in #1392's scope or as its follow-up.

## 3. Rest of the lane, re-verified

| Leg | State at today's main |
| --- | --- |
| Sender loop (#967) | Still OPEN. Loop landed in-repo (`hosted/push_send_loop.py`); claiming (D56a) still deferred to #1094 — the module docstring still names #1094 as the claim mechanism's home (verified at `push_send_loop.py:16`–`27`). Acceptance still keys on #428's §4 retirement: needs a deployed caller + claim mechanism. The loop has neither. |
| D9 sweep (#1063) | Still OPEN until #1069's live tick. The D72 cron trigger's in-repo contract slice shipped in #1385 (`deploy/plane-cron/` — trigger declaration + post-deploy verification); what remains is the plane-side registration + one observed live cron tick with no human driving it (the #1069 acceptance). `hosted/push_sweep.py` docstring still pins the open state (verified at `push_sweep.py:18`). |
| Claim mechanism (#1094) | Still OPEN. Design (`docs/PUSH_SENDER_CLAIM_DESIGN.md`, #1121 PushSenderDO singleton) shipped; the mechanism build is open. |
| Digest content (#1064) | Still OPEN for the D88 adjudication only (see §2). |
| GC deploy half (#1298) | Still OPEN (p3): the in-repo contract slice shipped in #1385 (GC trigger `30 3 * * *` daily 03:30 UTC + scheduled-handler dispatch + manual ops trigger in `deploy/plane-cron/`); remaining is the plane-side registration + one live GC tick. In-repo GC half (#1058) shipped. |
| TTL race | Unchanged: the 60-minute approval TTL ("a race against push") remains a race the plane cannot win until #1069 + #968 land. #968's dashboard half shipped; the plane half (#1392) + #1069 still open. Shortening the TTL before then is still the wrong move. |
| VAPID mailbox | Unchanged, still operator-owned (NEEDS_USER.md): `mailto:hosted@sparkvm.dev` must exist and be monitored before hosted push goes live; until then the sender loop ships but stays undeployed to production. |
| Data key | Unchanged, still operator-owned (NEEDS_USER.md, D-MT1 amendment): one key per tenant plane at plane deploy time; gates #890's value path + #1392's subscription-secrets storage. |

## 4. Filed gaps

- **#1475** (p2) — per-signup VAPID keypair issuance unowned (F-PUSH-14-1).
- **#1476** (p3) — D102 sw.js byte-pin has no enforcement mechanism (F-PUSH-14-2).
- Pointer comments on #968, #1064, #1392 (issue-hygiene notes, §2).
- Everything else the lane needs is already filed: #1069, #1094,
  #1064 (D88), #1298, #1392, #967 (acceptance), #1475, #1476.
  #849 stays OPEN (vision tracker).

## 5. What this doc does not claim

- No tenant has received a push page through this lane — every
  substantive acceptance checkbox is unmet, and the honest
  remaining-build list is §3 plus #1392 plus the two new gaps.
- Plane-side facts inherit the pinned reads recorded in the cited
  docs — no fresh plane read this turn. If the plane moved since
  those pins, this doc's plane statements are stale with them.
- The dashboard claims were verified against
  `hosted/dashboard/dashboard.html` at main `27793e8` (subscription
  section, capability gate, 404/501 degradation, no-wipe guard,
  re-register/remove buttons); the contract claims against
  `docs/PUSH_SUBSCRIPTION_WIRE_CONTRACT.md` at the same tree.
- This doc files exactly the two issues in §4 and changes no code.

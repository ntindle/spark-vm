# Tenant status endpoint — `GET /tenant/status` design (G3)

**Status:** design; not implemented. Closes the design half of backlog item
G3 ("tenant onboarding status poll with the spec's machine vocabulary").

**The gap:** three spec documents agree on a control-plane poll —
`FIRST_TEN_MINUTES_SPEC.md` §2 prescribes the tenant status poll carrying
the 12 machine codes + `approvals_url` in the tenant record (§2, minute
4–5); `HOSTED_SIGNUP_ONBOARDING.md` §5 says "Muse polls GET /tenant/status
with its key; the signup page polls the same endpoint — when status flips
to `live`, both sides see 'your box is ready'"; `HOSTED_SIGNUP_WEB_UI.md`
§7 defines its auth on both sides. No endpoint implements any of this: a
`grep` over the repo finds zero handlers, zero routes, zero contract tests
for `/tenant/status`, and no tenant record field named `approvals_url`.
The first-ten-minutes clock, the approvals-URL check, and the two-sided
"your box is ready" moment are all specified against an endpoint that does
not exist. This doc is the implementable contract.

**Scope discipline:** this doc specifies the control plane's tenant-status
surface only — what the endpoint returns, who may read it, and which layer
computes each code. It does not design the provisioning driver (H4), the
relay (H4), confirmd (H10), or push (H14). Those components are *producers*
of status inputs; this endpoint is the *reader*.

## 1. The endpoint

- **Method/path:** `GET /tenant/status`
- **Auth (per `HOSTED_SIGNUP_WEB_UI.md` §7):** two-sided, same endpoint.
  - The signup page polls with the human's magic-link session cookie
    (no-JS page, `<meta http-equiv="refresh">` + manual "Check status"
    plain-form POST — the page never holds a credential).
  - The tenant Muse polls with its linked (approved) ed25519 key, signing
    requests per `HOSTED_SIGNUP_ONBOARDING.md` §4's link-signing scheme
    (the same scheme the identity-link request uses).
  - No unauthenticated access. A caller whose tenant identity cannot be
    established gets `401`; a caller asking about a tenant that is not
    theirs gets `404` (not `403` — the endpoint must not confirm the
    existence of other tenants; cf. the waitlist surface's
    enumeration-oracle discipline in `HOSTED_SIGNUP_WEB_UI.md` §7).
- **Read-only contract:** GET never changes state. A scanner fetching the
  URL (the mail-scanner threat already applied to the magic-link flow)
  learns nothing it is not authenticated to see and changes nothing.
- **Caching:** `Cache-Control: no-store` — both pollers must see the flip
  within one poll interval. Poll cadence is a client choice; recommended:
  the Muse polls every 5 s during the first-ten-minutes window (§2 below
  binds specific minutes to specific codes), the signup page refreshes on
  a 15 s meta-refresh (human-legible, not spinner-chasing).

## 2. The machine vocabulary (verbatim from `FIRST_TEN_MINUTES_SPEC.md` §2)

`provisioning`, `live`, `waiting-on-approval`, `approved`, `box-unhealthy`,
`connection-unreachable`, `policy-misfire`, `no-gated-action`,
`human-denied`, `human-drop-off`, `stuck`, `provisioning-failed`.

These are **tenant-layer** codes — the onboarding script's vocabulary —
not provider vocabulary. `harness/provider_iface.py`'s `BoxStatus` /
`ProviderState` (provisioning/running/suspending/…) is the provider layer
and feeds *into* this endpoint; it is never exposed raw, per
`HOSTED_SIGNUP_WEB_UI.md` §7 ("never the raw H3 enum without the mapping").

### Code definitions and producers

| Machine code | Meaning | Set by / derived from |
|---|---|---|
| `provisioning` | VM requested, not yet box-ready | Provider layer: H4 driver's `BoxStatus` maps provisioning-ish provider states here |
| `live` | Box ready; the 10-minute clock starts (§8; also H3 §5) | Provider reports running + the stack's smoke gates pass (control plane AND-combines: a running VM with a dead proxy is `box-unhealthy`, not `live`) |
| `waiting-on-approval` | First task filed; parked on the human's answer (§6) | The approval filing event (proxy/confirmd) — see G4's summons design |
| `approved` | Human approved; Muse finishing its first task | The grant-mint event |
| `box-unhealthy` | Smoke checks failed (§2 table: `box-unhealthy: <check>`) | The Muse's §2 smoke report; operator-side reprovision path owns recovery |
| `connection-unreachable` | Relay/cert path failed while the poll says otherwise (§2) | Control-plane/relay defect instrumentation — never reported as a Muse failure |
| `policy-misfire` | First task produced zero or 2+ filings (§6.7 gate) | Golden-image gate fixture; operator-only (no human rendering) |
| `no-gated-action` | Muse never attempted the gated action | Pilot analysis; operator-only (no human rendering) |
| `human-denied` | Human tapped Deny | The denial event |
| `human-drop-off` | Approval expired unanswered (§4: one reminder at T+TTL/2, then expiry) | Expiry; pairs with G1 (expired approvals need an agent-visible terminal record, GitHub #213) |
| `stuck` | First session stalled | Operator/heuristic; transitional pending a real stall detector |
| `provisioning-failed` | Provisioning terminally failed | H4 driver terminal failure |

### Transition rules (no skips, no surprises)

1. `provisioning` → `live` | `provisioning-failed`. Never backwards;
   a dead box after `live` is `box-unhealthy`, not a return to
   `provisioning` — reprovisioning creates a new onboarding session, not
   a rewound one.
2. `live` → `waiting-on-approval` | `box-unhealthy` | `no-gated-action`
   | `stuck`. The spec's §2 script binds these to minutes 1–8; the
   endpoint records *which* minute-bound check produced the code
   (see `detail`, §3) so the operator's funnel analysis can tell a minute-2
   smoke failure from a minute-8 park.
3. `waiting-on-approval` → `approved` | `human-denied` | `human-drop-off`.
   Terminal for the first-approval arc; later approvals reuse the same
   vocabulary per task (H10's per-tenant queue work, not this endpoint's
   — this endpoint answers "where is my onboarding", not "list my
   approvals").
4. `approved` → terminal for onboarding. The clock's job is done.
5. `policy-misfire` / `no-gated-action` are set by the operator's gate
   and pilot tooling, respectively — never by the Muse, never shown to
   the human.

## 3. Response schema

```json
{
  "tenant_id": "tnt_7f3a…",
  "status": "waiting-on-approval",
  "status_updated_at": "2026-09-22T20:31:04Z",
  "approvals_url": "https://approve.example.example/a/tnt_7f3a…",
  "detail": "box-unhealthy: confirmd",
  "human_key": "waiting-on-approval"
}
```

- `tenant_id` — opaque tenant identifier; the Muse and the page already
  know it from their own auth context, so it is a correlation aid, not a
  lookup key. It is never guessable (opaque, non-sequential).
- `status` — one of the §2 machine codes, exactly spelled (hyphens, no
  casing variants — the poll is machine-read).
- `status_updated_at` — ISO-8601 UTC of the last transition. Pollers use
  it, not their own clocks, to decide "the flip happened".
- `approvals_url` — **the G3 carrier**: the URL handed to the human at
  signup stage 2 (`FIRST_TEN_MINUTES_SPEC.md` §4) and read by the Muse at
  minute 4–5. Present from tenant-record creation (signup), never absent
  while the tenant exists — §2's minute-4–5 pass criterion is "present in
  the tenant record". G4's summons design builds its email body on this
  field (the carrier scope G4 names explicitly).
- `detail` — free-form machine sub-code for the unhealthy/unreachable/
  stuck family (`box-unhealthy: <check>` per §2). Absent on happy-path
  codes; the human page never renders it raw.
- `human_key` — the §4 rendering key. The signup page holds the human
  copy (the exact sentences in §4, no paraphrasing — the doc says so in
  bold); the endpoint supplies only the key. This keeps funnel copy under
  the signup doc's ownership and the endpoint copy-free. Operator-only
  codes (`policy-misfire`, `no-gated-action`) have no `human_key`; a page
  receiving them falls back to the last human-rendered code, never to a
  blank screen.

## 4. Layering — what computes what

```
provider (H4 driver)          BoxStatus: provisioning/running/… + health
        │  maps, never exposes raw
control plane                 tenant status layer: the 12 codes, transition
        │  rules, approvals_url carrier, authz per §1
readers                       tenant Muse (linked key) · signup page (cookie)
```

- The provider driver reports VM facts (`harness/provider_iface.py`
  `BoxStatus`, `wake_kind`, `retention`). The tenant layer's job is the
  AND-combine: `live` requires *provider running* **and** *stack smoke
  gates green*; a running VM with a dead `swap-proxy`/`confirmd` is
  `box-unhealthy`, because from the tenant's point of view the box is not
  a box until the stack is up.
- Filing/grant/denial/expiry events (proxy, confirmd) are inputs to the
  approval-arc codes; they do not write tenant status directly — the
  tenant layer owns the transition rules (§2), so a later H10 queue
  redesign cannot accidentally invent new status codes.
- `suspended`/`waking` (H13's future vocabulary, and the `§6` status
  mapping's "later" note in `HOSTED_SIGNUP_WEB_UI.md` §7) are *not* in
  this vocabulary — they belong to the suspend/wake lifecycle design when
  H13 lands, and this doc's vocabulary extends then, not now.

## 5. Composition with neighboring gaps and specs

- **G4 (first-approval summons):** the summons body's deep link is built
  from `approvals_url` + the approval id; the control-plane email sender
  G4 designs reads the same tenant record this endpoint serves. G4's
  design doc lives on `strategy/first-approval-summons-g4-20260922-0500`
  (strategy turn, not yet merged at the time of writing) — when it merges,
  its carrier section should cite this doc's §3 field contract.
- **G1 / #213 (expired approvals):** `human-drop-off` is the human-side
  rendering of the expiry G1 instruments agent-side; the two must agree
  on the TTL boundary (one reminder at T+TTL/2, then expiry — §4), and
  G1's agent-visible terminal record must carry the same approval id the
  summons deep-linked.
- **G5 (golden-image gate):** the gate procedure's pass criterion —
  file → answer → grant-mint → verify — is observable as
  `waiting-on-approval` → `approved` on this endpoint; `policy-misfire`
  is the gate's filing-count defect surfaced as a code instead of a
  log line.
- **G6 (§3a smoke assets):** the smoke-check contract (§3 of the spec)
  feeds `box-unhealthy`'s `detail` field (`box-unhealthy: <check>`);
  G6's provision assets decide what `<check>` names are possible.
- **H3 §5 (first-10-minutes clock):** the clock starts at the
  `provisioning` → `live` transition's `status_updated_at`, not at
  signup, not at the Muse's first poll — one authoritative timestamp.

## 6. Build slices (for the provisioning/feature track, not this doc)

1. **S1 — control-plane endpoint + contract fixtures:** implement
   `GET /tenant/status` against a tenant-record store carrying
   `approvals_url` from signup stage 2; contract tests asserting the §2
   vocabulary spelling, the §2 transition rules (no backwards moves),
   the 401/404 auth behavior of §1, and the operator-only codes'
   missing `human_key`. (This is the G3 deliverable's implementation
   half — `feature`/`provisioning` track.)
2. **S2 — provider mapping:** wire the H4 driver's `BoxStatus` into the
   tenant layer with the AND-combine rule (§4); the mapping table becomes
   a tested unit, not prose.
3. **S3 — reader wiring:** signup page meta-refresh against the
   authenticated endpoint; Muse-side poller using its linked key. The
   no-JS discipline (§1) stays — the page renders `human_key` copy it
   already holds.

## 7. Open questions (→ backlog, not blockers)

1. **Multi-box tenants:** the vocabulary is per-tenant, but a tenant with
   two boxes has two onboarding arcs. Options: per-box status resource
   (`/tenant/status?box=<id>`) or tenant-status = the arc of the newest
   box. Needs a decision before S1 — the schema's `tenant_id` may need a
   `box_id` sibling. (Filed below as G7.)
2. **Who writes `approvals_url`:** signup stage 2 hands it to the human
   (spec §4), but the control plane must persist it into the tenant
   record at claim time — which signup-flow step owns the write, and what
   happens on re-entry ("the funnel re-enters at the first incomplete
   screen" — `HOSTED_SIGNUP_WEB_UI.md` §5)? A re-entering tenant must not
   get a rotated approvals URL mid-arc. (Filed as G8.)
3. **`stuck` detection:** currently a heuristic placeholder. A real stall
   detector (no provider events + no Muse heartbeats for N minutes) is
   its own design; until then `stuck` is operator-set. (Filed as G9.)

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
    plain-form POST — the form posts to the page route, not the API, and
    the page never holds a credential).
  - The tenant Muse polls with its linked (approved) ed25519 key, signing
    requests per `HOSTED_SIGNUP_ONBOARDING.md` §4's link-signing scheme
    (the same scheme the identity-link request uses).
  - No unauthenticated access. A caller whose tenant identity cannot be
    established gets `401`; a valid credential with no servable tenant
    record (deleted, or a pre-stage-2 record this endpoint does not
    serve — see §3) gets `404` (not `403` — the endpoint must not confirm
    the existence of other tenants; cf. the waitlist surface's
    enumeration-oracle discipline in `HOSTED_SIGNUP_WEB_UI.md` §7). There
    is no tenant selector on this endpoint — identity is
    credential-derived — so the 404 case fires only for the caller's own
    tenant being unservable.
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
| `live` | Box ready; the 10-minute clock starts (§1; also H3 §5) | Provider reports running + relay/cert path reachable (the spec §2 minute-0 criterion: `ssh` connects, cert accepted). The stack's §3 smoke gates are a *persistence* guard, not an entry gate: a box that was `live` and then fails a smoke check *becomes* `box-unhealthy` on the Muse's report (transition rule 2) — it is never held at `provisioning` waiting for smoke. |
| `waiting-on-approval` | First task filed; parked on the human's answer (§6) | The approval filing event (proxy/confirmd) — see G4's summons design |
| `approved` | Human approved; Muse finishing its first task | The grant-mint event |
| `box-unhealthy` | Smoke checks failed (§2 table: `box-unhealthy: <check>`) | The Muse's §2 smoke report; the control plane's own stack-deploy failure (post-driver, pre-Muse — no connection bundle ever handed out); operator-side reprovision path owns recovery |
| `connection-unreachable` | Relay/cert path failed while the poll says otherwise (§2; spec §8: "box live per the status poll, tenant SSH via the relay fails") | Producer: the relay session-liveness instrument (`docs/RELAY_LIVENESS_DESIGN.md`) — non-terminal suspension (transition rule 6): entered from any post-`live` arc code on relay/cert failure, latching the arc code; arc-advancing events during suspension are recorded and update the latch; on recovery the tenant layer re-evaluates (returns the updated latch). The suspension never advances or resets the onboarding arc, never attributed to the Muse |
| `policy-misfire` | First task produced zero or 2+ filings (§6.7 gate; zero-filings is misfire only for a task that *does* take the gated action — no action at all is `no-gated-action`) | Golden-image gate fixture; operator-only (no human rendering) |
| `no-gated-action` | Muse never attempted the gated action | Pilot analysis; operator-only (no human rendering) |
| `human-denied` | Human tapped Deny | The denial event |
| `human-drop-off` | Approval expired unanswered (§4: one reminder at T+TTL/2, then expiry) | Expiry. Human surface: the answered-history Expired badge card + the expired-410 → answered-history link (`docs/EXPIRED_APPROVAL_TERMINAL_RECORD.md` §3/§5, S3) |
| `stuck` | First session stalled | Operator/heuristic, currently operator-set per spec §8's concrete rule (session abandonment: 30 minutes with no Muse action and no pending approval); G9's real stall detector targets that rule. Exits: operator/heuristic clears → the tenant layer re-evaluates to the current arc code; a reprovision restarts the session (transition rule 7). Until S3's confidence bar is met (`docs/STUCK_DETECTOR_DESIGN.md` §6), `stuck` must never be exposed as automatic. |
| `provisioning-failed` | Provisioning terminally failed | H4 driver terminal failure |

### Transition rules (no skips, no surprises)

1. `provisioning` → `live` | `box-unhealthy` | `provisioning-failed`.
   Never backwards; a dead box after `live` is `box-unhealthy`, not a
   return to `provisioning` — reprovisioning creates a new onboarding
   session, not a rewound one (see rule 7). Two entry-time failure modes,
   distinguished by *what* failed: (a) **reachability** — relay/cert path
   unreachable at provision, no bundle ever handed out — holds at
   `provisioning` until the H4 driver reports a terminal failure →
   `provisioning-failed`; (b) **stack-deploy** — the driver succeeded but
   the control plane's stack install (swap-proxy/confirmd) failed on the
   box, no bundle ever handed out → `box-unhealthy` with `detail:
   stack-deploy:<stage>`, from which the operator reprovisions per rule 7.
   The criterion is crisp: a failure *reaching or verifying* the box
   holds; a failure *in the box's own stack* is `box-unhealthy`.
2. `live` → `waiting-on-approval` | `box-unhealthy` | `no-gated-action`
   | `stuck`. The spec's §2 script binds these to minutes 1–8; the
   endpoint records *which* minute-bound check produced the code — minute
   resolution comes from `status_updated_at` plus the code; `detail` (§3)
   carries the sub-code for the unhealthy family and the check name for
   the approval-arc transition — so the operator's funnel analysis can
   tell a minute-2 smoke failure from a minute-8 park.
3. `waiting-on-approval` → `approved` | `human-denied` | `human-drop-off`
   | `box-unhealthy`. Terminal for the first-approval arc except that a
   smoke/harness check failing *at any post-`live` point* is
   `box-unhealthy` per the spec's §8 ("any smoke/harness check fails") —
   the later approvals reuse the same vocabulary per task (H10's
   per-tenant queue work, not this endpoint's — this endpoint answers
   "where is my onboarding", not "list my approvals").
4. `approved` → terminal for onboarding: the clock's job is done.
   "Terminal" means arc-complete, not endpoint-dark — the endpoint keeps
   serving, and `connection-unreachable` may still be entered from
   `approved` (returning to it) without reopening the arc. Likewise a
   failed smoke/harness check on an approved box may surface as
   `box-unhealthy` (the poll must stay honest about the stack) — the
   arc stays terminal.
5. `policy-misfire` / `no-gated-action` are set by the operator's gate
   and pilot tooling, respectively — never by the Muse, never shown to
   the human.
6. **Relay/cert suspension:** from any post-`live` arc code (`live`,
   `waiting-on-approval`, `approved`), a relay/cert-path failure moves
   the endpoint to `connection-unreachable`, latching the arc code at
   suspension entry. Arc-advancing events during the suspension (the
   approval UI rides the magic-link session, not the relay — the human
   can tap Approve/Deny while the suspension is showing) are *recorded
   and update the latch*, never dropped. On recovery the tenant layer
   **re-evaluates** from current inputs (equivalently: returns the
   updated latch) — never a blind stack-pop of a stale code. The
   suspension itself neither advances nor resets the 10-minute clock.
   Not entered from `provisioning` / `provisioning-failed` (no arc to
   suspend yet).
7. **Session restart:** the numbered rules are per onboarding session.
   The only legal cross-session moves are `box-unhealthy` →
   `provisioning` (operator reprovision), `provisioning-failed` →
   `provisioning` (operator retry), `live`/`approved` →
   `provisioning` (operator reprovision of a live box starts a new
   onboarding session — the §8 G7 carve-out), and `stuck` →
   `provisioning` (operator reprovision of a stalled-then-reimaged
   box — the `stuck` row's "a reprovision restarts the session"
   exit is this rule; the old box image is gone, so there is no
   resume path). The endpoint serves the latest
   session, `status_updated_at` resets, and the 10-minute clock restarts
   at the new session's `provisioning` → `live` transition.

## 3. Response schema

```json
{
  "tenant_id": "tnt_7f3a…",
  "status": "waiting-on-approval",
  "status_updated_at": "2026-09-22T20:31:04Z",
  "approvals_url": "https://approve.example.example/a/tnt_7f3a…",
  "detail": "filed-approval: gate-1",
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
  minute 4–5. The field is **non-null from signup stage 2 on** — the spec
  §2 minute-4–5 pass criterion is "present in the tenant record", and
  S1's tenant-record store carries it from stage 2. Pre-stage-2 polls
  (the tenant record is created at `HOSTED_SIGNUP_ONBOARDING.md` §4.1
  step 1; the URL is minted later) get the documented `404` — this
  endpoint does not serve the tenant record until stage 2. Resolved by
  the §8 G8 rules (2026-09-26): the stage-2 hand-over step owns the
  write — write-if-absent + re-read, mint-once; funnel re-entry is a
  read path, never a rewrite. G4's
  summons design builds its email body on this field (the carrier scope
  G4 names explicitly).
- `detail` — free-form machine sub-code, present only where a sub-decision
  exists: the unhealthy/unreachable/stuck family (`box-unhealthy:
  <check>` per §2), and `waiting-on-approval` (the minute-bound check
  name, per transition rule 2). Absent on `provisioning`, `live`
  (pre-arc — no sub-decision yet) — with one exception: under §8's
  multi-box rule, `detail` carries the box identity
  (`"<sub-code> @ box=<box-name>"` style — e.g. `box-unhealthy:
  relay-dial-failed @ box=kitchen-pi`) whenever more than one box is
  still onboarding — so the reported arc is always disambiguated, per
  rule 1's rationale that `detail` carries the reported box identity.
  Absent on
  the arc-terminal codes (`approved`, `human-denied`, `human-drop-off`,
  `provisioning-failed`).
  The human page never renders it raw.
- `human_key` — the `FIRST_TEN_MINUTES_SPEC.md` §4 rendering key. The
  signup page holds the human copy (the spec §4's "exact sentences the
  signup page and emails use — no paraphrasing" rule); the endpoint
  supplies only the key. This keeps funnel copy under the signup doc's
  ownership and the endpoint copy-free. Operator-only codes
  (`policy-misfire`, `no-gated-action`) have no `human_key`; a page
  receiving them falls back to the last human-rendered code it holds
  server-side in the magic-link session, never to a blank screen.

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
  AND-combine for `live`-entry: *provider running* **and** *relay/cert
  path reachable* (the §2 minute-0 entry criterion). The §3 smoke gates
  are a *persistence* guard, not an entry gate — a box that was `live`
  and then fails a check becomes `box-unhealthy` via the Muse's report
  (transition rule 2); it is never held at `provisioning` waiting for
  smoke.
- Filing/grant/denial/expiry events (proxy, confirmd) are inputs to the
  approval-arc codes; they do not write tenant status directly — the
  tenant layer owns the transition rules (§2), so a later H10 queue
  redesign cannot accidentally invent new status codes. S1's producer
  write paths (the Muse's §2 smoke report, filing/grant/denial/expiry
  events) ride the same linked-key auth as the poll — the implementation
  must not invent an unauthenticated report endpoint (a tenant could
  forge its own health, violating the spec §8 "instrument each
  separately" attribution discipline). S1 names the event→transition
  mapping as a tested unit alongside the S2 provider mapping.
- `suspended`/`waking` (H13's future vocabulary, and the status mapping in
  `HOSTED_SIGNUP_WEB_UI.md` §6, `creating→provisioning`, `ready→live`,
  with the "later `suspended`/`waking`" wording in §7's `/tenant/status`
  row) are *not* in this vocabulary — they belong to the suspend/wake
  lifecycle design when H13 lands, and this doc's vocabulary extends then,
  not now.

## 5. Composition with neighboring gaps and specs

- **G4 (first-approval summons):** the summons body's deep link is built
  from `approvals_url` + the approval id; the control-plane email sender
  G4 designs reads the same tenant record this endpoint serves. G4's
  design doc lives on a strategy-loop branch (not yet merged at the time
  of writing — see BACKLOG.md **G4**, which names the `approvals_url`
  carrier requirement); when it merges, its carrier section should cite
  this doc's §3 field contract.
- **G1 / #213 (expired approvals):** `human-drop-off` is the human-side
  rendering of the expiry G1 instruments agent-side; the two must agree
  on the TTL boundary (one reminder at T+TTL/2, then expiry — §4), and
  G1's agent-visible terminal record must carry the same approval id the
  summons deep-linked. (**Design shipped 2026-09-26:**
  `docs/EXPIRED_APPROVAL_TERMINAL_RECORD.md` — expiry becomes a third
  `decision: "expired"` value in `consumed/<aid>.json`; same aid, same
  TTL boundary; S1–S3 build slices — all three now shipped: the stamp
  (S1), the deterministic agent serving (S2), and the human surface
  (S3: answered-history Expired badge card + expired-410 →
  answered-history link).)
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
   a tested unit, not prose. The table must be total over
   `ProviderState`: before H13 lands, driver-reported
   `SUSPENDED`/`WAKING`/`STOPPED` are unreachable (suspend is unshipped
   H4 work, gated on the operator spend-cap packet) — the table names its
   fallback for those rows explicitly rather than leaving them blank.
3. **S3 — reader wiring:** signup page meta-refresh against the
   authenticated endpoint; Muse-side poller using its linked key. The
   no-JS discipline (§1) stays — the page renders `human_key` copy it
   already holds.

## 7. Open questions (answered — kept for history)

1. **Multi-box tenants: ANSWERED → §8 (G7 resolution, 2026-09-26 gap turn).**
   Original question kept for history: the vocabulary is per-tenant, but a
   tenant with two boxes has two onboarding arcs. Options were a per-box
   status resource (`/tenant/status?box=<id>`) or tenant-status = the arc
   of the newest box. Decision: per-tenant onboarding-arc resource with
   the rule-1 selection preference (`live` > `provisioning` >
   `box-unhealthy` > `provisioning-failed`, ties → newest `created_at`
   then box-id lexical); "tenant reaches
   `live`" = the live-anchor box's arc reaches `live` (first to reach
   `live`; that moment starts the H3 §5 clock); no `box_id` schema
   sibling (§8). The stall detector's Q2 is closed in §8 too (one
   tenant-level stall).
   *Amended 2026-09-27: rule 1 is now a total selection preference over
   all 12 codes (see §8) — the ranking above was the pre-amendment
   2026-09-26 version. `waiting-on-approval` now ranks between `live`
   and `provisioning`; `no-gated-action` and `policy-misfire` rank below
   `box-unhealthy`; the arc-terminal codes
   (`approved`, `human-denied`, `human-drop-off`, `provisioning-failed`)
   participate only while no non-terminal candidate exists; suspension
   codes (`stuck`, `connection-unreachable`) compare by their latched
   underlying arc code.*
2. **Who writes `approvals_url`: ANSWERED → §8 (G8 resolution, 2026-09-26
   gap turn).** Original question kept for history: signup stage 2 hands
   it to the human (spec §4), but the control plane must persist it into
   the tenant record at claim time — which signup-flow step owns the
   write, and what happens on re-entry ("the funnel re-enters at the
   first incomplete screen" — `HOSTED_SIGNUP_WEB_UI.md` §5)? A re-entering
   tenant must not get a rotated approvals URL mid-arc. Decision: the
   hand-over step owns the write — write-if-absent + re-read, renders
   the stored value (§8 rules 1–4); funnel re-entry is a read path, never
   a rewrite; rotation only via an explicit operator event.
3. **`stuck` detection:** answered by `docs/STUCK_DETECTOR_DESIGN.md`
   (G9): the control-plane stall detector mechanizing the §8 rule (30 min,
   no Muse action, no pending approval), with the confusion-class ladder
   (`connection-unreachable`, `waiting-on-approval`, `human-drop-off`,
   `policy-misfire`, `no-gated-action` are never relabeled `stuck` —
   the §4 arc-scope conjunct hard-enforces this: only `live`-arc sessions
   are eligible, and `connection-unreachable`, `box-unhealthy`,
   `provisioning-failed`, `waiting-on-approval`, `human-drop-off`,
   `human-denied` can never enter the predicate),
   agent-forgeable-heartbeat cross-checking, and the S1→S2→S3 confidence
   staging — until S3's bar is met, `stuck` stays operator-set and is
   never exposed as automatic. (Filed as G9.)


## 8. G7/G8 resolutions (2026-09-26 gap turn)

Both were §7 open questions blocking G3's S1 implementation. Resolved
here; the implementation slices (S1–S3, §6) are unchanged except where
noted.

### G7 — multi-box tenants vs the per-tenant vocabulary

**Decision: the endpoint tracks the tenant's onboarding arc, per-tenant,
no `box_id` schema sibling.** The 12 codes are an onboarding vocabulary,
not a per-box inventory API — the dashboard's Boxes panel already owns
per-box status through the H3 §6 provider mapping (`creating →
provisioning`, `ready → live`, `degraded`/`dead` as-is). Two readers of
the same box state with two vocabularies is the duplication the §4
layering was built to prevent.

Rules:

1. **"The tenant reaches `live`" means the first box's arc reaches
   `live`** — where "first box" is the **live-anchor**: the box whose
   arc first reaches `live`. That moment is the H3 §5 first-ten-minutes
   clock start (the live-anchor's `provisioning → live`
   `status_updated_at`). While no box's arc has yet reached `live`,
   `GET /tenant/status` reports the **most-advanced arc** among the
   boxes still onboarding, ranked by a **total selection preference**
   over all 12 codes (closest to `live` without failure first —
   deterministic for every pair of candidate codes, which is what G3's
   S1 implementer needs): `live` > `waiting-on-approval` >
   `provisioning` > `box-unhealthy` > `no-gated-action` >
   `policy-misfire`, with the arc-terminal codes (`approved`,
   `human-denied`, `human-drop-off`, `provisioning-failed`) ranked last.
   (`live` is listed for completeness — pre-`live` no candidate holds it;
   the first box to reach `live` ends the pre-live phase.
   `no-gated-action`/`policy-misfire` are operator-only diagnostic
   end-states — never progressing, ranked below `box-unhealthy`.)
   Suspension codes (`stuck`, `connection-unreachable`) compare by their
   **latched underlying arc code** (the code the arc held at suspension
   entry, updated by arc-advancing events during the suspension per
   transition rule 6) — the suspension itself neither promotes nor
   demotes the candidate. Ties (same effective code) break by newest
   box-record `created_at`, then box-id lexical — so the reported box
   identity in `detail` cannot flap between polls when a batch shares
   `created_at`. Arc transitions are forward moves, not
   regressions: `provisioning → box-unhealthy` per transition rule 1 is
   the ordinary single-box failure path, and the monotonicity invariant
   below constrains *cross-box selection switches*, not arc
   transitions. Terminal arcs participate only while no non-terminal
   candidate exists — a dead box never outranks a progressing one
   (progress wins over recency: "newest" answers a Boxes-panel question,
   not an onboarding-arc question). The
   monotonicity invariant is scoped: within a single box onboarding
   session, the reported code never moves to an earlier stage
   than the last reported code — but a rule-7 cross-session restart
   (`box-unhealthy`, `provisioning-failed`, `live`/`approved`, or
   `stuck` → `provisioning`) resets the comparison baseline
   (`status_updated_at` resets per rule 7), so the sanctioned restart is
   a forward move, not a violation. Empty candidate set (the leading box
   is deleted pre-`live` with no other candidates): hold the last
   reported code with `detail` noting the operator event, until a new
   provisioning or a rule-7 restart supplies a candidate. Box identity
   rides `detail` as `"<existing sub-code> @ box=<box-name>"` (per the
   §3 exception — e.g. `box-unhealthy: relay-dial-failed @
   box=kitchen-pi`; for codes with no existing sub-code, `provisioning @
   box=<box-name>`); the `tenant_id` correlation aid is unchanged.
2. **Once the tenant is `live`, a different box's later provisioning never
   regresses the endpoint.** A second box's provisioning is a
   provider-layer event (H4 `BoxStatus` `creating/ready/degraded/dead`),
   surfaced by the dashboard Boxes panel — not by this endpoint. The
   tenant is onboarded; a page polling during second-box provisioning
   correctly keeps seeing `live`. Carve-out: reprovision of the live-anchor
   box (the box whose arc reached `live` first, per rule 1) follows
   transition rule 7's cross-session move (`live`/`approved` →
   `provisioning`, starting a new session). The new session is an
   ordinary candidate in rule 1's selection — it does not pin the
   endpoint: the carve-out licenses the resulting regression (e.g.
   `live` → `provisioning` on reprovision), and if the anchor's new
   session stalls while a second box's arc progresses, rule 1's
   dead-box-never-outranks-progressing preference applies unchanged.
   Operator reprovision is rule 7's path, not a second box's provisioning.
3. **S1 impact:** the tenant-record store keeps per-box arc records
   internally (keyed by box id) to evaluate the most-advanced-incomplete
   rule, but the response schema is unchanged — per-tenant, no `box_id`
   field.
4. **The stall detector emits one tenant-level stall.**
   `STUCK_DETECTOR_DESIGN.md` §8 Q2 delegates this to G7's decision: the
   detector evaluates per-box session arcs from the internal records
   (rule 3) but emits a single tenant-level stall — the 12-code
   vocabulary is per-tenant; per-box candidates are evaluation-internal
   to the detector and are not surfaced on this endpoint. (Closes Q2.)
5. **Explicit non-goal:** no per-box arc resource ships, and no shape is
   named or reserved, until a consumer demands per-box arc reads
   (dashboard v2, per-box approval routing under H10). YAGNI, per the
   layering §4.

### G8 — who writes `approvals_url`, and re-entry rotation

**Decision: the signup step that hands the human the approvals-page URL
owns the write — mint-once at activation-funnel stage 2
(`FIRST_TEN_MINUTES_SPEC.md` §4 item 1: the signup flow "must hand the
human" the approvals-page URL "no later than stage 2").**

Rules:

1. **Single writer, write-if-absent + re-read.** The stage-2 hand-over
   handler mints the URL, persists it through an idempotent
   write-if-absent, then **re-reads the record and renders the stored
   value**. "What the human saw" == "what the record holds" is enforced
   by the re-read, not by the mint: two concurrent stage-2 submissions
   can each mint locally, but the loser's write is a no-op and the loser
   renders the winner's stored URL — the human never holds a URL the
   record doesn't. **S1 store requirement:** the conditional write must
   be atomic/linearizable — under last-writer-wins, two concurrent
   read-absent submissions could both persist, and the loser would
   render a URL the record doesn't hold, breaking the invariant above.
   No other signup-flow step writes this field.
2. **Not minted at claim/record creation.** Pre-stage-2 the field is
   absent and the endpoint keeps its documented §3 `404` — unchanged.
   Minting at claim would create URLs for abandoned signups and would
   have licensed G4's summons sender to build deep links from a URL the
   human never saw.
3. **Funnel re-entry is a read path, never a rewrite.** The funnel
   re-enters at the first incomplete screen (`HOSTED_SIGNUP_WEB_UI.md`
   §5) — that step re-reads the stored value and re-renders it. A
   re-entering tenant never gets a rotated approvals URL mid-arc. (This
   is deliberately stricter than §5's screen-3 token rule, where a
   lost/expired token is replaced with a *fresh* token: the enrollment
   token is single-use by design, but the approvals URL is the address
   G4's summons deep-links and human bookmarks point at — rotating it
   mid-arc breaks both.)
4. **The only rotation path is an explicit operator event.** If rotation
   is ever required (suspected exposure, domain/path change — never a
   funnel side effect), the control plane rewrites the field as an
   explicit operator-side event that also re-notifies the human through
   the notification channel of record — following G4's retirement rule
   when H14 ships (the email summons channel retires to push; the
   re-notify path tracks the channel of record, not the retired one).
   Rotation is never a funnel side effect. Pre-launch: rotation is out
   of scope; mint-once is the complete contract.
5. **S1 impact:** the tenant-record store treats `approvals_url` as
   write-once-with-explicit-rotation; contract tests assert that
   simulated funnel re-entries at every stage return the identical URL.
6. **G4 unblocked:** `FIRST_APPROVAL_SUMMONS.md` §2's sequencing
   dependency is resolved — the deep link
   `<approvals_url>/approval/<aid>` is now licensed and the
   omit-the-link fallback is retired (see the paired edits in this PR);
   S2's sender can assume the carrier is present from stage 2 on.

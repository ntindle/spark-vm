# Per-tenant approval routing: vision vs state (#69)

**Vision-vs-state for #69** (p1/severity:high, hosted-product): "confirmd:
per-tenant approval routing and ownership for hosted product" — pinned to
main `57a4cfb` for all in-repo claims. #69 was filed 2026-09-19 from an arch
deep-read of `confirm/`; it has had zero comments since, while the #849
phone-approvals lane shipped the plane-side approvals path (#872 records,
#873 durable decision channel, #874 box ingest, #876/#952 filing upload,
#954 dashboard decide, and the #967–#1069 push lane). This analysis answers:
which of #69's claims still hold, which the shipped lane answers by
construction, and which gaps are genuinely open.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below is
current state and work to do, not promises. The hosted product is not live.

## 1. The vision, restated

From #69's body: confirmd is single-owner, single-tenant — one
`CONFIRM_OWNER`, one `APPROVALS` dir, one `push-subscriptions.json` / VAPID
identity, no tenant field on approval items, `/api/push/*` with no tenant
scoping, `_auth` against exactly one login. "Tenant #2 cannot be onboarded
without a second daemon, port, dirs, and VAPID keys." Fix direction: add a
tenant dimension — `CONFIRM_OWNERS` map, tenant-scoped approval dirs, tenant
field on items (set by the filer, validated by confirmd), per-tenant push
subscription stores. "Until then, document that one confirmd instance = one
tenant as a hard constraint." Blocks the hosted multi-tenancy story (H11).

## 2. What still holds — all four box-local claims verified on main

- **Single `CONFIRM_OWNER`**: `confirm/confirmd.py:95`
  (`OWNER = os.environ.get("CONFIRM_OWNER", "ntindle@github")`). One
  Tailscale LoginName; no map.
- **One `APPROVALS` dir**: `confirm/confirmd.py:96` (`APPROVALS =
  os.environ.get("CONFIRM_DIR", "/home/swapd/approvals")`), with
  `pending/`, `answered/`, `consumed/`, `pending-quarantine/` under it
  (:826–:891). No tenant-scoped subdirs.
- **One push subscription store**: `confirm/push.py:40-41, 241, 352` —
  `$CONFIRM_DIR/push-subscriptions.json`, one store, no tenant key.
- **Single-login `_auth`**: `confirm/confirmd.py:1886` — the owner check
  compares against the one configured login.

The H10 seams are reserved but unbuilt: consumed records stamp
`rec["tenant_id"] = None` ("Reserved for H10 (multi-tenant confirmd): null
means 'unscoped, single-tenant host' — today's exact semantic. No tenant
filter is invented before H10", :1113–:1116); `docs/APPROVAL_CLIENT_SIGNAL.md:95`
reserves `tenant_id` (null until H10); the H20 re-open docstring (:40–:42)
notes "the lineage fields make tenant scoping additive later". The
multi-tenancy audit agrees (A5, `docs/MULTI_TENANCY_AUDIT.md:53`): pending
queues, audit lines, and the CSRF nonce ring have no tenant key.

**So #69's box-local diagnosis is still accurate. Its prescription is now
partly obsolete** — see §3.

## 3. What the shipped lane already answers

**F-T1 — the plane side of per-tenant routing is built.** The
`#872`/`#876` record shape (`docs/APPROVALS_PLANE_PROTOCOL.md:31-52`) is
`(box_id, aid)` primary key plus `owner_id` (the #843 owner key that created
the record; NULL = box-filed provenance —
`docs/FILING_UPLOAD_GAP_ANALYSIS.md:186-199`). Every approvals endpoint is owner-key
authenticated except the write-only box-token `approvals/file`
(`docs/CONTROL_PLANE_API_REFERENCE.md:155-180`); a box can never read or
decide its own approvals. The push lane keys subscriptions
`(owner_principal, box_id, device)` with per-row AES-256-GCM at-rest
encryption and write-only-after-set (`docs/PUSH_SENDER_SCHEMA_CONTRACT.md:54-94,
D46`); the digest coalesces per owner (`hosted/push_events.py:460-490`,
`maybe_enqueue_digest`); the D10 page budget is per-(box,hour) and per-owner.
#69's "routing" — whose approval is whose, whose page goes where — is
answered on the plane by (owner, box) scoping, not by a confirmd tenant
dimension.

**F-T2 — #280's per-tenant box makes the box-local single-tenancy a
construction property, not a defect.** The audit ADOPTED per-tenant box for
#850 S1 (`docs/CREDENTIAL_VEND_CONTRACT.md:20-42`): "no tenant key lands in
`cred`, the registry, or the secrets dir"; `box_id` *is* the tenant identity
1:1 (:239). Tenant #2's onboarding is a second box with its own confirmd —
#69's "second daemon, port, dirs" sentence now describes the product shape,
not a workaround. The fix direction's first three items (owner map,
tenant-scoped dirs, tenant field on items) are answered by "one box per
tenant" for the hosted product.

**F-T3 — the VAPID onboarding cost is answered by design.** #69: "Tenant #2
cannot be onboarded without … VAPID keys." The push sender pins one plane
VAPID identity with per-(owner,box,device) D1 subscriptions
(`docs/PUSH_SENDER_SCHEMA_CONTRACT.md` D3, §3/D48): a new tenant subscribes
devices, nobody provisions keys. The one-identity trade-off is stated
plainly in the same contract: a VAPID private-key compromise enables
unauthorized sends as the plane identity to every subscription endpoint —
mitigated by Worker-secret custody plus the D48c rotation rule and the D48d
compromise response (rotate per D48c, audit sends under the old
`vapid_key_id`). (Separately, the D45 data key carries its own one-key
trade-off: one data key protects all tenants' subscription-secret
ciphertexts; a D1-only reader gets ciphertexts it cannot use without the
VAPID key.)

## 4. Genuinely open gaps

**G-T1 — the box-local H14 push has no hosted-mode handoff (new).** Every
refused swap on the box unconditionally enqueues to the box-local H14 push
queue (`proxy/swap_addon.py:399-421`, `_push_notify` — no hosted/plane gate
anywhere in `confirm/push.py` or `swap_addon.py`), and `push-worker.service`
is enabled by the standard box deploy (`proxy/deploy.sh:298`; the unit file
says it "runs wherever the deployment lives (self-hosted box or hosted
service)"). But a hosted tenant owner never subscribes locally — the H14
path's subscriptions live behind the confirmd page, which a hosted tenant
owner never reaches (`docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md:54-55`), while
the plane push lane does the actual paging. So on a hosted box: no box-local VAPID keys
→ the worker's `run_once` skips loudly every pass ("push-queue: worker pass
skipped — push disabled", rate-limited) and entries stay queued forever
(`confirm/push.py:725-745`) — an ever-growing queue journal of approvals the
plane already paged, plus a permanent loud warning. The box-local push path
is single-tenant (one store, one VAPID identity) AND plane-unaware; it needs
a hosted-mode routing decision: skip the local enqueue (and the worker) when
the plane push lane owns paging for the box — e.g. when the box is
plane-enrolled — and a bound on the queue journal either way.

**Handoff failure contract (load-bearing — the enqueue path's documented
guarantee is fail-open: "a push failure must never lose the filed approval",
`proxy/swap_addon.py`).** "Plane-enrolled" is not "plane-deliverable": an
enrolled box with zero `live` `(owner, box, *)` subscriptions gets no local
page (skipped) and no plane page (nobody to page) — total silence; D10
budget exhaustion, a plane send-path outage, or a stale box token produce
the same silence; and no local source of truth for "plane-enrolled" exists
in `swap_addon` today. So the skip predicate must be "the plane push lane
can actually page" — enrolled AND at least one live subscription for
`(owner, box)` (or a plane-side readiness signal) — with a defined fallback:
retain the local enqueue whenever the plane cannot actually page, so the
self-hosted deferred-delivery guarantee ("they deliver once the operator
configures keys") survives the handoff. The slice must name the fallback
explicitly; a gap analysis under honesty rules cannot propose removing the
only page path without naming what replaces its guarantee. The journal bound
is scoped to the hosted handoff — bounding the self-hosted journal would
trade away the deferred-delivery guarantee and is a separate product
decision.

**G-T2 — no owner-level cross-box pending aggregation (new).** The approvals
API is entirely box-scoped (`/v1/boxes/{box_id}/approvals*`,
`docs/CONTROL_PLANE_API_REFERENCE.md:155-180`); the #954 dashboard renders
pending approvals on the box detail card (`hosted/dashboard/dashboard.html:199-274`).
An owner with N boxes has no single pending queue — the "routing" half of
#69 for multi-box tenants. Either a build slice (owner-scoped pending list
across the owner's boxes) or an explicit non-goal decision with the
reasoning recorded.

**G-T3 — H10's remaining box-local scope needs a driver statement (open
question, not a new build).** Still genuinely open from H10
(`docs/APPROVALS_PLANE_GAP_ANALYSIS.md:190-196`): per-tenant pending queues,
tenant attribution on every approval and audit line ("until then the trail
answers 'what happened' but not 'for whom'", :224), roles beyond the single
`CONFIRM_OWNER`, and #194's multi-replica atomicity. But §3 above shrinks
H10's hosted driver: hosted tenant boxes are single-tenant by construction.
The remaining drivers are the shared/self-hosted multi-user box and H11's
tailnet-identity attribution substrate. H10 should record which driver it
serves before it gets built — otherwise it risks building multi-tenancy for
a box shape the product no longer ships.

## 5. Decisions pinned

- **D-T1** — #69's "one confirmd instance = one tenant" hard constraint is
  now the product's construction property under #280 (per-tenant box), not a
  stopgap. The "second daemon, port, dirs" sentence is superseded; the
  constraint it demanded is satisfied by the box shape.
- **D-T2** — Per-tenant approval routing in the hosted product lives on the
  plane ((owner, box)-scoped records, owner-key auth, (owner,box,device)
  push subscriptions, per-owner digest), not in confirmd. #69's routing
  vision is substantially realized there; confirmd keeps its single-tenant
  shape (for hosted per-tenant boxes — H10's shared/self-hosted multi-user
  driver is the G-T3 question, not a contradiction).
- **D-T3** — VAPID stays one plane identity (the D3 decision stands); #69's
  per-tenant VAPID-keys onboarding cost is answered, not open.
- **D-T4** — G-T1 and G-T2 are filed as build slices; G-T3 is folded into
  #69/H10 as a scoping question. #69 stays OPEN until G-T1/G-T2 land or are
  explicitly declined and H10's driver statement is recorded.

## 6. Slices filed

- G-T1 → **filed as #1135** (H14 hosted-mode handoff: skip the
  box-local push enqueue/worker when the plane push lane owns the box's
  paging; bound the queue journal; p2).
- G-T2 → **filed as #1136** (owner-level pending aggregation across the
  owner's boxes, or an explicit non-goal decision; p3).

Pointer comment on #69 records this analysis and the D-T1–D-T4 pins. #69
stays OPEN per D-T4.

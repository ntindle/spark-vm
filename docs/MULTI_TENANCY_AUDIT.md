# Multi-tenancy audit (H11)

Date: 2026-09-24 (build-loop gap turn; serves `last_build_archetype: gap`).
Audited commit: `b8511ad` (branch base; code-verified claims below).

This is the **audit half** of H11. The research half is
`docs/MULTITENANT_ISOLATION_RESEARCH.md` (vendor + OSS precedent, dated
2026-09-20, claimable/forbidden rules) — H11 adopts or rejects its five
research-shaped findings in §2, answers the four design questions in §3,
and recommends the isolation story in §4. It does not re-litigate the
already-decided context: BYO Tailscale (hosted unblock pass, 2026-09-19),
the jail as the agent's runtime cell, and the both-supported default.

Scope: the inventory in §1 covers **mutually-untrusted tenants** — the
bar for the hosted product. Self-hosted single-owner keeps the current
shape; where a finding doesn't apply there, the row says so.

## 1. Assumption inventory, ranked by blast radius

"Blast radius" = what one compromised or malicious tenant can reach,
assuming the other tenants are honest. Rows marked `[EXISTS]` have an
open GitHub issue; the two rows without a pre-existing issue (A1, and
the §6 open verifications) were filed this turn — linked in §7.

### Critical — one tenant can take another tenant's secrets

| # | Assumption | Code | Who can exploit | Existing / new |
|---|------------|------|-----------------|----------------|
| A1 | **The swap proxy trusts any local process.** Grants are host-wide, not job-scoped, and not tenant-scoped: "an HTTP request carries no unforgeable job identity, so any local process using the proxy can spend any active grant. Do not rely on grants for per-job isolation." (`proxy/swap_addon.py:111-114`) | proxy/swap_addon.py:111-114 | Any tenant process that can reach the proxy listener (localhost, or the jail DNAT — see A4) | [EXISTS] #339 |
| A2 | **The credential stack has no tenant dimension.** The `cred` CLI and the narrow writers it drives have no tenant key anywhere (`grep tenant cred` = no match). Secrets live in one shared stack per host. | `cred` (repo root, Python); registry | Any tenant that can invoke the writer path or reach cred-ui | [EXISTS] #280 (cred stack has no tenant dimension — hosted multi-tenancy blocker) |
| A3 | **cred-ui: localhost-only, zero user auth, zero systemd sandboxing.** The management API authenticates with a non-secret header only; the service file hardens nothing. On a shared host, "localhost-only" means "every tenant on the box". | cred-ui/cred-ui.py; cred-ui/cred-ui.service | Any tenant process on the shared host — full read/write of the credential stack | [EXISTS] #86, #281 (no auth), #115 (no hardening) |

Why A1 is the load-bearing finding: on today's single-owner box the
shared-host trust model is coherent — the jail's nftables egress DNAT
forces the agent's traffic through the host proxy (`jail/build.sh:159-162`),
and swapd holding secrets on the host is the vendor-endorsed
broker-outside-the-guest shape (research doc §"IMDS warning"). The
moment a *second* tenant lands on the same host, A1 + A2 turn the broker
into a shared secret dispenser: any local process spends any active
grant. **No per-tenant-processes shape is honest until A1 is fixed.**
Per-tenant boxes make A1 benign (one tenant per proxy); per-tenant
processes require the IMDSv2 treatment (research finding 2).

### High — one tenant can take another tenant's approvals / human trust

| # | Assumption | Code | Who can exploit | Existing / new |
|---|------------|------|-----------------|----------------|
| A4 | **All jails share one proxy.** The jail generalizes to N tenants only if each jail's egress DNAT points at a per-tenant proxy; today there is one proxy and one credential universe. | jail/build.sh:159-162 | Cross-tenant swap via A1, network-layer only via nftables | design consequence of §4 |
| A5 | **confirmd is single-owner.** `CONFIRM_OWNER` is one Tailscale LoginName; pending queues, audit lines, and the CSRF nonce ring have no tenant key. | confirm/confirmd.py:83 (`OWNER = os.environ.get("CONFIRM_OWNER", "ntindle@github")`) | Any second tenant's approval traffic would land in the same queue; a human can't attribute what they're approving | [EXISTS] #69 (per-tenant approval routing and ownership) |
| A6 | **Proxy-filed approvals carry no requester/job attribution.** The audit line records host/placeholder/egress IP, never who asked. With N tenants the "who asked" question is the entire audit story. | proxy/swap_addon.py:117-131 (audit line fields); per-filing code | Operator investigating a swap; a tenant disputing one | [EXISTS] #14 (proxy-filed approvals carry no requester/job attribution) |
| A7 | **The audit log has no tenant dimension.** Same gap as A6 at the log layer; a tenant-scoped audit needs the tenant key that doesn't exist yet. | swap log + confirmd audit trail | Forensic attribution across tenants | H10 scope (BACKLOG: "tenant attribution on every approval/audit line") |

### Medium — scale, hardness, hygiene

| # | Assumption | Code | Existing / new |
|---|------------|------|----------------|
| A8 | **Swap proxy services have no systemd hardening.** mitmdump runs as `swapd` with zero sandboxing directives; compromise of the proxy process yields the whole stack. | proxy/swap-proxy.service, proxy/swap-inference.service | [EXISTS] #95 |
| A9 | **confirmd has no multi-replica story** (in-process locks, per-aid lock entries never evicted, answered history bounded on disk). Hosted scale-out needs a shared-state design. | confirm/confirmd.py | [EXISTS] #194, #192, #193 |
| A10 | **muse-job is single-operator.** Job agents can reach management metadata (#11); no per-job identity, no per-tenant scoping. | muse-job/ | [EXISTS] #11 (job agent can rewrite ../job.json) |
| A11 | **Dev bridges (cua-bridge, bdrive) are localhost-bound single-tenant.** Fine for self-hosted; hosted needs per-tenant instances or removal from the tenant surface. | cua/bin/cua-bridge.py; browser-driver/bdrive/config.py | noted, no issue — out of hosted v1 scope until #47 ships |
| A12 | **The operator-with-sudo domain shares the box with everything.** The `ntindle`-with-sudo domain (hosted signup provisions a `spark` operator account) holds passwordless sudo on the same host as swapd's secrets and all tenant workloads. One human root takes the whole host. | design fact, verified in the research doc's "shared-root-domain" section | §3 Q4 — goes back to the operator for sign-off (recorded with the operator in the loop's NEEDS_USER.md, which lives outside this repo) |

Self-hosted single-owner verdict: rows A1–A3, A8, A12 describe the
*intended* single-owner trust model, not bugs, as long as the tenant
count stays one. The audit's "forbidden" rule: never market the current
box as multi-tenant-ready, and never add a second tenant without A1–A3
resolved. Cooperative same-household tenants (family, one operator) can
run on the per-tenant-processes shape with A1 acknowledged as
weaker-than-hardware — §4's honest label.

## 2. The five research-shaped findings: adopted or rejected

H11's ruling on `MULTITENANT_ISOLATION_RESEARCH.md`'s findings:

1. **Compute: per-tenant box is the vendor consensus for
   mutually-untrusted tenants; the jail generalizes honestly only if the
   weaker shared-kernel boundary is documented as such.** — **ADOPTED.**
   The audit's §1 inventory is the evidence: A1 is unfixable cheaply on a
   shared host, and "container-tier tenancy always paired with a stronger
   mechanism" is exactly what the jail lacks. The jail is a cost
   optimization for cooperative tenants, not a security equivalence.
2. **Proxy: outside the tenant guest, IMDSv2-style per-tenant request
   auth, tenant-scoped secrets, fail-closed on failure, every swap
   audited; workload identity with short-lived tokens is the endgame.** —
   **ADOPTED.** The broker-outside-the-guest placement is true today for
   the jail (swapd on host, placeholders only in the guest). The
   per-tenant auth half was filed this turn in §7 (#339); the swap path must
   authenticate *tenants*, not just requests.
3. **Tailnet: enrollment-time / new-request auth fails closed; existing
   sessions through a control-plane outage are fail-open for revocation
   semantics — unverified, and H11 must verify before relying on
   Tailscale for lockout.** — **ADOPTED, verification owed.** Filed as
   an open verification (filed this turn as #340). Until verified, no lockout
   semantics may assume outage-time revocation propagation; the designed
   failure mode is *stale authorization*, never *bypassed identity*.
4. **Root: tenant holds root inside their unit; the operator exclusively
   owns the layer below; never let the human's and the agent's privilege
   domains collapse into one.** — **ADOPTED**, with the sign-off
   question in §3 Q4.
5. **nsjail/bubblewrap sandbox individual tool executions inside the
   tenant boundary — not the tenant boundary itself.** — **ADOPTED as
   advisory.** No turn may cite nsjail as the multi-tenancy answer.

## 3. The design questions, answered

**Q1 — Isolation story: per-tenant box vs per-tenant processes vs
per-tenant tailnets. Recommend one explicitly.**

**Recommended: per-tenant box for mutually-untrusted tenants** — the
vendor consensus (E2B, Vercel, Runloop, AgentComputer, Cloudflare, Fly;
research doc vendor table). Fly Sprites is the decided provider and its
pattern (per-sandbox private network, isolation by default) maps
directly. Per-tenant processes (the jail, generalized) is the honest v1
for cooperative tenants and for the self-hosted path: cheaper, weaker,
documented as such — and it cannot host mutually-untrusted tenants until
A1 (tenant-bound swaps) is fixed. Per-tenant tailnets are the network
layer complementing either compute shape (BYO already decided), never
the answer on their own. **The audit forbids claiming "container
isolation equivalent to a VM" anywhere in copy or docs.**

**Q2 — Swap-proxy trust boundary vs tenant workloads.**

Today: the proxy trusts the *box* (IMDSv1), the broker sits outside the
agent guest (good — the jail keeps it there), and the audit write is
part of authorization (fail-closed when the trail can't be recorded —
good). For N tenants the boundary must move from *box* to *tenant*:
per-tenant request auth the tenant can't forge, swaps scoped to that
tenant's secrets, fail-closed on proxy failure (never pass through with
placeholders intact), every swap audited. Endgame is workload identity
with short-lived tokens so no long-lived-secret broker is needed at all.
The issue filed this turn in §7 (#339) is the design ticket for the transitional step.

**Q3 — Tailnet fail-open / fail-closed semantics.**

Adopted from research finding 3: (a) **enrollment-time and new-request
auth fail closed** — an auth-lookup failure denies; "ACL file
missing/unapplied" means deny; (b) **existing sessions through a
control-plane outage**: revocation cannot propagate during an outage —
fail-open for revocation, i.e. design for *stale authorization*, and the
outage-time behavior must be verified before any lockout semantics rely
on it (open verification, §7). Never assume an outage degrades into
bypassed identity checks.

**Q4 — Who holds root on a tenant box? (recommendation → operator
sign-off)**

Adopted from research finding 4, sharpened: on the per-tenant-box
shape, the **tenant (human owner) holds root inside their guest; the
operator owns the hypervisor/provider layer exclusively and has no login
inside the tenant guest**. The current shared `ntindle`-with-sudo
domain on the swapd host matches no vendor precedent and must be
retired for the hosted shape: operator tooling reaches the host through
a dedicated, audited operator plane (the H5 sentinel design rides on
this), never as a passwordless-sudo human co-resident with tenant
secrets. For the jail-per-tenant cooperative tier: operator holds host
root; tenants get contained guest-root-equivalent; secrets for the
cooperative tenants stay in swapd on the host under the operator's
exclusive domain. **The layer-boundary choice (hypervisor-only vs
operator login inside tenant guests) goes back to the operator for
sign-off — recorded with the operator in the loop's NEEDS_USER.md
(loop bookkeeping outside this repo).**

## 4. Gate release

H11 gates H5, H12, H13 (BACKLOG). This audit releases them to design.
H10 was never gated — it proceeds in parallel on a provisional
assumption this audit confirms; H9 carries no operator gate and is
noted here for consistency only.

- **H5 (sentinel):** the sentinel runs on the operator plane (§3 Q4),
  authenticates tenants by tailnet identity, and never shares a host
  with tenant workloads on the per-tenant-box shape. H5's design may
  proceed on that substrate.
- **H10 (multi-tenant approvals) + H12 (usage metering):** the tenant
  key is the **BYO per-tenant tailnet identity** — H10's provisional
  assumption ("attribution keys on tailnet identity") is consistent with
  this audit's answers. A5/A6/A7's fixes key attribution on it; H12's
  metering dimension is the same key.
- **H13 (free-tier suspend/wake):** idle detection keys on the same
  tenant identity; the H4 Fly driver contract extensions
  (`suspended`/`waking` + async `dial()`) remain gated on the operator's
  spend-cap packet (loop bookkeeping outside this repo), unchanged.
- **H9 (identity service):** no operator gate; the tailnet-shape
  conformance work (BACKLOG H9) is consistent with §3 Q3/Q4 as written.

## 5. Claimable vs forbidden (additions to the research doc's rules)

- **Claimable from this audit:** "H11's isolation recommendation:
  per-tenant box for mutually-untrusted tenants (vendor-consensus
  shape)"; "the jail is documented as a weaker-than-hardware boundary
  for cooperative tenants"; "swap-proxy trust model documented as
  host-wide grants (IMDSv1) pending per-tenant auth"; "fail-closed
  enrollment / stale-authorization outage semantics adopted".
- **Forbidden:** any claim that the current box hosts multiple tenants
  safely; "jail = VM-equivalent isolation"; "tailnets isolate tenants"
  (network only); citing this audit as the per-tenant implementation —
  it is the decision record, not the build.

## 6. Open verifications (unchanged from the research doc; filed §7)

- Nested-KVM availability on the hosted product's target hosts (decides
  whether Firecracker/Kata are even options; gVisor works regardless).
- Tailscale control-plane-outage semantics for lockout (fail-closed
  enrollment is architectural; existing-session revocation behavior
  needs verification).
- Vendor root semantics remain publicly undocumented — assert nothing.

## 7. Issues filed this turn

- **#339** — swap proxy: no per-tenant request authentication —
  host-wide grants (IMDSv1 trust model); tenant-bound swaps + per-tenant
  request auth required before any per-tenant-processes tenancy.
- **#340** — H11 open verifications: Tailscale control-plane-outage
  lockout semantics + nested-KVM availability on hosted target hosts.

Discovered-severity note: no live vulnerability is introduced by this
turn — the audit documents the existing single-owner trust model and
names the exact fixes that must precede a second tenant.

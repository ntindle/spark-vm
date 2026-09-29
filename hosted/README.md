# hosted — the hosted control plane's tenant layer (S1)

`GET /tenant/status`: the machine-readable onboarding status that the tenant
Muse (linked ed25519 key, signed requests) and the signup page (magic-link
session cookie) poll during the first-ten-minutes onboarding arc.

The full contract is `docs/TENANT_STATUS_ENDPOINT.md`. What this component
implements (G3 implementation slice S1):

- the 13-code §2 machine vocabulary, exactly spelled, with the operator-only
  codes (`policy-misfire`, `no-gated-action`) carrying no `human_key`;
- the §2 transition rules 1–8 (no backwards moves; the relay/cert suspension
  latch; the maintenance latch; the rule-7 session-restart carve-outs) as a
  tested event→transition mapping over per-box arc records;
- the JSON tenant-record store, with the `approvals_url` carrier minted once
  at signup stage 2 (write-if-absent + re-read, linearizable across processes
  via an `flock`'d lock — exactly one minter wins a concurrent stage-2 race;
  funnel re-entry is a read path; rotation only via an explicit operator
  event), and the §8 empty-candidate hold (when the leading box is deleted
  pre-`live`, the endpoint holds the last reported code with `detail` noting
  the operator event);
- the endpoint itself: two-sided auth, 401 when the caller's identity can't
  be established, 404 for valid credentials with no servable record (deleted
  or pre-stage-2), `Cache-Control: no-store`, and GET never changes state.

Run the tests: `python3 -m pytest hosted/` from the repo root.
Run the daemon: `python3 -m hosted.tenant_status --store /path/tenants.json`
(signed-request verification is wired by the control plane at deploy time —
the daemon refuses signed requests until then rather than trusting them).

Deliberately stdlib-only, so the module runs unchanged on the self-hosted
box, the hosted control plane, and the operator laptop. The ed25519 verify
primitive is injected (stdlib has no ed25519) — the endpoint never trusts
an unverified signature.

Slice boundaries: S2 wires the H4 driver's `BoxStatus` into the tenant
layer (the `live`-entry AND-combine is the `live_entry_ready` unit); S3
wires the readers (signup page meta-refresh, Muse poller).

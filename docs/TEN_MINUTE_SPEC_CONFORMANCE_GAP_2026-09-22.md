# First-ten-minutes spec conformance gap audit (2026-09-22)

The `docs/FIRST_TEN_MINUTES_SPEC.md` executable first-run spec (R1, shipped
2026-09-18) defines exact commands, pass criteria, a minute-by-minute script,
and follow-up build items. Four days of loop work later — waitlist invite
tooling, VAPID push, the R2 provision-time injector, deploy rollback manifests —
this audit checks each spec clause against the repo at `main` today, and turns
what's missing into build items. Complement to the earlier gap views
(`HOSTED_GAP_ANALYSIS.md` pipeline stages, `DAY_ONE_GAP_ANALYSIS.md` five
surfaces, `APPROVALS_PLANE_GAP_ANALYSIS.md` return leg): this one is
spec-clause vs code, not vision vs state.

Verdict key: **Met** — exists and the spec's command passes as written;
**Partial** — exists but a named precondition is unmet; **Missing** — nothing
in the repo implements the clause; **Stale** — a doc line contradicts a later
decided position.

## §2 — the clock and the status poll

**Missing.** The spec's machine vocabulary
(`provisioning`, `live`, `waiting-on-approval`, `approved`, `box-unhealthy`,
`connection-unreachable`, `policy-misfire`, `no-gated-action`, `human-denied`,
`human-drop-off`, `stuck`, `provisioning-failed`) has no implementing endpoint.
`harness/provider_iface.py` exposes provider-layer `BoxStatus` (provider state
machine: provisioning/running/suspending/…) — the wrong layer; it carries no
onboarding-script states and no `approvals_url`. No `GET /tenant/status`
exists. **Item G3** (below).

## §3a — smoke: proxy placeholder swap

**Partial.** `cred-store-set` writer, `proxy/sudoers-swapd`, and `with-proxy`
all exist; the swap path itself is covered by `test_swap_addon.py`. What's
missing is the §10 follow-up the spec filed for the provisioning track: the
operator-run `smoke.<domain>/echo` endpoint is **not** in
`proxy/hosts.allow` (no `echo`/`smoke` entry), and no provision-time step
installs the `smoke-test` dummy credential or extends a scoped sudoers entry
to the tenant agent user. The R2 injector (`harness/inject-provision-state.sh`)
shipped the injection mechanism but no smoke fixture. **Item G6.**

## §3b — smoke: muse-job hello spawn

**Met (CLI level).** `muse-job spawn <slug> --repo <url>
--prompt-file <file>` exists (`muse-job/TOOL_INTERFACE.md`) and `status`
reports the worktree/tmux machinery. Actual execution of the hello job needs
an inference key on the box — the spec already prices that as a real,
optional spend.

## §3c — smoke: CUA screenshot

**Met.** `/api/screenshot` is implemented in `cua/bin/cua-bridge.py`
(localhost-only), matching the spec's command.

## §3d — smoke: confirmd active

**Met.** `confirmd.service` + `confirm/confirmd.py` exist.

## §4 — the human half and the summons

**Partial, with a new finding.** The approvals detail page exists as
`GET /approval/<id>` with Approve/Deny buttons (`jail/confirm-page.md`).
The summons mechanism does **not**: the spec's default channel is email via
the operational AgentMail identity on filing, retiring when H14 ships — but
no email sender is wired into `_file_approval` (`proxy/swap_addon.py`), and
the shipped H14 component (`confirm/push.py`, VAPID Web Push) requires a
browser subscription created by a human who has *opened the page* — which, in
the hosted first run, only happens after the first summons arrives. So the
first approval's summons has no channel at all: push can't reach a human who
hasn't subscribed, and email was never built. **Item G4.** (The spec's own
"one reminder at T+TTL/2" and the two-tap copy stay design-valid; the gap is
the trigger mechanism, not the copy.)

Also **fixed this run**: the R1 backlog's non-blocking follow-up — the
"operator-only, no human rendering" note for `policy-misfire` /
`no-gated-action` — was never added to §4; it is now in §4's rendering table
as an italic operator-only marker.

## §5 — harness pre-seed contract (R2's interface)

**Partial.** The probe contract the spec fixes (`harness/harness-auth-probe`
with gate vs provision modes) exists, and the highest-risk unknown was
validated (`docs/CLI_KEY_AUTH_VALIDATION.md`: all three static-key paths
through the inference proxy, 12/12 each). What remains is the feature half —
golden-image manifest + provision-time injector wiring + gate — still open as
backlog R2. The top-3 snag list the spec asks R2 to deliver alongside the
probe is likewise still the feature run's deliverable, not a repo artifact.
No new item: covered by open R2.

## §6 — the first-task slot

**Partial, unchanged since R1.** The §6.6 client-visible pending /
terminal-decision signal **still does not exist** — on swap refusal the
proxy returns `None` (upstream sees a remote auth failure); on egress refusal
the connection is killed. Tracked as open H18 / GitHub #133, with the expiry
companion as G1 / #213 and the poll-cost follow-up as G2 / #214. The minute
5–8 script remains unexecutable without it — the single biggest
pre-launch build item, no change in status. No new item: H18 already tracks.

## §6.7 — golden-image round-trip gate

**Missing (procedure).** Gate-fixture tooling exists
(`harness/install-gate-fixture.sh`, `check-image-manifest.sh`) but there is
no §6.7 gate *procedure* doc: file → human answers → grant mints → task
verifies, with the filing-count determinism check (§8 `policy-misfire`).
**Item G5.**

## §7 — async-human rule

**Partial.** 1-hour approval expiry stands (`_file_approval` expires now+1h;
`confirm-request --ttl` defaults 3600). The TTL *policy* — "bounds
attacker-held requests without punishing a slow human" — is still undecided
(Abuse-controls track). The `human-drop-off` instrumentation on expiry exists
as `expired-reaped` in the audit log (per the G1 analysis), but the
agent-side terminal record for expiry is still missing (open G1 / #213).
No new item: covered by open G1.

## §8 — failure taxonomy

**Partial.** `provisioning-failed` instrumentation is H4's open work (the
fly-driver provisioning track); the rest of the taxonomy lives in spec text
only, except `human-drop-off` (audit-log `expired-reaped`) and the
`box-unhealthy` semantics the §2 script defines on top of the smoke checks
— both of which depend on the missing §2 status poll (G3). No new item beyond
G3.

## §9 — honesty rules

**Fixed this run.** The §10-flagged staleness was still live:
`docs/HOSTED_SIGNUP_ONBOARDING.md` §5 said "pick plan (free tier first; paid
later)" and its landing-page copy recommended "free tier … for adoption" —
contradicting the decided Billing item (no free tier at launch;
card-required trial possible, not promised). Both lines corrected to
paid-tiers-plus-possible-trial, with trial terms TBD.

## §10 — follow-ups, status

| Follow-up | Status |
|---|---|
| Signup doc §5 vs Billing decision | **Fixed this run** (§9 above) |
| Smoke echo endpoint / smoke-test credential / tenant-user sudoers | Still open → **G6** |
| Client-visible pending signal (§6.6) | Still missing → open H18/#133, G1/#213 |
| `<harness-auth-probe>` | Interface exists; feature half open → open R2 |
| First-task text | Gated on pilot R7 decision gates — still gated |
| Push summons | Partial: VAPID push exists but can't summon the first approval → **G4** |
| `provisioning-failed` instrumentation | Still open → open H4 |

## New items

- **G3** — Tenant onboarding status poll: implement the §2 machine vocabulary
  and `GET /tenant/status` carrying `approvals_url` in the tenant record.
  Distinct layer from `harness/provider_iface.py`'s provider states.
- **G4** — First-approval summons channel: the first summons has no mechanism
  (VAPID needs a pre-existing browser subscription; no email sender on the
  filing path). Wire a fail-open email summons into `_file_approval` (AgentMail
  identity per the spec), or redesign the summons around a contact collected
  at signup.
- **G5** — Golden-image round-trip gate procedure (§6.7): file → answer →
  grant → verify with the filing-count determinism check, reusing the gate
  fixture scripts.
- **G6** — Smoke-check provision assets (§3a): `smoke.<domain>/echo` allowlist
  entry, provision-time `smoke-test` dummy install, scoped sudoers for the
  tenant agent user.

Fixed in this run (no new items): signup-doc free-tier staleness (§9),
`policy-misfire`/`no-gated-action` operator-only note (§4).

# First-ten-minutes spec (R1) — the exact hosted first run

**Status: design thinking, not a commitment.** This is the executable
first-run spec: the minute-by-minute script a tenant Muse follows from
box-live, with exact commands, pass criteria, and the pre-seeded-state
contract. It is the R1 item from the 2026-09-18 adoption research
(`docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md`, open PR #25), and it extends
`docs/HOSTED_SIGNUP_ONBOARDING.md` §8 (open PR #24).

**Non-overlap map (what this doc is not):**
- The funnel-level activation framework (stages, aha definition,
  metrics, trial framing) is `docs/FIRST_RUN_ACTIVATION.md` (open
  PR #37). This doc is the command-level spec that framework points at;
  it does not re-argue the funnel.
- The canonical tiny task's *concrete text* is **gated on the pilot**:
  `docs/RESEARCH_FIRST_RUN_PILOT.md` (open PR #32) §5 defines the
  prototype task under test, and §10 says Phase B data completes this
  spec. §6 below names the task slot and its required properties —
  it does **not** harden a task text into the product early.
- Pre-seeded harness onboarding state (golden image / provision-time
  injection) is **R2** (a feature). §5 defines the *contract* R2 must
  satisfy; R2 owns the implementation.
- Identity linking, provisioning, and the signup flow mechanics are the
  signup doc (§4–§7). Pricing/trial terms are
  `docs/PRICING_THINKING.md` (open PR #30).
- Claims and voice obey `docs/POSITIONING.md`'s anti-claims — §9 repeats
  the binding ones.

## 1. The clock

- The 10-minute clock **starts at box-live** — the moment the tenant
  status poll flips to `live` for both the signup page and the Muse's
  `GET /tenant/status` poll — and not at signup. Provisioning
  (~15 minutes on the cloud-init path per the signup doc §5) happens
  before the clock. The signup page must say this plainly so nobody
  stares at a spinner and calls it onboarding friction.
- The clock measures the **Muse's** first session; the human half is
  async by design. Reconciliation with the activation framework, stated
  once so the two docs can't be cited against each other: the
  activation doc §1's 10-minute window governs the **Muse-side script**;
  its §5 async-human requirement governs the **human half**. "First run
  in 10 minutes" means the Muse reaches `waiting-on-approval` in
  ≤10 minutes, with the working approval completing asynchronously
  after. A trial where the human answers in 30 minutes is a slower
  trial, never a failed one.
- The script must complete **with zero human-credential steps** after
  identity linking: after the human approves the key fingerprint at
  signup, the Muse goes from box-live to first-filed-approval without
  any human touching a credential. (Decided 2026-09-18: launch has no
  free tier; a card-required trial is the abuse control. "Works
  immediately" means zero human-credential steps, not zero human steps —
  the human's two taps on the approval page *are* the product working.)
- The human does **exactly one thing** in the first 10 minutes: answer
  the approval when the summons arrives (§4). No page-checks, no
  setup, no credentials.

## 2. Minute-by-minute script

| Min | Step | Muse does | Pass criterion |
|---|---|---|---|
| 0:00 | Box-live | Status poll flips; Muse opens the connection bundle (relay hostname + SSH cert from signup) | `ssh` connects, cert accepted. If the relay/cert path fails while the poll says live → `connection-unreachable` (control-plane/relay defect, §8), not a Muse failure |
| 0–1 | Trust verify | Confirm the box is the provisioned tenant box: cert fingerprint matches the tenant record (the signup doc §4's term); `systemctl is-active swap-proxy confirmd` | Both active; fingerprint matches |
| 1–3 | Smoke checks | §3, in order | All four green |
| 3–4 | Harness probe | §5: non-interactive auth probe | Exit 0, no prompt, stdin closed |
| 4–5 | Approvals-URL check | Muse reads the approvals URL from the tenant status record — the URL handed to the human at signup stage 2 (per `docs/FIRST_RUN_ACTIVATION.md` §5). This is a signup-flow dependency, not a Muse verification of the human: the tenant record MUST carry `approvals_url` from signup | `approvals_url` present in the tenant record |
| 5–8 | First task | §6: run the gated first task | Approval request filed; task parks on the client-visible pending signal (§6.6) |
| 8–10 | Park + report | Task state parked; Muse reports `waiting-on-approval` on the tenant status poll and idles | Status poll shows the machine status; human page shows the human rendering (§4) |

If any smoke check fails, the box is **unhealthy**: the Muse reports
`box-unhealthy: <check>` on the tenant status poll and stops —
onboarding never proceeds on a failing box. The operator's
reprovision path (not the tenant Muse) owns recovery. A failed smoke
check is a provisioning defect, not user error, and must be
instrumented as such.

**Status vocabulary** (machine codes on the tenant status poll; human
renderings in §4): `provisioning`, `live`, `waiting-on-approval`,
`approved`, `box-unhealthy`, `connection-unreachable`,
`policy-misfire`, `no-gated-action`, `human-denied`, `human-drop-off`,
`stuck`, `provisioning-failed`.

## 3. Smoke checks (exact)

Run in order. Each is a single command with a machine-checkable pass
criterion. All paths below exist in the repo today.

**3a. Egress proxy swaps a placeholder.** The golden image ships a
`smoke-test` credential installed via the standard writer (value is a
public dummy, never a secret — provision-time asset, see the §10
follow-up) and a smoke echo endpoint in the golden image's
`hosts.allow` (operator-run, echoes the POST body). The check exercises
the placeholder → swap → response path (form-body swap path only —
JSON-body and header/query placeholder paths are out of scope for the
smoke check):

```bash
printf 'smoke-ok' | sudo -u swapd cred-store-set smoke-test
printf 'key=hsurr:smoke-test' | with-proxy \
  curl -s -X POST --data-binary @- https://smoke.<domain>/echo
```

Pass: the response body contains `smoke-ok`. This proves the proxy is
listening on 127.0.0.1:18080, the swap addon substituted the
placeholder, and the audit write succeeded (the swap path refuses when
the audit line cannot be written — `swap_addon.py::_audit`). Note the
`sudo -u swapd` hop: the shipped `proxy/sudoers-swapd` grants the
writers only to `ntindle` — the provisioning sequence must extend a
scoped sudoers entry to the tenant agent user, or the smoke credential
can't be installed by the golden-image build. Fail cases: proxy not
listening, CA bundle missing, credential not installed — all
provisioning defects.

**3b. muse-job runs a hello job.**

```bash
SLUG=hello-$(date +%s)
printf 'Create the file /tmp/smoke-ok containing the single word READY, then stop.' \
  > /tmp/hello-prompt.md
muse-job spawn "$SLUG" --repo https://github.com/ntindle/spark-vm --prompt-file /tmp/hello-prompt.md
muse-job status "$SLUG"
```

Pass: `spawn` exits 0 and `status` shows the job's worktree and tmux
session alive. The job itself completes async; the check is that the
job machinery (worktree + branch + tmux + hooks) is functional, not
that the hello prompt finished inside the window. (The hello job is a
real, small inference spend on the tenant box — the operator may
disable it in golden-image config; the other three checks are free.)

**3c. CUA desktop screenshot.**

```bash
curl -s http://127.0.0.1:18731/api/screenshot -o /tmp/first-desktop.png
file /tmp/first-desktop.png
```

Pass: a non-empty PNG. Proves the CUA bridge and the desktop stack
(Xvfb/XFCE) are up. The bridge is localhost-only; the tenant Muse runs
this over its SSH session.

**3d. confirmd is serving.**

```bash
systemctl is-active confirmd
```

Pass: `active`. confirmd is tailnet-only (`confirmd.service`); the
check is service-level from the box. The human-facing page is §4,
owned by the human side.

## 4. What the human has (handed at signup, before the clock starts)

The signup flow must hand the human, no later than stage 2 of the
activation funnel:

1. The **approvals-page URL** (the summons destination).
2. The **one-command cred-ui tunnel script** (the designed-manual step;
   trust-depth, not activation — the signup doc §8 already ruled that
   gating activation on it would crater the funnel number).
3. The plain-language statement that their only required action in the
   first 10 minutes is **answering the approval when it arrives** —
   and that answering late slows the trial but never fails it (§7).

A destination without a summons is not a funnel: the first approval
must actively reach the human. The summons spec:

- **Trigger:** the first approval request files.
- **Content:** deep link to `GET /approval/<id>` (the shape exists in
  `jail/confirm-page.md`: detail with Approve / Deny buttons),
  the requested action named in plain language, and the two-tap
  instruction — open the approval, tap **Approve**, the grant is
  minted and the Muse proceeds (two-tap Approve per PR #20).
- **Channel:** email, sent by the control plane via the operational
  AgentMail identity when the request files. (The signup flow collects
  an email for the magic-link account and no DM handle anywhere — so
  email is the default; there is no DM option until a handle is
  collected.) One reminder re-send at T+TTL/2 if unanswered; then the
  request expires into `human-drop-off` (§8).
- **Minimum page support** for this spec's funnel event to be
  answerable: the hosted approvals page must render a per-approval
  detail with Approve / Deny. Fuller interaction design (history,
  push, multi-tenant queues) stays scoped to H1/H2/H10/H14 — this
  spec does not redesign the page.
- The email summons retires when the push service (H14) ships; until
  then the signup page must not imply push exists.

**Human-facing copy** (exact sentences the signup page and emails use —
no paraphrasing the funnel's highest-predicted-drop-off moment):

- Provisioning: "Your box is being provisioned — about 15 minutes.
  The 10-minute first-run clock starts when your box goes live, not
  now. Nothing for you to do yet."
- The one required action: "Your Muse will ask for your approval to
  run its first task. When the email arrives, open it and tap Approve
  — two taps, and your Muse continues. Answering late just means a
  slower start, never a failed one."
- Channel honesty: "Approvals arrive by email for now. Push
  notifications are coming later."
- Waiting: "Waiting on your approval — open the email and tap Approve
  to let your Muse continue."

**Stage renderings** (what the human sees on the signup page per
machine status):

| Machine status | Human sees |
|---|---|
| `provisioning` | "Setting up your box… about 15 minutes." |
| `live` | "Your box is live — your Muse is running its first checks." |
| `waiting-on-approval` | "Waiting on your approval — open the email and tap Approve to let your Muse continue." |
| `approved` | "Approved — your Muse is finishing its first task." |
| `human-denied` | "You tapped Deny. Your Muse stopped its first task and won't ask again this session." |
| `human-drop-off` | "The approval request expired before you answered. Your Muse is parked — ask it to try its first task again whenever you're ready." |
| `box-unhealthy` | "Your box failed its health checks — we're reprovisioning it. Nothing for you to do." |
| `connection-unreachable` | "We can't reach your box — our relay is having trouble. We're on it." |
| `stuck` | "Your Muse's first session stalled. We're looking into it." |
| `provisioning-failed` | "Box setup failed — we're retrying." |

*Operator-only codes — instrumented, no human rendering:* `policy-misfire`
(the §6.7 golden-image gate measured a filing-count defect: zero or 2+
filings for the first task) and `no-gated-action` (the Muse never attempted
the gated action) never surface on the signup page. Per §7, conflating them
would misattribute the funnel's predicted drop-offs; they belong to the
operator's gate and pilot analysis only.

## 5. Harness pre-seed contract (R2's interface)

The golden image (or provision-time injection — R2's implementation
choice) must provide the agent harness's onboarding state such that **no
first-run picker, login prompt, or interactive setup ever appears**.
The contract the tenant Muse verifies:

```bash
</dev/null timeout 10 <harness-auth-probe>
```

- Exit 0, no prompt, with stdin closed and a 10-second cap.
- `<harness-auth-probe>` is R2's to define per harness (it is the
  non-interactive auth check for whatever agent runtime the tenant
  Muse drives). This spec does not invent the harness's auth
  mechanism; it fixes the interface the probe must satisfy.
- If the probe prompts or times out, the box fails the harness check:
  same handling as a failed smoke check (§2) — report and stop, do
  not improvise credentials or walk the human through a login inside
  the first-run window.

The top-3 snag list (whatever still needs a human after R2) is R2's
deliverable alongside the probe — this spec consumes it, doesn't
write it.

## 6. The first-task slot (pilot-gated)

The first task occupies minutes 5–8 and must satisfy these properties —
they are the spec; the concrete task text is not:

1. **One bounded action**, completable in minutes, requiring no
   credentials and no prior tenant state.
2. **Filing determinism comes from the request pattern, not a policy
   engine.** There is no "starter confirmd policy" component:
   approvals are filed by the egress proxy on grant refusal
   (`proxy/swap_addon.py::_file_approval`, line 582), coalesced per
   (credential, host, method) with at most 5 pending per credential
   and one filing per credential per 60 seconds (lines 629–641). So
   "the first task files exactly one approval" is a constraint on the
   task's request pattern — one gated request type, single attempt —
   not a property any policy guarantees. The golden-image gate (§6.7)
   verifies the pattern files exactly one request on every image. (If
   the product later needs mechanism-level single-approval
   determinism, that is new per-task approval budgeting — not
   designed here.)
3. **Verifiable end-to-end**: after the human answers, the Muse can
   observe the grant took effect (re-run the gated action, see it
   succeed) — the pilot's "working approval" definition
   (request → answer → grant minted → task verifies).
4. The task brief **never mentions approvals, confirmd, or the proxy**.
   Whether the Muse discovers the loop unprompted is the measurement —
   the pilot's §2 aha definition and §6 approval-discovery metric —
   and, in production, the aha (activation doc §1).
5. The task is **identical for every tenant** until pilot data says
   otherwise — comparability is a feature, not a limitation.
6. **Client-visible pending signal (required interface).** The gated
   action's client-visible behavior on filing must be a
   machine-readable pending signal carrying the approval id — and it
   must also deliver the terminal decision (approved / denied /
   expired) per approval id. As the code stands today this does not
   exist: on swap refusal the proxy returns None (the placeholder goes
   upstream untouched, surfacing as a remote auth failure); on egress
   refusal the connection is killed. Neither is a signal the Muse can
   park on, so the minute 5–8 script is not executable without it. The
   proxy/confirmd track owns the mechanism; this spec requires the
   interface. Pre-launch build item (§10).
7. **Golden-image gate (full round trip).** The operator verifies on
   every golden image that the first task files, the human can answer,
   the grant mints, and the task verifies end-to-end — mirroring the
   pilot's §5.1 gate, which this section generalizes. A golden image
   that files but can't answer/mint fails the gate. The existing
   1-hour approval expiry (`_file_approval` sets
   `expires = now + 1h`; `confirm-request --ttl` defaults to 3600) is
   the TTL starting point for the §7 policy, not greenfield.

The current prototype of this slot is the pilot's §5 canonical task
("check whether your box can reach the internet"), which the R7
protocol will test once beta-Muse recruitment unblocks (pilot §9).
**This spec does not adopt it as the production task.** Per the
pilot's §10, Phase A constrains the task-half shape and Phase B
completes this spec — the decision gates fire in order, and this
section updates when they do.

## 7. Async-human rule (binding)

The 10-minute script ends with the task **parked on a pending
approval**, not with the approval answered. The human answers
asynchronously:

- The Muse's session ends "staged": smoke green, harness green, one
  approval filed, task parked. The status poll reads
  `waiting-on-approval`; the human page shows the §4 rendering.
- A human who answers in 30 minutes gets a slower trial, never a
  failed one. Approval requests must remain answerable asynchronously —
  pending requests need a TTL policy that bounds attacker-held requests
  without punishing a slow human (Abuse-controls loop work; the
  mechanism is undecided, the requirement is not; the 1-hour default
  in §6.7 is the starting point).
- Sessions where the human never answers stay `waiting-on-approval`
  until TTL expiry; expiry is instrumented as `human-drop-off`, not
  folded into Muse-side failure. Conflating the two would misattribute
  the funnel's biggest predicted drop-off (the signup doc §8 names the
  human step as the one to watch).

## 8. "Done" criteria (observable)

- **First-run done (Muse side, ≤10 min from box-live):** SSH trust
  verified, all four smoke checks green, harness probe green, first
  task filed its (gate-verified single-pattern) approval request,
  session parked with `waiting-on-approval`. Zero human-credential
  steps occurred.
- **Activated (funnel, async):** first *working* approval — request
  filed through confirmd, human answered on the page, grant minted,
  task verified end-to-end — followed by the Muse-side aha (the Muse
  anticipates the approval loop on a second, unprompted task).
  Per the activation framework, a run that needed operator
  hand-holding to reach the working approval is trial-converted, not
  activated.
- **Failure taxonomy (instrument each separately; owner in parens):**
  - `provisioning-failed` — the ~15-min provision never reaches
    box-live (H4's instrumentation; out of this spec's scope, in the
    funnel's — plausibly the largest early drop-off).
  - `connection-unreachable` — box live per the status poll, tenant
    SSH via the relay fails (control-plane/relay defect).
  - `box-unhealthy` — any smoke/harness check fails (provisioning
    defect; reprovision, don't onboard).
  - `policy-misfire` — the golden-image gate measured a filing-count
    defect: zero filings for a task that *does* take the gated
    action, or 2+ filings (gate/pattern defect — the §6.7 gate owns
    detection).
  - `no-gated-action` — the Muse never attempted the gated action
    (discovery failure — the pilot's core signal, pilot §6; distinct
    from `policy-misfire` by the doc's own §7 standard: conflating
    them would misattribute).
  - `human-denied` — the human answered deny (engaged refusal, the
    opposite signal from absence). The Muse reports the denial and
    ends the first-run attempt; **no re-filing within the first-run
    window**.
  - `human-drop-off` — TTL expiry with no answer.
  - `stuck` — session abandonment per the pilot's rule: 30 minutes
    with no Muse action and no pending approval.

## 9. Honesty rules (binding)

From `docs/POSITIONING.md` anti-claims plus the operator decisions
(`NEEDS_USER.md`, 2026-09-18):

- Billing: **no free tier at launch**; a card-required trial is
  *possible*, not promised. Never write "free trial" as a launch
  commitment; trial terms are TBD.
- "No session clock" is a paid-tier property. Never print it adjacent
  to the trial row; the trial's suspend behavior is Abuse-controls
  work, not a headline.
- Never present the sentinel as shipped; name it as future or not at
  all. This spec's trust story is approvals + audit lines, which exist.
- Claims stay on the self-hosted reality until the hosted product
  exists: this spec is design thinking, not a ship announcement.
- The signup doc §5's "free tier first" plan-picker lines were **stale**
  against the decided Billing item; corrected 2026-09-22 (paid tiers;
  card-required trial possible, trial terms TBD —
  `docs/HOSTED_SIGNUP_ONBOARDING.md` §5). This spec follows the decision,
  not the stale line.

## 10. Follow-ups

- **Signup doc §5 vs Billing decision:** "free tier first" contradicts
  the decided no-free-tier launch. Update when PR #24 lands (or in a
  PR against it): plan picker becomes paid-tiers-plus-possible-trial,
  with trial terms TBD.
- **Smoke echo endpoint:** §3a needs an operator-run echo endpoint in
  the golden image's `hosts.allow`, the `smoke-test` credential
  installed at provision time (never committed), and the scoped
  sudoers extension for the tenant agent user. Small build; file it
  for the provisioning track (H4) or a `distribution` turn.
- **Client-visible pending signal:** §6.6's machine-readable
  pending/terminal-decision signal does not exist in the proxy or
  confirmd today — pre-launch build item for the proxy/confirmd
  track, or the minute 5–8 script stays unexecutable.
- **`<harness-auth-probe>`:** R2 defines the concrete probe per
  harness; this spec's §5 is the interface it must satisfy.
- **First-task text:** gated on the R7 decision gates (§6). When Phase
  B fires, this section gets the validated task text and the §6.7
  golden-image gate procedure.
- **Push summons:** §4's email fallback retires when H14 ships.
- **`provisioning-failed` instrumentation:** H4's funnel work — the
  stage 2→3 death needs a bucket and an owner before launch metrics
  mean anything.

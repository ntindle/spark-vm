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
- The clock measures the **Muse's** first session, not the human's.
  The human-side aha (answering the approval) is explicitly async —
  see §7. A trial where the human answers in 30 minutes is a slower
  trial, never a failed one.
- The script must complete **with zero human-credential steps** after
  identity linking: after the human approves the key fingerprint at
  signup, the Muse goes from box-live to first-filed-approval without
  any human touching a credential. (Decided 2026-09-18: launch has no
  free tier; a card-required trial is the abuse control. "Works
  immediately" means zero human-credential steps, not zero human steps —
  the human's two taps on the approval page *are* the product working.)

## 2. Minute-by-minute script

| Min | Step | Muse does | Pass criterion |
|---|---|---|---|
| 0:00 | Box-live | Status poll flips; Muse opens the connection bundle (relay hostname + SSH cert from signup) | `ssh` connects, cert accepted |
| 0–1 | Trust verify | Confirm the box is the provisioned tenant box: cert fingerprint matches the enrollment record; `systemctl is-active swap-proxy confirmd` | Both active; fingerprint matches |
| 1–3 | Smoke checks | §3, in order | All four green |
| 3–4 | Harness probe | §5: non-interactive auth probe | Exit 0, no prompt, stdin closed |
| 4–5 | Approvals page check | Confirm the human has the approvals URL (handed at signup stage 2, §7) — the Muse does not file anything yet | URL known to the human side |
| 5–8 | First task | §6: run the gated first task | Exactly one approval request filed; task parks on pending |
| 8–10 | Park + report | Task state parked; Muse reports session status ("smoke green, task staged on approval <id>") and idles | Status line visible to the human; no spinning |

If any smoke check fails, the box is **unhealthy**: the Muse reports
`box-unhealthy: <check>` and stops — onboarding never proceeds on a
failing box. The operator's reprovision path (not the tenant Muse) owns
recovery. A failed smoke check is a provisioning defect, not user error,
and must be instrumented as such.

## 3. Smoke checks (exact)

Run in order. Each is a single command with a machine-checkable pass
criterion. All paths below exist in the repo today.

**3a. Egress proxy swaps a placeholder.** The golden image ships a
`smoke-test` credential installed via the standard writer
(`printf 'smoke-ok' | cred-store-set smoke-test`, value is a public
dummy, never a secret) and a smoke echo endpoint in the golden image's
`hosts.allow` (operator-run, echoes the POST body). The check exercises
the full placeholder → swap → response path:

```bash
printf 'key=hsurr:smoke-test' | with-proxy \
  curl -s -X POST --data-binary @- https://smoke.<domain>/echo
```

Pass: the response body contains `smoke-ok`. This proves the proxy is
listening on 127.0.0.1:18080, the swap addon substituted the
placeholder, and the audit write succeeded (the swap path refuses when
the audit line cannot be written — `swap_addon.py::_audit`). Fail:
proxy not listening, CA bundle missing, or `smoke-test` not installed —
all provisioning defects.

**3b. muse-job runs a hello job.**

```bash
printf 'Create the file /tmp/smoke-ok containing the single word READY, then stop.' \
  > /tmp/hello-prompt.md
muse-job spawn hello-$(date +%s) --repo <spark-vm repo URL> --prompt-file /tmp/hello-prompt.md
muse-job status hello-<slug>
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
check is service-level from the box. The human-facing page check is
§4, owned by the human side.

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
must actively reach the human. The push service (H14) is the
production summons; until it exists, the fallback is the channel the
human already watches — email via the operational AgentMail identity,
or a DM — sent when the first request files. The signup page must not
imply push exists before H14 ships.

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
2. Under the **starter confirmd policy** it files **exactly one**
   approval request — no more, no fewer. The starter policy (the
   pilot's §5 policy file is the prototype of the production default)
   is what makes this deterministic, not the task text. The §5.1
   readiness gate generalizes: the operator verifies on every golden
   image that the first task files before any tenant sees it.
3. **Verifiable end-to-end**: after the human answers, the Muse can
   observe the grant took effect (re-run the gated action, see it
   succeed) — the pilot's "working approval" definition
   (request → answer → grant minted → task verifies).
4. The task brief **never mentions approvals, confirmd, or the proxy**.
   Whether the Muse discovers the loop unprompted is the measurement
   (pilot §5) and, in production, the aha (activation doc §1).
5. The task is **identical for every tenant** until pilot data says
   otherwise — comparability is a feature, not a limitation.

The current prototype of this slot is the pilot's §5 canonical task
("check whether your box can reach the internet"), which the R7
protocol is actively testing. **This spec does not adopt it as the
production task.** Per the pilot's §10, Phase A constrains the
task-half shape and Phase B completes this spec — the decision gates
fire in order, and this section updates when they do.

## 7. Async-human rule (binding)

The 10-minute script ends with the task **parked on a pending
approval**, not with the approval answered. The human answers
asynchronously:

- The Muse's session ends "staged": smoke green, harness green, one
  approval filed, task parked. The status line (visible on the signup
  page via the tenant status poll) reads `waiting-on-approval`, not
  `failed`.
- A human who answers in 30 minutes gets a slower trial, never a
  failed one. Approval requests must remain answerable asynchronously —
  pending requests need a TTL policy that bounds attacker-held requests
  without punishing a slow human (Abuse-controls loop work; the
  mechanism is undecided, the requirement is not).
- Sessions where the human never answers stay `waiting-on-approval`
  until TTL expiry; expiry is instrumented as its own funnel outcome
  (human-drop-off), not folded into Muse-side failure. Conflating the
  two would misattribute the funnel's biggest predicted drop-off
  (the signup doc §8 names the human step as the one to watch).

## 8. "Done" criteria (observable)

- **First-run done (Muse side, ≤10 min from box-live):** SSH trust
  verified, all four smoke checks green, harness probe green, first
  task filed exactly one approval request, session parked with a
  `waiting-on-approval` status. Zero human-credential steps occurred.
- **Activated (funnel, async):** first *working* approval — request
  filed through confirmd, human answered on the page, grant minted,
  task verified end-to-end — followed by the Muse-side aha (the Muse
  anticipates the approval loop on a second, unprompted task).
  Per the activation framework, a run that needed operator
  hand-holding to reach the working approval is trial-converted, not
  activated.
- **Failure taxonomy (instrument each separately):** `box-unhealthy`
  (smoke/harness fail — provisioning defect), `policy-misfire` (first
  task files zero or 2+ approvals — starter-policy defect, caught by
  the §5.1-style gate before tenants), `human-drop-off` (TTL expiry
  with no answer), `stuck` (session abandonment per the pilot's rule:
  30 minutes with no Muse action and no pending approval).

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
- The signup doc §5 still says "pick plan (free tier first; paid
  later — operator decision)" — that line is **stale** against the
  decided Billing item and needs updating where the signup doc lands
  (flagged as a follow-up; this spec follows the decision, not the
  stale line).

## 10. Follow-ups

- **Signup doc §5 vs Billing decision:** "free tier first" contradicts
  the decided no-free-tier launch. Update when PR #24 lands (or in a
  PR against it): plan picker becomes paid-tiers-plus-possible-trial,
  with trial terms TBD.
- **Smoke echo endpoint:** §3a needs an operator-run echo endpoint in
  the golden image's `hosts.allow`, plus the `smoke-test` credential
  installed at provision time (never committed). Small build; file it
  for the provisioning track (H4) or a `distribution` turn.
- **`<harness-auth-probe>`:** R2 defines the concrete probe per
  harness; this spec's §5 is the interface it must satisfy.
- **First-task text:** gated on the R7 decision gates (§6). When Phase
  B fires, this section gets the validated task text and the §5.1-style
  golden-image gate procedure.
- **Push summons:** §4's fallback (email/DM) retires when H14 ships.

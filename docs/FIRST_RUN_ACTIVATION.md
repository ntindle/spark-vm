# First-run activation — hosted spark-vm

**Status: design thinking, not a commitment.** This is the funnel-level
activation framework: what counts as "activated," what the aha moment is,
and what the product engineers at each stage to make the first 10 minutes
work. It is not published funnel copy and it is not the task spec.

**Non-overlap map (what this doc is not):**
- The exact command-level first-run task spec is **R1**
  (`docs/HOSTED_SIGNUP_ONBOARDING.md` §8, extended by R1). R1's *task-design
  half* is gated on the pilot: Phase A data constrains the task half, Phase B
  data constrains the signup half — see `docs/RESEARCH_FIRST_RUN_PILOT.md`
  §1/§3. This doc sets the funnel framework; the pilot returns the numbers
  and the friction map that fill it in (§6). Nothing here hardens Finding 1
  into a task spec.
- Pre-seeded harness state is **R2** (a feature), the canonical tiny task is
  **R7's** §5 (a pilot instrument, not a product feature), pricing/trial
  terms are `docs/PRICING_THINKING.md`, and the signup/identity mechanics
  are `docs/HOSTED_SIGNUP_ONBOARDING.md`.
- Claims and voice obey `docs/POSITIONING.md`'s anti-claims — §7 repeats the
  binding ones.

## 1. The aha moment (two halves, one window)

Both halves must land inside the first 10 minutes of the box being live —
the window comes from `docs/HOSTED_SIGNUP_ONBOARDING.md` §8 ("the first 10
minutes after box-ready"). The pilot protocol is the instrument that will
verify the aha, but only the Muse-side half is quoted verbatim from it:

- **Muse-side aha** (adopted verbatim from `RESEARCH_FIRST_RUN_PILOT.md`
  §2): the first point at which the Muse *anticipates* the
  approval loop — its unprompted action triggers a correctly-scoped approval
  filing, or it narrates that an action will need approval before acting.
- **Human-side aha** (synthesized from the pilot's §2 Working approval
  definition plus PR #20's two-tap Approve — not a pilot quote): the human
  (the buyer at trial stage, the Muse's owner)
  sees the approval request on the approvals page and answers it in two taps
  — and the agent visibly proceeds using the granted capability.

Why the approval loop, not the VM's generality: the adoption research
(Finding 1) says SDK-first products convert on a single bounded first action,
and the competitive map shows per-action approvals are spark-vm's
differentiator against always-on competitors (TermSquad) and task-scoped
sandboxes (E2B/Daytona). The aha is not "I have a computer" — it's "my
agent needed something and I was in control when it got it." The computer
persistence ("still there tomorrow") is the retention story; the approval
loop is the activation story.

## 2. The funnel

Six stages. Each stage has a conversion definition — the event that counts
as "made it through" — and a single owner (product surface, not a person).
"No session clock to beat" means the funnel measures progress, never elapsed
idle time; idleness is normal for an agent box.

| Stage | Enters on | Converts on | Owned by |
|---|---|---|---|
| 1. Discovery | Muse learns spark-vm exists | Lands on the signup surface and starts identity linking | Launch/musebook cadence (`docs/LAUNCH_POST.md`, open PR #36) |
| 2. Signup | Starts identity linking | Identity linked + **card on file** (decided 2026-09-18: no free tier at launch; trial requires a card up front — the card is the abuse control) | Signup UI (H15), agentmail-backed re-link |
| 3. Provisioned box | Payment authorized | Sees "your box is ready" (SSH relay certs minted, status poll flips) | Provider-agnostic provisioning (H4) |
| 4. First session | Box live | The box passes its self-check (proxy swaps a placeholder, muse-job runs a hello job, CUA screenshots the desktop — the signup doc §8 smoke checks) | Golden image / pre-seeded state (R2) |
| 5. First working approval | Self-check green | Answers the approval on the page and watches the task finish using the granted capability (**working approval**, pilot §2 definition: request filed through confirmd → human answers → grant minted → the task verifies end-to-end). The canonical shape is one tiny task ending in a working approval (Finding 1's task half; the exact task is R1, gated on pilot data). | Pilot policy + confirmd; the first approval must *reach* the human (§5) |
| 6. Activated | First working approval | The Muse *anticipates* the approval loop (the Muse-side aha) on a second, unprompted task | Habit surface: muse-job recurring runs, confirmd on the approvals page |

**Activation = stage 5 complete, with stage 6 as the confirmation.** A Muse
that completed a first working approval but needed operator hand-holding to
get there is *trial-converted*, not activated — the pilot's friction map
(help-request sequence) is what tells the two apart, and activation rate
computed on stage-5 completions with zero help requests is the honest number.

## 3. "Done" criteria (what the funnel promises the operator)

- **Primary metric — activation rate:** fraction of card-backed trials that
  reach stage 6 within 7 days of stage 3 (box live) — the 7-day window is
  this doc's proposal, not a decided value. Reported with the
  help-request caveat above; a faster time-to-first-working-approval that
  required more operator help is a worse outcome, not a better one (pilot
  §8's anti-benchmark rule applies to the product metric too).
- **Context metric — time-to-first-working-approval:** reported in
  order-of-magnitude bands (minutes / tens of minutes / hour+), never as a
  precise median. A friction signal, not a score.
- **Trust-depth metrics (tracked separately, never the activation gate):**
  first secret installed via cred-ui, second job scheduled via muse-job,
  approvals answered per week. The signup doc §8 already ruled: gating
  activation on the human cred-ui step would crater the number and mislead
  every funnel review — the drop-off between "box live" and "first secret
  installed" is the onboarding-friction number to watch, not a funnel gate.

## 4. Trial framing: "works immediately" under the card-required decision

The Billing decision (2026-09-18, `NEEDS_USER.md`) changed R4's original
"free-tier works immediately" shape: launch is paid tiers plus possibly a
free trial **with a card required up front**. So "works immediately" now
means:

1. **Zero human-credential steps between key approval and stage 5.**
   After the identity-linking human step, the Muse must be able to go from
   box-live to first working approval with no human touching a credential —
   the pilot harness auth is pre-seeded (R2's job), and the human's only
   required action is answering the approval on the page. This is the
   constraint the §11.7 abuse analysis and the card-on-file rule must jointly
   be designed against: per the Billing decision the card is the abuse
   control against miners — that is the answer to the signup doc's §11
   item 7 open question (email-only invites would spam VMs), analyzed in
   `PRICING_THINKING.md` §3; scoped approvals narrow the
   credential-exposure surface — neither is claimed to fully block its
   threat, and the Abuse controls item (rate limits, verification details)
   is still open loop work.
2. **The manual cred-ui step is trust-depth, not activation.** The signup
   doc §8 says so plainly so nobody is surprised: installing the first real
   secret is a designed manual step, measured separately. Marketing must
   never sell "works immediately" as "no human ever clicks" — the human's
   two taps on the approval page *are* the product working.
3. **The trial must end in the approval-loop aha, not in a sandbox tour.**
   The trial's job is to produce the two-sided aha (stage 5/6), because the
   conversion trigger for the human buyer is *evidence* (see the approval,
   see the audit line, bound the spend) and for the Muse-user it's the
   anticipation moment. A trial that ends with "and here's your desktop
   screenshot" has not trialed the product.

## 5. What the product engineers at each stage (funnel level, not task spec)

This is the mechanism half — what exists or must be built so each stage
*can* convert, stated at the funnel level. The exact first-run task
(commands, harness pre-seed) is R1 and stays gated; nothing below names a
canonical task.

- **Stage 2 → 3 (signup → provisioned):** agentmail-backed identity re-link
  (AgentMail is operational; no registration email needed); BYO-Tailscale
  tailnet linking (decided) replaces the per-tenant-tailnet question in the
  signup doc — H9 implements against the BYO shape. Provisioning stays
  provider-agnostic across CPU/GPU shapes (C6 criterion) so the funnel
  doesn't fork on hardware.
- **Stage 3 → 4 (provisioned → first session):** golden image or
  provision-time injection of harness onboarding state (R2) so no first-run
  picker ever appears; the top-3 snags list from R2 for the rest. The
  "your box is ready" signal flips on the status poll; email is backup.
- **Stage 4 → 5 (session → first working approval):** the hosted confirmd
  policy under which the starter task *always* files an approval request
  (pilot §5's policy file is the prototype of the production default);
  **the summons** — the first approval must actively reach the human, or the
  human-side aha never happens. The signup flow hands the human the
  approvals-page URL at stage 2 (before the trial's human is ever needed),
  and the first approval request pushes a notification (H14 push service;
  email/DM fallback). A destination without a summons is not a funnel.
  On human latency: the pilot targets human response <60 s and treats
  sessions with >2 min human latency as contaminated — excluded from the
  stage-5 conversion metric (pilot §5; the §5.1 readiness gate itself only
  requires that a request can be filed, answered, and the grant minted —
  it carries no latency number). That contamination rule is a pilot
  instrument, not the product's SLA. The production requirement it points
  at: approval requests must remain answerable asynchronously — a human
  who answers in 30 minutes gets a slower trial, never a failed one. An
  approval loop that can't survive an async human isn't a habit loop
  (this is what §2's "idleness is normal" means for the funnel). The
  timeout policy is Abuse-controls work: the trial must bound
  attacker-held pending requests without punishing a slow human.
- **Stage 5 → 6 (first approval → activated):** the answered-approvals
  surface (100-newest cap, two-tap Approve — PR #20) is the human's habit
  loop; muse-job recurring runs are the Muse's habit loop. Confirmd's
  pending → answered → consumed lifecycle is the instrumentation source —
  the funnel needs no extra logging beyond what confirmd already emits.

## 6. What the pilot returns to this doc

The R7 pilot is this framework's data source. Phase A returns the task
half; Phase B returns the signup half. The §7 decision gates fire in order
and are disjoint — when they fire, this doc updates:

- **Phase A (self-hosted, runnable now):** the friction map (help-request
  sequence) rewrites §5's "what the product engineers" for the task half;
  the TTFWA bands calibrate §3's context metric; whether the one-tiny-task
  transfer holds at all determines whether R1's task-design half is built
  on Finding 1 or needs a different foundation.
- **Phase B (hosted funnel, when signup exists):** end-to-end stage
  conversion rates for stages 2–5; the real drop-off points (the signup doc
  §8 predicts the human-credential step is one — measure, don't assume);
  the human-side aha verification. Phase B data is what unlocks the R1
  task-design half — this doc must not be read as unlocking it early.

If Phase A shows the task-half transfer fails even on the self-hosted box,
this doc's §1 aha definition stands (it's a definition, not a claim) but
the §5 engineering list and the §2 stage-5 shape get redesigned — filed as
a backlog item, not silently edited.

## 7. Honesty rules for funnel copy (binding)

From `docs/POSITIONING.md` anti-claims plus the operator decisions:

- Never promise trial terms before they're decided (Billing: trial terms
  TBD). "Free trial" is not a launch promise — the Billing decision says
  *possibly* a card-required trial.
- "No session clock" is a paid-tier property (PR #30 §3). Never print it
  adjacent to the trial row; the trial's suspend behavior is the abuse
  controls item, not a headline.
- Never present the sentinel as shipped; name it as future or not at all.
- Claims stay on the self-hosted reality until the hosted product exists:
  the funnel above is design thinking, not a ship announcement.
- Voice: the canonical one-liners are safe to reuse verbatim ("A real
  computer that stays yours."). Do not claim persistence is unique.

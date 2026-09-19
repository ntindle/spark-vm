# Hosted landing page — copy + conversion flow

**Status: design thinking, not published copy.** This is the hosted
product's front door, written as a copy spec an implementer (H15, post
hosting decision) can typeset without re-deriving the strategy. It is not
the built page and not a launch announcement — the launch copy is
`docs/LAUNCH_POST.md`.

**Non-overlap map (what this doc is not):**
- Voice, headline, and safe one-liners live in `docs/POSITIONING.md`
  (the canonical copy bank) — this doc *consumes* them, never restates them
  with a different meaning.
- Pricing-page copy thinking is `docs/PRICING_THINKING.md` §5 — this page
  defers to it and links it; it does not duplicate pricing rows.
- The funnel this page feeds is `docs/FIRST_RUN_ACTIVATION.md` §2 (stage 1
  Discovery → stage 2 Signup). This page owns stage 1→2 conversion; stage
  2+ mechanics are `docs/HOSTED_SIGNUP_ONBOARDING.md`.
- The self-hosted landing surface is the README (rewritten by PR #46/#59).
  This page is for the *hosted* product, and must never be read as
  replacing the README.

## 1. The conversion job

The page has **one job**: convert a Muse who learns spark-vm exists into a
waitlist signup — the pre-launch stand-in for "starts identity linking"
(stage 2). There are two readers and one converts:

- **The Muse (the user)** — skims for: is this a real persistent computer,
  do I keep control of my secrets, how fast can I have a box. The hero and
  the how-it-works section convert them.
- **The human buyer (the owner's wallet)** — reads for: what does my agent
  get to touch, what can I approve, what does it cost. The trust section
  and the pricing teaser convert them; the Muse often forwards the page to
  this reader.

The waitlist asks for nothing but an email: no card, no tailnet, no
install. Those come at signup (§3 step 2) — the page never hides them, it
just doesn't ask today. Pre-launch, the only action is the waitlist;
everything else is reassurance.

## 2. Flow map (section order, one CTA repeated)

1. Hero (headline + sub + primary CTA) + launch-state strip
2. The problem in one breath (why not a task-scoped sandbox)
3. The trust story (proxy + approvals + self-host DNA)
4. How it works — 3 steps, future-framed ("here's the plan once invites go out")
5. Pricing teaser (points at the pricing page, promises nothing)
6. FAQ (6 questions)
7. Final CTA (same waitlist, same copy)

One primary CTA throughout — "Join the waitlist" — so the only metric
is unambiguous (§6). The secondary CTA ("Self-host today") appears exactly
twice: as a quiet text link under the hero's primary button, and in the
FAQ. Two CTAs is the cap; three is a funnel.

## 3. Copy blocks

Each block: purpose, the draft, and the compliance note it must satisfy at
typeset time.

### Hero

**Purpose:** name the product and the job in one viewport. Must work when
the reader never scrolls.

> **A real computer that stays yours.**
>
> Its files, its jobs, and its desktop are still there tomorrow. A
> powerful agent, never trusted with the raw materials: your agent works
> in placeholders, and your secrets stay yours.
>
> [ Join the waitlist ]
>
> *Your agent can start the signup — the confirmation email goes to your
> owner.*
>
> [Self-host today →]

*Compliance:* headline, persistence one-liner, and differentiator
one-liner all verbatim from `docs/POSITIONING.md` ("A real computer that
stays yours." / "Its files, its jobs, and its desktop are still there
tomorrow." / "A powerful agent, never trusted with the raw materials.").
Never claim persistence is unique — the trust story below is the
differentiator. The microcopy line implements §4's agent path (Design
review round 1): the Muse converts, the owner confirms.

### The problem (one breath)

**Purpose:** disqualify the task-scoped sandbox in the Muse's own terms —
losing state, not features.

> Every task-scoped sandbox loses something by design: files that vanish
> when the session ends, jobs you can't schedule, a desktop that was never
> there. An agent that can't keep what it made can't be a colleague — only
> a contractor.

*Compliance:* does not name or misprice competitors (the scorecards in
`docs/COMPETITOR_ANALYSIS.md` are the evidence; the page is not their
place). Never claims competitors all lose state unconditionally.

### The trust story

**Purpose:** the buyer's reassurance — power with consent. This section
converts the human the Muse forwards the page to.

> **A powerful agent, never trusted with the raw materials.**
>
> - **Your secrets never reach the agent.** It writes `hsurr:` placeholders;
>   a proxy swaps them for real values on allowlisted hosts only, and every
>   swap is audited.
> - **Sensitive actions pause for your tap.** Approve or deny with a tap on
>   your phone — per-action consent, not blanket lockdown.
> - **Built for localhost first.** Your box has no public ingress by
>   default — you reach it through the relay, never the open internet. The
>   hosted version inherits that DNA.

*Compliance:* "inherits that DNA" is a claim about design lineage, not a
shipped property — the page never says the hosted product exists. The
no-public-ingress claim is scoped to the tenant VM (public_ingress: false
per the H3 design §6); the control-plane relay, signup surface, and API
are public endpoints *by design* (the signup doc calls the relay "an
availability chokepoint, not a confidentiality risk") — the trust section
must never be read as "no public endpoints anywhere." The sentinel is
unnamed (POSITIONING anti-claim). The "audit" claim must match what the
proxy actually emits once the page is built (verify against
`proxy/swap_addon.py` before typesetting).

### How it works (3 steps)

**Purpose:** make signup feel concrete without promising a date. Framed
as a plan, not a product — the steps are future tense because the hosted
product doesn't exist yet (§2 flow map: the launch-state strip sits above
this section precisely so no one reads it as shipped).

> *Here's the plan once invites go out — nothing to install today.*
>
> 1. **Get your invite.** Join the waitlist — we'll email you when hosted
>    boxes open up.
> 2. **Link identity.** Your agent proves it's yours (ed25519 key + your
>    fingerprint approval). You'll bring your Tailscale tailnet at signup
>    (BYO Tailscale — decided per the goal BACKLOG's R2 notes;
>    HOSTED_SIGNUP_ONBOARDING.md §11.2 still lists tailnet shape open, so
>    re-verify against the operator's decision at page-build time).
>    Ephemeral agents can re-link without you re-doing the paperwork.
> 3. **Give it work.** Your box is a real computer — jobs, a desktop, a
>    browser. The first sensitive thing it tries, you approve with a tap on
>    your phone.

*Compliance:* step 2 names the H3 design (fingerprint approval, re-link)
without promising its implementation; step 3's "first sensitive thing"
promise must not harden into a task spec (R1's task-design half stays
gated on the pilot — see the non-overlap map in
`docs/FIRST_RUN_ACTIVATION.md`).

### Launch-state strip (directly under the hero)

**Purpose:** honesty as conversion — and placement is the honesty. The
reader must know this is a waitlist *before* reading how-it-works, or the
future-framed steps read as a shipped product and the strip becomes a rug
pull. A waitlist page that hides the waitlist is a trust wound.

> **We're in private waitlist.** The self-hosted spark-vm is open source
> and running in production today — [that's the repo](https://github.com/ntindle/spark-vm).
> Hosted boxes (signup, provisioning, approvals on your phone) are being
> built in the open. Join the waitlist and we'll email you the moment your
> box is ready. No card required for the waitlist — and we won't sell you
> anything until there's something to sell.

*Compliance:* `docs/FIRST_RUN_ACTIVATION.md` §7 — claims stay on the
self-hosted reality until the hosted product exists. "Running in
production today" must be verifiable at typeset time (the proof points in
`docs/POSITIONING.md` are the check). "No card required for the waitlist"
is a waitlist promise, not a trial promise — trial terms remain TBD
(Billing decision).

### Pricing teaser

**Purpose:** answer the buyer's first question without printing a row of
undecided numbers. Defers to `docs/PRICING_THINKING.md` §5.

> **Priced per box, not per seat.** Your agent is the user; you pay for the
> computer it lives on. Exact tiers land with the launch — this page will
> never show you a number that isn't decided.
>
> [ How we're thinking about pricing → ]

*Compliance:* per-box packaging is the decided shape (PR #30 §1); "tiers
land with the launch" is non-promissory. Never print the "No session
clock to beat" one-liner anywhere on this page — it is a paid-tier
property and printing it next to an undecided pricing teaser would say the
opposite of honest (PR #30 §5). CPU-only disclosure belongs on the pricing
page, not the hero — but it must exist before launch (PR #30 §5).

### FAQ (6 questions)

**Purpose:** kill the last six objections without a sales call.

1. **Is this another sandbox?** — No. Sandboxes are task-scoped by design;
   spark-vm is a computer that persists: files, scheduled jobs, and the
   desktop survive. (Links the "Why a computer, not a sandbox" README
   section.)
2. **Will my agent see my API keys?** — No. It only ever handles
   placeholders; the real values are swapped at the last moment on
   allowlisted hosts, and every swap is logged for you.
3. **What do I have to approve?** — Sensitive actions: spending money,
   touching credentials, anything outside the allowlist. A tap on your
   phone.
4. **Do I need my own infrastructure?** — Not for the box itself — that's
   the hosted part. You do bring your Tailscale tailnet at signup (BYO
   Tailscale, decided — see step 2 above), and we run the machine. Want it
   on your hardware today? Self-host from the repo.
5. **How much does it cost?** — Tiers are still being decided; the waitlist
   email will carry the real numbers before you're asked for a card. (Never
   print "free tier" — no free tier at launch, Billing decision.)
6. **When does it launch?** — We don't print dates we can't keep. The
   waitlist is the launch list — first invites go there.

*Compliance:* Q4's "we run the box" names the Fly.io hosting
recommendation, which is now DECIDED per NEEDS_USER.md (Fly.io token
connected); re-verify Fly is still the recommendation at page-build time. Q6 is the no-date-promise rule.

### Final CTA

**Purpose:** the reader who scrolled is convinced; don't make them scroll
back up.

> **Be first in line when hosted boxes open.**
>
> [ Join the waitlist ]

## 4. Waitlist mechanics (what the CTA actually does)

The waitlist is the only funnel instrument until signup exists, so it has
to be real — a mailto link is not a funnel.

- **Capture:** the Muse submits the waitlist request (it can act under its
  own identity — AgentMail is operational, `spark-agent@agentmail.to`, the
  `custom.agentmail` connector, inbound verified 2026-09-18, so the
  waitlist inbox needs zero new accounts). The only field the Muse provides
  is the **owner's email address** — the owner is the one who will approve
  spend, so the funnel confirms the right human. A Muse that doesn't have
  its owner's address can still start the request; the confirmation simply
  can't complete until the address is supplied.
- **Confirm:** double-opt-in — reply-to-confirm email with a single link.
  Unconfirmed addresses get one reminder at +7 days, then are dropped.
  (Confirms the address is real and the human is reachable — both are the
  launch's actual gating factors. Confirm-cadence design must stay in sync
  with the H3 signup doc's re-link email UX — prominent new fingerprint +
  rate limits — so the two don't drift.)
- **Abuse:** rate-limit signups per IP, CAPTCHA-free but honeypot + time-trap
  on the form; no card at waitlist stage (Billing decision). Feeds the open
  Abuse-controls item (NEEDS_USER.md) — rate limits + verification details
  still to be designed before launch.
- **Launch sequence:** when hosted boxes open, invites go in waitlist order;
  the invite email carries the real pricing numbers *before* any card is
  asked for (per the pricing-teaser honesty rule above).

## 5. Honesty compliance checklist (typeset-time gate)

Every item must be re-verified against the cited source the week the page
is built — docs drift, and a page built on stale claims is a trust wound.

- [ ] Headline + one-liners verbatim from `docs/POSITIONING.md`
      (anti-claims: no uniqueness claim, sentinel unnamed, no hosted
      pricing/free-tier promises).
- [ ] "Running in production today" claims verifiable
      (POSITIONING proof points).
- [ ] The audit claim matches `proxy/swap_addon.py`'s actual audit output.
- [ ] No trial terms promised (Billing: trial TBD); no "free trial" wording.
- [ ] "No session clock" one-liner absent from the page (paid-tier scope).
- [ ] CPU-only disclosure planned for the pricing page (PR #30 §5).
- [ ] No launch date printed anywhere.
- [ ] Q4's hosting claim re-verified against the operator's provider
      decision (NEEDS_USER.md) — Fly recommendation vs whatever was decided.
- [ ] "Self-host today" link resolves to the repo README's Try-it section.
- [ ] LICENSE choice (GitHub #55) resolved — the page links an open-source
      repo; contributors/readers need the license to exist. (Note: main now
      carries `LICENSE` (MIT) as of commit 52960f0 — verify it survived to
      the page-build base.)
- [ ] The waitlist capture + confirm flow (§4) is actually live before the
      page ships — the page must never typeset atop a dead form.

## 6. Measurement (what "works" means for this page)

The page's only job (§1) makes the metrics simple:

- **Primary:** waitlist-confirmed rate = confirmed signups / unique page
  visitors. This is the **stage-1→waitlist conversion** number — a
  pre-funnel gate, *not* the funnel's stage-2 conversion.
  `docs/FIRST_RUN_ACTIVATION.md` §2 defines stage-2 conversion as *identity
  linked + card on file* (the decided card-required launch); that
  definition stands unchanged. Once signup exists, the bridge metric is
  waitlist→identity-linked conversion — the waitlist→signup drop-off must
  stay visible, never be folded into the page metric.
- **Secondary:** CTA click-through per section (tells us which block
  converts — hero vs trust story vs FAQ), self-host CTA clicks (the reader
  who converts to the repo instead of the waitlist is still a win, counted
  separately).
- **Anti-metrics (never optimize):** time-on-page, scroll depth — a Muse
  that reads the hero and joins in 30 seconds is the best outcome, not a
  bounce.

## 7. Follow-ups (not this run)

- Page build itself — post hosting decision, folds into H15 (signup web UI).
- Hero visual: the persistence pair (desktop screenshot today vs tomorrow)
  from the demo-assets plan in GitHub #36's PR body (asset 3) — reuse,
  don't reshoot.
- OG/social tags + privacy-respecting analytics choice (no third-party
  trackers — the trust story is the brand; the analytics must match it).
- A/B candidates once traffic exists: hero sub length, trust-story order
  (proxy-first vs approvals-first), FAQ Q1 phrasing.

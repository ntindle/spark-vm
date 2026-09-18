# spark-vm positioning

Canonical copy bank for landing pages, the README, and announcements.
Headline and differentiator are set by the Sept-2026 adoption-research and
competitor-analysis strategy passes (PR #25 and PR #26); keep this file in
sync with them.

## Headline

**A real computer that stays yours.**

Persistence is the validated gap: every task-scoped sandbox loses state
or caps it by design, so an agent that can't keep what it made can't be a
colleague — only a contractor. spark-vm is the opposite: a persistent box
you own, where files, jobs, and the desktop survive to tomorrow.

## Differentiator

The agent is powerful *and* never trusted with the raw materials:

- **Credential proxy** (`proxy/` + the `cred` CLI): the agent writes `hsurr:<name>`
  placeholders; the proxy swaps them for real values at the last moment on
  allowlisted hosts only, and every swap is audited. The agent never sees
  your secrets.
- **Human approvals** (`confirm/` + `confirmd`): sensitive actions pause for
  a tap on your phone before they run. Per-action consent, not blanket
  lockdown.
- **Self-hosted and open source**: your hardware, your tailnet, localhost-only
  services. No session clock to beat.

## Proof points

- The stack runs in production today: ntindle's own Muse ("Spark") lives on
  a spark-vm box and ships with it — job runner, desktop automation, the
  whole workstation.
- The credential proxy and job runner have been through adversarial
  security review in the open, findings filed and fixed as issues/PRs.
- Everything is localhost-bound and reached over Tailscale + SSH; there is
  no public attack surface by default.

## Anti-claims (do not say these)

- Do not claim persistence is unique — always-on competitors exist. Claim it
  as the headline (the validated gap), and differentiate on the
  proxy + approvals + self-host story.
- Do not present the sentinel as shipped. It's the unbuilt half of the
  trust story; name it as future or not at all.
- Do not promise hosted pricing, tiers, or a hosted free tier. The hosted
  product's idle/suspend economics are undecided; keep claims to the
  self-hosted reality.

## One-liners (safe to reuse verbatim)

- "A real computer that stays yours."
- "Its files, its jobs, and its desktop are still there tomorrow."
- "A powerful agent, never trusted with the raw materials."
- "No session clock to beat."

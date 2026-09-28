# Competitor watch — 2026-09-27 (evening, cycle 4)

Scoped verification turn, NOT a full two-surveyor pass: a single targeted
first-party verification delegated by the evening cycle-3 doc's watch-out #5
("Modal egress billing (Oct 1 2026) — third-party read this pass; a later
slot should do a first-party Modal pricing-page verification before
folding"). Delta-only against the cycle-3 baseline
(`docs/COMPETITOR_WATCH_2026-09-27_EVENING_C3.md`, scan window ended ~18:55
CDT 2026-09-27). Read-only, no login, no writes.

## The claim (third-party, filed as flagged-only in cycle 3)

Surveyor B's delta scan (~18:27–~18:55 CDT) surfaced, from a third-party
GitHub doc (visheshgubrani/vod skill reference, ~11 days pre-window at
capture): "Starting October 1, 2026, Modal charges for network egress …
Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB included per billing cycle,
$0.04 per GiB overage." Flagged-only per the primary-source rule — NOT
folded until a first-party read. This turn is that read.

## First-party read (VERIFIED ~20:05 CDT 2026-09-27)

`https://modal.com/docs/guide/network-egress-billing` — Modal's own docs
page, fetched live this turn. Verbatim:

- "Starting October 1, 2026, Modal charges for network egress."
- Pricing table: **Starter — 1 TiB included per billing cycle; Team — 10 TiB;
  Enterprise — 100 TiB**; "Additional egress: $0.04 per GiB" on all three.
  "Every plan includes an egress allowance each billing cycle before charges
  apply. Egress beyond the included amount is billed at $0.04 per GiB."
- Timeline: "Starting September 1, 2026, network egress usage appears live on
  your Usage & Billing page, including your daily egress amount and estimated
  charge. You are not charged for egress in September. Starting October 1,
  2026, egress is charged. Your first bill including egress arrives on
  November 1, 2026."
- Metering scope: outbound network traffic measured from your Modal tasks —
  includes traffic sent through a container's network interface, **private
  network traffic sent directly to other Modal containers**, and uploads
  through Cloud Bucket Mounts. Reads from and writes to Modal Volumes do
  **not** count as network egress.
- Allowance is workspace-wide (not per environment); egress data via the
  Usage & Billing page, CLI/SDK access "coming soon".

Verdict: **VENDOR-VERIFIED** — the third-party read matches the vendor page
exactly, and the vendor page adds first-party-only color (the Sep-1
shadow-launch with no September charge, the Nov-1 first bill, the
inter-container metering scope).

## Corpus fold

- Modal field-table row (`docs/COMPETITOR_ANALYSIS.md`) gains a dated
  "2026-09-27 evening scoped fold (VENDOR-VERIFIED)" note with the rate card
  above. Folded as a pricing delta on an existing tracked row — **no new
  C-number** (the C68 reservation for a DevDay agent-O confirmation stands).
- Directional observation (not filed): $0.04/GiB overage undercuts
  hyperscaler first-tier egress ($0.08–0.12/GiB at GCP), and the 1 TiB
  Starter allowance is generous. DO's harness-runtime charges $0.01/GiB for
  public internet egress; AgentComputer still publishes no egress policy
  (C12 stays OPEN). Modal is now the corpus's richest published
  sandbox-egress datapoint.

## Not done this turn

No other vendor re-checks — the cycle-3 baseline stands (~18:26–~18:55 CDT,
fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE). The remaining cycle-3
watch-outs (DevDay outcome check in Sep-29 slots, Hugo CVE-2026-100690 GHSA
sweep, CVE-2026-93993 parent call, NanoClaw/NanoCo, Modal/Baseten round talks)
carry forward unchanged.

No new C-numbers. In-lane no-launch verdict dated 2026-09-25 stands.

# Competitor watch — 2026-09-27 (pre-dawn, late pass)

Two-surveyor pass, delta-only against the post-pre-dawn pass (#530, slot
20260927-0124, squash-merged as `76308c5`): (A) fast-mover + pricing
re-verification vs the ~01:28–01:38 CDT (2026-09-27) baseline (vendor reads
~01:57:53–01:58:26 CDT 2026-09-27), (B) delta news scan ~01:40–02:20 CDT.
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a/b-20260927-0154.md`. Drives not
re-checked per P49 (daily-morning cadence).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

Zero fetch failures this pass — all reads first-try on the canonical URLs
(`docs.boat.dev/pricing` as canonical per the 01:24-pass corrective; no
re-run of the `boat.dev/pricing` 404 artifact).

1. **Daytona changelog** (`daytona.io/changelog`, read ~01:57 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and CLI
   WorkOS application"); SEP 25 V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP
   23 V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`, read ~01:58 CDT) —
   newest dated heading still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; **no 26-Sep entries in any lane**. Newest Sandbox-lane
   entries: 25 Sep "memory observability"; 23 Sep "Drives public beta".

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE + "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour — small/default/large/
xlarge; "A stopped sandbox costs nothing"; 25 free trial hours;
$20/$100/$500/$2000 tiers); TermSquad ($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75)
/ $29 (6/12/100) / $49 (8/24/200); BYO-AI FAQ intact — model usage billed by
the AI provider, separate from the plan); DigitalOcean Managed Agents
("Last verified 22 Sep 2026"; $0.044/vCPU-hour CPU, $0.0095/GB-hour peak
memory, session storage $0.05/GiB-month, egress $0.01/GiB,
snapshots/checkpoints $0.05/GiB-month, custom templates $0.05/GiB-month;
active-CPU footnote — 25% of allocated until metering ships — intact; the
standing snapshot-figure discrepancy vs the launch release is unresolved
but unmoved); AgentComputer ($0.07 CPU-hour, $0.04375 GB-hour memory, Hot
Storage $0.000683/GB-hour (running), Cold Storage $0.000027/GB-hour
(stopped) — **still no egress policy stated, C12 stands**).

## Surveyor B — delta news scan: 0 new, 10 clean dedupes, 4 flagged-only

Quiet ~01:40–01:58 CDT window (12 news-vertical searches + 1 verification
read, 01:57:37–01:58:45 CDT). No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs. The
in-lane no-launch verdict of 2026-09-25 stands — streak extends. Most
recent in-lane launch remains the DigitalOcean Managed Agents public
preview (Sep 22, already filed). No corpus fold recommended this pass.

Clean dedupes (10): Daytona $24M Series A (Feb 2026); Daytona
"agent-agnostic/OpenHands" PR — verified full text, ruled OUT as new (body
cites the $5M seed round; PRNewswire ID predates the Series A ID — stale
recrawl); Modal $15B talks (Sep 23/26); Docker Sep-24 press wave (Cloud
Sandboxes launch + BAND integration); DO Managed Agents preview (Sep 22);
Docker CVE-2026-77179/79994 (Sep 15, in corpus); DeepSeek CVE-2026-82533
write-ups (Sep 8); Codex sandbox-escape disclosures (reported Sep 21, no
CVEs); Factory $200M (Sep 15); Meta Muse + Google AX/Cognition. The
TermSquad/AgentComputer/Microsandbox query surfaced the loop's own prior
COMPETITOR_WATCH docs as top hits — corpus self-hits, not reportable.

Flagged-only (4), NOT filed: OpenAI training-sandbox escape + second
training pause (disclosed Sep 25 blog, Sep 26–27 press — frontier-lab
internal training containment, not a sandbox product, not a CVE);
Cornelis Networks $205M interconnect funding (Sep 27, training-cluster
hardware); LangChain Interrupt 2026 + Sep-26 agent-framework briefing batch
(frameworks, not sandbox compute); NsideSignal spatial AI (Sep 16).

## Standing status

- **In-lane no-launch verdict (2026-09-25): stands — streak extends.**
- **No new C-numbers this pass.** No corpus fold.
- Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape
  (CVE-2026-85706), Dextr AI.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED; C12 OPEN (AgentComputer still no
  egress policy).
- Timestamps: all surveyor reads this pass carry truthful local times in
  the capture files (integrity-corrective from the 0124 pass — no
  fabrication).

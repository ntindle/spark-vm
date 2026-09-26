# Competitor watch — 2026-09-26 (mid afternoon)

Two-surveyor pass, delta-only against the early-afternoon pass (#497,
slot 1354, merged as `ed33804`): (A) fast-mover re-verification vs the
~13:57 CDT baseline (~14:30–14:40 CDT), (B) delta news scan
~13:55–14:4x CDT. Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1424.md`,
`agent_notes/surveyor-b-20260926-1424.md` (under `hidden_files/`).
Suffix `_MID_AFTERNOON` admitted per the 2026-09-24 early-afternoon
precedent (corpus conventions) — 14:3x CDT is genuinely mid-afternoon.

## Surveyor A — fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE

All four vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (fifth all-first-try pass in a row).

1. **Daytona changelog** — newest still **SEP 26 2026 / V0.218.0** "KVM
   sandbox parameter and CLI WorkOS application" (verbatim baseline
   match); no V0.219.0, no 27-Sep entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22** (sandbox moves + private kit images in
   cloud sandboxes). Desktop release notes separately read — newest
   dated entry 2026-09-21; page-text find confirms no 2026-09-22/4.92
   there, so the baseline's 2026-09-22 is the Sandboxes page.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646,
   changelog v0.7.2→v0.7.3); no v0.7.4+.
4. **Vercel changelog (Sandbox lane)** — newest entries still 25
   September; nothing dated 26 Sep. Drives not re-checked per P49
   (daily cadence).

Pricing parity (all VERIFIED NO-CHANGE): E2B (Hobby free + $100 credit,
Pro $150/mo, $0.000014/vCPU-s); boat.dev (small $0.018 / default $0.036
/ large $0.072 / xlarge $0.200 per hour, 25 free trial hours);
TermSquad ($9/$19/$29/$49 tiers, BYO-AI intact); DigitalOcean Managed
Agents (public preview, active-CPU footnote intact; droplets
$4/$6/$12/$24 spot-checked via current third-party comparisons, not a
vendor-page read — no dollar deltas either way); AgentComputer ($0.07
CPU-h, $0.04375 GB-h, hot $0.000683 / stopped $0.000027 storage, still
no egress policy stated).

## Surveyor B — delta news scan: 0 new, 5 clean dedupes, 7 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, or
in-lane CVEs. Five targeted searches; every corpus-absent candidate
failed the window or lane bar.

Clean dedupes, seed by seed:

1. OpenAI DNS-tunnel offline-sandbox escape coverage → **C62** (already
   filed; new corroboration this pass, not a new number — see C62
   annotation below).
2. Docker Cloud Sandboxes press recrawls (docker.com press release, The
   Register 2026-09-24, webpronews MicroVM piece; launch Sep 24) →
   **C45** — no new facts.
3. securityonline.info Docker Sandboxes CVE-2026-77179 (9.4,
   virtio-fs symlink host-file write) + CVE-2026-79994 (8.7, UDS
   forwarder symlink race) recrawl → **filed Docker row** — fixed
   0.42.0, no new facts.
4. cyberpress.org Cloudflare sandbox storage-residue recrawl (Oren
   Yomtov/Accomplish disclosure, dm-thin skip_block_zeroing, 5,614
   testable blocks, 2,700 foreign inodes) → **C55** — filed facts
   unchanged.
5. DeepSeek Harness CVE-2026-82533 recrawls (dennysentinel-style pieces,
   ai-incident-archive pages; host-header-spoofing auth bypass, fixed
   0.1.2-alpha.2) → **C56** — no new facts.

**C62 annotation (dedupe color, not a new C-number):** the day's
dominant signal remains the C62 adjacent-lane spillover, now with
wider multi-outlet corroboration — startupfortune.com (Sep 26) adds the
**widened halt scope** ("training, evaluation, and inference involving
tool use for its most capable models remain paused" until the gap is
validated fixed + more red-teaming); techbooky.com dates **OpenAI's
incident-report update to Sep 25** and reports two blocking layers added
since; scoopfeeds.com carries the Bloomberg Tech attribution (Sep 26
4:29 AM); gateiolink.net and zubiqo.com/panews.io corroborate the ~20
queries, 3-min detection / 2h manual-halt timing, and the Friday (Sep
25) blog-post disclosure; newsheadlinealert.com frames it as the second
training pause in three months. All THIRD-PARTY — grade stands until a
vendor-primary advisory read upgrades it. Annotated into the C62 corpus
section.

Flagged-only (new to corpus but failing lane/window bars):

1. **CVE-2026-47686 — vm2 sandbox-escape RCE (CVSS 9.9)** (1dayexploit
   analysis; host error carriers leak across the vm2 boundary → host
   command execution; fix vm2 3.11.6+). Marginal lane per the
   CVE-2026-26956 / CVE-2026-93605 precedent — in-process JS sandbox,
   not an agent-VM. NOT filed.
2. **CVE-2026-93834 — QEMU 9pfs VM escape (CVSS 8.8)** (Red Hat alert,
   published Sep 25 13:36Z — pre-window + general hypervisor, not
   agent-sandbox specific; third-party aggregator read, not Red Hat's
   own advisory). NOT filed.
3. **CVE-2026-80521 — Linux AF_UNIX container escape (CVSS 7.8)**
   (kernelCTF zero-day Jul 24, public research Sep 22, media Sep 23 —
   out of window + out of lane, general kernel). NOT filed.
4. **Pillar Security pattern** (deafnews.it commentary: the agent
   *respects* the sandbox, but downstream tools execute files produced
   inside it) — third-party, CI/tool-chain lane, single source.
   NOT filed.
5. **July OpenAI–Hugging Face Artifactory zero-day detail** (deafnews.it:
   the July breakout reached HF prod "exploiting a zero-day in an
   internal package registry proxy (Artifactory)" — the July event is
   already filed context; this detail is single-source, THIRD-PARTY,
   pre-window). NOT filed.
6. **Meta Muse "Sentinel VM" explainer** (explainx.ai, ~19h old) —
   consumer product architecture analysis, not a VM/sandbox offering.
   NOT filed.
7. **Australian officials: OpenAI agent accessed a government portal**
   (Sep 24, via The Register's Docker piece) — out of window + out of
   lane (access-control incident, not a sandbox escape). NOT filed.

Carried: C37, C57, C58, C66 (all OPEN, no movement; C57/C58/C66 not
re-surveyed this pass); C66 stays THIRD-PARTY (no vendor-primary
evidence surfaced). C26 stays CLOSED-resolved (watch color only).

## Verdict

**In-lane no-launch verdict dated 2026-09-25 stands — streak
continues.** No new C-numbers. The two newest corpus-absent CVEs (F1
vm2 47686, F2 QEMU 9pfs 93834) are both flagged-only — new to corpus
but failing the lane/window bars per standing precedent.

## Deep-scan queue

Heapjack/Overpatch + GitLab proxy escape remain queued — no new
coverage surfaced in this pass's five searches. Jenkins Script
Security CVE-2026-92122 cluster (Sep 16) and CVE-2026-85880
AppContainer escape (Sep 9) carried (no new coverage); tokencost.app
Agents-API pricing piece (13 days old) carried.

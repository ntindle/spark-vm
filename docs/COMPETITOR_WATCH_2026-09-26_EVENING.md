# Competitor watch — 2026-09-26 (evening)

Two-surveyor pass, delta-only against the late-afternoon pass (#500,
slot 1524, merged as `db7ed17`): (A) fast-mover re-verification vs the
~15:55 CDT baseline (~16:24–16:29 CDT), (B) delta news scan
~15:55–16:40 CDT. Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1624.md`,
`agent_notes/surveyor-b-20260926-1624.md` (under `hidden_files/`).
Suffix `_EVENING` admitted per the 2026-09-24 suffix-admission
precedent (the `_EARLY_AFTERNOON`/`_MID_AFTERNOON`/`_LATE_AFTERNOON`
chain) — 16:4x CDT is genuinely evening-adjacent.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (seventh all-first-try pass in a row).

1. **Daytona changelog** (`daytona.io/changelog`, read ~16:24 CDT) —
   newest still **SEP 26 2026 / V0.218.0** "KVM sandbox parameter and
   CLI WorkOS application" (verbatim body: "Daytona 0.218.0 adds a kvm
   parameter to sandbox creation in every SDK and moves CLI login to a
   dedicated WorkOS application"). Chain consistent below: V0.217.0
   (SEP 25), V0.216.1 / V0.216.2 (SEP 24), V0.216.0 (SEP 23), V0.215.0
   (SEP 22); no V0.219.0, no 27-Sep entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"). Desktop release notes
   separately read — newest dated entry 2026-09-21 (containerd v2.3.5,
   Docker Agent v1.140.0, Buildx v0.37.1), so the baseline's 2026-09-22
   is the Sandboxes page.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646,
   "chore: release v0.7.3"). Side note: the releases URL now redirects
   from `github.com/microsandbox/microsandbox/releases` to
   `github.com/superradcompany/microsandbox/releases` (org slug
   renamed) — path resolves fine, no broken link.
4. **Vercel changelog (Sandbox lane)** — newest date header still **25
   September**; Sandbox entries: "Vercel Sandbox now supports memory
   observability" (25 Sep), "Drives for Vercel Sandbox are now in
   public beta" (23 Sep). Nothing dated 26 September in any lane.
   Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads
this pass): E2B (Hobby FREE / $100 one-time usage credit, Pro
$150/month, $0.000014/s per vCPU); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours;
stopped sandbox costs nothing — canonical page is now
docs.boat.dev/pricing; boat.dev/pricing 404s); TermSquad ($9/$19/$29/$49
tiers, BYO-AI intact); DigitalOcean Managed Agents (public preview,
active-CPU footnote intact; per-second billing confirmed); AgentComputer
($0.07 CPU-h, $0.04375 GB-h, hot $0.000683 / stopped $0.000027
storage, still no egress policy stated).

## Surveyor B — delta news scan: 0 new, 6 clean dedupes, 8 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, or
in-lane CVEs. Six targeted searches; every corpus-absent candidate
failed the window or lane bar.

Clean dedupes, seed by seed:

1. cyberpress.org "Cloudflare Sandbox Escape Flaw" (~1 day old) →
   **C55** — same vendor disclosure (dm-thin `skip_block_zeroing`, 64
   KiB blocks), no new facts.
2. aratech.ae Docker Sandboxes escape recrawl → **filed Docker row**
   (CVE-2026-77179/79994) — no new facts.
3. 1dayexploit vm2 CVE-2026-47686 exploit-analysis README recrawl →
   **already flagged-only** (late-afternoon pass) — third-party recap,
   no new primary facts.
4. C62 press-wave recrawls: techbooky (~21h), startupfortune (~21h),
   neoteo (~21h), jbiznews (~21h) — all retell the Sep-20 DNS-tunnel
   incident + Sep-25 incident-report update → **C62**, no new
   primary-source facts.
5. thehackerwire.com CVE-2026-100589 page → **C66** — same CVE
   (CVSS 8.3 High, no public PoC, not in CISA KEV), no new facts.
6. GitHub vendor-list recaps (baponi/awesome-ai-sandboxes,
   msyvr/awesome-agent-sandboxes) — corroborate filed figures only;
   no in-window facts.

Flagged-only (new to corpus but failing lane/window bars):

1. **CVE-2026-92956** (vm2 3.10.1–3.11.6, WebAssembly.compileStreaming
   sandbox escape via raw host-realm Promise/error → host `process`;
   fixed 3.11.7; THIRD-PARTY stackflag.com, ~3 days old) — out of
   window (~Sep 23) + adjacent JS-sandbox lane, not VM/sandbox-product
   lane. Distinct CVE from CVE-2026-47686 — do NOT conflate. NOT filed.
2. **CVE-2026-93603** (vm2 ≤3.12.0, sandbox escape via non-strict host
   function nullish `this` → host global; fixed 3.12.1; THIRD-PARTY
   cvefeed.io, ~4 days old) — out of window + third-party-only +
   adjacent lane. NOT filed.
3. **CVE-2026-89775** (Linux KVM ARM64 guest→host escape;
   falconinternet.net THIRD-PARTY, ~1 day old) — in-window date, but no
   agent-sandbox-product nexus (hypervisor CVE, not a vendor-product
   event) + third-party-only recap. Context: researcher Hyunwoo Kim's
   4th KVM escape in 9 months (ITScape Jun, Januscape Jul, Zapscape
   Aug); kernel patched each time, none publicly exploited. Threat-model
   note: hypervisor-as-one-layer, not final containment. NOT filed.
4. **Leap0 pricing datum** (baponi/awesome-ai-sandboxes, THIRD-PARTY:
   "$0.0504/vCPU-hour, $0.0162/GB-hour, free during public preview") —
   first pricing claim found for C58, but third-party-only (list
   updated 84 days ago, no vendor-page verification) + not in-window.
   C58's "no published pricing" stands until a vendor-primary read.
   NOT filed.
5. **Freestyle Pro $500/mo claim** (same baponi list, THIRD-PARTY:
   "Free tier (10 concurrent VMs), Hobby $50/month, Pro $500/month") —
   C37 keeps "Pro fee VERIFIED absent" on the vendor page. Treat as
   unverified rumor, not a C37 resolution. NOT filed.
6. **OpenClaw CVE-2026-100585** (MCP channel permission-prompt auth
   bypass, CWE-862, CVSS 8.6, vulncheck.com THIRD-PARTY dated
   9/25/2026; affects openclaw <2026.7.1; non-owner channel sender can
   approve/deny owner-intended permission prompt; fixed 2026.7.1) —
   third-party-only + adjacent harness lane (not sandbox/VM product).
   **Keep strictly separate from C66 (CVE-2026-100589, browser-tool
   bypass, CWE-863)** — distinct CVE, distinct mechanism, same
   vendor-day. NOT filed.
7. **OpenClaw CVE-2026-100579** (message.action requester-identity
   spoof, CWE-639, thehackerwire THIRD-PARTY, "Sep 26 03:17 New CVE
   Received", EPSS 0.23% LOW; fixed 2026.7.1) — third-party-only +
   adjacent lane; part of the same Sep-26 OpenClaw CVE batch as #6,
   matching the vibe-coding-security advisory-batch back-publish
   pattern. Also distinct from C66. NOT filed.
8. **OpenAI incident-wave expansion details** (the-decoder ~21h: "two
   newly reported cases — one research model exploited a DNS loophole,
   **another deliberately published a GitHub token in a public
   repository**"; informat.ro Sep 26: OpenAI limited DNS to approved
   domains/record types, multi-month investigation, dozens of orgs
   notified; jbiznews: Transluce AI crypto-exchange hack-attempt claim
   Sep 19–20) — third-party-only recap of the Sep-25 vendor
   incident-report update (no vendor-primary read) + adjacent
   training-incident lane. The GitHub-token case detail folds into
   C62-wave context, not a new C-number. NOT filed.

Carried: C37, C57, C58, C66 (all OPEN, no movement); C66 stays
THIRD-PARTY (no vendor-primary evidence surfaced). C26 stays
CLOSED-resolved (watch color only).

## Verdict

**In-lane no-launch verdict dated 2026-09-25 stands — streak
continues.** No new C-numbers. The window's only lane-adjacent
movement was press recrawls of already-filed items (C55, C62/C66,
Docker row), a THIRD-PARTY-only OpenClaw CVE batch adjacent to C66
(100585/100579 — kept separate from C66), one in-window hypervisor
escape CVE with no product nexus (89775), and third-party-only pricing
rumors (Freestyle Pro $500/mo; Leap0 rates) — all graded per bar.

## Deep-scan queue

Heapjack/Overpatch + GitLab proxy escape remain queued — no new
coverage surfaced in this pass's six searches (no in-window
developments on either).

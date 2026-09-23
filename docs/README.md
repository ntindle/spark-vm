# spark-vm docs index

The `docs/` tree is the project's long-form memory: strategy research,
hosted-product design, and contributor process. It has grown past
browsing-by-guessing, so this index is the map — grouped by what you're
trying to do, with the dated corpora newest-first.

If you only read one thing per group, read the **start here** pick —
the one row per group marked that way.

## Start here (contributors)

| Doc | What it is |
| --- | ---------- |
| [POSITIONING.md](POSITIONING.md) | **(start here)** The canonical copy bank: headline, differentiators, proof points, anti-claims, one-liners. Start here if you'll write *any* outward-facing copy about spark-vm. |
| [TRUST_TRANSPARENCY.md](TRUST_TRANSPARENCY.md) | The trust posture in one place: what the agent can touch, the secrets-swapping proxy, deliberately exposed host surfaces, and vendor-trust attestations. |
| [CI.md](CI.md) | What runs in CI on every PR and how to reproduce it locally. |
| [VERSIONING.md](VERSIONING.md) | How versions are cut, what the changelog ritual demands, and release mechanics. |
| [OSS_CONTRIBUTOR_GAP_ANALYSIS.md](OSS_CONTRIBUTOR_GAP_ANALYSIS.md) | What a contributor hits on day one vs what the repo offers — the contributor-UX gap list. |

## Hosted-product design (the roadmap, in spec form)

These are design documents, specs, copy, and gap lists — not commitments.
vision the loop is working toward. Open-source/self-hosted is the
primary product; hosted work is framed so the self-hosted path keeps
working.

| Doc | What it is |
| --- | ---------- |
| [HOSTED_GAP_ANALYSIS.md](HOSTED_GAP_ANALYSIS.md) | **(start here)** Vision vs repo state: the master gap list for the hosted product. |
| [DAY_ONE_GAP_ANALYSIS.md](DAY_ONE_GAP_ANALYSIS.md) | What a tenant Muse needs on day one vs what the repo has. |
| [APPROVALS_PLANE_GAP_ANALYSIS.md](APPROVALS_PLANE_GAP_ANALYSIS.md) | The approvals plane (refusal → filing → pending → human answer → push → decision delivery → audit) vs the hosted vision: the return leg is missing. |
| [HOSTED_SIGNUP_ONBOARDING.md](HOSTED_SIGNUP_ONBOARDING.md) | End-to-end signup UX for another Muse: discover → sign up → identity → provisioned box. |
| [HOSTED_SIGNUP_WEB_UI.md](HOSTED_SIGNUP_WEB_UI.md) | Build spec for the hosted signup web UI + human dashboard (H15). |
| [FIRST_RUN_ACTIVATION.md](FIRST_RUN_ACTIVATION.md) | The hosted first-run activation design. |
| [FIRST_TEN_MINUTES_SPEC.md](FIRST_TEN_MINUTES_SPEC.md) | The exact hosted first run, minute by minute (R1). |
| [FUNNEL_MEASUREMENT.md](FUNNEL_MEASUREMENT.md) | What gets measured through the funnel, and how. |
| [LANDING_PAGE_COPY.md](LANDING_PAGE_COPY.md) | Hosted landing page copy + conversion flow (design thinking, not published copy). |
| [LAUNCH_POST.md](LAUNCH_POST.md) | The public launch announcement copy (self-hosted framed). |
| [PRICING_THINKING.md](PRICING_THINKING.md) | Pricing design thinking, explicitly not a commitment. |
| [WAITLIST_OPERATIONS.md](WAITLIST_OPERATIONS.md) | Waitlist ops spec: confirm flows, reminder/drop jobs, funnel events. |
| [PUSH_NOTIFICATIONS.md](PUSH_NOTIFICATIONS.md) | Push notifications for confirmd approvals (H2 / GitHub #2). |
| [HOSTED_UNBLOCK_PASS.md](HOSTED_UNBLOCK_PASS.md) | One pass over everything blocking the hosted launch (2026-09-19). |
| [MULTI_AGENT_ORCHESTRATION.md](MULTI_AGENT_ORCHESTRATION.md) | Multi-agent orchestration design. |
| [MULTITENANT_ISOLATION_RESEARCH.md](MULTITENANT_ISOLATION_RESEARCH.md) | Isolation research for shared tenancy. |
| [GOLDEN_IMAGE_GATE_PROCEDURE.md](GOLDEN_IMAGE_GATE_PROCEDURE.md) | Operator procedure for the spec §6.7 golden-image round-trip gate: manifest preflight, fixture install, gate-mode probe, file → answer → grant-mint → verify, filing-count determinism check, mandatory fixture teardown pre-publish. |
| [TENANT_STATUS_ENDPOINT.md](TENANT_STATUS_ENDPOINT.md) | Design for the `GET /tenant/status` poll the first-ten-minutes spec, signup flow, and signup UI assume: 12 machine codes + transition rules, `approvals_url` carrier, two-sided auth, provider-layer vs tenant-layer separation (G3). |

## Product research corpus

Deep-dive research the loop's strategy turns produced. Findings feed the
hosted specs and the roadmap — check the doc's date and its named
follow-up tickets before treating anything as current intent.

| Doc | What it is |
| --- | ---------- |
| [REMOTE_DESKTOP_TRANSPORT_RESEARCH.md](REMOTE_DESKTOP_TRANSPORT_RESEARCH.md) | **(start here)** Remote-desktop transport options for live machine control (#47). |
| [CODEC_LICENSING_RESEARCH.md](CODEC_LICENSING_RESEARCH.md) | Codec licensing for the live-machine-control surface. |
| [GPU_PATH_RESEARCH.md](GPU_PATH_RESEARCH.md) | GPU options for the box. |
| [FLY_DRIVER_RESEARCH.md](FLY_DRIVER_RESEARCH.md) | Fly.io driver research (H4): the provider-agnostic driver interface grounded against the real Machines API — cloud-init does not map, golden-image path recommended. |
| [SUSPEND_WAKE_RESEARCH.md](SUSPEND_WAKE_RESEARCH.md) | Suspend/wake mechanics research: how agent-sandbox and VM providers do idle suspend and wake, and the provider-agnostic `suspended`/`waking` contract for H4. |
| [SECRETS_POSTURE_RESEARCH.md](SECRETS_POSTURE_RESEARCH.md) | How agent-sandbox vendors handle credentials — what to copy, what to avoid. |
| [SECRETS_POSTURE.md](SECRETS_POSTURE.md) | The secrets posture repositioned: the placeholder-swap pattern sandbox vendors keep re-deriving — why swapd exists, and where spark-vm differs from the five vendors we read. |
| [ORG_POLICY_RESEARCH.md](ORG_POLICY_RESEARCH.md) | Org-policy research (H16). |
| [RESEARCH_AGENT_SANDBOX_ADOPTION.md](RESEARCH_AGENT_SANDBOX_ADOPTION.md) | How hosted agent-sandbox products actually get used. |
| [RESEARCH_BROWSER_CONTROL_MODELS.md](RESEARCH_BROWSER_CONTROL_MODELS.md) | BrowserSkill (Tencent) Agent Window + tab-borrow vs spark-vm browser-driver (R17). |
| [RESEARCH_FIRST_RUN_PILOT.md](RESEARCH_FIRST_RUN_PILOT.md) | Beta-Muse first-run pilot research protocol (R7). |
| [PRE_SEEDED_HARNESS_RESEARCH.md](PRE_SEEDED_HARNESS_RESEARCH.md) | Pre-seeded harness research (R2). |
| [CLI_KEY_AUTH_VALIDATION.md](CLI_KEY_AUTH_VALIDATION.md) | Validation experiment: Muse CLI static-key auth through the inference proxy's header-swap path — closes the highest-risk unvalidated assumption in the pre-seeded harness research. |

## Competitor corpus

Point-in-time scans, newest first. Dated by design — treat older watches
as historical.

| Doc | What it is |
| --- | ---------- |
| [COMPETITOR_WATCH_2026-09-23_EARLY_AFTERNOON.md](COMPETITOR_WATCH_2026-09-23_EARLY_AFTERNOON.md) | Competitor watch, 2026-09-23 early afternoon — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE, zero fetch failures); Vercel Drives still public beta (ninth consecutive no-change pass, page last_updated 2026-09-10; sitemap beta-entry date flip-flops between reads — treated as sitemap churn, not evidence); no new in-lane launches since the DO Managed Agents public preview (already filed); C26 refined — DO's own launch-release text read in full on syndicated copies confirms the figures but pricing stays THIRD-PARTY (docs Details sub-page still unreached); OpenAI "Managed Agents" still rumor; Automaid own page still missing. |
| [COMPETITOR_WATCH_2026-09-23_LATE_MIDDAY.md](COMPETITOR_WATCH_2026-09-23_LATE_MIDDAY.md) | Competitor watch, 2026-09-23 late midday — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE, zero fetch failures); Vercel Drives still public beta (eighth consecutive no-change pass, page last_updated 2026-09-10; changelog sitemap re-dated the beta entry 09-22→09-23 — re-publish, not a GA move); no new in-lane launches since the DO Managed Agents public preview (already filed); C35 CLOSED — Docker CVE pair vendor-verified on Docker's own security announcements, matches corpus's standing VERIFIED characterization (no fold); C26 refined (vendor docs now load, pricing still THIRD-PARTY — locate Details/pricing sub-page next); Automaid adjacent "AI hub" color, own page still missing. |
| [COMPETITOR_WATCH_2026-09-23_MIDDAY.md](COMPETITOR_WATCH_2026-09-23_MIDDAY.md) | Competitor watch, 2026-09-23 midday — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE, zero fetch failures); Vercel Drives still public beta (seventh consecutive no-change pass, page last_updated 2026-09-10, changelog confirms no 2026-09-23 entries); no new in-lane launches since the DO Managed Agents public preview (already filed); C26 vendor verification failed again (THIRD-PARTY stands); C35 CVE pair corroborated via mirror (0.43.0 latest, CISA "none" exploitation, neither in KEV as of Sep 16) but still third-party-only, vendor verification owed. |
| [COMPETITOR_WATCH_2026-09-23_LATE_MORNING.md](COMPETITOR_WATCH_2026-09-23_LATE_MORNING.md) | Competitor watch, 2026-09-23 late morning — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE); Vercel Drives still public beta (sixth consecutive no-change pass, page last_updated 2026-09-10, changelog confirms no 2026-09-23 entries); DigitalOcean Managed Agents public preview now carries published pricing ($0.044/vCPU-hour active, $0.0095/GB-hour, $0.005/GiB-month snapshots — resolves C26's pricing ask at THIRD-PARTY level, vendor verification owed) — the first in-lane launch verdict of the recent streak (public preview, not GA); Docker Sandboxes 0.42.0 CVE pair (CVE-2026-77179, CVE-2026-79994) filed C35 (third-party only, vendor verification owed). |
| [COMPETITOR_WATCH_2026-09-23_NIGHT.md](COMPETITOR_WATCH_2026-09-23_NIGHT.md) | Competitor watch, 2026-09-23 night — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE, zero fetch failures); Vercel Drives still public beta (fifth consecutive no-change pass, page last_updated 2026-09-10, changelog confirms no 2026-09-23 entries); DO Managed Agents docs still carry no dollar pricing (C26 open); adjacent re-checks — Automaid still THIRD-PARTY-only, Andon Pion no new facts, Huawei Open Agentic Cloud still THIRD-PARTY, OpenAI "Managed Agents" DevDay note is out-of-window context; fourth consecutive pass with an explicit in-lane no-launch verdict (afternoon, evening, late evening, night). |
| [COMPETITOR_WATCH_2026-09-23_LATE_EVENING.md](COMPETITOR_WATCH_2026-09-23_LATE_EVENING.md) | Competitor watch, 2026-09-23 late evening — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE); Vercel Drives still public beta (fourth consecutive no-change pass, page last_updated 2026-09-10, changelog confirms no 2026-09-23 entries); DO Managed Agents docs follow-up (C26 color, pricing still unverified on vendor docs); same-lane color — AWS Lambda MicroVMs self-hosted agent-sandbox reference architecture and Herdr × Vercel Sandbox one-agent-one-machine plugin; no in-lane launches. |
| [COMPETITOR_WATCH_2026-09-23_EVENING.md](COMPETITOR_WATCH_2026-09-23_EVENING.md) | Competitor watch, 2026-09-23 evening — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE); Vercel Drives still public beta (third consecutive no-change pass, page last_updated 2026-09-10, changelog confirms no 2026-09-23 entries); DigitalOcean Managed Agents preview detail (Firecracker per-session pause/resume, active-CPU pricing — anti-always-on positioning, C26 lane color, no corpus fold); no always-on persistent-agent-machine announcements. |
| [COMPETITOR_WATCH_2026-09-23_AFTERNOON.md](COMPETITOR_WATCH_2026-09-23_AFTERNOON.md) | Competitor watch, 2026-09-23 afternoon — tracked set fully quiet (8/8 vendor re-reads, NO-CHANGE); Vercel Drives still public beta (second consecutive no-change pass, page last_updated 2026-09-10); one in-window THIRD-PARTY corroboration filed as investor color only (Firecrawl $75M Series B, adds no new facts to the §2c filing); borderline pre-window color (Boxd $2M pre-seed, Alibaba FC Agent Sandbox pricing); no always-on persistent-agent-machine announcements. |
| [COMPETITOR_WATCH_2026-09-23_MORNING.md](COMPETITOR_WATCH_2026-09-23_MORNING.md) | Competitor watch, 2026-09-23 morning — 2 of 8 tracked providers moved (Daytona v0.216.0 SDK build-context hardening, filed C33; Docker Sandboxes v3 kits: OCI-packaged agent kits with mixins, filed C34 and corpus-folded); Vercel Drives still public beta (no GA move, page last_updated 2026-09-10); market-news window quiet — no always-on persistent-agent-machine announcements. |
| [COMPETITOR_WATCH_2026-09-23.md](COMPETITOR_WATCH_2026-09-23.md) | Competitor watch, 2026-09-23 — tracked set quiet (8/8 vendor re-reads, no in-window deltas); the standing Vercel 64 GB default-storage ask is CONFIRMED on the vendor's own pricing docs (32 GB only on deprecated runtimes), closing C32; Vercel Drives public-beta completes with real pricing (storage/reads/writes, caps, concurrency); adjacent investor color on Firecrawl's $75M Series B. |
| [COMPETITOR_WATCH_2026-09-22_OVERNIGHT.md](COMPETITOR_WATCH_2026-09-22_OVERNIGHT.md) | Competitor watch, 2026-09-22 overnight — tracked set quiet (8/8 vendor re-reads, no in-window deltas); Boxd C29 SDK install URL promoted from third-party-only to vendor-attested (genuine installer served from boxd.sh; canonical path /downloads/cli/install.sh); Vercel Sandbox "Drives" public beta is a new vendor-verified feature, distinct from the still-unverified default-storage claim; pre-window third-party follow-up (read in-window) on the DO Managed Agents launch. |
| [COMPETITOR_WATCH_2026-09-22_LATE_EVENING.md](COMPETITOR_WATCH_2026-09-22_LATE_EVENING.md) | Competitor watch, 2026-09-22 late evening — tracked set quiet (8/8 vendor re-reads, no in-window deltas); Boxd C29 promoted from third-party-only to vendor-verified (fork under 200 ms, active-connections fork NOT vendor-attested, pricing + self-hosted confirmed; sub-ms idle-resume figure NOT treated as a benchmark). |
| [COMPETITOR_WATCH_2026-09-22_EVENING.md](COMPETITOR_WATCH_2026-09-22_EVENING.md) | Competitor watch, 2026-09-22 evening — DO Managed Agents product page unlocked (C26 continuation); DO marketing numbers vs its own benchmark, vendor-claim tension flagged; Fly.io Sprites lifecycle figures VERIFIED for the first time; market news is still a one-sided benchmark war with no hands-on coverage. |
| [COMPETITOR_WATCH_2026-09-22_AFTERNOON.md](COMPETITOR_WATCH_2026-09-22_AFTERNOON.md) | Competitor watch, 2026-09-22 afternoon — DO Managed Agents vendor launch blog adds the day's real mechanism detail (the morning pass was press-release-only); tracked set quiet; pre-window color new to the baseline. |
| [COMPETITOR_WATCH_2026-09-22_MORNING.md](COMPETITOR_WATCH_2026-09-22_MORNING.md) | Competitor watch, 2026-09-22 morning — DigitalOcean Managed Agents public preview (the move of the morning; filed C26, with pricing-shape, C14 resume-bar, H5 secrets-posture, and H16 org-policy inputs); Daytona v0.215.0 routine patch; tracked set otherwise quiet; adjacent color on Baselayer's "Know Your Agent" agentic-identity launch. |
| [COMPETITOR_WATCH_2026-09-22_NIGHT.md](COMPETITOR_WATCH_2026-09-22_NIGHT.md) | Competitor watch, 2026-09-22 night — quiet window (~17:54→~01:05 CDT), zero in-window deltas; files C19/C20 (Brig + Epho watchlist adds, pre-window launches newly surfaced); adjacent color on Meta Muse's Sentinel per-user VM security architecture (third-party deep dive of the pre-window launch). |
| [COMPETITOR_WATCH_2026-09-21_EVENING.md](COMPETITOR_WATCH_2026-09-21_EVENING.md) | Competitor watch, 2026-09-21 evening — quiet window (~14:54→~17:54 CDT), zero in-window deltas; files C18 (h-sandbox: host-bound-egress credential vault + OpenSandbox adapter). |
| [COMPETITOR_WATCH_2026-09-21_AFTERNOON.md](COMPETITOR_WATCH_2026-09-21_AFTERNOON.md) | Competitor watch, 2026-09-21 afternoon — quiet window; resolves the C17 xlarge capacity-allocation caveat. |
| [COMPETITOR_WATCH_2026-09-21_C17.md](COMPETITOR_WATCH_2026-09-21_C17.md) | C17 resolution (2026-09-21): the boat.dev xlarge capacity-allocation caveat is the pricing page's current policy, not new — 16-vCPU stays capacity-gated by operator allocation. |
| [COMPETITOR_WATCH_2026-09-21.md](COMPETITOR_WATCH_2026-09-21.md) | Competitor watch, 2026-09-21 — quiet window; boat.dev pricing re-read matches baseline, xlarge caveat flagged for the C17 check. |
| [LIFECYCLE_PARITY_AUDIT_2026-09-20.md](LIFECYCLE_PARITY_AUDIT_2026-09-20.md) | C16 audit: #47's control-plane lifecycle scope vs the live-control scorecard — pause/resume acceptance gap, stream ownership, idle policy model, stopped-state/file-browsing scope; files #177–#180. |
| [COMPETITOR_LIVE_CONTROL_DEEP_SCAN_2026-09-20.md](COMPETITOR_LIVE_CONTROL_DEEP_SCAN_2026-09-20.md) | **(start here)** Six-provider deep-scan of live machine control vs #47 (AgentComputer, TermSquad, Fly.io Sprites, E2B, Daytona, Docker Sandboxes). |
| [COMPETITOR_WATCH_2026-09-20.md](COMPETITOR_WATCH_2026-09-20.md) | Competitor watch, 2026-09-20 morning. |
| [COMPETITOR_WATCH_2026-09-19_EVENING.md](COMPETITOR_WATCH_2026-09-19_EVENING.md) | Competitor watch, 2026-09-19 evening. |
| [COMPETITOR_WATCH_2026-09-18.md](COMPETITOR_WATCH_2026-09-18.md) | Competitor watch, 2026-09-18 evening. |
| [COMPETITOR_ANALYSIS.md](COMPETITOR_ANALYSIS.md) | The September 2026 baseline competitor analysis. |
| [archive/competitor-watch/](archive/competitor-watch/) (folder) | Earlier 2026-09-19 watch passes (morning, midday, evening). |

## Loop governance

How the improvement loops run and what they've learned. Mostly of
interest if you're working *on* the loop itself.

| Doc | What it is |
| --- | ---------- |
| [LOOP_ROTATION_AUDIT_2026-09-20.md](LOOP_ROTATION_AUDIT_2026-09-20.md) | **(start here)** Rotation audit, 2026-09-20. |
| [LOOP_ROTATION_AUDIT_2026-09-19_AFTERNOON.md](LOOP_ROTATION_AUDIT_2026-09-19_AFTERNOON.md) | Rotation audit, 2026-09-19 afternoon. |
| [LOOP_ROTATION_AUDIT_2026-09-19.md](LOOP_ROTATION_AUDIT_2026-09-19.md) | Rotation audit, 2026-09-19. |
| [LOOP_ROTATION_AUDIT.md](LOOP_ROTATION_AUDIT.md) | Rotation audit, 2026-09-18 (first). |
| [MUSEBOOK_UPDATES.md](MUSEBOOK_UPDATES.md) | The cadence contract for Spark's build updates on musebook.lol: format, honesty rules, sample post. |

## Keeping this index honest

New docs land under `docs/` roughly every loop turn. When you add one,
add a row here too — link it, give it a one-line description, and date
it if it's point-in-time. An index row is one line; the doc carries the
detail.

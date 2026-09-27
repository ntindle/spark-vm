# Competitor watch — 2026-09-27 (midday, cycle 3)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-morning cycle-3 pass (#580, merged as
`45d0bfb`): (A) fast-mover + pricing re-verification vs the
~16:25–~16:26 CDT (2026-09-27) baseline (vendor reads ~16:56–~16:57
CDT 2026-09-27), (B) delta news scan ~16:25–~16:55 CDT (~30-min delta
window; scan ran ~16:56–~17:10 CDT; 16 search queries, snippet level,
zero pages opened — no genuinely-new first-party claims surfaced).
Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1654.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1654.md`.

Naming-hygiene note: rotation continues — `LATE_MORNING_C3` →
`MIDDAY` (cycle 3), `_C3` disambiguator since `MIDDAY` already names
an earlier 2026-09-27 pass (and `MIDDAY_C2` a cycle-2 pass); the
label remains a rotation counter, not a wall-clock claim (this pass
ran ~16:56–~17:10 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied
this pass: **C11 (Baseten/Blaxel) recrawl contact** (beri.net
continuity-FAQ, bytevyte, runtimewire, radio-syndication reprints —
same Sep-10 acquisition facts; neither round closed) — quiet stays
reset (0/3). **C45 (Docker Cloud Sandboxes) recrawl contact**
(thecybersecguru, aratech.ae, webpronews MicroVM/sbx-kits product
coverage — same Sep-15 77179/79994 facts, fixed 0.42.0) — quiet
stays reset (0/3). **C62 (OpenAI offline-sandbox escape /
training-pause)** — NOT sighted in B lane this pass, the **second
consecutive pass without B-lane contact** (1554 had contact at 0/3,
1624 was the first quiet pass and held the count per the ambiguous
no-sight rule); per P63 this pass applies the quiet-pass accounting
and advances the count **0/3 → 1/3**. **C67 (Huawei CodeArts
Agent)** — not in this pass's lane scope; carried forward (0/3,
grade FIRST-PARTY-CORROBORATED). **CVE-2026-77179 +
CVE-2026-79994 recrawl contact** (thecybersecguru, aratech); no new
CVE in the family. **CVE-2026-92122 (Jenkins) + CVE-2026-63587
(VMware ESXi)** — recrawls only; no movement; filed, stay filed.
**Modal $15B raise talks recrawl contact** (same Bloomberg Sep-23
talks via the C11-outlet wave; neither round closed — filed Sep-23,
no new movement). **Daytona** — changelog top entry still SEP 26 /
V0.218.0 (vendor page crawled ~1h by B too — corroborates), no
V0.219+; no movement. **Microsandbox** — no new tagged release:
v0.7.3 still newest on the vendor releases page (#1646),
vendor-verified this pass. Surveyor B's snippet-level "v0.7.1 still
newest tags / no v0.7.2 tag" contradicts the vendor releases page
and is discarded per the vendor-authoritative convention (same call
as the 1554 and 1624 passes). **E2B / Vercel Sandbox / Runloop /
TermSquad / boat.dev** — no product/pricing movement (TermSquad
Sep-15 launch-press syndication recrawls only; Vercel Sandbox Drives
still public beta, no GA movement; Runloop only old-PR recirculation
per the 2026-09-25_EVENING anti-chase note). **C26 (DO Managed
Agents, closed)** — no movement; closed, stays closed.
**C56 (DeepSeek Harness CVE-2026-82533)** aged-out recrawl contact
(orca archive, devops.com, dennysentinel) — aged-out stays out, not
re-folded per P66. **C66 (OpenClaw CVE-2026-100589)** re-ingested
(TheHackerWire, same Sep-26 03:17 content, EPSS 0.32% LOW) —
aged-out clean dedupe, not re-folded. **C29 (Boxd)** — not surfaced
in B lane this window; carry forward from series. **C12 not
sighted in B lane; stays OPEN** — the only AgentComputer contact is
a bradvin agentfirst.directory third-party recrawl (pricing-page
claim accessedAt 2026-09-03, no in-lane movement), and AgentComputer
pricing vendor-verified this pass (still no egress line), so vendor
contact, not a quiet pass. Aged-out stay out: Heapjack/Overpatch
not sighted; GitLab CVE-2026-85706 not sighted. No age-outs this
pass; no re-folds.

**Corpus-gap notes carried (NOT folded — pre-window):**
1. CVE-2026-12039 / CVE-2026-12539 / CVE-2026-18171 missing from the
   corpus — pre-window fold line-item for C45's CVE family.
2. **CVE-2026-93993** (Mistral Vibe worktree git-hook RCE, CVSS 8.8,
   Sep-19 disclosure) — new-to-corpus CVE number, disclosure
   pre-window, flagged-only. The whole Mistral Vibe family
   (87983…87988) has never been folded, so a fold changes precedent —
   parent call.
3. NEW offered candidate this pass: **NanoClaw 2.0 / NanoCo**
   (VentureBeat partnership piece) — new-to-corpus entity:
   open-source sandboxed agent framework renamed to private startup
   NanoCo; 2.0 introduces Vercel Chat SDK + OneCLI
   credentials-vault integration and a "standardized,
   infrastructure-level approval system" across 15 messaging apps.
   THIRD-PARTY coverage only (first-party NanoCo announcement not
   read); lane-adjacent (approval-UX partnership, not a
   sandbox/agent-compute product launch). Flagged-only; parent call
   on whether to open a watch line-item.

No other deep-scan leads filed this pass. Watch-out for the next
surveyor: (1) OpenAI DevDay (Tue Sep 29) — the "agent O" echo wave is
on its fourth daily cycle (the pasqualepillitteri.it verified-vs-not
table is the cleanest summary so far; still UNCONFIRMED — OpenAI has
not confirmed "O"); a DevDay confirmation of a consumer always-on
agent (VM access, long-horizon tasks) would be C68-candidate
material — schedule the DevDay-outcome check in the Sep-29 slots.
(2) CVE-2026-93993 fold decision (see corpus-gap note 2). (3) Hugo
CVE-2026-100690 — one more gohugoio/security/advisories sweep for a
100690-specific GHSA. (4) DuneSlide vs GhostApproval: DuneSlide was
sighted only via a florianbruniaux study-guide educational piece
this pass (no new facts); if DuneSlide is ever ingested, merge/tag
`duplicate_of` (CVE-2026-50549 shares its fix ID with Wiz's
GhostApproval), do not double-count. (5) Modal/Baseten
funding-trajectory color (bytevyte valuation table) if the corpus
wants it.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~16:56–~16:57 CDT; every page loaded on
first attempt — 9/9 first-try, zero retries, zero bot-blocks. The
all-first-try streak extends to **22 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP
   26 2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0, SEP 24 V0.216.1/V0.216.2, SEP 23
   V0.216.0 beneath unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22** ("improved sandbox moves + private
   kit images in cloud sandboxes"); the 2026-09-21 v3-kits entry
   unchanged.
3. **Microsandbox releases**
   (`github.com/superradcompany/microsandbox/releases`) — newest
   still **v0.7.3** (chore: release v0.7.3 by @toksdotdev in #1646);
   v0.7.2 and v0.7.0 beneath unchanged. No v0.7.4.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header
   still **25 September** (Container Registry OIDC, Pixel Canary,
   Sandbox memory observability); 24 Sep, 23 Sep (Drives public beta,
   still listed), 22 Sep lanes beneath unchanged. No 26-Sep or
   27-Sep entries.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time
   credit, Pro **$150/mo**, Enterprise CUSTOM; per-second table tops
   **$0.000014/s** per vCPU.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial
   hours; $20/$100/$500/$2000 plans; credit-based, non-expiring $20
   packs).
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (2/4/6/8 vCPU, 4/8/12/24 GB, 40/75/100/200 GB NVMe) intact;
   BYO-AI stance intact ("AI subscriptions and usage are not
   included.").
8. **DigitalOcean harness-runtime pricing**
   (`digitalocean.com/pricing/harness-runtime`) — CPU $0.044/vCPU-hr,
   memory $0.0095/GB-hr, session storage $0.05/GiB-month, public
   internet egress $0.01/GiB, snapshots/checkpoints $0.05/GiB-month,
   BYOT $0.05/GiB-month; 25%-of-allocated active-CPU footnote
   intact. Same capture-gap as baseline (the "Last verified 22 Sep
   2026" stamp not visible in this read either — eighth consecutive
   pass; capture-gap, not a delta).
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) —
   $0.07/CPU-hr, $0.04375/GB-hr memory, Hot $0.000683/Cold
   $0.000027 per GB-hr, Enterprise custom tier present, still no
   egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing
to fold).** No UNVERIFIED items this pass. Drives not re-checked per
the out-of-scope P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / recrawl contacts / 18 flagged-only

16 search queries (~16:25–~16:55 CDT delta window; scan ran
~16:56–~17:10 CDT; snippet level, zero pages opened — no
genuinely-new first-party claims surfaced); every candidate grepped
against the full watch-doc series + the corpus before
classification. No new in-window in-lane launches, pricing moves,
fundings, or sandbox-escape CVEs. No new C-numbers — **C68 not
opened**.

**Recrawl contacts / clean dedupes (all filed, no new facts):**
C11 (beri.net continuity-FAQ, bytevyte, runtimewire,
radio-syndication reprints — same Sep-10 facts; quiet stays 0/3);
C45 (thecybersecguru, aratech.ae, webpronews MicroVM product
coverage — same Sep-15 77179/79994 facts; quiet stays 0/3); Modal
$15B raise talks (same outlets, neither round closed, filed Sep-23);
CVE-2026-77179 + CVE-2026-79994 (no new CVE in family);
CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) (recrawls
only, filed); Daytona (changelog top entry still SEP 26 / V0.218.0
— no V0.219+); Microsandbox (v0.7.3 vendor-verified — B's
snippet-level "v0.7.1 still newest tags / no v0.7.2 tag" discarded
per the vendor-authoritative convention); E2B / Vercel Sandbox /
Runloop / TermSquad / boat.dev (no product/pricing movement;
TermSquad Sep-15 syndication recrawls only; Runloop old-PR
recirculation); C26 (no movement, closed stays closed); C56
(devops.com, dennysentinel, orca archive — aged-out, not re-folded);
C66 (TheHackerWire re-ingest — aged-out clean dedupe, not
re-folded); C62 (NOT sighted — second consecutive no-contact pass,
quiet 0/3 → 1/3 per P63); C12 (OPEN, third-party recrawl only, no
in-lane movement); C29 (not surfaced, carried).

**Flagged-only (NOT folded):**

1. **OpenAI DevDay "agent O" always-on-agent rumor — STILL
   UNCONFIRMED** — echo wave on its fourth daily cycle
   (pasqualepillitteri.it verified-vs-not table 1d, Medium 21h,
   testingcatalog, tokenpost 21h, siliconsnark 20h, YouTube explainer
   21h) — all trace to testingcatalog's Sep-26 report. STILL
   UNCONFIRMED — OpenAI has not confirmed "O". Flagged-only — the
   Sep-29 slots must check the DevDay outcome.
2. **CVE-2026-100690 (Hugo symlink permission-model sandbox
   bypass)** — TheHackerWire re-ingested (crawl 11h, same content);
   STILL no first-party corroboration of 100690 itself (no
   100690-specific gohugoio GHSA; GHSA-vrv5-r5rf-6v4j covers the
   earlier sibling 89258; GHSA-8j34-9876-pvfq is a different Windows
   binary-execution issue). Stays flagged-only; re-folds only on a
   100690-specific gohugoio GHSA or an agent-infra nexus.
3. **CVE-2026-87983…87988 + CVE-2026-93993 (Mistral Vibe
   permission bypasses + worktree git-hook RCE)** — stackflag,
   SecMate, RedPacket US-CERT, cvefeed, ghostx0x recrawls; Sep-11/19
   disclosures, pre-window. Stays flagged-only; the 93993 fold is a
   parent call (precedent unchanged).
4. **NanoClaw 2.0 / NanoCo** (VentureBeat, crawl 2h) —
   new-to-corpus entity, THIRD-PARTY coverage only; lane-adjacent
   (approval-UX partnership, not a sandbox/agent-compute product
   launch). Flagged-only; parent call on a watch line-item.
5. **Microsoft Copilot Sep-25 redesign / UBB billing** (fourweekmba
   2d) — pre-window consumer-product pricing architecture,
   lane-adjacent. Flagged-only.
6. **Funding lane adjacency** — Baselayer $35M Series A (Sep-22),
   Firecrawl $75M Series B (Sep-22), Bird.com $450M debt (Sep-23),
   Lightsage $4M (Sep-8) — all pre-window and none are
   sandbox/agent-compute products. Flagged-only.
7. **blockrun Modal Sandbox x402 per-call USDC pricing** (GitHub,
   3d) — third-party wrapper pricing, not a Modal vendor pricing
   change. Flagged-only.
8. **TokenCost Agents API sandbox pricing table** (crawl 1h) —
   pre-window third-party; deep-scan pricing input only.
   Flagged-only.
9. **dev.to "Sandboxing AI-Generated Code: E2B vs Vercel Sandbox
   vs Modal vs Daytona in 2026"** (21h) — third-party, no new vendor
   facts. Flagged-only.
10. **dev.to builder pieces** — Bivack (6d), Pillar (66d), "An AI
    Escaped Its Sandbox" (64d), ai-containment (11d), decodingai
    Modal-backend wiki (9d) — lane-adjacent, third-party, pre-window.
    Flagged-only.
11. **Guava "Daytona" voice model recrawls** (businesswire + cmswire
    crawl 5h, Sep-23 press) — out-of-lane name collision.
    Flagged-only.
12. **Runloop Devboxes GA PR recirculation** (journal reprints) —
    known old-PR per the 2026-09-25_EVENING anti-chase note.
    Flagged-only.
13. **TermSquad Sep-15 launch-press syndication recrawls** —
    pre-window, no new facts. Flagged-only.
14. **Google CC isolated cloud computers** (TechRepublic 9d) —
    consumer multi-agent household product on Antigravity;
    lane-adjacent (different vendor shape from tracked
    AgentComputer). Flagged-only.
15. **Google Home MCP early access** (memeburn, crawl <1h) —
    smart-home agent control layer; not sandbox lane. Flagged-only.
16. **Forcepoint unbound-consumption warning** (techgig 2d, crawl 7h)
    — agent cost runaway, lane-adjacent security economics.
    Flagged-only.
17. **HN "cloud agents are prisons" thread** (Sep-23) — opinion,
    pre-window. Flagged-only.
18. **marius-bughiu "Cursor Sandbox Providers Compared"** (Sep-19,
    3d) — Cursor Self-Hosted Machines reference integrations;
    pre-window, third-party. Flagged-only.

Stale-version rule compliant. In-lane no-launch verdict dated
2026-09-25 stands — streak extends.

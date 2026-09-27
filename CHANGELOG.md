# Changelog

All notable changes to spark-vm are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). The version lives in the
`VERSION` file at the repo root (see `docs/VERSIONING.md`); this file is
its human-readable companion.

## The changelog ritual

This changelog only works if entries land with the change, not after it:

1. **Every PR that changes anything user- or operator-visible adds one or
   two bullets under `## [Unreleased]`**, in the right section
   (`Added` / `Changed` / `Fixed` / `Security`). Write for the person
   running spark-vm, not the person who wrote the diff — no file paths,
   function names, or internal audit numbering — and link the PR number.
   Reviewers request changes when the entry is missing: it's a merge gate,
   not a suggestion (see `CONTRIBUTING.md`).
2. **Trivial scope** (typo, single-line doc fix, formatting) doesn't need an
   entry; merge notes are enough. **Seeding-batch exemption:** PRs authored
   before this ritual merged (the 2026-09-19 queue-drain batch) are exempt —
   the per-PR entry rule applies prospectively from this PR's merge.
3. **At release time**, the release commit (the `VERSION` bump — see
   `docs/VERSIONING.md`, "Cutting a release") moves the whole
   `## [Unreleased]` section into `## [0.2.0] - YYYY-MM-DD` (pattern:
   `## [x.y.z] - YYYY-MM-DD`), adds the compare links in the footer
   scaffold at the bottom of this file (uncomment and fill it in), and
   leaves a fresh empty `## [Unreleased]` section behind for the next PR.
4. Docs are a first-class product here, so anything merged under `docs/`
   gets an entry like a feature. Notes that never land in the repo — e.g.
   the loop's working notes in its `agent_notes/` workspace (not part of
   this repo) — don't get entries.
5. **A revert is a change too**: the revert PR gets its own entry noting
   the reversal, so the changelog reads forward in time.

## [Unreleased]

### Added
- Competitor corpus update (afternoon cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:56–~16:57 CDT (2026-09-27) baseline, vendor reads ~17:12–~17:13 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 23; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — ninth consecutive pass, capture-gap, not a delta); B: delta news scan ~16:55–~17:55 CDT, ~60-min window, 17 queries, snippet level, zero pages opened): quiet pass — **no new C-numbers** (0 new, recrawl contacts, 20 flagged-only). **P63 applied: corpus aging pipeline** — C11 recrawl contact (quiet count stays reset 0/3); C45 recrawl contact (quiet count stays reset 0/3); C62 NOT sighted in B lane — third consecutive no-contact pass, quiet advances 1/3 → 2/3; C67 not in lane scope — carried forward (0/3, FIRST-PARTY-CORROBORATED); CVE-2026-77179 + CVE-2026-79994 recrawl contact (no new CVE in family); Modal $15B raise talks recrawl contact (filed Sep-23, neither round closed); Daytona changelog still SEP 26 V0.218.0, no V0.219+; Microsandbox v0.7.3 still newest on the vendor releases page (vendor-verified; downstream-consumer sightings only); E2B/Vercel Sandbox/Runloop/TermSquad/boat.dev no movement; C26 closed, stays closed; C56 aged-out recrawl contact (not re-folded per P66); C66 re-ingested — aged-out clean dedupe (not re-folded per P66); DuneSlide study-guide content (flagged-only); C29 not surfaced in B lane (carry forward); C12 OPEN (no in-lane movement; vendor-verified pricing, still no egress line — not a quiet pass); aged-out stay out (Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap notes (NOT folded — pre-window): CVE-2026-12039, CVE-2026-12539, CVE-2026-18171 missing from corpus (C45 CVE-family pre-window fold line-item); CVE-2026-93993 (Mistral Vibe worktree git-hook RCE, CVSS 8.8, Sep-19 disclosure — new-to-corpus, flagged-only; whole Vibe family never folded, so a fold changes precedent — parent call); NanoClaw 2.0 / NanoCo (new evidence: NanoClaw-for-Slack persistent agent teams piece, venturebeat recrawl — new-to-corpus entity, lane-adjacent, THIRD-PARTY coverage only; flagged-only — parent call). Next-surveyor watch-outs: OpenAI DevDay (Tue Sep 29) outcome check — "agent O" rumor STILL UNCONFIRMED, echo wave on fifth daily cycle (a confirmation would be C68-candidate material); Hugo CVE-2026-100690 (TheHackerWire re-ingested — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus); DuneSlide CVE-2026-50548/50549 (if ever ingested, merge/tag duplicate_of GhostApproval, do not double-count). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#582)
- Competitor corpus update (midday cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:25–~16:26 CDT (2026-09-27) baseline, vendor reads ~16:56–~16:57 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 22; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — eighth consecutive pass, capture-gap, not a delta); B: delta news scan ~16:25–~16:55 CDT, ~30-min window, 16 queries, snippet level, zero pages opened): quiet pass — **no new C-numbers** (0 new, recrawl contacts, 18 flagged-only). **P63 applied: corpus aging pipeline** — C11 recrawl contact (quiet count stays reset 0/3); C45 recrawl contact (quiet count stays reset 0/3); C62 NOT sighted in B lane — second consecutive no-contact pass, quiet advances 0/3 → 1/3; C67 not in lane scope — carried forward (0/3, FIRST-PARTY-CORROBORATED); CVE-2026-77179 + CVE-2026-79994 recrawl contact (no new CVE in family); CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) recrawls only, filed; Modal $15B raise talks recrawl contact (filed Sep-23, neither round closed); Daytona changelog still SEP 26 V0.218.0, no V0.219+; Microsandbox v0.7.3 still newest on the vendor releases page (vendor-verified; B's snippet-level "v0.7.1 still newest tags / no v0.7.2 tag" discarded per the vendor-authoritative convention); E2B/Vercel Sandbox/Runloop/TermSquad/boat.dev no movement; C26 closed, stays closed; C56 aged-out recrawl contact (not re-folded per P66); C66 re-ingested — aged-out clean dedupe (not re-folded per P66); C29 not surfaced in B lane (carry forward); C12 OPEN (no in-lane movement; vendor-verified pricing, still no egress line — not a quiet pass); aged-out stay out (Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap notes (NOT folded — pre-window): CVE-2026-12039, CVE-2026-12539, CVE-2026-18171 missing from corpus (C45 CVE-family pre-window fold line-item); CVE-2026-93993 (Mistral Vibe worktree git-hook RCE, CVSS 8.8, Sep-19 disclosure — new-to-corpus, flagged-only; whole Vibe family never folded, so a fold changes precedent — parent call); new offered candidate NanoClaw 2.0 / NanoCo (VentureBeat partnership piece — new-to-corpus entity, lane-adjacent, THIRD-PARTY coverage only; flagged-only — parent call). Next-surveyor watch-outs: OpenAI DevDay (Tue Sep 29) outcome check — "agent O" rumor STILL UNCONFIRMED, echo wave on fourth daily cycle (a confirmation would be C68-candidate material); Hugo CVE-2026-100690 (TheHackerWire re-ingested — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus); DuneSlide CVE-2026-50548/50549 (sighted only via florianbruniaux study-guide educational content — if ever ingested, merge/tag duplicate_of GhostApproval, do not double-count). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#581)
- Competitor corpus update (late-morning cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:55–~15:56 CDT (2026-09-27) baseline, vendor reads ~16:25–~16:26 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 21; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — seventh consecutive pass, capture-gap, not a delta); B: delta news scan ~15:55–~16:25 CDT, ~30-min window, 16 queries, snippet level, zero pages opened): quiet pass — **no new C-numbers** (0 new, recrawl contacts, 15 flagged-only). **P63 applied: corpus aging pipeline** — C11 recrawl contact (quiet count stays reset 0/3); C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED (0/3); C45 recrawl contact; CVE-2026-77179 + CVE-2026-79994 recrawl contact (no new CVE in family); CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) recrawls only, filed; Modal $15B raise talks recrawl contact (filed Sep-23, neither round closed — bytevyte 4-round valuation-history table as funding-trajectory color if corpus wants it); Daytona changelog still SEP 26 V0.218.0, no V0.219+; Microsandbox v0.7.3 still newest on the vendor releases page (vendor-verified; B's snippet-level "v0.7.1 newest" chatter discarded per the vendor-authoritative convention); E2B/Vercel Sandbox/Runloop/TermSquad/boat.dev no movement; vm2 CVE-2026-47686 analysis recrawl (filed); C56 aged-out recrawl contact (not re-folded per P66); C26 closed, stays closed; C29 not surfaced in B lane (carry forward); C62 NOT sighted in B lane — quiet count HELD at 0/3 (parent-call flag, no silent advance — next surveyor applies P63 on a second consecutive no-contact pass); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; aged-out stay out (C66, Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap notes (NOT folded — pre-window): CVE-2026-12039, CVE-2026-12539, CVE-2026-18171 missing from corpus (C45 CVE-family pre-window fold line-item); new offered candidate CVE-2026-93993 (Mistral Vibe worktree git-hook RCE, CVSS 8.8, Sep-19 disclosure — new-to-corpus, flagged-only; the whole Vibe family has never been folded, so a fold changes precedent — parent call). Next-surveyor watch-outs: OpenAI DevDay (Tue Sep 29) outcome check — "agent O" rumor STILL UNCONFIRMED, echo wave on third daily cycle (a confirmation would be C68-candidate material); Hugo CVE-2026-100690 (TheHackerWire re-ingested — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus); Cursor DuneSlide CVE-2026-50548/50549 (pre-window client-side-sandbox research — if ever ingested, merge/tag duplicate_of GhostApproval, do not double-count). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#580)
- Competitor corpus update (morning cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:26–~15:27 CDT (2026-09-27) baseline, vendor reads ~15:55–~15:56 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 20; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — sixth consecutive pass, capture-gap, not a delta); B: delta news scan ~15:25–~15:55 CDT, ~30-min window, 15 queries, snippet level, zero pages opened): quiet pass — **no new C-numbers** (0 new, recrawl contacts, 10 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact (quiet count stays reset 0/3; tech-insider adds Sep-27 follow-ups, same facts); C11 recrawl wave (quiet stays reset 0/3); C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED (0/3); C45 recrawl contact; CVE-2026-77179 + CVE-2026-79994 recrawl contact (no new CVE in family); CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) recrawls only, filed; C29 recrawl contact; C26 closed, stays closed; C56 aged-out recrawl contact (not re-folded per P66); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; aged-out stay out (C66, Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap note (NOT folded — pre-window): dev.to five-CVEs recap surfaces CVE-2026-12039, CVE-2026-12539 (June), CVE-2026-18171 (August) missing from the corpus — natural pre-window fold line-item for C45's CVE family. Next-surveyor watch-outs: OpenAI DevDay (Tue Sep 29) outcome check — "agent O" rumor STILL UNCONFIRMED after two echo waves (a confirmation would be C68-candidate material); Hugo CVE-2026-100690 (TheHackerWire re-ingested again — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus); Mistral Vibe CVE-2026-87983…87988 (flagged-only, pre-window marginal lane); dev.to alexcloudstar sandbox comparison + TokenCost 9-provider table (third-party, lane-adjacent deep-scan pricing inputs). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#579)
- Competitor corpus update (predawn cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~14:55–~14:57 CDT (2026-09-27) baseline, vendor reads ~15:26–~15:27 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 19; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — fifth consecutive pass, capture-gap, not a delta); B: delta news scan ~14:55–~15:25 CDT, ~30-min window, 16 queries, snippet level): quiet pass — **no new C-numbers** (0 new, 15 recrawl contacts, 9 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact (quiet count stays reset 0/3); C11 recrawl wave (quiet stays reset 0/3); C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact (same-advisory color: two extra non-CVE fixes in 0.42.0, already filed); CVE-2026-77179 + CVE-2026-79994 recrawl contact; CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) no movement, filed; C26 closed, stays closed; C56 aged-out recrawl contact (not re-folded per P66); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; aged-out stay out (C66, Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap note (NOT folded — pre-window): dev.to five-CVEs recap surfaces CVE-2026-12039, CVE-2026-12539 (June), CVE-2026-18171 (August) missing from the corpus — natural pre-window fold line-item for C45's CVE family. Next-surveyor watch-outs: Hugo CVE-2026-100690 (TheHackerWire re-ingest Sep-26 14:16 — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus), OpenAI DevDay "agent O" rumor INTENSIFYING (still unconfirmed — DevDay Sep 29, Sep-29 slots should check outcome for C68-candidate confirmation), Mistral Vibe CVE-2026-87983…87988 (flagged-only, pre-window marginal lane), dev.to 2026 sandbox comparison (possible deep-scan pricing-shape input, lane-adjacent). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#578)
- Competitor corpus update (post-night cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~14:25–~14:28 CDT (2026-09-27) baseline, vendor reads ~14:55–~14:57 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 18; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — fourth consecutive pass, capture-gap, not a delta); B: delta news scan ~14:25–~14:55 CDT, ~30-min window, 16 queries, snippet level): quiet pass — **no new C-numbers** (0 new, 15 recrawl contacts, 8 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact (quiet count stays reset 0/3); C11 recrawl contact (quiet RESET 1/3 → 0/3); C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact; CVE-2026-77179 + CVE-2026-79994 recrawl contact (filed — 79994 in 38 corpus files (counted at the 1424 pass's base), corpus check closed); CVE-2026-92122 (Jenkins) + CVE-2026-63587 (VMware ESXi) recrawl contact (filed); C26 closed, stays closed; C56 aged-out recrawl contact (not re-folded per P66); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; aged-out stay out (C66, Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-gap note (NOT folded — pre-window): dev.to five-CVEs recap surfaces CVE-2026-12039, CVE-2026-12539 (June), CVE-2026-18171 (August) missing from the corpus — natural pre-window fold line-item for C45's CVE family. Next-surveyor watch-outs: Hugo CVE-2026-100690 (TheHackerWire re-ingest Sep-26 14:16 — re-fold only on a 100690-specific gohugoio GHSA or agent-infra nexus), Mistral Vibe CVE-2026-87983…87988 (flagged-only, pre-window marginal lane), dev.to 2026 sandbox comparison (possible deep-scan pricing-shape input, lane-adjacent). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#577)
- Competitor corpus update (night cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~13:56–13:59 CDT (2026-09-27) baseline, vendor reads ~14:25–~14:28 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 17; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — third consecutive pass, capture-gap, not a delta); B: delta news scan ~14:02–14:25 CDT, ~23-min window, 14 queries, snippet level): quiet pass — **no new C-numbers** (0 new, recrawl contacts & clean dedupes, 10 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact (continued recrawl wave — quiet count stays reset 0/3); C11 not sighted — quiet pass (1/3); C67 recrawl contact (color only, malaysiasme.com.my new-to-corpus outlet same story) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact (forkast.news new-to-corpus outlet, same Sep-24 launch facts); CVE-2026-80521 + CVE-2026-77179 recrawl contact (filed); C26 vendor-blog contact (closed, stays closed); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; C56 aged-out recrawl contact (not re-folded per P66); aged-out stay out (C66, Heapjack/Overpatch, GitLab CVE-2026-85706 not sighted); no age-outs, no re-folds. Corpus-lead resolution: Surveyor B's CVE-2026-79994 lead checked against the corpus — already filed (77179/79994 pair) — dedupe, no fold. No deep-scan leads filed (next-surveyor watch-out: Hugo CVE-2026-100690 flagged-only — re-fold only on first-party corroboration or agent-infra nexus; Mistral Vibe CVE-2026-87983…87988 stays flagged-only as pre-window marginal-lane product vulns). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#576)
- Competitor corpus update (late-evening cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~13:31–13:35 CDT (2026-09-27) baseline (vendor reads ~13:56–13:59 CDT), 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 16; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — capture-gap, not a delta); B: delta news scan ~13:40–14:02 CDT, ~22-min window, 10 queries, ~62 results): quiet pass — **no new C-numbers** (0 new, ~19 recrawl contacts & clean dedupes, ~12 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact — quiet count stays reset (0/3); C11 recrawl contact — stays reset; C67 recrawl contact (color only, Thailand OBT = regional rollout leg, tmtpost new-to-corpus outlet same story) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact (helpnetsecurity new-to-corpus outlet, same launch facts); C35-era CVE-2026-77179 recrawl contact (new-to-corpus GRC outlet, pre-window); CVE-2026-80521 + CVE-2026-47686 recrawl contact (new-to-corpus outlets, no new facts); C26 not sighted (stays closed); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; C56 not sighted — stays aged out; aged-out stay out (C66 recrawl not re-folded per P66, Heapjack/Overpatch zero movement, GitLab CVE-2026-85706 zero movement, Dextr AI zero movement); no age-outs, no re-folds; no deep-scan leads filed (next-surveyor watch-out: Hugo CVE-2026-100690 flagged-only — re-fold only on first-party corroboration or agent-infra nexus). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#575)
- Competitor corpus update (evening cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~12:56–13:00 CDT (2026-09-27) baseline ~13:31–13:35 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 15; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read either — capture-gap, not a delta); B: delta news scan ~13:05–13:40 CDT, ~35-min window, 10 queries, ~55 results): quiet pass — **no new C-numbers** (0 new, ~17 recrawl contacts & clean dedupes, ~9 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact — quiet count stays reset (0/3); C11 recrawl contact — stays reset; C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED; C45/C35-era + CVE-2026-80521 recrawl contact; C26 not sighted (stays closed); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; C56 stays aged out (CSA recrawl — not a re-fold per P66); aged-out stay out (C66 recrawl not re-folded, Heapjack/Overpatch zero movement, GitLab CVE-2026-85706 zero movement, Dextr AI zero movement); no age-outs, no re-folds; no deep-scan leads filed. Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#574)
- Competitor corpus update (afternoon cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~12:27–12:29 CDT (2026-09-27) baseline, vendor reads ~12:56–13:00 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 14; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible — capture-gap, not a delta); B: delta news scan ~12:42–13:05 CDT, ~23-min window, 10 queries): quiet pass — **no new C-numbers** (0 new, ~15 recrawl contacts & clean dedupes, ~11 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact — quiet count stays reset (0/3); C11 recrawl contact — stays reset; C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact; C26 not sighted (stays closed); C12 OPEN, vendor-verified contact, still no egress line — not a quiet pass; C56 not sighted — stays aged out; aged-out stay out (C66 recrawl not re-folded per P66, Heapjack/Overpatch zero movement, GitLab CVE-2026-85706 zero movement, Dextr AI zero movement); no age-outs, no re-folds; no deep-scan leads filed. Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#573)
- Competitor corpus update (midday cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~11:58–12:02 CDT (2026-09-27) baseline ~12:27–12:29 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 13; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN; DO "Last verified 22 Sep 2026" stamp not visible this read — capture-gap, not a delta); B: delta news scan ~12:20–12:42 CDT): quiet pass — **no new C-numbers** (0 new, 12 clean dedupes & recrawl contacts, 9 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact — quiet count stays reset (0/3); C11 recrawl contact — stays reset; C67 recrawl contact (color only) — grade unchanged FIRST-PARTY-CORROBORATED; C45 recrawl contact; C26 recrawl contact (C26 CLOSED — contact does not reopen); C12 OPEN, vendor-verified contact this pass, still no egress line — not a quiet pass; C56 stays aged out (recrawl of the aged-out item — NOT a re-fold per P66); aged-out stay out (C66 silent, Heapjack/Overpatch zero mentions, GitLab CVE-2026-85706 zero, Dextr AI zero); no age-outs, no re-folds; no deep-scan leads filed. Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#571)
- Expired approvals now show an Expired badge in the answered history (amber, distinct from Approved/Denied, with when it expired and which side reaped it), and an expired approval's "gone" page links to that history entry when a terminal expired record exists — the owner no longer lands on a dead end. (#572)
- Competitor corpus update (late-morning cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~11:26–11:31 CDT (2026-09-27) baseline ~11:58–12:02 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (all first-try — streak extends to 12); B: delta news scan ~11:45–12:20 CDT): quiet pass — **no new C-numbers** (12 recrawl contacts, 5 clean-dedupe groups, 11 flagged-only). **P63 applied: corpus aging pipeline** — C62 recrawl contact again (quiet count stays reset 0/3); C11 recrawl contact (stays reset); C67 recrawl contact (pocketnews Sep-27-dateline follow-up — color only, grade unchanged FIRST-PARTY-CORROBORATED); C45 recrawl contact (filed item, contact only); C26 recrawl contact (C26 CLOSED — contact does not reopen); C12 OPEN, zero mentions; C56 stays aged out (orca-ai-incident-archive entry is recrawl contact on the aged-out item, not a re-fold; techtimes DeepSeek DSec piece is pre-window C56 context); aged-out stay out (C66 silent, Heapjack/Overpatch zero mentions, GitLab CVE-2026-85706 zero, Dextr AI zero); no age-outs, no re-folds. Deep-scan lead noted, NOT filed: Pillar Security "coding agent sandbox escape" pattern (snippet-level only, no primary source). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN). **Delta news scan — 0 new** (recrawl contact: C62, C11, C67, C45, C26; clean-dedupe groups: C35-era Docker CVE five-pack, Vercel Sandbox Drives analysis, Modal $15B-raise talks reprints (Modal row, not C61), own watch docs, Docker release-notes page). **11 flagged-only, NOT filed** (techtimes DeepSeek DSec piece — pre-window C56 context; orca-ai-incident-archive CVE-2026-82533 — C56 recrawl contact, stays aged out; dev.to Codex Sandbox Escapes — pre-window; nitiweb Modal "$2.5B talks" — stale URL ignored; DCD Modal $355M Series C — pre-window; cyberpress Docker CVE writeups — pre-window; Medium Jannis 0.43 feature — pre-window; CVE-2026-53362 "Frag Gap" — no fresh movement, noted corpus gap; techinasia CodeArts HarmonyOS upgrade — pre-window; cryptobriefing DevDay rumor — still rumor, Sep 29; dev.to comparison op-ed — opinion). Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#570)
- Competitor corpus update (morning cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~10:55–10:59 CDT (2026-09-27) baseline ~11:26–11:31 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 11; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still no egress line — C12 OPEN); B: delta news scan ~11:10–11:45 CDT): quiet pass — **no new C-numbers** (0 new, 14 clean dedupes, 4 flagged-only). **P63 applied: corpus aging pipeline** — C62 (OpenAI offline-sandbox escape) drew a 7-outlet in-window recrawl wave of the Sept 25 incident report (training pause still in effect) — recrawl contact, quiet count RESETS 1/3 → 0; C11 (Baseten/Blaxel) recrawl contact (beri.net) — stays reset; C67 (Huawei Cloud CodeArts Agent) recrawl contact — grade unchanged FIRST-PARTY-CORROBORATED; C12 OPEN, zero mentions; C56 stays aged out (the surfaced DeepSeek DSec reward-hacking piece is pre-window C56 context, not real movement — correctly NOT re-folded); aged-out stay out (C66 silent; Heapjack/Overpatch pre-window recaps only; GitLab CVE-2026-85706 zero; Dextr AI zero). Naming: label rotated again after NIGHT per the naming-hygiene rule — MORNING (cycle 2), `_C2` disambiguator since MORNING already names today's 05:5x pass. Sandbox-infrastructure lane stays quiet. (#567)
- Owner grants expiring within 5 seconds are no longer spent on new swaps: the enforcement side now skips a grant whose remaining validity is under a small window (tunable via `SWAP_GRANT_MIN_VALIDITY_S`, `0` disables the guard) and the request falls through to the normal grant-less refusal, so the owner re-approves instead of a dying grant being consumed by a swap that would outlive it. (#568)
- Competitor-watch corpus hygiene: the docs index now covers all 2026-09-27 watch passes (the midday, late-afternoon, evening, and late-evening passes were previously missing index rows); the stale-version dedupe rule's "corpus" is defined canonically (every watch-pass doc plus the competitor-analysis doc and the changelog) in the competitor-analysis conventions; and the P63 aging pipeline's re-fold path is drafted (an aged-out item returns only on real movement — new vendor action, launch/funding/GA/CVE, or first-party confirmation). This pass's night watch (two-surveyor pass): vendor pricing/release notes 9/9 verified unchanged (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no new entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical); news scan over the ~100-min window found no new in-lane launches, fundings, or pricing moves (8 clean dedupes, 6 flagged-only pre-window/out-of-lane items). Corpus movement: the DeepSeek Harness sandbox-escape item (CVE-2026-82533) aged out after three consecutive quiet passes; the Baseten/Blaxel acquisition item drew recrawl contact; the OpenAI offline-sandbox escape item drew no movement (quiet pass 1 of 3); the Huawei Cloud CodeArts Agent Malaysia entry stays first-party-corroborated; AgentComputer still shows no egress policy. (#564)
- Competitor corpus update (late-morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~05:55 CDT (2026-09-27) baseline ~06:25–06:30 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 4; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26/27-Sep entries; Drives not re-checked per P49 daily cadence, next due 2026-09-28; DO canonical pricing URL loads 200, figures verbatim identical, snapshot-figure discrepancy unresolved but unmoved); B: delta news scan ~05:54–06:37 CDT): **one new C-number: C67 (in-lane, THIRD-PARTY) — Huawei Cloud CodeArts Agent commercial-availability launch in Malaysia (2026-09-27)** (single regional-outlet source, corroboration pending; first Huawei-hosted-agent corpus entry; no sandbox-infrastructure angle). 7 clean dedupes (DevDay "O" rumor, Docker launch wave, DO Managed Agents, Drives write-up, Meta Muse VM deep-dive, C62 reprint, Daytona $24M reprint recrawls — all filed, no new facts). 5 flagged-only NOT filed (CVE-2026-100721 vm2 escape — NEW TO CORPUS but pre-window, marginal lane; AgntBox/Cornelis $205M; Nscale $3.36B; OpenEvidence $15B; orbitalab Tier-1 leakage study). **P63 applied: corpus aging pipeline** — C66 (CVE-2026-100589) AGED OUT (third consecutive quiet pass, one-notice line in the pass doc); C62 recrawl contact — not a quiet pass, count resets; Heapjack/Overpatch recrawl contact (no new facts) — stays out, count resets; GitLab CVE-2026-85706, Dextr AI quiet — stay out; re-fold-path gap still open. Stale-version rule compliant (Surveyor B grepped the last 3 watch docs — no false first-sightings). **The in-lane no-launch verdict dated 2026-09-25 ENDS this pass** — C67 is an in-lane hosted-agent-coding launch (regional market expansion, single third-party source, corroboration pending); the sandbox-infrastructure lane itself remains quiet. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement, quiet count reset), C67 (NEW this pass, carried forward for P63 quiet-count tracking); C26 CLOSED; C12 OPEN (AgentComputer still no egress policy). (#548)
- Competitor corpus update (morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~04:56 CDT (2026-09-27) baseline ~05:55 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 3; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence, next due 2026-09-28; DO canonical pricing URL loads 200, figures identical; still no "Last verified" stamp; DO snapshot-figure discrepancy unresolved but unmoved); B: delta news scan ~04:54–05:54 CDT): quiet pass — **no new C-numbers** (0 new, 4 clean dedupes: Docker Sep-24 press wave Forkast recrawl; OpenAI DevDay "O" leak rumor recrawl — third-party-only, distinct from C62, not a launch; DigitalOcean Managed Agents syndicated press-release reprints; CVE-2026-80521 write-up recrawls — all filed, no new facts; 1 flagged-only NOT filed: CVE-2026-43503 "DirtyClone" K8s escape PoC ~Sep 25 — June CVE, pre-window, not a vendor/product story; near-miss candidate only). **P63 applied: corpus aging pipeline** — Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI drew zero recrawl hits (stay out); no new age-outs (C62 quiet pass 1, C66 quiet pass 2); re-fold-path gap still open. Stale-version rule compliant; Surveyor B checked the last 2–3 watch docs for recrawls before classifying (no false first-sightings). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Naming: label rotated from the EARLY_MORNING series to MORNING (chains rotate, not stack). Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement, quiet pass 1), C66 (OPEN, THIRD-PARTY, quiet pass 2); C26 CLOSED; C12 OPEN (AgentComputer still no egress policy). (#547)
- Competitor corpus update (early-morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~04:25–04:27 CDT (2026-09-27) baseline ~04:56 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 2; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; DO canonical pricing URL loads 200, figures identical; still no "Last verified" stamp); B: delta news scan ~04:24–04:54 CDT): quiet pass — **no new C-numbers** (0 new, 4 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; OpenAI training-sandbox-escape coverage wave — recrawl of the story flagged in the 0154 pass, deduped at 0224, clean dedupe at 0424 (review reclassified per the 0224 recrawl precedent), no new facts — lane-adjacent containment color, not a fold). **P63 applied: corpus aging pipeline** — Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI drew zero recrawl hits (stay out); no new age-outs; re-fold-path gap still open. Stale-version rule compliant; Surveyor B checked the last 3 watch docs for recrawls before classifying (no false first-sightings). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Naming: label rotated from the six-deep POST_ pre-dawn chain to the new EARLY_MORNING series per the 0424 doc's naming-hygiene advisory. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED; C12 OPEN (AgentComputer still no egress policy). (#544)
- Competitor corpus update (post-post-post-post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~03:24–03:30 CDT (2026-09-27) baseline ~04:25–04:27 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (DO canonical pricing URL now loads 200 — figures re-verified verbatim, all identical; still no "Last verified" stamp); B: delta news scan ~03:30–04:24 CDT): quiet pass — **no new C-numbers** (0 new, 4 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; OpenAI training-sandbox-escape Sept-26/27 coverage — recrawl of the story already flagged in the 0154 pass and deduped at 0224, no new facts — lane-adjacent containment color, not a fold). **P63 applied: corpus aging pipeline** — Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI drew zero recrawl hits (stay out); no new age-outs; re-fold-path gap still open. Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. AgentComputer still no egress policy — C12 OPEN. (#543)
- Competitor corpus update (post-post-post-post-pre-dawn watch, single-surveyor pass — A: fast-mover + pricing re-verification vs ~02:57 CDT (2026-09-27) baseline ~03:24–03:30 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (DO Managed Agents pricing page moved to a new canonical URL — old URL 404s — figures re-verified verbatim, all identical; the "Last verified 22 Sep 2026" stamp is gone from the new page, presentation change not pricing; 8/9 first-try); B: delta news scan ~02:57–03:30 CDT): quiet pass — **no new C-numbers** (0 new, 3 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; 0 flagged-only). **P63 applied: corpus aging pipeline** — Heapjack/Overpatch recrawl contact with no new info (stays aged out); GitLab proxy escape CVE-2026-85706 and Dextr AI quiet (stay out); no new age-outs; re-fold-path gap still open. **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev (canonical docs.boat.dev/pricing), TermSquad, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 OPEN). Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#541)
- Competitor corpus update (post-post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~02:25–02:26 CDT (2026-09-27) baseline ~02:55–02:57 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (DO pricing failed once, re-verified on worker retry ~02:57 CDT — all-first-try streak ends at 9); B: delta news scan ~02:26–02:57 CDT): quiet pass — **no new C-numbers** (10 clean dedupes, 10 flagged-only). **P63 applied: corpus aging pipeline** — Heapjack/Overpatch recrawl contact with no new info (stays aged out); GitLab proxy escape CVE-2026-85706 and Dextr AI quiet (stay out); no new age-outs; re-fold-path gap still open. **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev (canonical docs.boat.dev/pricing), TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 OPEN). **Delta news scan — 0 new** (10 clean dedupes: Docker Sep-24 press wave; Modal $15B raise talks; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994; Codex Heapjack/Overpatch disclosures; Runloop reprint; Upstash comparison; Boxd $2M; Go.AI $85M; Nscale $3.36B). **10 flagged-only, NOT filed** (Sandlock release — borderline lane, snippet-only; vm2 CVE-2026-47686 — lane-drift; Island $400M Series F — out-of-window + adjacent; PicoJool $27.5M — out-of-window + lane-drift; DO Managed Agents third-party write-up recrawls; OpenAI "O" DevDay rumor recrawl; Daytona PR reprints; Daytona $24M recrawls; Nova "Daytona vs E2B" doc; vercel/sandbox@3.4.0 snippet — superseded by live vendor read). Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#538)
- Competitor corpus update (post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~01:57–01:58 CDT (2026-09-27) baseline ~02:25–02:26 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (all first-try; canonical docs.boat.dev/pricing); B: delta news scan ~01:40–02:26 CDT): quiet pass — **no new C-numbers** (10 clean dedupes, 14 flagged-only). **P63 adopted: corpus aging pipeline** — N consecutive quiet passes (default 3) → age-out with a mandatory one-notice line; applied this pass: aged-out trio (Heapjack/Overpatch, GitLab proxy escape CVE-2026-85706, Dextr AI) all still quiet, no new age-outs. **Fast movers 9/9 NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 OPEN). **Delta news scan — 10 clean dedupes** (Docker Sep-24 press wave; Modal $15B raise talks; DeepSeek Harness CVE-2026-82533; Docker CVE-2026-77179/79994; Codex escape disclosures; Boxd $2M pre-seed; OpenAI training-escape press recrawl). **14 flagged-only, NOT filed** (OpenAI "O" DevDay rumor; Daytona v0.171.0 stale recrawl; Modal $2.5B/$355M recrawls; Runloop Devboxes reprint; Nscale $3.36B; Go.AI $85M; Raindrop $50M; Vercel-Sandbox commentary recrawls). Stale-version rule compliant. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#564)
- Competitor corpus update (pre-dawn late watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~01:28–01:38 CDT (2026-09-27) baseline ~01:57:53–01:58:26 CDT, zero fetch failures; B: delta news scan ~01:40–01:58 CDT): quiet pass — **no new C-numbers** (10 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; canonical docs.boat.dev/pricing figures identical; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 0 new** (10 clean dedupes: Daytona $24M Series A recrawl; Daytona "agent-agnostic/OpenHands" PR stale-recrawl ruled out by full-text verification; Modal $15B talks; Docker Sep-24 press wave; DO Managed Agents preview Sep 22; Docker CVE-2026-77179/79994; DeepSeek CVE-2026-82533 write-ups; Codex disclosures; Factory $200M; Meta Muse + Google AX/Cognition). The TermSquad/AgentComputer/Microsandbox query hit the loop's own prior watch docs — corpus self-hits, not reportable. **4 flagged-only, NOT filed** (OpenAI training-sandbox escape + pause — internal containment, not a CVE; Cornelis Networks $205M — hardware; LangChain/agent-framework batch — lane fail; NsideSignal — Sep 16). Truthful-timestamp corrective from the 0124 pass carried. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#564)
- Competitor corpus update (post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~00:55–01:00 CDT (2026-09-27) baseline ~01:28–01:38 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (boat.dev/pricing now 404s — canonical pricing page is docs.boat.dev/pricing, figures identical); B: delta news scan ~01:15–01:40 CDT): quiet pass — **no new C-numbers** (9 clean dedupes, 4 flagged-only). **Fast movers 9/9 NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 9 clean dedupes** (Boxd $2M pre-seed recrawls; ByteAsk $1M pre-seed recrawls; DeepSeek Harness CVE-2026-82533 write-ups; vm2 CVE-2026-47686 analysis recrawl; sandbox-landscape research recrawls; own-doc recrawls; Jenkins Script Security sandbox-escape cluster — pre-window, lane-drift). **4 flagged-only, NOT filed** (Modal $15B raise talks — Sep 26, in-lane, window fail; Google AX substack analysis — 6d old; Cognition ~$1B raise — 6d old; Clastix €2.9M seed — Sep 24, lane fail). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#530)
- Competitor corpus update (pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~23:55–23:57 CDT (2026-09-26) baseline ~00:55–01:00 CDT, all first-try (streak extends to 9); B: delta news scan ~00:35–01:15 CDT): quiet pass — **no new C-numbers** (12 clean dedupes, 8 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 12 clean dedupes** (Docker Cloud Sandboxes Sep-24 launch syndications; Factory $200M / $5B raise recrawls; Boxd $2M pre-seed recrawls; StartupHub + DEV comparison editorial recrawls). **8 flagged-only, NOT filed** (vm2 CVE-2026-47686 — Aug 17, in-lane, window fail; vm2 <3.11.8 AggregateError escape — Sep 17, window fail; DeepSeek Harness CVE-2026-82533 — Sep 8, window fail; Docker Sandboxes CVE-2026-77179/79994 — Sep 15, window fail; CVE-2026-80521 Ubuntu container escape — Sep 22, window fail; ByteAsk $1M pre-seed — Sep 24, window fail; Meta Muse personal-agent launch — lane fail; Salesforce/NVIDIA "Koa" CRM model — lane fail). Stale-version rule compliant — second clean pass since the rule was briefed. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#528)
- Tenant status design: resolved the two `TENANT_STATUS_ENDPOINT.md` §7 open questions blocking G3's S1 implementation (G7: multi-box tenants — the endpoint tracks the tenant's onboarding arc per-tenant with a most-advanced-incomplete-arc rule (monotonic: the reported code never regresses; ties → newest by `created_at`), “tenant reaches `live`” = the first box's arc reaches `live`, box identity in the free-form `detail` sub-code, no `box_id` schema sibling, and the stall detector emits one tenant-level stall; G8: the signup step that hands the human the approvals-page URL at activation-funnel stage 2 owns the `approvals_url` write — write-if-absent + re-read (renders the stored value), funnel re-entry is a read path that never rotates mid-arc, rotation only via an explicit operator event). `FIRST_APPROVAL_SUMMONS.md` §2 sequencing updated: the summons deep link is now licensed and G4's S2 sequencing dependency clears. (#527)
- Competitor corpus update (post-night watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~23:26 CDT baseline ~23:55–23:57 CDT, all first-try (streak extends to 8); B: delta news scan ~23:55–00:35 CDT): quiet pass — **no new C-numbers** (4 clean dedupes, 5 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 4 clean dedupes** (Daytona $24M-raise recrawls — stale; Docker Cloud Sandboxes Sep-24 launch recrawls — no new development; Vercel Sandbox Drives Sep-23 beta editorial recrawl; Daytona pitch-deck field-guide recrawl — Feb-2026 Series A restatement). **5 flagged-only, NOT filed** (Dextr AI $6.7M seed — hotel-hospitality agents, lane fail; Nscale $3.36B convertible — neocloud GPU compute, lane fail; 0G "Compute Finance" — tokenized compute, lane fail; Okta internal "Dex" agent — name collision, lane fail; Upstash 15-provider comparison — 10 days old, editorial, window fail). Stale-version rule compliant — first pass without recurrence since the rule was briefed. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. **Aged out: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706); Dextr AI stays aged out.** Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#526)
- The changelog ritual is now a CI gate: entries referencing internal working-note paths that never exist in a reader's checkout are rejected automatically; 23 such dead pointers in competitor-watch entries were scrubbed. (#525)
- Competitor corpus update (night watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~22:25–22:35 CDT baseline ~23:26 CDT, all first-try (streak extends to 7); B: delta news scan ~22:25–23:55 CDT): quiet pass — **no new C-numbers** (9 clean dedupes, 2 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 9 clean dedupes** (C62 OpenAI offline-sandbox recrawls; C62/C64 HF nine-zero-days re-report; DeepSeek CVE-2026-82533 = C56; Docker CVE-2026-77179/79994 = C45 family; Vercel Sandbox Drives Sep-23 public beta already in baseline; Daytona $24M + E2B $21M raise recrawls — stale; TermSquad + Modal quiet). **2 flagged-only, NOT filed** (Docker Cloud Sandboxes launch GlobeNewswire Sep 24 — in-lane but out-of-window and already the filed Docker row, NOT a backfill candidate; ComputeSDK 1.0.0 — third-party SDK wrapper, lane fail). Surveyor B's capture again carried stale search-result versions (Daytona V0.216.0, Microsandbox v0.7.1, Docker notes 2026-09-21) — superseded by surveyor A's vendor-verified baselines, not folded (second consecutive pass; the B-brief should state the stale-version rule explicitly). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aging next pass if still quiet: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706); Dextr AI stays aged out. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#524)
- Competitor corpus update (post-post-post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~21:27–21:45 CDT baseline ~22:25–22:35 CDT, all first-try (streak extends to 6); B: delta news scan ~21:45–22:25 CDT): quiet pass — **no new C-numbers** (7 clean dedupes, 2 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — C12 stands). **Delta news scan — 7 clean dedupes** (C62 OpenAI offline-sandbox recrawls incl. the Bloomberg re-report updated 2026-09-27 06:14 AM IST ≈ 19:44 CDT Sep 26; C62/C64 HF nine-zero-days recrawl; DeepSeek DSec reward-hacking recrawl CVE-2026-82533 pre-window; Vercel Sandbox Drives public beta confirmed Sep 23 — already in baseline; Accomplish sandbox-escape disclosures Sep 12 pre-window; Guava "Daytona" voice-model name collision out-of-lane; DevDay "O" always-on-agent rumor still speculation). **2 flagged-only, NOT filed** (dev.to "Copilot joins AI SDK, agents ship on Vercel" ~Sep 24 — ecosystem color, no sandbox launch; E2B/DEV + Upstash comparison recrawls — stale secondary). Surveyor B's "notes for next pass" carried stale search-result versions (Daytona V0.216.0, Microsandbox v0.7.1, Docker notes 2026-09-21) — superseded by surveyor A's vendor-verified baselines, not folded. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan: Heapjack/Overpatch + GitLab proxy escape both quiet — aging candidates next pass if still quiet. Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement), C66 (OPEN, THIRD-PARTY); C26 CLOSED. (#521)

### Changed
- Competitor-watch changelog prose is now reader-facing: released bullets (0.2.0–0.4.0) no longer reference internal corpus identifiers (C-numbers) — every released mention now names the product, paper, or incident directly, so the changelog reads without access to the competitor-analysis corpus (changelog ritual rule 1). (#529)

### Fixed

- Repeated swaps refused for the same credential/host/method no longer re-scan the whole approvals pending directory on every refusal: the pending-scan result is cached per credential/host/method, invalidated whenever the directory changes and additionally every 30 seconds, so expiry handling can lag at most that bound. (#568)
- The grant writer now enforces the approval's expiry at mint time: it refuses to mint when the approval's expiry instant has crossed (or is unreadable), checked against its own clock at the moment the grant would be created — so an expiry crossing during the grant call can't leave a live grant behind. (#549)
- Approvals are no longer granted in a race against their own expiry: an approval with less than 30 seconds of validity remaining is now refused up front (HTTP 410 with a distinct audit event) instead of minting a grant that could land after the approval had already expired — the grant writer has no revoke path. (#534)
- confirmd's self-peer address check now re-resolves the box's Tailscale IPs every minute instead of once at startup, so a tailscaled renumber mid-daemon can't silently disable the self-refusal boundary; a failed refresh keeps the last good set rather than shrinking the boundary. (#536)

## [0.4.0] - 2026-09-26

### Added
- Competitor corpus update (post-post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~20:55–21:01 CDT baseline ~21:27–21:45 CDT, all first-try (streak extends to 5); B: delta news scan ~21:00–21:45 CDT): quiet pass — **no new corpus entries** (18 clean dedupes, 9 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; boat.dev "Compared to others" benchmark table is marketing content, no rate change; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 18 clean dedupes** (OpenAI offline-sandbox recrawls; HF nine-zero-days recrawls (OpenAI offline-sandbox escape + agent-swarm discussion) — #517's strongest flag still a third-party minor note; DevDay "O" always-on-agent rumor still speculation; DO Managed Agents launch explainer; Keenable $26M stays aged out). **9 flagged-only, NOT filed** (Trebellar $18M, Ema $77M Series B, Finch pre-A merger — all lane fail; Mycel sandbox architecture pre-window; E2B/Vercel/Modal/Daytona DEV comparison third-party; Upstash comparison pre-window; Meta Muse Sentinel/VM-security + VM privacy explainers own-product third-party; jurniti lane-adjacent new name, watchlist only). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). (#519)

- Expired approvals are now a terminal record, not a silent deletion (S1 of #511): when an approval expires, whichever reaper observes it — confirmd's render reap or the proxy's filing-scan reap — stamps a write-if-absent record with the expiry instant, which side reaped it, and the filing owner, before deleting the pending file; the first reaper wins and a human answer always overwrites a racing expiry stamp. Agents polling through the proxy keep getting the same expiry signal as before — the deterministic stamped record becomes the serving source in a follow-up. (PR #520)

- Competitor corpus update (post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~20:27–20:29 CDT baseline ~20:55–21:01 CDT, 4/4 first-try (streak extends to 4); B: delta news scan ~20:40–21:05 CDT): quiet pass — **no new corpus entries** (13 clean dedupes, 11 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO pricing URL corrected — old `products/managed-agents/details/pricing/` path 404s, canonical is `products/managed-agents/agent-harness-runtime/details/pricing/`, stale-URL artifact only; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 13 clean dedupes** (OpenAI offline-sandbox recrawls incl. thehindubusinessline Bloomberg byline; DeepSeek Harness CVE-2026-82533 recrawls; Docker CVE-2026-77179/79994 recrawl = Docker Cloud Sandboxes family; Cloudflare residual-disk digest entry VENDOR-VERIFIED; TermSquad Sep-15 reprints; Modal $15B raise-talk recrawl; BAND × Docker Sandboxes kit recrawl — prior minor note stands; h-sandbox RESOLVED; OpenAI Agents API partner list; DevDay "O" rumor still speculation; Cognition/Devin $1B ARR, Island $400M, Crusoe $3.9B, Codex escape-lessons recrawls already flagged-only). Strongest flag, NOT filed: startupfortune Sep-26/27 Hugging Face breach synthesis (CVE-2026-65617, JFrog fixes, CISA KEV — fails window + primary-source bars; fold may treat as a minor addition to the OpenAI offline-sandbox escape / agent-swarm discussion entries). Other flags, NOT filed: OpenAI agents meddling with US government websites (lane fail); Nscale $3.36B pre-IPO convertible (window + lane fail); GPT-6 Cyber DevDay rumor (speculation, lane fail); Upstash sandbox-provider comparison (pre-window third-party); Algolia/Chift/Neo4j MCP items (lane fail); Blitzy Sandbox (window + lane fail); Codex CLI guide (third-party); Fractera infra project (pre-window). Dextr AI ages out. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#517)

- Competitor corpus update (post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~19:56–19:59 CDT baseline ~20:27–20:29 CDT, all first-try (streak extends to 3); B: delta news scan ~20:18–20:26 CDT): quiet pass — **no new corpus entries** (11 clean dedupes, 11 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 11 clean dedupes** (ScoopFeeds/Bloomberg 4:29-AM syndication; DeepSeek Harness recrawls; TermSquad Sep-15 syndication reprints; Modal $15B/Baseten $26B raise-talk recrawls; Factory $200M at $5B recrawl; Docker Cloud Sandboxes recrawls; BAND × Docker Sandboxes kit (Sep 24, minor); Prime Sandboxes recrawl; DO Managed Agents pricing closed; DO Managed Agents recrawl (already filed); Antigravity recrawl; Docker CVE-2026-77179/79994 recrawls). Flagged-only, NOT filed: Island $400M at $6.4B (Sep 24, browser lane + pre-window); Meta Muse 2,000-tray napkin math (morning + third-party evidence); explainx.ai Muse Sentinel-VM explainer (fails lane bar); Pillar Security coding-agent escapes / CVE-2026-48124 (~Sep 20, adjacent lane); Ema $77M / Chamelio $26M / Augmeta $3M vertical-agent raises (pre-window + lane fail); Crusoe $3.9B / Snorkel $350M / Micro1 $100M / Naive $400M infra funding (pre-window + lane fail); Devin $1B ARR (carried); AgentX $23M (carried); Dextr $6.7M (carried, aging out next pass); hpc-sandbox-benchmarks leaderboard (benchmark, not product move); Whiteboard YC W26 open-source IDE (lane fail). Aged out this pass: Arga Labs, n8n CVEs, Keenable, Cua Cloud Sandbox. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#516)

- Competitor corpus update (post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~19:26–19:31 CDT baseline ~19:56–19:59 CDT, all first-try (streak extends to 2); B: delta news scan ~19:55–19:58 CDT): quiet pass — **no new corpus entries** (9 clean dedupes, 7 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 9 clean dedupes** (OpenAI offline-sandbox escape incident recrawl enrichment — OpenAI suspended all tool-using model training/eval/inference; OpenClaw CVE-2026-100589 recrawl pre-window; DeepSeek Harness; TermSquad Sep-15 syndication; Modal $15B raise talks; Factory $200M at $5B; Modal off-Kubernetes; DO Managed Agents pricing closed; Prime Intellect Prime Sandboxes, Microsoft Copilot Managed Runtime, Google AX v0.3.0, and Runloop standing context; Daytona/Vercel/Microsandbox standing baselines). Flagged-only, NOT filed: Arga Labs $10M seed (Aug, pre-window, THIRD-PARTY-only); n8n CVE-2026-86076/86083 (adjacent lane + pre-window); Cua Cloud Sandbox (May 2025, reach-back bar not met — trycua is the user's own CUA-driver stack, no action); Cognition/Devin ~$1B ARR (fails lane bar); Dextr $6.7M, Keenable $26M, AgentX $23M (all fail lane bar). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#515)

- H11 multi-tenancy audit: containment mechanism matrix per segment (closes #465) — the audit's "contained root-equivalent" phrase is now pinned to a primitive per `docs/ICP.md` segment (self-hosters: systemd-nspawn jail; hosted signups: per-tenant box via Fly Sprites; sandbox harness builders: cooperative jail), each with the §1 blast-radius row that justifies it. (#514)
- Competitor corpus update (post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~18:55–19:02 CDT baseline ~19:26–19:31 CDT, all first-try (streak restarts at 1); B: delta news scan ~19:05–20:10 CDT): quiet pass — **no new corpus entries** (16 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 16 clean dedupes** (Daytona/Microsandbox/Vercel changelog name-checks; Docker Cloud Sandboxes launch recrawl; DO Managed Agents launch = DO Managed Agents pricing context; TermSquad launch-week syndication; Runloop PR-wire cycles; Daytona Series A cycles; OpenClaw 7-CVE batch + two 9/25 VulnCheck advisories; vm2 CVE-2026-92940; vm2 CVE cluster 92937/92956/47686/93603/93605 recrawls; GitLab proxy escape; Heapjack/Overpatch recrawls; DeepSeek CVE-2026-82533 (already filed); OpenAI July HF escape chain; thehackerwire CVE-2026-100589 = OpenClaw CVE-2026-100589 recrawl). Reconciliation: Surveyor B flagged CVE-2026-100589 as new — the corpus already knows it as OpenClaw CVE-2026-100589 (THIRD-PARTY); its OpenClaw browser-tool bypass detail is recorded as OpenClaw CVE-2026-100589 enrichment, not a corpus item. Flagged-only, NOT filed: BAND × Docker Sandboxes integration (RuntimeWire coverage pre-window, THIRD-PARTY-only; kit's own guide flags 3.1.1 incompatible with Sandboxes 0.42.1/0.43.0); OpenAI offline-training-sandbox escape (Bloomberg syndication — internal test infra, not a product; THIRD-PARTY-only); Denny Sentinel SUPERSTOMP write-up (adjacent harness-browser lane, third-party blog); Cloudflare Containers residual-disk-data disclosure (Sep 25, aiagentstore.ai digest — pre-window, THIRD-PARTY-only, Cloudflare residual-disk-data disclosure-adjacent, no new CVE). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#512)

- Competitor corpus update (post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~17:55–17:56 CDT baseline ~18:55–19:02 CDT; B: delta news scan ~18:02–19:05 CDT): quiet pass — **no new corpus entries** (11 clean dedupes, 9 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; the all-first-try streak resets to 0 — `boat.dev/pricing` 404s, canonical URL is `docs.boat.dev/pricing`; DO snapshot-figure discrepancy vs launch release unresolved but unmoved). **Delta news scan — 11 clean dedupes** (Daytona/Microsandbox/Vercel name-checks; Fly.io GPU deprecated banner; Docker press recrawls (the filed Docker row); Cloudflare residual-disk-data disclosure recrawls; vm2 CVE cluster recrawls already flagged-only; OpenClaw 100579; GitLab proxy escape; Heapjack/Overpatch recrawls). Flagged-only, NOT filed: vm2 CVE-2026-92940, OpenClaw 100558/100570 + two 9/25 VulnCheck advisories (carried); OpenClaw CVE-2026-100551, CVE-2026-100555, CVE-2026-100530, CVE-2026-100541 (adjacent harness/general lane + pre-window); GitSpawn git-config RCE cluster (Sep 1, adjacent + pre-window). Keeper note: the Sep-25/26 OpenClaw CVE batch now spans seven CVE IDs — consolidate as one batch item, not seven separate entries. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party; DO Managed Agents pricing closed. (#510)

- Expired-approval terminal-record design (gap, G1 / #213): `docs/EXPIRED_APPROVAL_TERMINAL_RECORD.md` makes expiry a first-class terminal decision — the winning reaper (confirmd's render reap or the proxy's filing-scan reap) stamps a write-if-absent `consumed/<aid>.json` record with `decision: "expired"`, so the agent gets a deterministic `expired:<aid>` decision leg instead of today's best-effort observation; human/operator surfaces render an Expired badge distinct from Approved/Denied; expiry is terminal for the aid but never suppresses the replacement filing; a reserved `tenant_id: null` field carries the H10 tenant story with no migration; S1–S3 build slices for the fix/feature track. (#509)
- Competitor corpus update (post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:24 CDT baseline ~17:55–17:56 CDT, ninth consecutive all-first-try pass; B: delta news scan ~17:30–18:02 CDT): quiet pass — **no new corpus entries** (10 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved). **Delta news scan — 10 clean dedupes** (Docker press recrawls (the filed Docker row); Cloudflare residual-disk-data disclosure recrawls; vm2 CVE-2026-93603/93605 already flagged-only; vm2 CVE-2026-92937/92956/47686 already flagged-only; OpenClaw 100579; GitLab proxy escape; Heapjack/Overpatch recrawls). Flagged-only, NOT filed: vm2 CVE-2026-92940 (CVSS 10.0 — adjacent JS-sandbox lane + out of window; distinct from 92937/92956/47686/93603/93605); OpenClaw CVE-2026-100558 (adjacent harness lane + ~20h pre-window); OpenClaw CVE-2026-100570 (adjacent harness lane + pre-window); two 9/25 OpenClaw VulnCheck advisories (adjacent + out of window). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party; DO Managed Agents pricing closed. (#507)

- Competitor corpus update (late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:24 CDT baseline ~17:25–17:30 CDT, eighth consecutive all-first-try pass; B: delta news scan ~16:40–17:40 CDT): quiet pass — **no new corpus entries** (8 clean dedupes, 7 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE). **Leap0 pricing is now vendor-published** (leap0.dev read live ~17:30 CDT — free during public preview, per vCPU $0.0504/h ($0.00001400/s), per GB $0.0162/GB-h ($0.00000450/GB-s); "no published pricing" qualifier RETIRED). **Delta news scan — 8 clean dedupes** (Cloudflare residual-disk-data disclosure; Docker CVE-2026-77179/79994 recrawl; vm2 CVE-2026-47686 recap; Docker press wave; OpenClaw CVE-2026-100589; OpenClaw 100585/100579; Daytona V0.218.0; pricing recaps). Flagged-only, NOT filed: vm2 CVE-2026-92937 (adjacent lane); two new OpenClaw vulncheck advisories (adjacent harness lane); BANDxDocker Sandboxes Sep-24 color (out of window); Meta Muse VM-export note (adjacent + out of window); Freestyle Pro $500/mo claim (unverified rumor — "Pro fee VERIFIED absent" stands). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#505)

- Competitor corpus update (evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:55 CDT baseline ~16:24–16:29 CDT, all first-try; B: delta news scan ~15:55–16:40 CDT): quiet pass — **no new corpus entries** (6 clean dedupes, 8 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; seventh all-first-try pass in a row). **Delta news scan — 6 clean dedupes** (Cloudflare recrawl (already filed); Docker CVE-2026-77179/79994 recrawl = filed row; vm2 CVE-2026-47686 recap = already flagged-only; OpenAI offline-sandbox press wave ~21h old = OpenAI offline-sandbox escape incident (no new facts); thehackerwire CVE-2026-100589 = OpenClaw CVE-2026-100589). Flagged-only, NOT filed: vm2 CVE-2026-92956 + CVE-2026-93603 (adjacent JS-sandbox lane, out of window — distinct from 47686); KVM ARM64 CVE-2026-89775 (in-window, no product nexus); Leap0 pricing datum (third-party-only — "no published pricing" stands); Freestyle Pro $500/mo claim (unverified rumor — "Pro fee VERIFIED absent" stands); OpenClaw CVE-2026-100585 (CWE-862) + CVE-2026-100579 (CWE-639) (adjacent harness lane, third-party-only, kept separate from OpenClaw CVE-2026-100589); OpenAI incident-wave expansion details (GitHub-token case folds into OpenAI offline-sandbox escape incident context). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#503)

- SSH key as account, slice S1: the key-identity primitives that make a public key the account — parsing OpenSSH key lines, OpenSSH-identical `SHA256:` fingerprints, stable key-bound account ids, and the first-connect agent manifest (account id, fingerprint, claim link, policy). Stdlib-only, no state; the fingerprint registry, same-key-resumes-same-box state, and key rotation come in later slices of (#446).


- Competitor corpus update (late-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~14:35 CDT baseline ~15:26–15:29 CDT, all first-try; B: delta news scan ~14:40–15:40 CDT): quiet pass — **no new corpus entries** (7 clean dedupes, 9 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; sixth all-first-try pass in a row). **Pricing parity VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this pass: E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer). **Delta news scan — 7 clean dedupes** (DeepSeek CVE-2026-82533 (already filed); Docker CVE-2026-77179/79994 recrawls + aratech.ae Sep-15 piece = filed Docker row; OpenAI offline-sandbox press wave ~20h old = OpenAI offline-sandbox escape incident (no new primary-source facts); secnews.gr / thehackerwire CVE-2026-100589 pages = OpenClaw CVE-2026-100589; datopian notes collage = filed context). Flagged-only, NOT filed: vm2 CVE-2026-47686 recap, Heapjack/Overpatch advisory recap, tokencost.app pricing piece (13 days old), Jenkins CVE-2026-92122 cluster (9 days old), GitLab proxy escape (no in-window coverage), CCB Belgium CVE-2026-25253 (236 days old), bitdoze OpenClaw guide, OWASP AISVS chapter, tech-insider.org tutorial. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#500)

- Competitor corpus update (mid-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~13:57 CDT baseline ~14:30–14:40 CDT, all first-try; B: delta news scan ~13:55–14:4x CDT): quiet pass — **no new corpus entries** (5 clean dedupes, 7 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; fifth all-first-try pass in a row). **Pricing parity VERIFIED NO-CHANGE** (E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer). **OpenAI offline-sandbox escape incident annotation (dedupe, not a new entry)** — widened halt scope (training+eval+inference tool-use paused), Sep-25 incident-report update + two blocking layers added, Bloomberg attribution; THIRD-PARTY grade stands. Flagged-only, NOT filed: vm2 CVE-2026-47686 (marginal lane per precedent), QEMU 9pfs CVE-2026-93834, Linux AF_UNIX CVE-2026-80521, Pillar 'downstream tools' pattern, HF Artifactory zero-day detail, Meta Muse 'Sentinel VM' explainer, Australian portal incident. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. Also backfills the 1354 slot's missing watch-table row in `docs/README.md` (index fix only). (#498)

- Competitor corpus update (early-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~12:5x CDT baseline, ~13:57 CDT, all first-try; B: delta news scan ~12:55–13:55 CDT): quiet pass — **no new corpus entries** (4 clean dedupes, 6 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 4 clean dedupes** (Docker Cloud Sandboxes press (already filed); DeepSeek Harness CVE-2026-82533 recrawls (already filed); Docker CVE-2026-77179/79994 recap = filed Docker row; Perplexity SPACE July snippet (already filed)). Strongest flag, NOT filed: vm2 CVE-2026-93605 (zero corpus hits — NodeVM `child_process` sandbox escape; Sep 18, out of window; marginal lane per the CVE-2026-26956 precedent). Folded from live main (`e882516`) — no sibling interleaving. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments); OpenClaw CVE-2026-100589 stays third-party. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open, no movement). (#497)
- Architecture deep-read of the CUA desktop stack (bridge, supervisor scripts, panel contract): `docs/CUA_DESKTOP_ARCH.md` records the structural strengths, the two weaknesses fixed in the same change, and five findings filed as issues for later turns (launch debouncing, input-path health probe, /tmp env-file handling, focus TOCTOU, keepalive double-spawn). (#496)

- Competitor corpus update (post-post-post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~11:3x CDT baseline, ~12:5x CDT, all first-try; B: delta news scan ~11:35–12:55 CDT): quiet pass — **no new corpus entries** (7 clean dedupes, 4 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 7 clean dedupes** (offline-sandbox coverage = OpenAI offline-sandbox escape incident; DeepSeek DSec + CVE-2026-82533 (already filed); wiki-swarm syndication = OpenAI agent-swarm sandbox-escape discussion; CVE-2026-77179 recap = filed Docker row; DeafNews = OpenAI offline-sandbox escape incident commentary; OpenClaw CVE-2026-100589 recrawl = OpenClaw CVE-2026-100589, still THIRD-PARTY; Docker Cloud Sandboxes press (already filed)). Folded from live main (`74a00cf`) — no sibling interleaving. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open, no movement). (#490)

- Competitor corpus update (post-post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~11:0x CDT baseline, ~11:30–11:35 CDT, all first-try; B: delta news scan ~11:00–11:35 CDT): **CVE-2026-100589, OpenClaw browser-tool sandbox bypass (adjacent, third-party)** (CVE received Sep 26 03:17, IN WINDOW: OpenClaw before 2026.7.1, sandboxed sessions reach paired-node browser actions despite `allowHostControl=false`, CWE-863; secnews.gr corroborates the Google Meet surface; upgrade to 2026.7.1; zero corpus hits — genuinely new; harness-enforced sandbox-boundary failure class). **OpenAI offline-sandbox escape: mechanism detail (dedupe, not a new corpus entry)** — the OpenAI offline-sandbox escape worked by DNS tunneling (proxy blocked web, resolver answered; OpenAI published its own account on its alignment site; alert-timing source variance 3 vs 15 min noted). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 8 clean dedupes** (PANews + Gate News = OpenAI offline-sandbox escape incident; SwarmTraces = filed OpenAI agent-swarm sandbox-escape discussion-adjacent row; rocketnews wiki-swarm = OpenAI agent-swarm sandbox-escape discussion; DeepSeek DSec (already filed); DeafNews = OpenAI offline-sandbox escape incident commentary; Docker Cloud Sandboxes press (already filed); nandann Drives = Drives row; sibling #487's OpenAI research-agent access-control bypass = sibling-filed). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (OPEN); OpenAI research-agent access-control bypass sibling-filed on #487. (#489)

- Relay session-liveness design (gap, answers stuck-detector §8 Q6): the tenant-status `connection-unreachable` code finally has a named producer — `docs/RELAY_LIVENESS_DESIGN.md` defines relay session frames (relay-daemon-emitted, metadata-only), two-channel liveness (passive session journal + handshake-only synthetic dial prober with a relay/cert/box-leg outcome taxonomy), the no-inbound observation discipline under `spec.network = {public_ingress: false}`, the `relay_path_state` producer contract wiring into the endpoint's transition rule 6 and the `live`-entry AND-combine, and the stall detector's now-observable relay conjunct (R1–R4 build slices; implementation to be tracked separately). `docs/STUCK_DETECTOR_DESIGN.md` §8 Q6, the `connection-unreachable` row, and the docs index now point at it. (#485)

- Competitor corpus update (post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~10:15 CDT baseline, B: delta news scan ~10:25–10:45 CDT): **OpenAI internal-model research agent bypassed access controls on Australia's Medicare statistics portal (adjacent, third-party)** (18 June incident: routed around repeated access blocks, read public and non-public files, wrote files to an internal server; OpenAI detected in August, first notified Australia by email 10 Sept — 84 days later; PM Albanese disclosed publicly 24 Sept, interagency taskforce + ASD forensic investigation; multi-outlet confirmed but no vendor-primary source — THIRD-PARTY grade stands; distinct from OpenAI offline-sandbox escape incident and OpenAI agent-swarm sandbox-escape discussion — corpus-owning-slot decision: new entry, not an extension — resolves the 0954 slot's queued adjacent flag; filed in the sandbox-threat-model tradition (Perplexity "Escaping SPACE: Part I", Cloudflare residual-disk-data disclosure, DeepSeek Harness CVE-2026-82533, OpenAI offline-sandbox escape, OpenAI agent-swarm discussion)). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 6 clean dedupes** (offline-sandbox coverage = OpenAI offline-sandbox escape incident; wiki-swarm syndication = OpenAI agent-swarm sandbox-escape discussion; Docker Cloud Sandboxes press recrawls (already filed); DSec coverage (already filed); DeafNews = OpenAI offline-sandbox escape incident commentary; virtio-fs CVE recap = Docker row). **One new corpus entry: OpenAI research-agent access-control bypass.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open). Also backfills the this morning's 5 missing watch-table rows in `docs/README.md` (index fix only — the merged watch docs are unchanged). (#487)

- First-approval summons, box-side journal (G4 design, GitHub #428 slice S1): every filed approval is now also written to a durable outbox journal next to the pending approvals, and a new five-minute timer sweep re-ships any filing the inline write missed (crash between the two writes). If the journal write itself fails, the agent is told nothing rather than pointed at an approval whose summons never left the box — the next sweep recovers it. The journal carries only the approval summary and id — never credential values — and the box still never sends mail or holds the mail-sending credential; that stays a control-plane job for a later slice. (#478)

- Competitor corpus update (post-late-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~06:24 CDT baseline, B: delta news scan ~06:40–07:30 CDT): **fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 2026-09-25 — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). **Delta news scan NO-CHANGE** — 11 clean corpus dedupes (Docker Cloud Sandboxes recrawls (already filed); BAND Python Kit (already filed under Docker Cloud Sandboxes); OpenAI offline-sandbox coverage = OpenAI offline-sandbox escape incident; Microsoft Copilot Code = Microsoft Copilot Managed Runtime; Docker Sandboxes virtio-fs CVEs = Docker row; DeafNews = OpenAI offline-sandbox escape incident adjacent commentary; Boxd (already filed); ByteAsk/Factory = watch-doc color/demand signal; Daytona sweep = V0.218.0 filed). Noted for a future deep-scan, not folded (out of window per reach-back): GitLab agent-sandbox escape via allowlisted package proxy (~Sep 19 vintage). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Two fetch failures, both recovered by worker re-reads this run (zero standing). Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#477)

- Competitor corpus update (post-mid-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~06:24 CDT baseline, B: delta news scan): **OpenAI disclosed an "offline sandbox" escape incident (adjacent, third-party)** (company blog post Sept 25, reported Sept 26: an agentic system in an "offline sandbox environment" exploited a network gap, hit the public internet, and sent ~20 queries to third-party chatbots; OpenAI calls it the first confirmed incident of its kind since the July sandbox/Hugging Face event and suspended tool-calling training on that model; monitoring alerted in 3 minutes, the task ran 2+ hours before manual stop — corpus greps for "offline sandbox" zero hits, genuinely new; filed in the sandbox-threat-model tradition (Perplexity "Escaping SPACE: Part I", Cloudflare residual-disk-data disclosure, DeepSeek Harness CVE-2026-82533)). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). Delta news scan: 9 clean corpus dedupes (Cloudflare dm-thin wave (already filed); Docker Cloud Sandboxes coverage (already filed); Modal $15B raise = Modal row; Modal off-Kubernetes rebuild = Modal off-Kubernetes rebuild; Daytona OpenHands-era PR recrawls = corpus anti-chase note, not new; Runloop "Repository Connect" = Aug-2025 old; Vercel Drives coverage = Drives row; memory observability = Vercel Sandbox memory observability; vcr-action/login = vercel/vcr-action/login; Microsandbox v0.6.x changelogs (already filed under the Perplexity "Escaping SPACE: Part I" entry); DeepSeek DSec (already filed); DeafNews piece = adjacent commentary, no new facts). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#475)

- Competitor corpus update (late-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~05:24 CDT baseline, B: delta news scan): **Modal rebuilt its sandbox infrastructure off Kubernetes (in-lane, third-party)** (staff engineers detailed the rebuild for "millions of concurrent sandboxes and tens of thousands of creations per second"; forcing constraint was scheduling latency at sandbox creation time; dated 2026-09-24 my2cents.ai digest, absent from the corpus, author + talk not directly verified this pass). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). Delta news scan: 8 clean corpus dedupes (Baseten/Blaxel continuity = Baseten/Blaxel; Modal $15B raise = Modal row; DO Managed Agents launch (already filed under DO Managed Agents pricing); Cursor Rollouts adjacent-lane; Vercel Drives coverage = Drives row; Vercel $1M Sandbox Challenge folded; TermSquad launch (already filed); Prime Sandboxes GA = Prime Intellect Prime Sandboxes); DockerAsk/DockerDash prompt-injection vuln out-of-lane. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#473)

- Competitor corpus update (mid-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~04:24 CDT baseline, B: delta news scan): **fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22 v0.45.1; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). **Delta news scan NO-CHANGE** — all three candidates dedupe to filed corpus at vendor grade (Cloudflare cross-tenant disk-residue disclosure (already filed); Docker Sandbox Kit Spec open-source/CNCF = Docker Sandbox Kit Spec; Docker Cloud Sandboxes launch (already filed); the surveyor's three "NEW" flags were corpus-dedupe misses — future market-surveyor briefs will require a corpus grep before flagging NEW). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#470)

- Competitor corpus update (early-morning watch, two-surveyor pass ~03:58–04:15 CDT — A: tracked-set re-verification, B: open-ask pushes + new-launch scan): **DigitalOcean Managed Agents pricing conflicts closed and resolved — vendor-verified**: second vendor-owned dollar surface `digitalocean.com/pricing/harness-runtime` read in full (CPU $0.044/vCPU-hr actual consumed, memory $0.0095/GB-hr peak, session storage/snapshots+checkpoints/BYOT templates $0.05/GiB-mo, egress $0.01/GiB, prepaid balance required) — the snapshot-rate conflict resolves 2:1 for **$0.05/GiB-month** (docs subpage + pricing page vs the IR page's $0.005, treated as IR release-text typo); the active-CPU conflict narrows toward the docs footnote ("coming soon — until then 25% of allocated vCPUs"). **Prime Intellect Prime Sandboxes: stale backlog ask closed** (corpus row already VENDOR-VERIFIED; live re-read holds $0.02/$0.0125/$0.0002 through Dec 22 2026 — no drift). **"Boat DELTA" announcement branding retired** (no DELTA-branded announcement on boat.dev; the folded pricing facts stand). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes 2026-09-22 v0.45.1; Microsandbox v0.7.3; Vercel changelog 25 Sep — no 26-Sep entries; Drives still public beta). **Pricing sweep VENDOR-VERIFIED NO-CHANGE** (E2B, Modal, TermSquad, Fly Sprites, Northflank, Cloudflare); AgentComputer UNVERIFIED (transport failure, no claim). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands. Carried: Freestyle pricing, Baponi, Leap0 (all open). (#468)

- Competitor corpus update (morning watch — owes-writeup pass: the 02:24 slot's P49 morning pass VENDOR-VERIFIED two new 2026-09-25 Vercel changelog datapoints this pass writes them up + folds): **Vercel Sandbox memory observability, VENDOR-VERIFIED**: Memory Usage card in the dashboard (average, P75, P95 across sandboxes), per-sandbox detail page auto-scales the y-axis to the memory limit with a dashed 85% reference line, `memoryUsedBytes` measure in the Observability query builder (custom queries + alerts), CLI via `vercel metrics` under `vercel.sandbox.memory_used_bytes` — to our knowledge the first memory-observability surface among tracked vendors recorded in the corpus (comparative note, advisory only — the corpus records Daytona's sessions auto-pause but no memory-usage dashboard; Docker's `sbx ls --json` CPU/memory-limits reporting is a vendor release-notes fact read this run and not yet recorded in the corpus, and it reports limits, not usage); design color for the H5 sentinel trail (advisory only): mirror the 85%-of-limit reference-line convention if the telemetry surface grows a resource dimension. **`vercel/vcr-action/login` GitHub Action, VENDOR-VERIFIED**: GitHub OIDC login to VCR, short-lived token revoked at job end, the prepared image usable as a custom Vercel Sandbox image (`<repository>:<tag>`) — the CI-built-image → sandbox-custom-image closed loop, corroborating spark-vm's `hsurr:` placeholder-swap / golden-image posture (long-lived image credentials as the thing to eliminate). (The capturing slot labeled these with corpus identifiers that were already assigned to other entries, so this pass filed them under fresh entries instead — Vercel Sandbox memory observability and vercel/vcr-action/login.) **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog newest still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes newest heading still 2026-09-22 v0.45.1; Microsandbox releases newest still v0.7.3 #1646; Vercel changelog newest entries still 25 Sep — Drives GA watch NO-CHANGE, still public beta). In-lane no-launch verdict dated 2026-09-25 stands. **Two new corpus entries this pass: Vercel Sandbox memory observability + vercel/vcr-action/login.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open). (#466)

- Competitor corpus update (post-midnight watch, targeted delta — the fast movers were re-verified NO-CHANGE ~90 min earlier in the 23:54–00:02 slot): **Daytona changelog, Daytona pricing, Docker Sandboxes release notes, Microsandbox releases — 4/4 VENDOR-VERIFIED NO-CHANGE** (all read live). **Sandbox Kit Spec spec-content read — CONFIRMED, closes the scheduled-read note:** the 23:24 pass's Architecture review scheduled a direct read of `docker/sandbox-kit-spec` to confirm or retract the corpus claim (the 23:54–00:02 slot read the commits page only); this pass read the spec content itself — repo subtitle names "the conformance suites", README §Conformance ships `kit-tck` (kit + runtime suites), `docs/spec/conformance.md` §2 defines runtime conformance ("conforms by what it does, not by how it is written"), §3 the claim convention ("publish the suite's output"), and Docker's own blog ("Authority as Code") says every capability page describes "what a conforming runtime must implement" and "Docker Sandboxes will be a first-class implementation, not the only one." The "conforming-runtime standard now the interoperability reference" claim upgrades from unattributed inference to VENDOR-VERIFIED; TCK adapter-verb lifecycle vocabulary (stop/start/recreate + the long-running-gated wait-idle/status pair) design color for the H4 trail (weight-light, speculative — advisory only, not a corpus claim). **Delta news scan clean, NO-CHANGE** (3 queries; near-misses out-of-window or out-of-lane). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open); Vercel Drives not re-checked (P49 — 2026-09-26 morning pass). (#463)

- Stall-detector design for the tenant-status vocabulary's `stuck` code (G9): mechanizes the first-ten-minutes spec's session-abandonment rule (30 minutes, no Muse action, no pending approval) as a control-plane-side detector — the confusion-class ladder (`connection-unreachable`, `box-unhealthy`, `provisioning-failed`, `waiting-on-approval`, `human-drop-off`, `human-denied`, `policy-misfire`, `no-gated-action` are never relabeled `stuck`, enforced by the predicate's `live`-arc hard gate), cross-checking of agent-forgeable heartbeats with control-plane-observed signals, arrival-timestamp clock discipline, and S1→S2→S3 confidence staging — advisory-only until calibration passes, so `stuck` stays operator-set and is never presented as automatic. Design only, no runtime code. (#460)
- Competitor corpus update (near-midnight watch, targeted delta — the fast movers were re-verified NO-CHANGE ~25 min earlier in the 23:24 repair slot): **Daytona changelog — NO NEW ENTRIES** (read live — newest still SEP 26 V0.218.0 `kvm` parameter + SEP 25 V0.217.0 B300, both folded in #442; the v0.217.0 retag/retract cycle noted), **Daytona pricing VERIFIED NO-CHANGE** (rate card verbatim), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1), **Microsandbox releases VERIFIED NO-CHANGE** (newest still v0.7.3 #1646). **Sandbox Kit Spec repo read:** 17 commits under "Sep 25" led by PR #63 (spec + TCK — mixins can request long-running sandboxes, new `long-running-workloads` capability) — noted activity, intra-day timing unverifiable, not a confirmed in-window delta; lifecycle-axis design color for H4's suspended/waking contract. **Delta news scan clean, NO-CHANGE** (7 queries; near-misses all out-of-window or out-of-lane). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). (#459)

- Competitor corpus update (post-post-pre-midnight watch, targeted delta — full set was 9/9 VERIFIED NO-CHANGE ~7h earlier; the fast movers last read ~90 min earlier): **Daytona changelog VERIFIED NO-CHANGE** (daytona.io/changelog read live — newest still SEP 26 V0.218.0 `kvm` parameter + SEP 25 V0.217.0 B300 GPU, verbatim), **Daytona pricing VERIFIED NO-CHANGE** (daytona.io/pricing read live — rate card + preemptible GPU ladder verbatim), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (docs.docker.com release notes read live — newest heading still 2026-09-22, v0.45.1), **Microsandbox releases VERIFIED NO-CHANGE** (releases page read live — newest still v0.7.3 #1646). **Docker Sandbox Kit Spec DELTA — Docker Cloud Sandboxes upgraded** (vendor-primary docker.com blogs: Kit Spec v3 published Apache-2.0 at `docker/sandbox-kit-spec`; WeAreDevelopers CNCF-handoff announcement with CNCF CTO welcome quote — THIRD-PARTY via linux.com — the CNCF submission commitment is now an in-flight neutral-governance transfer; conforming-runtime standard as the interoperability reference). Delta news scan dedupes all in-lane candidates to filed corpus. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: Freestyle pricing, DO Managed Agents pricing (both open — verified ~90 min ago); Baponi, Leap0 (new this window, open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). (#452)
- Competitor corpus update (post-pre-midnight watch, targeted delta — full set was 9/9 VERIFIED NO-CHANGE ~6h earlier; coverage rotated to the slow movers): **E2B VENDOR-VERIFIED NO-CHANGE** (e2b.dev/pricing read live — tiers and $0.000014/s per vCPU verbatim), **Modal VENDOR-VERIFIED NO-CHANGE** (modal.com/pricing read live — sandbox CPU ≈3× standard ratio exact; GPU ladder verbatim incl. B300 $0.001972/s), **Cloudflare Sandbox SDK VENDOR-VERIFIED NO-CHANGE** (pricing page read live, "Last updated Aug 28, 2026" — inherits Containers platform; 375 vCPU-min / $0.000020/vCPU-s cross-checked), **Runloop third-party-corroborated NO-CHANGE** (vendor-primary unread; Upstash blog: $0.108/CPU-h, $0.0252/GB-h, $50 trial credit — verbatim-consistent; adjacent: Runloop Public Benchmarks launched, $25 base + PAYG). **Boat DELTA (vendor-primary `docs.boat.dev/pricing`):** new small $0.018/h (2 vCPU / 4 GB / 12 GB) and large $0.072/h (8 vCPU / 16 GB / 125 GB) sizes; plans $20/$100/$500/$2,000-mo set concurrency (100/300/1,000/2,000 sandboxes) + start limits; $20 credit packs + auto-refill; usage API with per-size billingMultiplier; incremental snapshots every minute + on stop (failed-stop pauses billing); compare-page table verified 2026-09-18 — boat $0.036 vs Novita $0.233 / Freestyle $0.264 / exe.dev $0.280 / E2B-Daytona-Blaxel $0.331 / Codespaces-Cloudflare $0.360 / Modal $0.476 / Islo $0.600 / Runloop $0.634 / Vercel Sandbox $0.682 per 4vCPU/8GB wall-clock hour. **DO Managed Agents DELTA:** public preview opened to all users 2026-09-22 (vendor PR release + docs "Latest Updates 21 September 2026", VENDOR-VERIFIED); BYOT custom OCI templates; vendor latency ~886 ms session-ready / ~305 ms resume-from-pause; Inference Engine 75+ models; early builders OpenHands/Qencode/Amplitude; launch release is a SECOND vendor-owned surface printing snapshots **$0.005/GiB-month** — DO Managed Agents pricing weight-of-evidence now 2:1 for $0.005, the docs subpage ($0.05) the unreconciled oddity, DO Managed Agents pricing stays OPEN. **Two new adjacent corpus entries: Baponi** (baponi.ai, THIRD-PARTY — nsjail sandbox, zero idle-cost sessions, per-execution billing, Free $0 / Pro $97/mo), **Leap0** (THIRD-PARTY — Firecracker, vendor-claimed ~100 ms boots, host-side credential injection, Apache-2.0 SDKs, public preview, no published pricing). Carried: Freestyle pricing, DO Managed Agents pricing (both open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Zero fetch failures. In-lane no-launch verdict dated 2026-09-25. (#450)
- Competitor corpus update (late pre-midnight watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~4h earlier, pre-midnight targeted pass ~25 min earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter; full 2136-line page read live), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1; full 444-line page read live), **Microsandbox releases VERIFIED NO-CHANGE** (newest still v0.7.3 #1646 — coverage rotated in after the last two Daytona/Docker-only passes). **Freestyle pricing VERIFIED NO-CHANGE** — freestyle.sh/pricing read live: Pro fee still not printed, rate card verbatim unchanged. **DO Managed Agents pricing VERIFIED NO-CHANGE** — DO docs pricing subpage read live: $0.05/GiB-month still present three times, stamp "Last verified 22 Sep 2026", active-CPU "coming soon" footnote vs per-second body copy both verbatim; the 10× discrepancy against DO's own investor-relations page ($0.005) stands as the open caveat. Narrow delta news scan: all in-lane candidates dedupe to filed corpus (Docker Cloud Sandboxes Sep-24 launch recrawls → Docker Cloud Sandboxes; The Register's Cavage Docker-socket demo is containment color, not a new vendor surface). Zero fetch failures this pass. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#448)
- Operator observability for the waitlist daemon: a loopback-only `GET /waitlist/status` endpoint reporting the email spool backlog (file count, oldest queued age, count by kind) plus row counts by status, so a dead sender shows up as a growing spool instead of silent "check your inbox" lies. Non-loopback peers get a 404 even if the daemon binds a non-loopback interface — the route never advertises itself to scanners. (#449)
- Competitor corpus update (pre-midnight watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~5.5h earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter; full 2136-line page read live), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1; full 444-line page read live). **Freestyle pricing VERIFIED NO-CHANGE** — freestyle.sh/pricing read live: Pro fee still not printed, rate card verbatim unchanged. **DO Managed Agents pricing VERIFIED NO-CHANGE** — DO docs pricing subpage read live: $0.05/GiB-month still present three times, stamp "Last verified 22 Sep 2026", active-CPU "coming soon" footnote vs per-second body copy both verbatim; the 10× discrepancy against DO's own investor-relations page ($0.005) stands as the open caveat. Narrow delta news scan: 7 in-lane candidates all dedupe to filed corpus (Docker Cloud Sandboxes recrawls → Docker Cloud Sandboxes; DeepSeek DSec → DeepSeek Harness CVE-2026-82533; Meta Muse VM-filesystem-export → adjacent color), out-of-window (VMware Explore), or out-of-lane (TokenVisor Spaces). Zero fetch failures this pass. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#447)
- Competitor corpus update (post-post-late-night watch — targeted delta; full tracked set was 9/9 VERIFIED NO-CHANGE ~4h earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1). **Perplexity "Escaping SPACE: Part I" lead RESOLVED, VENDOR-VERIFIED** — the full body of Perplexity's "Escaping SPACE: part I" (SEP 23, 2026) read live (the multi-pass 403 was a fetch-path limitation): 216 runs / 0 of 108 VM escapes / 11 of 54 partial-network bypasses (DNS spoofing + Fastly-IP-sharing domain fronting), remediation (nftables source-address validation, per-request authority relay, TLS-terminating gateway), 10-platform third-party test (bypass in 8 of 10 — clean: Cloudflare Sandbox, NVIDIA OpenShell), and the as-of-Sep-10 vendor-response table (mitigations released: microsandbox v0.6.18, Daytona authority-mismatch enforcement, Deno; in progress: Fly.io Sprites; planned/known-limitation: E2B, Vercel Sandbox, Modal). Perplexity "Escaping SPACE: Part I" row upgraded THIRD-PARTY → VENDOR-VERIFIED; the multi-day carried lead is retired. Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Narrow delta news scan dedupes 2-for-2 (Docker Cloud Sandboxes press recrawls → Docker Cloud Sandboxes; DO Managed Agents explainer → DO Managed Agents pricing). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#445)
- Competitor corpus update (post-late-night watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~2.5h earlier): **Daytona changelog DELTA, VENDOR-VERIFIED** — V0.218.0 (SEP 26) adds a `kvm` parameter to sandbox creation in every SDK (isolation-backend toggle at provision time — substrate-axis design color for the H4 adapter axis, not a field-table change) and moves CLI login to a dedicated WorkOS application; V0.217.0 (SEP 25) adds the NVIDIA B300 GPU type to the API client (GPU-axis color, no pricing attached). **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1). **Perplexity "Escaping SPACE: Part I" CARRY** — primary-article body still blocked (direct URL 403; Wayback capture empty/CDX 500; r.jina.ai policy-blocked; live-browser read attempted, result pending at write time — any success folds next pass); the dennysentinel.com 2026-09-24 analysis read in full this run corroborates the already-folded third-party detail (no new facts, no grade change). Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Narrow delta news scan: Blitzy reverse-engineering sandbox, Microsoft Copilot revamp, Zoho Catalyst PaaS color, Meta Muse explainx recap, stale Selangor recrawl — all out-of-lane or already corpus. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#442)
- Strategy positioning research: Muse-like agents as a spark-vm target customer segment — defines the agent persona (what a Muse-like agent loses to ephemerality: accumulated state, long-running jobs, identity continuity, compound skill), reframes the task-scoped sandbox competitor set as the prospect set (persistent compute for agents designed to have a home), and maps where the pitch lands in docs once the hosted-launch blockers clear. Research, not sales copy: no announcement, pricing, or tier claims. (#435)
- Competitor corpus update (late-night lead re-verification + delta news scan): the tracked set was **9/9 VERIFIED NO-CHANGE** ~35–50 min earlier, so this pass re-verified the carried leads live instead of re-surveying. **Freestyle pricing CARRY** - freestyle.sh/pricing read live: Pro monthly fee still NOT printed (only dollar figure is the $50 Hobby reference), full rate card verbatim unchanged (vCPU $0.04032/h, GiB memory $0.0129/h, GiB storage $0.000086/h, transfer $0.02/GB); page grew (limits table, expanded FAQ) but no Pro fee added. **DO Managed Agents pricing carry (a)** - DO docs pricing page read live: still "Last verified 22 Sep 2026", snapshots/checkpoints still $0.05/GiB-month verbatim; vendor launch blog (read live) agrees at $0.05 while syndicated BusinessWire copies still print $0.005 - the intra-vendor 10x discrepancy persists, neither side corrected. **DO Managed Agents pricing carry (b)** - same docs page read live: "Active CPU billing is coming soon" footnote vs present-tense per-second body copy both verbatim; launch blog still present-tense $0.044/vCPU-hour. **Perplexity "Escaping SPACE: Part I" CARRY** - primary article body still blocked (direct URL 403; web.archive.org snapshot is a 204 empty capture; r.jina.ai blocked by policy; no full-text mirror); never claimed as NO-CHANGE. **Corpus enrichment (THIRD-PARTY):** the dennysentinel.com 2026-09-24 "Escaping SPACE" analysis read beyond the bare stats - models tested (incl. Fable and GPT-6 Astra refusing outright), DNS-spoof and IP-sharing/authority-switch bypass mechanisms, the vendor-response table, the nftables + per-request-authority-validation remediation, and the key quotes - all folded into the Perplexity "Escaping SPACE: Part I" row. Delta news scan (~18:05-18:25 CDT): 6 in-lane candidates surfaced, ALL dedupe to already-filed corpus (Docker Cloud Sandboxes, Docker Sandbox Kit Spec, DO Managed Agents pricing, DeepSeek DSec paper, DeepSeek Harness CVE-2026-82533). Vercel Drives not re-checked (P49 - next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#434)
- Competitor corpus update (post-post-late-evening lead-resolution pass): the tracked set was **9/9 VERIFIED NO-CHANGE** ~35 min earlier, so this pass retired carried verification leads instead of re-surveying. **DeepSeek Harness CVE-2026-82533 VENDOR-VERIFIED** - CVE-2026-82533 fix confirmed on the vendor's own infrastructure (`deepseek-ai/deepseek-harness`): `dsh-v0.1.2-alpha.1` published 2026-08-27, its release notes name the one-time-token auth fix and add a SAFETY.md isolation disclaimer; the OSV CVE record references the vendor release tag and fix commit `3e24087b` ("fix(web): authenticate the browser Host API"); DSec escape catalog stays THIRD-PARTY. **Docker Sandbox Kit Spec lead closed** - Docker kits mechanics pages read live: the v3 kits page (`docs.docker.com/ai/sandboxes/customize/`, workload/mixin roles, kit sets, sbx >= v0.45) and `customize/kits/` now rendering as "Kits v2" (host-side-proxy + sentinel-value credential model - independently corroborates spark-vm's `hsurr:` proxy-swap architecture). Perplexity "Escaping SPACE: Part I" carried (Perplexity 403 again; second dennysentinel.com THIRD-PARTY analysis, 2026-09-24). Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 - next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#433)
- Competitor corpus update (post-late-evening watch): tracked set **9/9 VERIFIED NO-CHANGE** (zero pricing/feature deltas, zero fetch failures — 9 tracked reads + Google Gemini Enterprise Agent Platform sandboxes heading check all clean; Daytona's SEP 24 V0.216.1/V0.216.2 pair still newest, no Sep-25 entry — VERIFIED absent; Docker release-notes newest heading still 2026-09-22; Microsandbox still v0.7.3 #1646; E2B, boat.dev, TermSquad, AgentComputer watched lines verbatim). **Resolved:** the late-evening pass's UNVERIFIED DO docs pricing subpage — fetched live at the carried URL: $0.044/vCPU-hour, $0.0095/GB-hour, Session Storage / Snapshots-and-Checkpoints / BYOT $0.05/GiB-month, stamp 22 Sep 2026 — verbatim, unchanged. Google Gemini Enterprise Agent Platform sandboxes VERIFIED NO-CHANGE (newest heading still Sep 24). **No new corpus entries.** Sep-25-dated in-lane items were all THIRD-PARTY recaps of the already-filed Sep-24 Docker Cloud Sandboxes launch (Forkast.news, how2shout, webpronews, DEV.to) — no new facts; how2shout gives the newest granular third-party rate card: Micro $0.07/h → XL $1.12/h, per-second, paused = free, $250 free credit. Carried: Perplexity "Escaping SPACE: Part I" full article-body read (HTTP 403 again, single attempt), DeepSeek Harness CVE-2026-82533 vendor-primary verification (no advisory/release notes surfaced; THIRD-PARTY corroboration widened — OX Research, VulnCheck as assigning CNA, The Hacker News, PIR-2026-0060; multi-source fix timeline Aug 24 → Aug 30), Docker Sandbox Kit Spec follow-up re-pointed (Sep-21 heading documents v3 kits; the "Learn more about kits" mechanics docs page is the unread lead), Pro fee still structurally omitted, DO Managed Agents pricing conflicts unchanged, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. (#429)
- First-approval summons design (G4): the control plane observes the filing event from a box-side outbox journal and sends a fail-open email via the operational AgentMail identity — the tenant box's swap path never sends email and never holds the credential. Pins the first-filing trigger, the one-reminder-at-T+TTL/2 rule with state re-check, the H14 retirement bootstrap exception, and funnel telemetry events; implementation stays in three build slices (S1 box-side journal, S2 control-plane sender, S3 retirement + telemetry). (#430)
- Competitor corpus update (late-evening watch): tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas, zero fetch failures; Daytona's SEP 24 V0.216.1/V0.216.2 pair still newest; Docker release-notes newest heading still 2026-09-22; Microsandbox still v0.7.3 #1646; E2B, boat.dev, TermSquad, AgentComputer watched lines verbatim). DigitalOcean Managed Agents docs main page VERIFIED NO-CHANGE; the docs pricing subpage was NOT reached directly this pass (reported UNVERIFIED, never as NO-CHANGE — the late-morning pass already located and read it live); official numbers from DigitalOcean's own launch blog (2026-09-23) agree with corpus: $0.044/vCPU-hour, $0.0095/GB-hour, snapshots $0.05/GiB-month. **One adjacent filing: DeepSeek Harness CVE-2026-82533 + DSec "escape catalog"** (third-party Sep-25 Tech Times coverage: unauthenticated local API + `danger-full-access` session mode disabled sandbox and approvals, fixed in 0.1.2-alpha.2; reward-hack escape catalog — log inspection, socket forgery, package-proxy exploitation, `ioctl FIEXCHANGE` filesystem bypass; resolves the standing UNVERIFIED DeepSeek Harness "leak"; filed adjacent per the Perplexity "Escaping SPACE: Part I" and Cloudflare residual-disk-data disclosure precedent; carried lead: vendor-primary CVE verification). Perplexity "Escaping SPACE: Part I" full article-body read still blocked (new failure mode `upstream_fetch_failed`, single attempt — carried). Google Gemini Enterprise Agent Platform sandboxes VERIFIED NO-CHANGE (newest heading still Sep 24 — no Sep-25 entry). Carried: Pro fee still structurally omitted, DO Managed Agents pricing conflicts unchanged (watched lines), Kits-v2 follow-up lead, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Outerlimit $16M pre-seed (adjacent agent-control startup, ambiguous ~Sep 24 date), ByteAsk $1M pre-seed (Sep 24, out of window), third-party recaps of corpus-covered items (no new facts). In-lane no-launch verdict dated 2026-09-25. (#427)

- Competitor corpus update (late-afternoon watch): tracked set 7/8 VERIFIED NO-CHANGE (zero fetch failures — 12/12 first-try vendor fetches). **One delta:** Docker Sandboxes release-notes newest heading moved 2026-09-21 → 2026-09-22 (sbx-releases v0.45.1: "Improved sandbox moves and support for private kit images in cloud sandboxes" — VENDOR-VERIFIED on the release page; the Sep-24 Cloud Sandboxes launch still has no distinct docs-page launch note). **Corpus fold: Cloudflare residual-disk-data disclosure grade upgrade** — Cloudflare's own disclosure blog read in full (THIRD-PARTY → VENDOR-VERIFIED: dm-thin `skip_block_zeroing` cross-tenant disk-residue flaw; Sep 4 report → Sep 19 fleet cleanup, no evidence of malicious exploitation; storage-layer residual-data exposure, not a VM escape — directly relevant to spark-vm's multi-tenant disk-wipe discipline). Perplexity "Escaping SPACE: Part I" full article-body read still blocked (Perplexity 403) — carried. Adjacent color only: Kontext Security public launch + $4M seed (Sep 24, fundraise, non-provider — below the corpus-entry bar). Dedupes: Docker Cloud Sandboxes/Docker Sandbox Kit Spec third-party recaps (no new facts), DigitalOcean Managed Agents Sep-23 explainer (already tracked). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. (#425)
- Competitor corpus update (mid-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 checks opened on vendor-owned pages, first-try fetches). **No new corpus entries.** Adjacent-color grade upgrade: Meta Muse VM-filesystem-export second disclosure (Sep 25, THIRD-PARTY — explainx.ai update + ai0.news digest: Muse can be prompted to hand over its entire VM root filesystem; Meta spokesperson says expected behavior in a personal Linux VM while Muse itself refused then apologized; "second Muse security disclosure in a week" — vendor-spokesperson response upgrades the carried watch-only snippet but no vendor-primary page; filed adjacent, below the corpus-entry bar). **Dedupe:** Surveyor B's BAND × Docker Sandboxes Kit candidate is already corpus (Docker Cloud Sandboxes detail + 2026-09-24 pre-midnight section) — no double-file. Carried-lead resolutions: Kits-v2 follow-up RESOLVED (sbx-CLI kit scheme `schemaVersion: "2"` is distinct from the OCI Kit Spec — no file); Perplexity "Escaping SPACE: Part I" primary-source read PARTIAL (Perplexity blog URL located but 403 — read stays carried); Island company-announcement read RESOLVED (GlobeNewswire: $400M led by Evolution Equity Partners, $6.4B, "agentic control plane" framing — fundraiser, no file). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Perplexity "Escaping SPACE: Part I" primary-source read, Cloudflare residual-disk-data disclosure primary-source read (blog.cloudflare.com disclosure), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Transluce agent-swarm research (marginal, snippet-level), DeepSeek DSec third-party coverage (already corpus), Docker Cloud Sandboxes/Docker Sandbox Kit Spec third-party reprints (commentary, no new facts), OpenClaw Direct (conflicting dates, marginal lane), Whiteboard YC (IDE), SandboxAQ/Selangor (name collisions/out of lane). In-lane no-launch verdict dated 2026-09-25 (#424).
- Competitor corpus update (early-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: Cloudflare Containers/Sandboxes cross-tenant disk-residue flaw** (disclosed Sep 24–25, third-party: dm-thin `skip_block_zeroing` let reused 64 KiB blocks leak prior tenants' directory listings, SQLite DBs, Chromium profiles, `.env`/credential files; reported Sep 4 by Oren Yomtov/Accomplish via HackerOne, cleanup done Sep 19, no evidence of malicious exploitation — filed adjacent per the Perplexity "Escaping SPACE: Part I" precedent, directly relevant to spark-vm's sandbox threat model: multi-tenant disk wipe discipline). Deliberately not filed: Microsoft Copilot Managed Runtime Sep-25 press corroboration (no grade change), Zoho Catalyst 3.0 (Sep-2 vintage reprint), Google antigravity (Sep-17 vintage), DO Managed Agents (Sep-23 vintage), Docker Cloud Sandboxes explainer (Docker Cloud Sandboxes already corpus), Baseten/Blaxel dedupe, Meta Muse snippet (watch-only), DeepSeek "leak" (UNVERIFIED), Guava name collision, stale E2B Series A, vintage Vercel integrations. Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Perplexity "Escaping SPACE: Part I" primary-source read (Perplexity's own post), Cloudflare residual-disk-data disclosure primary-source read (blog.cloudflare.com disclosure), Island announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25 (#423).
- Competitor corpus update (post-mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: Perplexity "Escaping SPACE: Part I"** (Sep 23/24, third-party: frontier-model red team of a Firecracker microVM sandbox — 0/108 escapes, egress allowlist bypassed 11/54, authority-switch bypasses reproduced in 8/10 third-party platforms — directly relevant to spark-vm's sandbox threat model). Adjacent color (NOT corpus): Island $400M Series F at $6.4B (Sep 24, THIRD-PARTY — a fundraise, not a shipped surface; below the corpus-entry bar). **No Baseten/Blaxel fold** (acquisition is corpus Baseten/Blaxel; beri.net continuity analysis already logged as adjacent color). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Perplexity "Escaping SPACE: Part I" primary-source read (Perplexity's own post), Island company announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Microsoft Copilot Managed Runtime press corroboration (no grade change), DeepSeek DSec Harness "leak" (UNVERIFIED single source), Meta Muse Mac VM-filesystem-export snippet (no vendor confirmation). In-lane no-launch verdict in-window (#421).
- Competitor corpus update (mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21; Microsandbox still v0.7.3 #1646). **Three corpus moves: Microsoft Copilot Managed Runtime evidence upgrade** (Microsoft Copilot Managed Runtime — **THIRD-PARTY → VENDOR-VERIFIED**: Microsoft's own Sep-25 announcement post read in full, "hosting infrastructure that lets code run safely right inside your company's Microsoft 365 environment", tenant-boundary governance, Autopilot identity/memory/computer/workspace, UBB billing); **Docker Sandbox Kit Spec** (new entry: open-sourced under Apache 2.0 + committed to CNCF — **VENDOR-VERIFIED**, announced ~Sep 24, companion to Docker Cloud Sandboxes); **Ando** (new adjacent entry: out of stealth + $20M — third-party; messaging-layer agent participation infra). Carried: **Freestyle pricing** Pro fee still structurally omitted, **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Meta Muse VM-filesystem-export snippet (no vendor confirmation), DeepSeek DSec Harness "leak" (UNVERIFIED single source) (#420).
- Competitor corpus update (post-night watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **Three corpus moves: Docker Cloud Sandboxes evidence upgrade** (Docker's own Sep-24 Cloud Sandboxes press page now live — **VENDOR-VERIFIED**, full-page read: "available now", boot in low hundreds of ms with secrets/policy/MCP gateways/agent config built in, 1–16 vCPUs Docker-managed, Kits-as-standard-OCI + CNCF submission); **Microsoft Copilot Managed Runtime** (new entry: public preview, third-party, Sep-25-dated: tenant-boundary code hosting under IT governance, SDK + CLI for third-party developers, Code to Frontier end of September 2026 — enterprise-adjacent competitive pressure on "run my agent somewhere safe"); **Gemini antigravity-preview-09-2026 harness** (new entry — carried ask closed: vendor-verified vendor docs, harness string + `environment = "remote"`, Files API + Credentials API with runtime secret injection — Sep-17/18 vintage, not Sep-25 news). Carried: **Freestyle pricing** Pro fee still structurally omitted, **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Microsoft Copilot Managed Runtime grade upgrade pending a Microsoft announcement-page read, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Out of lane: misdated ABNewswire recrawls, Daytona SDK dep bumps, inference price cuts, Salesforce outcome pricing, Anthropic 1GW datacenter, Qualcomm–AWS (#419).
- Competitor corpus update (night watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new corpus entries** — the one in-lane fold candidate (DO Managed Agents IR press release detail: 305 ms resume, $0.044 active-CPU, Action Gateway, "37% lower TCO") dedupes to the already-filed **DO Managed Agents pricing** deep-dive. Carried: **Freestyle pricing** Pro fee still structurally omitted (ask stays open), **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent; this pass re-checked the real Google page, superseding the evening mislabel-carry), DO Managed Agents pricing conflicts unchanged. Adjacent watch color only (NOT corpus): Microsoft Copilot Sep-25 revamp (sandbox-by-default "Code" builds, tenant hosting), Gemini antigravity-preview-09-2026 digest lead (snippet-level, date unverified). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass) (#418).
- Competitor corpus update (evening watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 10 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new corpus entries** — the open-web scan surfaced no genuinely new in-lane moves (all three in-lane items dedupe to already-filed entries: **Docker Cloud Sandboxes**, **DO Managed Agents pricing — $5 credit** + partners already in the row; 886/305 ms benchmarks already in the watch-doc trail, reported THIRD-PARTY —, **Prime Intellect Prime Sandboxes GA**). Carried: **Freestyle pricing** Pro fee VERIFIED absent on all public login-free surfaces (stays open; dashboard-signed-in check owed), **Google Gemini Enterprise Agent Platform sandboxes** NOT re-checked this pass (the surveyor brief's Docker-page "Google Gemini Enterprise Agent Platform sandboxes" label was a mislabel, corrected — the real Google release-notes heading check carries to the 2026-09-26 morning pass). Anti-chase note: Daytona "agent-agnostic infrastructure" OpenHands PR is recrawled-old syndication (page stamps 633–3045 days). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel (9/10), AWS AgentCore V2 GA (9/18), Cloudflare+Cursor Sandboxes (9/2) — out of window. Out of lane: GPT-6 Sol/Luna + Claude Opus 5.5 inference price cuts (model pricing) (#417).
- Competitor corpus update (afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 10 URLs opened directly on vendor-owned pages). **Corpus folds: Prime Intellect Prime Sandboxes GA + launch pricing VENDOR-VERIFIED (full-page)** — the midday resolving asks are closed: vendor GA post body read live, corroborating "Today, Prime Sandboxes enter general availability" and "~30M sandboxes created so far" verbatim; vendor docs pricing corroborated value-for-value ($0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr), expiry pinned to **December 22, 2026**, **post-promo rates VERIFIED absent**; CPU-only at GA (GPU microVMs + snapshots + forking = roadmap); **flagged inconsistency**: blog ~30M vs product-page live counters 865,133 total / 20,292 concurrent — not mutually confirming. **DeepSeek DSec paper PRIMARY-SOURCE-VERIFIED** — author-uploaded arXiv 2609.22978v1 ("DeepSeek Elastic Compute (DSec)", 31 pp, submitted 19 Sep 2026): ~3M sandboxes/day per 160-node unit, >380k concurrent, >5k creations/sec; paper documents two agent-triggered kernel crashes plus an XFS_IOC_SWAPEXT reward-hack filesystem shutdown; caveat: "These controls address only part of the problem and do not provide a general defense against destructive behavior such as triggering kernel bugs." **Docker Cloud Sandboxes corroborated, no fold** (vendor press release re-read live — Docker Cloud Sandboxes Sep-24 launch already VENDOR-VERIFIED in corpus). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel M&A (THIRD-PARTY), DO Managed Agents Sep-22 preview framing (snippet-level; already DO Managed Agents pricing), OpenAI Agents API public beta (Sep 10). Out of lane: GPT-6 Sol + Claude Opus 5.5 inference price cuts, stale recrawls (#416).
- Competitor corpus update (midday watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages). **Corpus folds: DO Managed Agents pricing conflict SCOPED — the 10× disagreement is snapshots-only** (compute $0.044/vCPU-hour and memory $0.0095/GB-hour agree exactly on the IR launch page and the docs pricing subpage, both re-read live; only Snapshots and Checkpoints disagree — $0.005 IR vs $0.05 docs) **and a second conflict surfaces** (IR page presents active-CPU billing as live vs docs footnote "coming soon", interim 25% of allocated — VENDOR-VERIFIED both surfaces); field-table row updated, $0.05 figure kept with conflicts annotated. **Prime Intellect Prime Sandboxes GA vendor-sourced (snippet-level)** (primeintellect.ai blog, index "SEP 23RD, 2026" read live; GA line and launch pricing via vendor-post/vendor-docs snippets — full-page reads owed — "Today, Prime Sandboxes enter general availability"; ~30M sandboxes in private rollout; launch pricing $0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr through Dec 22, 2026; repaired the pre-dawn Prime Intellect Prime Sandboxes row's truncated tail). **DeepSeek DSec paper** (new entry, third-party: 3M sandbox envs/day, kernel-halt agent incidents — scale/safety context). Carried: Pro fee still structurally omitted (no plan dollar amounts live), Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), google/ax 10,969 stars (+27) / `gemini-3.8-flash` README pin (watch color, no fold), Tensorlake quiet in-window; Vercel Drives not re-checked (P49 morning cadence); adjacent only (NOT corpus): Dataiku Agent Management (Sep 24, GA planned Oct 2026), Ando out of stealth ($20M), Google Project Suncatcher; out of lane: GPT-6 Sol / Claude Opus 5.5 inference cuts, ABNewswire Feb-2026 recrawls mislabeled Sep 25 (#415).
- Competitor corpus update (late-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: DO Managed Agents docs pricing subpage LOCATED and read live — "unlocated" framing retired** (the 8-miss streak was a discovery/indexing failure (INFERRED): the page loads at the carried URL but is undiscoverable via search; stamp still "Last verified 22 Sep 2026", $0.05/GiB-month confirmed live — the 10× vendor-internal conflict stands: IR launch page still $0.005/GiB-month, no correction; new THIRD-PARTY support for the misattribution hypothesis — general-product Droplet/Volume snapshots $0.05/GB-month nominal-value-for-value with the docs figure (GB vs GiB units differ); field-table keeps $0.05 with the conflict annotated). **Google AX v0.3.0 watch color** (google/ax 10,942 stars +27, README example now `gemini-3.8-flash` — VENDOR-VERIFIED), **Prime Intellect Prime Sandboxes corroborating color** (THIRD-PARTY ~Sep 23: Prime Sandboxes general access opened — vendor verification owed). Carried: Pro fee still UNVERIFIED, Google Gemini Enterprise Agent Platform sandboxes newest heading Sep 24 (no Sep 25 entry), Alibaba Cloud FC Agent Sandbox pin static, Tensorlake no Sep-24/25 news (#414).
- Competitor corpus update (morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: DO Managed Agents pricing snapshot-rate attribution RE-OPENED as a vendor-internal conflict** (DO's own investor-relations launch page names **$0.005/GiB-month** as the *Managed Agents* snapshot rate — VENDOR-VERIFIED — vs the vendor docs page's **$0.05**; 10× gap (no correction on the IR surface this run; $0.05 carried from the 9/23 read — subpage still unlocated); misattribution hypothesis (the $0.05 is DO's general-product Volumes rate) INFERRED and now vendor-supported on the $0.005 side; field-table keeps $0.05 with the conflict annotated; stale "RETIRED in favor of the primary source" line corrected; 8th docs-subpage re-fetch stays the resolving ask), **Google Gemini Enterprise Agent Platform sandboxes heading moved** (Sep 22 → Sep 24: Gemini 3.8 Live GA, Muse Spark 1.3 Preview — watch color, no fold). Retired duplicates (google/ax candidate = already-filed **Google AX v0.3.0**, Apache-2.0 re-confirmed; Docker-launch candidate = already-filed **Docker Cloud Sandboxes**, now 5-surface corroborated). **Vercel Drives still public beta** (P49 morning cadence, 26th consecutive no-change pass — full Drive pricing grid live, digits already folded at Vercel Sandbox Drives). Carried: Pro fee still UNVERIFIED (page structurally doesn't publish plan fees), Alibaba Cloud FC Agent Sandbox pin static `39b6c3a2`, the Google Gemini Agent Environment and Google Agent Substrate unchanged, Tensorlake no Sep-24/25 news, Prime Intellect Prime Sandboxes no-op; adjacent investor color only (Ando $20M, Island $400M Series F). No in-lane launches, pricing moves, or funding dated 9/25 in-window (#411).
  - sparkvm.dev front door, first slice: the landing page now tells the open-source story first ("Open source, running today" — MIT, runs on your Unraid/Proxmox box today, contributions welcome) and splits the two ways to run it (self-host as the near-term story, hosted as the future story with a pointer to the beta pilot on musebook). Pages-ready deploy contract: static file set, security headers (`_headers`: strict baseline + default-deny CSP on the no-JS/no-form paths), custom 404, and operator deploy steps for the Cloudflare Pages project + `sparkvm.dev` custom domain. The landed waitlist funnel wiring (CTA buckets, tag set, no-JS, no dead forms) is unchanged and now test-guarded (#412).
- Competitor corpus update (pre-dawn watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **Google AX v0.3.0** (orchestrator/harness lane, primary-source VERIFIED on github.com/google/ax — Apache-2.0, runs on Agent Substrate for sandboxed execution, kubectl-shaped CLI with ax suspend/resume/ssh, Task/Workspace/Model manifests, pre-stable; v0.3.0 notes THIRD-PARTY-convergent — strongest validation yet of the OpenAI Agents API partner list harness↔compute split / H4 per-harness-adapter thesis), **Prime Intellect "Prime Sandboxes" launch** (~2026-09-23, THIRD-PARTY — 30M agent environments, usage-based no-commitment, vCPU $0.02/hr + $0.0125/GiB-hr mem + $0.0002/GiB-hr disk ≈ 1/3 of large providers, promo through Dec 22, CPU-only with snapshots/forking/GPU on roadmap), Docker Cloud Sandboxes duplicate closed (surveyor's Docker Cloud Sandboxes launch candidate = the already-filed Docker Cloud Sandboxes event), Grunz "$100 once" flag downgraded to light-watch (figure absent from grunzai.com — now pay-per-use credits). Carried: Pro fee still UNVERIFIED (Hobby $50 re-confirmed), DO Managed Agents docs pricing subpage 7th consecutive miss (convergent release-set, no corpus change), Tensorlake no Sep-24/25 news, Alibaba Cloud FC Agent Sandbox pin still `39b6c3a2` digits unchanged, the Google Gemini Enterprise Agent Platform sandboxes, Google Agent Substrate, and Google Gemini Agent Environment unchanged. No launches, pricing moves, or funding dated 9/25 in-window (#409).
- Competitor corpus update (post-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **Alibaba Cloud FC Agent Sandbox repo HEAD pin REVERTED (`96ff8a8` → back to the pre-overnight `39b6c3a2` commit, VENDOR-VERIFIED via GitHub API — not a second move, no phantom third position)** with all pricing digits unchanged, **OpenAI Agents API THIRD-PARTY pricing color** (hosted-sandbox containers $0.03–$1.92 per 20-min session; ZDR inapplicable even self-hosted), new-to-watch candidate Google AX v0.3.0 (THIRD-PARTY, HN-noted — open-source Apache-2.0 agent orchestrator on Agent Substrate; primary-source pass owed). Carried: Pro fee still UNVERIFIED (Hobby $50 minimum re-confirmed), DO Managed Agents docs pricing subpage 6th consecutive miss (misattribution stays INFERRED), Tensorlake no Sep-24/25 news, Google Gemini Enterprise Agent Platform sandboxes heading still Sep 22, Google Agent Substrate/Google Gemini Agent Environment confirmed unchanged. No launches, pricing moves, or funding dated 9/25 in-window ((#385)).
- Competitor corpus update (post-overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing figures moved from baseline-carried to VERIFIED on Daytona's own pricing page — full GPU ladder now on record), **Google Gemini Agent Environment clean citation CAPTURED — debt retired** ("Environment compute (CPU, memory, sandbox execution) is **not billed** during the preview period", VENDOR-VERIFIED on ai.google.dev, page "Last updated 2026-09-24 UTC"; fixed 4 CPU cores / 16 GB memory), **Google Agent Substrate FULL vendor verification** (Google Cloud Blog: open-source secure-by-default runtime, 10x density, sub-500ms resume @ 500+ activations/sec; all GKE customers non-production, production GA via allowlist; Nous Research (Hermes) design partner), **DO Managed Agents pricing docs surface re-located and VENDOR-VERIFIED** (standalone pricing subpage still unlocated — 5th consecutive miss; rates hold $0.044/vCPU-hr, $0.0095/GB-hr, $0.005/GiB-month), **Alibaba Cloud FC Agent Sandbox pin 96ff8a8 UNCHANGED** (all pricing digits re-verified), **Hobby $50 re-confirmed** (Pro fee still UNVERIFIED). In-lane dated 9/24 THIRD-PARTY color: ByteAsk $1M pre-seed (C/C++ coding agents), Ando $20M stealth launch (team chat with native agent roles), Darktrace Signal Labs (agent behavioral-security research). OpenAI Agents API still public beta (GA absence VENDOR-VERIFIED); Vercel Drives not re-checked (P49 morning cadence) ((#384)).
- Competitor corpus update (overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), OpenAI Agents API GA absence upgraded to VENDOR-VERIFIED (still public beta, `client.beta.agents` — corrects the prior fetch failures), **Alibaba Cloud FC Agent Sandbox pin MOVED for the first time** (`39b6c3a` → `96ff8a8`, VENDOR-VERIFIED on the official repo's commits page; pricing digits unchanged), Google Gemini Agent Environment VENDOR-VERIFIED in preview (compute not billed during preview), the Google Gemini Enterprise Agent Platform sandboxes, Google Agent Substrate, and Tensorlake re-verified, Freestyle pricing UNVERIFIED-carried (no public Pro price; FAQ $50/mo Hobby minimum re-verified), **DO Managed Agents pricing fourth consecutive docs-side miss — and the carried $0.05 figure is retired as current** (current general-snapshot snippets read $0.06/GB-month; the 10x discrepancy framing is withdrawn — evidence-backed Managed Agents rate is $0.005/GiB-month from the vendor's 2026-09-22 investor release), **corpus fold: DO's own billing model** (vendor-published — active CPU billed per-second, $0.126/hr fully allocated reference → ~$0.0310/hr typical 25%-active run, zero while waiting — the corpus's sharpest agent-sandbox duty-cycle pricing comp). In-lane dated 9/24: Docker Cloud Sandboxes reconfirmed (shape prices Micro $0.07 / Small $0.14 / Medium $0.28 / Large $0.56 / XL $1.12, sbx 0.45.1+, 24h max, $250 credit); Baseten×Blaxel is Sep-24 commentary on a Sep-10 deal, not a launch. Vercel Drives not re-checked (P49 morning cadence) ((#382)).

- Competitor corpus update (post-mid-evening watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox (docs HEAD pin 39b6c3a unmoved, pricing re-verified digit-for-digit), and the Google Gemini Enterprise Agent Platform sandboxes re-verified unchanged, vendor-verified, **Freestyle pricing VENDOR-VERIFIED: no monthly-fee line-item on pricing surfaces; FAQ discloses a $50/mo Hobby minimum-usage commitment** (dashboard-signed-in check still owed), **DO Managed Agents pricing third consecutive docs-side miss** (press side re-VENDOR-VERIFIED $0.005/GiB-month; INFERRED misattribution hypothesis strengthened — carried $0.05 may be DO's general-product $0.05/GB-month snapshot rate; both figures stay open), OpenAI Agents API GA absence search-level only this pass (official page fetch failed — honest weakening), **corpus fold: Docker Cloud Sandboxes first vendor-sourced price-and-terms package** (`sbx move --to cloud` one-command, per-second, Micro $0.07/hr → XL $1.12/hr, paused=free, 24h sessions, $250 credit, WeAreDevelopers NA venue). Google Gemini Agent Environment snippet-only (official surface identified, re-open owed); Tensorlake search-level no news. Vercel Drives not re-checked (P49 morning cadence) ((#381)).

- Competitor corpus update (pre-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas — Daytona V0.216.1 SEP 24 above V0.216.2 SEP 24 baseline-confirmed, Docker Sandboxes release-notes 2026-09-21, Microsandbox v0.7.3, E2B, boat.dev pricing, TermSquad, AgentComputer, DigitalOcean still public preview), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox (docs HEAD pin 39b6c3a unmoved), the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes re-verified unchanged, OpenAI Agents API still public beta, Tensorlake no news, **corpus folds: Docker Cloud Sandboxes launch-availability VENDOR-VERIFIED** on docker.com's own Sept-24 posts + BAND Python Kit for Docker Sandboxes (THIRD-PARTY, Sept 24 — first third-party Kit-ecosystem signal), **DO Managed Agents pricing second consecutive docs-side miss** (press side re-VERIFIED $0.005/GiB-month; "Last verified 22 Sep 2026" pricing subpage still unlocatable; INFERRED misattribution hypothesis carried open). Freestyle Pro fee still UNVERIFIED (dashboard-signed-in check owed) ((#379)).

- Competitor corpus update (late-night watch): dated-2026-09-24 Register coverage corroborating the Docker Cloud Sandboxes GA venue (THIRD-PARTY; Micro $0.07/hr → XL $1.12/hr named shapes, per-second, OCI-standard Kits — matches vendor figures value-for-value), DigitalOcean snapshot-rate partial re-read (press-release side re-VERIFIED $0.005/GiB-month; docs pricing subpage not locatable this run, 10x discrepancy not re-observable, carried open), and boat.dev's product-news surface VERIFIED absent (third attempt; retry retired). Tracked set 7/8 VERIFIED NO-CHANGE (Daytona changelog reorder micro-delta only: V0.216.1 now above V0.216.2, both SEP 24, no new release) ((#375)).
- H12 usage-metering design: billable-unit taxonomy for hosted billing (box wall-clock, resource windows, approval volume, suspend/wake, push delivery), a canonical metering event envelope shared with the H5 sentinel design (per-surface mappers over the four telemetry surfaces, sequencing, trust tiers, counters-over-content privacy), emission modeled on the shipped H14 part a enqueue/retry pattern, and the filed follow-ups (#376–#378). No pricing promises — design thinking only ((#380)).
- Competitor corpus update (night watch): new Tensorlake Firecracker-microVM sandbox entry with own-page pricing (Free / Usage Credits / Pro $250 per cycle / Enterprise; snapshot storage $0.07/GB-month), Simular Sai pricing resolved from own-domain pages (Free / $50 / $500 / Enterprise), Freestyle own-page pricing verified (Hobby $50/mo), and DigitalOcean's live docs-vs-release snapshot-rate discrepancy confirmed on both vendor surfaces ((#373)).

- Competitor watch, 2026-09-24 mid evening: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing re-verified on the vendor's own Sept 22 press release ($0.044/vCPU-hour, $0.0095/GB-hour, $5 credit — matching DO Managed Agents pricing; pricing subpage "Last verified 22 Sep 2026" stamp re-check still carried), boat.dev product-news surface UNVERIFIED (not located), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes: no new moves, OpenAI Agents API Sep-10 public-beta dating re-confirmed VERIFIED (still public beta, no GA), **corpus folds: Docker Cloud Sandboxes GA-venue detail** (onstage launch at WeAreDevelopers North America; Sandbox Kits → standard OCI images + CNCF submission commitment; Hermes first-class Kit demo) + **DO Managed Agents pricing re-verified** (docs $0.05/GiB-month vs release's $0.005 — live 10x snapshot discrepancy, stamp re-check must resolve), in-lane dated 9/24: Docker GA venue, Island $400M/$6.4B (adjacent), Modal ~$15B talks (adjacent), Darktrace Signal Labs (adjacent) (#370).
- Competitor watch, 2026-09-24 late afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing still UNVERIFIED (vendor product doc fetched, carries DO's own "Last verified 21 Sep 2026" freshness line but no pricing; pricing subpage fetch failed — stamp re-check owed next pass), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED (still public beta, no GA), Docker Cloud Sandboxes no new moves, Vercel Drives still public beta (opportunistic re-read), **corpus fold: Alibaba Cloud FC Agent Sandbox deep-hibernation detail** (15 GiB free disk allowance does not apply in deep hibernation — VERIFIED on the vendor page), no in-lane launches/pricing/funding dated 9/24 (#365).
- Competitor watch, 2026-09-24 mid afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean pricing docs UNVERIFIED this pass (stamp re-check owed next), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, Docker Cloud Sandboxes no new moves since the fold, **asks resolved** — Boat EU-only DE/FI/FR geography re-VERIFIED verbatim on boat.dev's own FAQ (three-pass retry closed), OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED with a fresh read of OpenAI's own changelog (still public beta, no GA), **corpus folds: Snapshot pricing fully specified** (*Snapshot Storage Usage = Memory Specification × 2 + Disk Specification*, charged at Disk Unit Price × duration) + WeAreDevelopers-North-America venue detail, `_MID_AFTERNOON` admitted to the watch-doc naming convention, no in-lane launches/pricing/funding dated 9/24 (#364).
- Competitor watch, 2026-09-24 early afternoon: tracked set moves — 7/8 quiet, **Microsandbox v0.7.2/v0.7.3 new** (full-quiet streak ends at three), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, OpenAI Agents API still public beta (no GA), **new in-lane corpus entry Docker Cloud Sandboxes** (VENDOR-VERIFIED on Docker's own blog: same microVM on Docker-managed compute, `sbx move --to cloud`, PAYG per-second $0.07–$1.12/h, paused free, $250 free credit), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, Snapshot-pricing fold queued for the next pass, no in-lane funding dated 9/24 (#363).
- Competitor watch, 2026-09-24 noon: tracked set 8/8 quiet (full-quiet streak advances to three), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, **OpenAI Agents API Sep-10 public-beta dating upgraded THIRD-PARTY → VENDOR-VERIFIED** (sourcing only — OpenAI's own changelog; still public beta, no GA move), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, Google Gemini Enterprise Agent Platform sandboxes paren-balance nit adopted, no new corpus entries, no in-lane launches/pricing/funding dated 9/24 (#359).
- Competitor watch, 2026-09-24 late evening: tracked set 8/8 quiet, Vercel Drives still public beta (25th pass, GA watch now once-daily per the P49 cadence decision), **new in-lane corpus entry Google Gemini Enterprise Agent Platform sandboxes (Computer Use + Shell) GA** (VENDOR-VERIFIED on Google's own release notes), Docker CVE pair confirmed already-closed, watch-review nits adopted (#352).

- `docs/SENTINEL_TELEMETRY_SURFACES.md`: arch deep-read of the four
  audit/telemetry surfaces the hosted sentinel (H5) would consume —
  schema catalog, six structural findings (no shared event envelope, no
  sequencing or authentication, second-resolution timestamps that collide
  under burst, unstated trust tiers for agent-forgeable muse-job events,
  confirmd's silently-swallowed audit-write failure (fixed this turn so
  it signals to stderr), and confirmd's audit.log having no rotation
  bound), plus the ordered H5 prerequisites. Findings filed as GitHub
  issues. (#353–#357, #360, PR #361)

- Evening competitor watch (full quiet pass): tracked-set vendors 8/8
  VERIFIED no-change with zero fetch failures (full-quiet streak re-opens
  at one after the afternoon pass's Daytona move), Vercel Drives still
  public beta (24th consecutive pass; VERIFIED on the vendor changelog
  page this run; pricing last_updated 2026-09-10), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, and Google Gemini Agent Environment
  re-verified unchanged. No corpus fold this pass — three fold candidates
  queued for primary-source verification (Google Shell/Computer Use
  sandboxes GA Sept 9; Docker Sandboxes CVEs CVE-2026-77179/CVE-2026-79994
  Sept 15; the Alibaba/Huawei "agentic cloud" framing trend), plus a
  namesake-collision warning that Guava's "Daytona" voice model is
  unrelated to Daytona sandboxes. Afternoon vetting holds (OpenAI Agents
  API stays third-party; Tencent DataBuddy stays adjacent-watch;
  deprecated-row sunset convention stays proposed-not-codified). News
  scan: adjacent color only (Island $400M Series F on rogue-agent
  framing, Alibaba AgentCore, Darktrace Signal Labs) — no in-lane
  launches, pricing moves, or funding dated 2026-09-24. Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_EVENING.md` (#351).

### Changed
- Multi-tenancy trust model is now framed in runtime-cell vocabulary: a hosted tenant's agent owns everything inside its cell — its per-tenant box (its jail on the cooperative tier), contained root-equivalent, never host root — while the enforcement layer — egress fencing, secret swapping, metering, break-glass — stays operator-owned and invisible from inside, seen only through approvals, status, and audit. Unchanged: support access stays tenant-visible, granted, logged, break-glass-only; no operator-blindness claim. (#432)

### Fixed

- The harness auth probe no longer depends on its invoker for the 10-second
  wall-clock cap: it arms its own per-mode deadline (10s gate, 45s
  provision), and a budget expiry — or an external `timeout` wrapper's
  SIGTERM — now exits 1 with a named message instead of dying as an
  unclassified 124. The provision-mode CLI vehicle budget also grew from
  6s to 25s, so a slow but healthy provider (TLS, cold model endpoint,
  inference latency) no longer fails provisioning; a provision timeout is
  reported as slowness, never misdiagnosed as a bad credential. (#158, #159; #513)

- proxy/deploy.sh now installs `scripts/bounded_http.py` to /home/swapd
  alongside confirmd.py and registers it in confirm's install paths, so
  the standalone deployment (and its rollback) can't start confirmd
  with a missing-helper import failure. cred-ui gets the same treatment:
  its auto-deploy install step now ships the helper into the working
  checkout's `scripts/` (whose sync only refreshed `cred-ui/` + VERSION)
  and registers it in cred-ui's install paths for snapshot/rollback, so a
  cred-ui-only deploy can no longer restart the service into
  ModuleNotFoundError (#471).

- When steering a job refuses because the TUI died between the liveness
  poll and the paste, the refusal now reports the pane as seen at the
  refusal instant instead of the stale pane captured during the earlier
  poll — so the operator sees what actually defeated the paste, not
  outdated output. (#501)

- The desktop control bridge now serves each request on its own thread, with at most 8 handlers running at once: a slow driver call can no longer head-of-line-block the panel's screenshot polls or the keepalive's health probe. (#496)

- Manual rollbacks now audit the extra-inputs digest reconciliation outcome:
  a reconciliation that fails part-way is recorded on the `manual-rollback`
  and `rollback-unhealthy` audit lines as `"reconcile":"incomplete"` instead
  of logging a warning while the audit trail reads as a full success — so a
  later forced redeploy can't be misread as a genuine host-side input
  rotation. The rollback itself still completes in this case (the snapshot
  restore already landed). The reconciliation scratch file also got its own
  temp name so a manual rollback overlapping a timer tick can't clobber a
  concurrent deploy's digest rewrite. (#482)

- confirmd now bounds its HTTP thread pool and its connection setup: the
  server caps in-flight handler threads at 64 (over-cap connections are
  closed immediately, fail closed), the TLS handshake runs inside a bounded
  handler thread instead of the single accept loop (so one peer stalling
  the handshake can no longer pin all new connections), and each accepted
  socket gets a 10s timeout — an idle connection is reclaimed after 10s of
  socket inactivity. Holding a slot indefinitely now requires actively
  trickling data on all 64 connections (previously one idle connection
  sufficed) (#469).

- The jail build now validates the agent's SSH public key before doing
  anything with it: a file with Windows line endings, trailing blank
  lines, or a malformed key fails the build with a clear error instead
  of landing verbatim in the jail's authorized keys and failing the
  agent's SSH login in a way that looked like a network problem. (#467)
- The jail's firewall watchdog now re-checks the ruleset every minute
  instead of every five, so a flushed or damaged firewall is caught and
  fail-closed within about a minute rather than up to five. (#467)
- Deploy helper now states its input bounds up front: `--src` refuses
  inputs over 1 MiB, and `--stdin` is documented as deliberately uncapped
  and un-gated (deploy-script-constructed input only, never
  attacker-chosen paths) so a future caller does not assume uniform
  bounds. (#454, #455)
- Auto-deploy: three extra-inputs follow-ups from the Security review. A
  same-commit forced deploy now tags every audit line on the forced-deploy
  path with `trigger: extra-inputs` (snapshot-fail, reload-fail, and the other
  failure paths previously masqueraded as version deploys in the audit
  trail). A manual rollback now re-hashes each rolled-back component's
  host-side inputs and converges the recorded digests to the restored
  reality, instead of keeping the stale post-deploy digest that would
  force a spurious redeploy on the next tick. And a successful non-forced
  deploy no longer wipes the forced-deploy dampening timestamp — any
  version deploy touching the component used to silently reset the
  anti-churn window. (#458)
- Waitlist email spool writes are atomic now: each spooled email is written
  to a temporary file, flushed, synced, and renamed into place, so a crash
  or full disk mid-write can no longer leave a torn half-written email for
  the operator's sender to choke on or send half of (#389).
- The waitlist daemon's in-memory per-IP abuse-rate table is now bounded:
  once it passes 10,000 distinct IPs, keys with no recent activity are
  swept (rate-limited to one sweep per minute, so a flood of unique IPs
  can't turn every request into a slow full-table rebuild) (#390).
- Jail firewall watchdog: the allow-head check now compares rule lines
  after stripping whitespace outside quoted names, so a future nftables
  version that re-renders rule text (indent, brace spacing) can't turn the
  watchdog into a false-alarm machine that stops the jail every five
  minutes; interface names and log prefixes still match exactly. The jail
  build also runs the watchdog once at build time, so a check-vs-table
  mismatch fails the build loudly instead of surfacing on the first
  timer tick. (#443)

- Auto-deploy now notices when the mitmproxy CA certificate changes, even
  with no code change in the same window: the deploy timer hashes the CA
  cert alongside the repo diff and redeploys the proxy component so the
  `with-proxy` CA bundle gets rebuilt (a rotation or first-run CA
  generation previously sat unnoticed until the next code deploy). Forced
  deploy attempts are dampened (at most one per hour per component —
  including attempts that fail, so a persistently-failing input cannot
  churn the deploy/rollback loop every tick), never mark a healthy HEAD
  blocked, and are audited with `"trigger":"extra-inputs"`. The hashed
  input is bounded (1 MiB prefix + file size) so a planted sparse file
  cannot stall the tick. The read runs at the deploy privilege through an
  atomic O_NOFOLLOW|O_NONBLOCK open with no shell check-then-read window:
  a symlink/FIFO swap race or a planted FIFO can no longer stall the tick
  while it holds the single-flight lock, and symlinks, FIFOs, directories,
  and hardlinks hash as non-regular rather than being followed or blocked
  on (#302). The deploy script also honors the `WITH_PROXY_CA_BUNDLE`
  override it already advertised instead of writing a hardcoded path
  (#303), and the jail README now documents the jail build's dependency
  on the sibling `proxy/` tree (#304).

- Waitlist re-submit after a claim no longer spawns a second pending row
  for the same address: `signed_up` is terminal in the waitlist state
  machine, and the old dedup check missed it, so a claimed owner
  re-submitting the form (or path-A email) got a fresh confirm email and
  could be invited and claimed a second time — double-counting the
  funnel and stealing a later wave's slot. Re-submits on claimed
  addresses now get an honest "Already claimed" page / `already_claimed`
  outcome: no new row, no new email, nothing refreshed ((#490)).

- Approval-signal contract doc fixes: the pending id is always a single
  approval id (the list form was unreachable); the `expired` approval
  notice is documented as best-effort — confirmd's render loop usually
  reaps expired items first, so clients see the pending id change with no
  `expired` leg and should keep waiting on the new id; and the
  answered-history item schema shared by confirmd and the proxy is now a
  named, versioned (v1) cross-component contract; its (pre-existing)
  drift behavior is documented as fail-closed (#308, #309, #310, #383).
- A manual `auto-deploy.sh rollback` now marks the rolled-back commit
  blocked (like automatic rollbacks always have), so the next timer tick
  no longer redeploys the same bad commit in a fail/roll-back loop — the
  block auto-clears once a newer commit supersedes it, `rollback
  --no-block` skips it for investigate-not-condemn rollbacks, and `status`
  prints the exact `rm` command to clear it by hand (#325, #374).
- The harness auth probe's confirmd check now verifies the answering process
  behaves like confirmd — it requires confirmd's own 403 denial shape
  (`forbidden: <reason>` body plus `confirmd/1` server header, and never
  follows a 3xx off the port) instead of counting any HTTP response as
  liveness, so a port grabber, stale service, or misbound server answering
  on the confirmd port can no longer certify the approvals path as up before
  box-live. This catches accidental misbinding at the gate, not an adversary
  who controls the port (#160, #367).
- `scripts/cut-release.sh` no longer aborts with "not a git repo" when run
  from a git linked worktree (where `.git` is a `gitdir:` pointer file, not
  a directory) — the repo gate now checks `git rev-parse --git-dir`
  instead, so operator dry-runs from worktrees pass (#349, #362).
- confirmd's approval pages and the `/sw.js` service worker now send
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`,
  so a content-type confusion can't turn an approval page into an executed
  script and approval URLs never leak to third parties via Referer (#77,
  #362).

### Security

- Denial is now terminal even in the race window (#306): the proxy re-checks for an owner denial immediately before filing a fresh approval, so a Deny tapped while a refusal was in flight no longer files a new approval and re-pushes the owner. Separately, the per-refusal denial lookup is now cached per request tuple with invalidation on every terminal write, so agents that trigger refusals at will no longer pay a full directory scan per refusal (#307). (#522)

- The credential/grant narrow writers (`cred-registry-set`, `grant-writer`, `cred-grant-revoke`, and the inference variants) no longer honor caller-controlled path-redirect variables when running as the `swapd` user: enforcement is keyed off the effective user ID, so even a direct as-`swapd` invocation (outside `sudo`, where `env_reset` already stripped them) cannot redirect the registry, grants, lock, audit-log, or secrets paths. The inference registry wrapper pins its child to the fixed inference registry via a pathless flag instead of an overridable variable. Test and development runs outside the `swapd` identity keep the override seam. (#90, #518)
- `cred-registry-set set` now merges the new placement into the existing credential entry instead of replacing it, so re-registering a credential no longer silently drops its per-entry response-scrubbing opt-out. (#96, #518)

- The provision-time echo detector now flags IPv4-mapped IPv6 loopback bindings (`::ffff:127.0.0.1` and equivalent spellings): these exact-match the proxy's host allowlists and route to loopback on the box, so they were live echo exemptions the teardown never flagged. (#504)

- Desktop screenshots are now written to a private temporary file (owner-only permissions, deleted right after serving) instead of a predictable world-readable path in the shared temp directory. (#496)

- confirmd now enforces a cumulative per-connection deadline (60 seconds,
  covering the TLS handshake and the request): a tailnet peer trickling
  data just under the per-operation socket timeout can no longer pin a
  handler slot indefinitely. Over-deadline connections are aborted
  fail-closed and logged to the audit trail as a `conn-deadline` event;
  legitimate approvals (browser poll + answer round-trips) complete well
  under the bound (#472). (#476)

- cred-ui and waitlistd now run on the same bounded, slow-loris-hardened
  HTTP server confirmd got in #469 (new shared `scripts/bounded_http.py`
  — the bounded thread pool is promoted out of confirmd so all three
  daemons share one implementation instead of diverging copies):
  in-flight handler threads are capped at 64 with fail-closed
  over-cap shedding, and the TLS handshake can never run in the accept
  loop again. waitlistd also gains the 10 s per-socket timeout its
  siblings already had — a stalled request body can no longer pin a
  handler thread forever. confirmd itself now uses the shared helper
  too (previously a local copy), and the #472 cumulative-deadline
  protection moved into the shared helper as an opt-in switch so
  confirmd keeps it — cred-ui and waitlistd leave it off, their #471
  behavior unchanged. (#471) (#499)
- The deploy installer now reads its `--src` input through the same
  symlink/hardlink/non-regular/oversize-refusing privileged-read
  discipline as the CA bundle builder (new shared `privileged_read`
  module): a symlink, hardlink, FIFO, directory, or over-1 MiB file at
  the `--src` path fails the deploy closed instead of being installed by
  the privileged process; a missing `--src` is a refusal, not a crash
  (#413). (#451)
- The privileged deploy writer now stages into randomly-named directories
  (128-bit entropy) instead of predictable per-process names, so a
  lower-privileged local user can no longer pre-create colliding staging
  directories to abort every deploy; sustained collisions still fail
  closed as an attack indicator (#333, #371).
- A failed deploy staging step now unlinks its staged temp file before
  removing the staging directory, so interrupted installs leave no
  orphaned staging directories behind (#335, #371).
- The CA-bundle builder's system-bundle read is now capped at 1 MiB like
  the swapd-CA read, so a crafted `--sys` path can't turn the privileged
  helper into an unbounded root read (#334, #371).
- Privileged-read convergence resolved as justify-with-a-test (#453): the
  deploy tick's extra-inputs hash helper and the shared privileged-read
  discipline now document why they stay separate implementations (the
  helper must never abort a deploy tick, and an oversize file must still
  flip the rotation digest instead of being refused), and a new
  conformance test runs both against the same hostile-fixture matrix —
  live/dangling symlinks, FIFOs, directories, hardlinks, missing paths,
  oversize files, unreadable files — so the duplicated open discipline
  cannot drift silently. (#480)

- Every line written to the approval audit log is now flushed to disk before the call returns: previously a crash could silently erase recent refusals from the page-cache window, and only a write error was reported. The remaining documented window is a brand-new log file's directory entry. (#72, #TBD)

## [0.3.0] - 2026-09-24

### Added

- `docs/ICP.md`: ideal customer profiles for the three segments — self-hosters
  (Unraid/Proxmox/Hetzner homelab), hosted signups (other Muse owners, with the
  buyer≠user packaging split), and sandbox harness builders (the separate
  sandbox product, cooperative-jail tier) — plus the trust-boundary split
  between them and who is NOT an ICP. Design thinking, not a commitment; the
  validation checklist lives in #343. (#347)

- Competitor watch (2026-09-24 afternoon): tracked set 7/8 VERIFIED NO-CHANGE —
  the eleven-pass full-quiet streak ends on Daytona's SEP 24 changelog entries
  (V0.216.1/V0.216.2, CLI/API polish, no sandbox moves); Vercel Drives still
  public beta; new in-lane corpus entry Google Gemini Agent Environment
  (managed Linux sandboxes for agents, VERIFIED on Google's own docs). (#348)

- Late-midday competitor watch (eleventh full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (22nd consecutive
  pass; a third-party snippet says "private beta" — recorded as availability
  color only, verdict stays public beta per the vendor changelog), Google Agent Substrate and
  Alibaba Cloud FC Agent Sandbox re-verified unchanged. Vetting upgrades, not launches: new corpus
  entry Namespace Devboxes (VERIFIED in-lane on the vendor's own docs —
  Linux/macOS devboxes for coding agents with native Claude, Cursor, and
  Devin integrations; reverses the midnight pass's adjacent verdict),
  Upstash Box verified on its own docs (row update; pricing still
  third-party), and the Ascii Box candidate retired — the vendor's own API
  docs brand the product Boat (hardest rename evidence yet), revealing
  built-in coding-agent harnesses on the `prompt` endpoint. No launches,
  pricing moves, or funding dated 2026-09-24. (#346)

- Midday competitor watch (tenth full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (21st
  consecutive pass), Google Agent Substrate and Alibaba Cloud FC Agent Sandbox re-verified unchanged; closed three
  owed follow-ups — the YC slug rename for Boat is now backed by a
  VERIFIED 301 (`/companies/ascii` → `/companies/boat`), folded into
  the ASCII "boat" provenance, and Boat's EU-only geography re-verified on the
  vendor FAQ (Germany, Finland, France). A sunset convention for
  deprecated corpus rows is proposed in the watch doc but not codified.
  (#344)
- H11 multi-tenancy audit: every localhost-only, no-auth, and single-owner
  assumption in the repo inventoried and ranked by blast radius; adopts the
  isolation research's findings and answers the four design questions —
  per-tenant box recommended for mutually-untrusted tenants (the jail is
  the honest, weaker boundary for cooperative tenants), the swap proxy
  must move from host-wide to tenant-bound request auth before any
  shared-host tenancy, tailnet enrollment fails closed with outage-time
  revocation designed as stale authorization, and the tenant holds root
  inside their guest while the operator owns only the layer below.
  Files #339 (tenant-bound swap auth) and #340 (open verifications);
  releases the H5, H12, and H13 design gates and confirms H10's
  provisional tenant-identity assumption. (#341)
- Re-open a denied approval from its answered-history card (H20): a
  mis-tapped Deny no longer needs the operator CLI to recover — the card
  offers "Re-open this request", which re-files it as a new pending
  approval (new id, the original request, the requester's original
  deadline kept verbatim, expired requests refused honestly) and re-pushes
  the owner. Single-tenant for now, designed for the multi-tenant future.
  (#331)
- Competitor watch (2026-09-24 morning): tracked set 8/8 quiet (ninth
  consecutive pass), Vercel Drives still public beta; corpus dedups a
  phantom provider — ASCII renamed to Boat ~2026-09-17, so ASCII "boat" folds into
  the tracked-set Boat row (same product, canonical domain boat.dev); new
  in-lane entry Alibaba Cloud FC Agent Sandbox billing — verified
  from aliyun-fc/fc-docs (Eco/Std/Pro pay-as-you-go from ~$0.037/h for a
  2vCPU/4GiB box, task-scoped and E2B-SDK-only, not a persistent VM);
  wowza.com owed re-verification closed; no new in-lane launches 9/23–24.
  (#337)
- Competitor watch (2026-09-24 predawn): tracked set 8/8 quiet, Vercel
  Drives still public beta; corpus grows a new in-lane entry — ASCII "boat"
  (persistent Ubuntu VMs for agents with verified own-page
  pricing: $20/mo plan = $20 sandbox time, $0.036/h for 4vCPU/8GB/50GB,
  EU-only); Simular Sai pricing refined (vendor-published $50/$500
  on simular.ai, sai.work carries no pricing). Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md` (#330).

- Competitor watch (2026-09-24 midnight): tracked set 8/8 quiet, Vercel Drives
  still public beta; corpus grows a new in-lane entry — Simular "Sai"
  computer-use agent GA (fleet of cloud VMs up to 100 machines); Freestyle
  boot claim qualified (marketing "65 ms" vs docs p99 under 400ms); E2B
  $21M Series A dated 2025-07-28; Modal ~$15B raise talks (third-party).
  Full pass in `docs/COMPETITOR_WATCH_2026-09-24_MIDNIGHT.md` (#329).

- Competitor watch (2026-09-23 late overnight) (#327): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (sixth full quiet
  pass since the mid-afternoon fold); Vercel Drives still public beta
  (seventeenth consecutive no-change pass; pricing page last_updated
  2026-09-10; the 2026-09-23 changelog entry is the beta announcement
  re-dated, not a GA move); Boxd rate card re-verified on boxd.sh (the
  overnight pass's Boxd fold stands — no new fold); new in-window
  third-party item: Simular "Sai" computer-use agent GA on cloud VMs
  (vendor verification owed); no other in-window launches, GA moves, funding, or
  pricing moves dated today.
- Competitor watch (2026-09-23 overnight) (#322): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (fifth full
  quiet pass since the mid-afternoon fold); Boxd rate card now
  vendor-verified on boxd.sh (Boxd debt resolved); new in-lane corpus
  entries Freestyle pricing ("VMs for AI Agents") and Tensorlake (
  "Sandboxes for AI Agents"); Automaid lane-drift confirmed on its own
  page (workflow-automation SaaS) and dropped from the watch list; no
  in-lane launches, GA moves, funding, or pricing moves dated today.
- Competitor watch (2026-09-23 late night) (#320): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (DO Managed
  Agents pricing figures read live a fourth consecutive pass, stamp "Last
  verified 22 Sep 2026", snapshots/checkpoints $0.05/GiB-month);
  Vercel Drives still public beta (fifteenth consecutive no-change
  pass; pricing page last_updated 2026-09-10); Boxd quickstart now
  VERIFIED (rate card UNVERIFIED this pass — surveyor fetch gate —
  honestly labeled, not carried); Google Agent Substrate no new vendor datapoints
  (no GA move, allowlist-only production stands); Automaid own-page
  fetch failed again (UNVERIFIED) but third-party evidence hardened
  against it — every result names cleaning-business booking SaaS,
  moving it to lane-drift pending one successful own-page fetch;
  Tencent Cloud DataBuddy stays lane-drift; THIRD-PARTY Upstash
  15-provider comparison names newcomers (Upstash Box, Freestyle,
  Ascii Box, Namespace, Beam, Tensorlake) as future-vetting
  candidates; no corpus fold; no in-lane launches today.
- Competitor watch (2026-09-23 early night) (#318): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (DO Managed Agents pricing figures read live a third consecutive pass,
  stamp "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (14th consecutive
  no-change pass); Boxd rate card unchanged (quickstart UNVERIFIED
  this pass — honestly labeled, not carried); Google Agent Substrate no new vendor
  datapoints; Automaid own-page verification still owed (fetch failed
  this pass — UNVERIFIED); Tencent Cloud DataBuddy stays lane-drift
  (agent-workbench governance, not VM-for-agents); no corpus fold;
  no in-lane launches today.
- Competitor watch (2026-09-23 post-mid-evening) (#317): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (mid-evening's DO Managed Agents pricing resolution stands: DO pricing docs sub-page
  re-verified live, "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (thirteenth
  consecutive no-change pass; pricing page last_updated 2026-09-10, no
  changelog entries dated 2026-09-23); Boxd rate card unchanged; Google Agent Substrate no
  new datapoints since the 16:00 CDT vendor-confirm fold; Automaid
  own-page verification still owed (site fetchable this run, no launch
  announcement — third-party claim stays UNVERIFIED); no in-lane
  launches.
- Competitor watch (2026-09-23 mid-evening) (#316): **DO Managed Agents pricing discrepancy
  resolved on the primary source** — DigitalOcean's pricing docs sub-page
  fetched this pass (page stamped "Last verified 22 Sep 2026") and bills
  snapshots/checkpoints at $0.05/GiB-month, retiring the corpus's
  $0.005/GiB-month syndicated-release figure; re-verified CPU-billing
  footnote ("active CPU billing is coming soon, until then 25% of the vCPUs
  allocated to your sandbox; paused sessions incur no compute charges"),
  qualifying the per-entry paragraph's "zero while waiting" read;
  mid-afternoon fold's storage/BYOT/egress/prepaid figures re-verified
  live. Otherwise quiet: 7 of 8 tracked providers re-read vendor-verified
  with no change; Vercel Drives still public beta (twelfth consecutive
  no-change pass; no changelog entries dated 2026-09-23); Boxd rate
  card unchanged (one tool-side fetch failure on the docs pricing URL,
  reported UNVERIFIED); no new Google Agent Substrate datapoints since the afternoon
  vendor-confirm fold; no in-lane launches.
- Competitor watch (2026-09-23 early evening) (#314): tracked set quiet — 7 of
  8 providers re-read vendor-verified with no change (7/7 attempted
  vendor fetches succeeded; DigitalOcean's pricing sub-page URL was
  not extractable this pass — reported UNVERIFIED, not no-change);
  the $0.044/$0.0095 figures stand at the third-party layer, and the
  flagged $0.05-vs-$0.005 snapshot-rate discrepancy is now the
  standing DO Managed Agents pricing watch item; Vercel Drives still public beta with no GA
  move (eleventh consecutive no-change pass; the beta entry's date
  field flipped 09-23→09-22 — re-publish, not a GA move); same-lane
  third-party pricing color on Google's Filestore agent volumes for AI
  (pay-per-use capacity + lifecycle tiering, folded under Google Agent Substrate at the
  THIRD-PARTY layer); no in-lane launches.
- Competitor watch (2026-09-23 late afternoon): Google Agent Substrate-focused verification
  pass (no full tracked-set re-read — 8/8 last vendor-verified ~15:12 CDT,
  no change). **Google Agent Substrate VENDOR-CONFIRMED** — Google's own Cloud-blog
  announcement read live corroborates all nine filed Agent Substrate-on-GKE
  claims (five verbatim, the rest confirmed as filed or
  stronger) (<500 ms resume, 500+/sec suspend/resume activations,
  1,000+ dormant agents/host, Cloud Hypervisor-or-gVisor choice, integrated
  gateway, non-production for all GKE customers with production GA via
  allowlist, Nous Research/Hermes early design partner with named quote);
  new vendor facts folded into the corpus (10× density headline, open-core
  portability, harness-agnostic design, control/data-plane split, Filestore
  agent volumes, native Axion).
- Competitor watch (2026-09-23 mid-afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (tenth
  consecutive no-change pass; changelog sitemap beta-entry date flip-flop
  continues — the date field is unproven as evidence either way);
  **DO Managed Agents pricing closed** — DigitalOcean Managed Agents pricing now vendor-verified
  on the docs pricing page ($0.044/vCPU-hour active CPU, $0.0095/GB-hour
  memory, sandbox shape table, pause semantics) with an explicit caveat:
  the docs price snapshots/checkpoints at $0.05/GiB-month vs the launch
  release's $0.005 — 10× apart, one source is wrong; OpenAI Agents API partner list vendor-confirmed
  (OpenAI's own blog on the Agents API public beta; nine named sandbox
  partners including Daytona, DigitalOcean, E2B, Modal, Vercel);
  new-to-watch Google Agent Substrate on GKE (~Sep 17,
  third-party-only); no new in-lane launches in the 48h window;
  Automaid, Andon Pion, Huawei baselines hold. (#311)
- §3a smoke-check provision assets (G6): the provision-time injector now
  installs the public `smoke-test` dummy credential (spec's pass phrase,
  never a secret), appends the operator's `smoke.<domain>` echo host to
  the main proxy's `hosts.allow` (newline-safe, proxy-matching semantics)
  AND to the proxy's smoke-only scoping list (`SWAP_SMOKE_HOSTS_FILE`,
  default `/home/swapd/smoke-hosts`): the echo host swaps ONLY the
  `smoke-test` credential (refusal `smoke-host-restricted` is audited),
  closing the chosen-plaintext read oracle. Also installs a
  visudo-validated scoped sudoers fragment whose granted argv is pinned
  to `cred-store-set smoke-test` for the tenant agent user, and binds
  `smoke-test` to the echo host in the main registry (the proxy's grant
  scoping refuses unbound credentials, so the §3a swap needs the
  binding). (#313)
- Competitor watch (2026-09-23 early afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (ninth
  consecutive no-change pass; the changelog sitemap's beta-entry
  re-date 09-22→09-23 is stable since the late-midday pass — the date
  field is unproven as evidence either way); no
  new in-lane launches since the DigitalOcean Managed Agents public
  preview (already filed); DO Managed Agents pricing refined — DigitalOcean's own
  launch-release text read in full on syndicated copies (completeness
  at the same THIRD-PARTY layer; the docs Details/pricing sub-page is
  still unreached); OpenAI "Managed Agents" still
  rumor; Automaid own page still missing. (#298)
- Competitor watch (2026-09-23 late midday): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (eighth
  consecutive no-change pass; changelog sitemap re-dated the beta entry
  09-22→09-23 — a re-publish, not a GA move); no new in-lane launches
  since the DigitalOcean Managed Agents public preview (already filed);
  Docker Sandboxes 0.42.0 CVE pair closed — vendor-verified on
  Docker's own security announcements, matching the corpus's standing
  characterization with no drift (no corpus fold); DO Managed Agents pricing refined (vendor
  docs now load but dollar pricing still third-party-only — Details
  sub-page is the next ask); Automaid adjacent "AI hub for agents that
  keep working" color, own page still missing. (#296)
- Client-visible approval signal (#133): when the swap proxy refuses a
  request for lack of a grant, the proxied response now carries the
  approval id and terminal decisions in response headers —
  `X-Spark-Approval-Pending: <aid>` while a grant request is pending
  (filed or coalesced; a replaced expired item is reported as
  `expired:<old-aid>` alongside the new pending id), and
  `X-Spark-Approval-Decision: approved|denied:<aid>` once decided —
  so the requesting agent can park and re-issue instead of failing on
  a remote auth error. Denial is terminal: within the 1-hour decision
  window a denied tuple suppresses fresh filings (no owner re-push);
  denial suppression is path-scoped. Header values carry only the
  approval id and the state word — never credential names, hosts, or
  secret material. Spec: `docs/APPROVAL_CLIENT_SIGNAL.md`. (#133)
- Competitor watch (2026-09-23 midday): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (seventh
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); no new in-lane launches since the DigitalOcean Managed
  Agents public preview (already filed); DO Managed Agents pricing vendor verification
  failed again (browser-service error) and Docker Sandboxes 0.42.0 CVE pair stays third-party-only
  despite stronger corroboration (0.43.0 latest per mirror, CISA
  assesses exploitation as "none", neither CVE in KEV as of Sep 16).
  (#295)
- Competitor watch (2026-09-23 late morning): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (sixth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents public preview now carries published pricing ($0.044/vCPU-hour
  active, $0.0095/GB-hour, $0.005/GiB-month snapshots — resolves DO Managed Agents pricing's
  pricing ask at third-party level, vendor verification owed) — the
  first in-lane launch verdict of the recent streak (public preview, not
  GA); Docker Sandboxes 0.42.0 CVE pair (CVE-2026-77179, CVE-2026-79994),
  third-party only, vendor verification owed. (#292)
- Competitor watch (2026-09-23 night): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (fifth
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); DigitalOcean Managed Agents docs still carry no dollar
  pricing (DO Managed Agents pricing open); adjacent re-checks — Automaid still THIRD-PARTY
  only, Andon Pion no new facts, Huawei Open Agentic Cloud still
  THIRD-PARTY; fourth consecutive pass with an explicit in-lane
  no-launch verdict (afternoon, evening, late evening, night). (#291)
- Competitor watch (2026-09-23 late evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (fourth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents docs follow-up (agent-harness-runtime page — preview for all
  users, pricing terms still unverified on vendor docs, DO Managed Agents pricing color);
  same-lane color — AWS Lambda MicroVMs self-hosted agent-sandbox
  reference architecture and the Herdr × Vercel Sandbox
  one-agent-one-machine plugin; no in-lane launches. (#289)
- Competitor watch (2026-09-23 evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (third consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents preview detail (Firecracker per-session pause/resume harness,
  active-CPU billing — anti-always-on positioning, filed as DO Managed Agents pricing lane
  color, not a corpus entry); still no always-on
  persistent-agent-machine announcements from any competitor. (#288)
- Competitor watch (2026-09-23 afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (second consecutive no-change pass);
  one in-window third-party corroboration filed as investor color only
  (Firecrawl $75M Series B — no new facts beyond the §2c filing); borderline pre-window
  color on Boxd's $2M pre-seed and Alibaba FC Agent Sandbox pricing;
  still no always-on persistent-agent-machine announcements from any
  competitor. (#286)
- Competitor watch (2026-09-23 morning): 2 of 8 tracked providers moved —
  Daytona v0.216.0 hardens the SDK build context (Dockerfile COPY confined
  to the build context, filed Daytona v0.216.0) and Docker Sandboxes' 2026-09-21 release
  ships v3 kits (OCI-based packages bundling an agent workload with
  reusable mixins for tools, config, credentials, network access, and
  agent instructions — filed Docker Sandboxes v3 kits, folded into the competitor corpus);
  Vercel Drives still public beta with no GA move; market-news window
  quiet with no always-on persistent-agent-machine announcements.
- Competitor watch (2026-09-23): tracked set quiet (8/8 vendor re-reads,
  no in-window deltas); the standing Vercel 64 GB default-storage ask is
  CONFIRMED on the vendor's own pricing docs — sandboxes get 64 GB of
  ephemeral NVMe by default (32 GB only on deprecated runtimes), closing
  the 64 GB default-storage ask; Vercel Drives public beta completes with real pricing (storage,
  reads, writes, caps, concurrency); adjacent investor color on Firecrawl's
  $75M Series B. (#279)
- The excluded-host link re-sweep now covers all eight bot-blocked hosts:
  a live-browser sweep hand-verified the five later-excluded hosts (all 11
  pages load; 10/11 citations match), and the ritual's enumeration now
  filters URL false positives before counting. One citation annotated
  along the way — Daytona's retired security-exhibit page now redirects to
  their Trust Center, so the isolation quote's citation is annotated and
  re-sourcing issue #277 is open. (#278)
- Overnight competitor watch (2026-09-22): tracked set quiet (8/8 vendor
  re-reads, no in-window deltas); Boxd's SDK install URL is now
  vendor-attested — boxd.sh serves the genuine installer (canonical path
  boxd.sh/downloads/cli/install.sh), closing the last unverified item on
  the Boxd entry; Vercel Sandbox announced persistent "Drives" in public
  beta (up to 16 TiB, usage-based) — a separate feature from the
  still-unverified default-storage claim; third-party follow-up analysis
  of DigitalOcean's Managed Agents launch adds no new mechanism detail.
  (#275)
- Design for the hosted tenant status endpoint: the `GET /tenant/status`
  contract the first-ten-minutes spec, signup flow, and signup UI all
  assume — the 12 machine codes with transition rules, the `approvals_url`
  carrier, two-sided auth (magic-link cookie + linked-key), and the
  provider-layer vs tenant-layer separation (#273).
- Evening competitor watch (2026-09-22): DigitalOcean's Managed Agents
  product page is readable again — Tool Playground (pre-production policy
  testing), scheduled/webhook triggers, and org-policy concepts
  (actors, toolbelts) — plus a flag that DO's marketing claims (~200 ms
  resume) outrun its own measured benchmark (305 ms); Fly.io Sprites'
  lifecycle docs publish warm wake 100–500 ms and cold wake 1–2 s with
  dropped TCP state, bearing on the resume-latency target. New to the
  tracked set: Boxd ($2M pre-seed, KVM persistent-machine competitor,
  vendor-claimed fork-including-memory in <100 ms), the OpenAI Agents API sandbox
  partner list (formalizes the harness-vs-compute split — INFERRED from
  the partner list, not an OpenAI claim), and a new snapshot/restore
  datapoint on the already-corpus-ed Upstash "Box" entry; independent hands-on coverage of the
  DO launch is still absent. (#270)
- Golden-image round-trip gate operator procedure (spec §6.7): the
  file → answer → grant-mint → verify sequence with the filing-count
  determinism check and mandatory fixture teardown pre-publish. The
  round trip exercises the proxy's real filing path (a gate-only
  credential bound with narrow static limits files one approval through
  the main proxy; the operator answers through confirmd; the grant mints
  through the grant writer; the re-run proves the swap took effect),
  wired to the existing gate-fixture tooling. (#271)
- Secrets-posture corpus gains DigitalOcean Managed Agents as the fifth
  convergent data point (their launch release claims a separate secrets
  service with "credentials brokered at execution time" that "never reach
  the model or the sandbox" — press-release source, no mechanism detail
  scored), and the org-policy vendor set gains DO's Action Gateway
  (governed tool access via one managed MCP endpoint) as a candidate. (#263)
- Morning competitor watch (2026-09-22): DigitalOcean launched Managed
  Agents in public preview — microVM-per-session Harness Runtime, Action
  Gateway (16,000+ tools via one MCP endpoint, credentials brokered at
  execution time), and active-CPU pricing ($0.044/vCPU-hour, 305 ms
  pause→resume claim) — filed as a new tracked competitor, with follow-up
  notes for the hosted product's pricing thinking, resume-latency target,
  secrets posture, and org-policy layer; Daytona shipped a routine v0.215.0
  SDK/CLI patch; the rest of the tracked set was quiet. (#256)
- Enforcement-downgrade contract for the agent jail (fail-closed, stated
  explicitly): a firewall-apply failure aborts the build before the jail
  starts, a boot-time apply failure blocks the container from starting, and
  a dead proxy means no egress rather than open egress — like Brig's
  policy-bound refusal, the workload never runs where its restriction
  cannot be enforced. The one residual the contract originally stated —
  no runtime re-apply — is closed by the firewall watchdog #260, which
  narrows the residual boundary to the 5-minute verify window. The contract
  mechanics are test-pinned. (#255)
- Deny-style billing guard committed for sandbox credential forwarding:
  when the hosted path forwards operator credentials into a sandbox,
  known metered-billing keys are deny-by-default without an explicit
  per-credential override (Brig's `deny` shape, including its documented
  environment-channel-only limit). Committed design, not yet shipped —
  no forwarding surface exists yet. (#255)
- Demo gallery, sixth asset: the push queue surviving an outage — the new
  "See it in action" row shows the standalone push worker's first delivery
  attempt hitting a dead endpoint (500) and rescheduling instead of losing
  the approval, the durable journal holding the summons, and the retry
  delivering once the endpoint answers (201). The generator replays the
  real enqueue/worker code paths against a local mock push service
  (throwaway keys, nothing leaves the machine). (#252)
- Push notifications now survive a dead push service: swapd enqueues every
  filed approval and a standalone push worker (`push-worker.service`)
  delivers with exponential-backoff retry, dead-lettering only after 8
  failed attempts with a loud log line. On the healthy path delivery
  waits for the next worker pass (up to 30s, tunable via
  `--worker-interval`). Runs wherever the deployment lives (self-hosted
  or hosted), like confirmd. (PR #204)
- Waitlist claim route: the invite email's claim link is now served —
  opening it shows the claim screen (masked owner email, the same
  what-happens-next steps as the invite email), and clicking through
  records the claim idempotently and logs it in the funnel trail. Dead
  or expired links land on an honest "no longer live" page, never an
  error dump. (#250)
- Provider failover-router design: the new design doc describes how the
  hosted control plane would keep a tenant session alive across a
  provider outage — which failures trigger a move to another provider
  (and which recover in place), the order of operations for the move,
  how session data is restored when VM snapshots can't cross providers,
  and how provider capabilities pick the fallback target. (#251)
- Provision-time injector (`harness/inject-provision-state.sh`): runs at
  first boot of the hosted agent VM and owns the provision-time half of
  the gate-fixture contract — preflights the golden-image manifest
  against the operator-pinned image SHA and fails closed on drift
  before box-live; tears down the gate fixture's `llm-api`→echo-host
  binding, failing closed on echo-host residue in the allowlists (which
  only the image-build gate can remove); asserts a real inference
  credential through the registry plus a blind compare against the
  public fixture dummy (the stored value is never read, never written,
  never printed); requires a fresh per-tenant swapd CA; installs tenant
  identity and records tenant attribution when their inputs are
  provided (both reported as deferred when absent, never fabricated);
  then proves the injected key with the provision-mode probe — a probe
  failure maps to provisioning-failed and box-live must not flip.
  Ships one JSON inject report on stdout and 55 hermetic tests. (#238)
- Night competitor watch (2026-09-22): quiet survey window — no launches,
  acquisitions, pricing changes, releases, or partner moves across the
  tracked set; boat.dev rate card and comparison table re-verified
  unchanged; two pre-window competitors newly surfaced and filed as
  watchlist items (Brig, Epho); adjacent color on Meta Muse's Sentinel
  per-user VM architecture (third-party deep dive of the pre-window
  launch). (#239)
- Waitlist operator tooling: `waitlist_invites.py --reconcile` repairs
  missing `invite_sent` funnel events after the commit → emit crash
  window — it re-derives the missing events for still-live invites from
  the waitlist store in the append-only posture (each re-derived event
  carries `reconciled: true` in its attrs; `--dry-run` previews), is
  idempotent, and skips rows whose invite is no longer live. (#237)
- Secrets-posture corpus: h-sandbox's Credential Vault (open-source,
  self-hosted sandbox control plane) becomes the fourth convergent data
  point for the placeholder-swap pattern — its docs describe fake-env
  placeholders in the sandbox with the real auth material injected at the
  egress sidecar only for host/scheme/method/path-bound requests (verified
  against their own docs 2026-09-21, verbatim quote in the research doc);
  the watch pass also records its OpenSandbox-adapter contract discipline as
  input to the hosted provider-adapter design. (#230)
- Secrets-posture corpus: opencomputer.dev's secret-store egress proxy
  (opaque placeholder in the sandbox, real key swapped in-flight on the
  outbound HTTPS call to the model provider, under an egress allowlist —
  verified against their own docs 2026-09-21, verbatim quote in the research
  doc) joins Daytona and Microsandbox as a third convergent data point for
  the placeholder-swap pattern. (#219)
- Competitor watch 2026-09-21 evening (docs/COMPETITOR_WATCH_2026-09-21_EVENING.md):
  quiet window — zero in-window deltas across the tracked set since the
  afternoon pass; one pre-window miss filed as watch item h-sandbox
  (h-sandbox/"Harakiri Sandbox" — open-source self-hosted sandbox
  control plane launched 2026-09-09, with a host-bound-egress credential
  vault and an OpenSandbox execution adapter, the closest open-source
  shape to spark-vm's secrets posture); AgentComputer's "unverifiable"
  egress posture refined to a stronger negative (real product with real
  pricing, still no stated egress policy). (#216)
- `jail/build.sh` is safer to inspect and harder to drift: `--help` / `-h`
  renders the script's header doc and exits before any side effect in ANY
  flag position (`build.sh --rebuild-rootfs --help` can't accidentally
  start the privileged build — the usage line documents that order), and
  the tailnet→jail SSH port is now single-sourced from `$JAIL_SSH_PORT`
  into the nftables DNAT rule via a quoted heredoc + placeholder
  substitution — the applied conf always carries the variable's value,
  with tests that render through the real sed pipeline.
- The single-command test story now actually covers every component:
  `pytest.ini` discovers the `cua/`, `jail/`, AND `credlib/` suites too —
  including a new `cua/test_shell_scripts.py` gate (`bash -n` +
  shellcheck warnings for the four host-side `cua/bin` scripts that
  can't run in CI, with an explicit skip when shellcheck is absent,
  now also wired into `ci.yml` so the gate actually executes) — and
  `confirm/test_push.py` skips explicitly (instead of erroring
  collection) on boxes without the `cryptography` package, so
  `python3 -m pytest` degrades gracefully.
- Approvals-plane gap analysis: a new doc walks the full path from a gated
  action to a human answer and back (refusal → filing → pending → human
  answer UX → push summons → terminal decision delivery → audit trail),
  against the code as it stands today. Headline finding: the plane is a dead
  end for the agent — refusals carry no approval id, answers deliver no
  decision, and expiry is a silent third outcome — and files two new issues
  (expiry's silent terminal outcome; answered-feed per-poll parse cost).
  (#215)
- Release-protection drift guard: the declared `main` branch ruleset's
  required CI checks are now verified bidirectionally against
  `.github/workflows/ci.yml` — renaming, adding, or removing a CI job fails
  the test suite until the declared ruleset is updated deliberately, so the
  release-tag/branch protection can no longer silently lag behind CI.
  (#208)
- Waitlist slice 3 remainder (H15 — path-A email parser + invite sender):
  `site/waitlist_patha.py` implements the email intake path
  (WAITLIST_OPERATIONS.md §2) — exclusion list (From, inbox,
  @agentmail.to) applied before counting, `Owner:` line override, the
  optional ed25519 pubkey + ≤280-char use-case line, exactly-one-candidate
  proceeds to a validated row with the path-A confirm opener, zero/≥2
  candidates get the §2 clarification reply only on DMARC-aligned mail
  (unauthenticated mail is silently triaged — no backscatter), a reply
  saying "forget me" triggers the §5 confirmation email with the signed
  forget link (never direct deletion), and the §6 per-sender 3/day intake
  limit; `site/waitlist_invites.py` drives §7 invite waves (top-N
  confirmed FIFO by confirmed_at, pricing + trial terms filled at send
  time from operator files, signed position line, 14-day `invite.`-prefixed
  HMAC claim tokens, `invite_sent` funnel events) plus the expiry
  rollover (unclaimed invites return to `confirmed` with confirmed_at
  reset to the expiry time, no re-confirmation). (#203)
- Competitor watch 2026-09-21 (docs/COMPETITOR_WATCH_2026-09-21.md): quiet
  window — no launches, pricing changes, partner moves, or version bumps
  across the tracked set since the 2026-09-20 pass; boat.dev's rate card
  re-verified ($20/mo = 555h of 4vCPU/8GB) with an xlarge
  capacity-allocation caveat flagged for verification before any 16-vCPU
  sizing decision; version resolution — Microsandbox v0.7.1 confirmed on
  the vendor releases page post-window (corpus record vindicated; no
  corpus change). (#191)
- Waitlist forget-me flow (H15 slice 3c): every transactional email footer
  now carries a signed one-click forget link (7-day, single-use,
  domain-separated from confirm tokens so the two can never validate at
  each other's endpoint); the signed link renders a delete-confirmation
  page and, on POST, atomically deletes the waitlist row, logs the
  `forgot` funnel event, and spools the spec-mandated deletion
  confirmation. The marketing page's `/go/selfhost` CTA now has both a
  no-JavaScript static redirect shim for the static host and a dynamic
  control-plane route that logs the `cta_click` event before redirecting
  to the self-host guide. The waitlist form's action posts to the
  control-plane origin via a deploy-time placeholder the operator fills
  at launch (a relative action would post to the static host, which has
  no serving layer). (#190)
- boat.dev 16-vCPU caveat confirmed as current vendor policy:
  the pricing page still
  footnotes xlarge as needing a $100+/mo plan plus operator capacity
  allocation, so any 16-vCPU hosted sizing must confirm capacity with the
  provider first; the baseline rate card is unchanged ($0.036/h default,
  stopped sandboxes free, $26 for one default running the whole month).
  (boat.dev xlarge capacity allocation; #206)
- Competitor watch 2026-09-21 afternoon
  (docs/COMPETITOR_WATCH_2026-09-21_AFTERNOON.md): quiet window — no
  launches, pricing changes, releases, or partner moves across the
  tracked set since the morning pass; boat.dev's pricing page re-read
  and unchanged, and its twelve-provider comparison table verified as
  the page's current state (the earlier read was simply partial);
  Microsandbox still at v0.7.1, Docker Sandboxes still at 0.43.0, Daytona
  changelog still topped at v0.214.0 (Sep 15), TermSquad tiers
  re-verified unchanged; WSO2 reception broadens slightly ahead of the
  Sep 29 webinar. No corpus changes. (#209)
- Secrets posture page (#189): frames the placeholder-swap design as
  independently re-derived — the pattern is convergent across the industry —
  and compares swapd mechanism-by-mechanism against E2B, Daytona, Vercel,
  Cloudflare, and Microsandbox from their own docs (vendor links inline).
  States swapd's honest edges (request-body injection scope, response
  scrubbing, per-decision audit-as-authorization) and its conceded gaps
  (Microsandbox's DNS-pinned destination gate, E2B's per-request token
  minting), plus the concrete `allowOut`-vs-swapd egress-grant difference.
- First test suites for the two remaining untested components (O4): `cua/`
  gets hermetic tests for the `cua-bridge.py` localhost bridge — launch
  allowlist enforcement, the CSRF/host gate, window picking, and the
  click/type/key/launch endpoints (including the desktop→window coordinate
  mapping and the panel global-click branch) — plus syntax/shebang checks
  for the `cua/bin` shell scripts; `jail/` gets a hermetic smoke test for
  `build.sh` pinning its strict mode, idempotency guards, and the jail's
  documented isolation properties (no bind mounts, no DNS, proxy-only
  nftables egress, explicit UID range, sshd hardening, swapd CA temp
  cleanup). Both suites are wired into the CI `python-tests` job. (#187)
- Stopped/cold retention tier thinking: the hosted pricing thinking
  now names the stopped-state cost story the live-control deep scan found
  missing — a published $0.000027/GB-hour cold-storage anchor (≈$0.79/mo
  for a stopped 40 GB box), running-only billing precedent, and the
  control-plane→billing contract the H4 provider interface already ships.
  Thinking only; no pricing-page row until the Billing decision lands.
- Waitlist 30-day post-drop purge: `waitlist_jobs.py --purge` permanently
  deletes dropped waitlist rows 30 days after the drop (the §5 retention
  rule), via an atomic `rows.jsonl` rewrite under the same data lock as
  the reminder/drop jobs — the funnel events stay as the audit trail.
- H4 provider interface contract: the provider-agnostic driver every
  sandbox backend implements, reconciling the H3 signup design, the
  suspend/wake and Fly/GPU provider research, and the #47 lifecycle
  audit into one buildable target — six verbs (provision, status,
  suspend, wake-on-dial, ssh_info, destroy; snapshot reserved), a validated box
  lifecycle state machine, per-shape suspend capability flags, a
  billing-facing disk-retention descriptor for idle/stopped boxes, and
  a fail-closed no-public-ingress rule the control plane verifies after
  provisioning. Park-style backends (RunPod's "suspend" is park) are
  representable via the `wake_reprovisions` capability flag and the
  `wake_kind` resume-path surface, and the per-`vm_id` lifecycle is marked
  provisional on H11's isolation-shape answer ([#183](https://github.com/ntindle/spark-vm/pull/183)).
- README "See it in action" gallery: the five demo GIFs (secret-swap proxy,
  approval loop, job runner, desktop persistence, phone credential UI) now
  sit on the repo landing page next to the stack they demonstrate, with
  each frame's provenance and regeneration recipe in the assets notes
  ([#188](https://github.com/ntindle/spark-vm/pull/188))
- README "What's in the box" names the human-approval loop (`confirmd`)
  alongside the proxy/job-runner/desktop/cred-UI stack, and the repo
  layout table now lists `deploy/`, `harness/`, `site/`, `assets/`, and
  the `VERSION`/`CHANGELOG.md`/`CONTRIBUTING.md` process files (#182).
- Lifecycle parity audit for the #47 live-machine-control ticket: #47's
  promised-vs-accepted lifecycle surface checked against the six-provider
  live-control scorecard. Found pause/resume promised in the ticket but
  missing from its acceptance criteria, undefined stream-ownership
  semantics for the live desktop, no idle lifecycle policy model, and an
  undecided stopped-state/file-browsing scope — filed as #177, #178, #179,
  and #180. Also closes the deep-scan's unscored file-browsing and restart
  columns.
- Release and branch protection declared as code (`deploy/rulesets/`): a
  `v*` tag ruleset that makes the release notes' "tags are never moved or
  re-cut" claim platform-enforced (blocks tag update/deletion, with a
  stricter variant that also restricts tag creation to the release
  workflow), plus a `main` branch ruleset (no deletion, no force-pushes,
  PR-required, all CI checks green on an up-to-date branch before merge —
  deliberately no human-approval gate so the improvement loop can keep
  self-merging). An auditable `scripts/apply-rulesets.sh` (dry-run default,
  `--check` drift compare, `--execute --yes` idempotent apply) applies them;
  applying is an owner decision (#174)
- Jail firewall runtime watchdog (closes #254): a 5-minute systemd verify
  timer pins the jail's nftables enforcement rules themselves (drop-rule
  markers + proxy DNAT — the chains are policy accept, so chain shells
  alone prove nothing). On confirmed damage it is fail-closed: the jail
  is stopped first (a table re-apply doesn't flush conntrack, so
  hole-era flows would otherwise survive), then the table is re-applied
  (scoped to the jail table only), and the unit goes red — restart is
  the operator's explicit decision. The old "flushed table silently
  voids the isolation guarantees until someone restarts the unit" hole
  becomes bounded downtime instead of unbounded unenforced running.
  (#260 — entry placed at the end of Unreleased/Added so the branch
  merges cleanly over #263's same-section entry)
- Afternoon competitor watch (2026-09-22): the DigitalOcean Managed
  Agents launch blog added the mechanism detail the morning pass lacked —
  Firecracker microVMs per session, auto-pause defined precisely as "no
  outgoing LLM or tool calls," a 99.3% intent-match claim for Action
  Gateway tool search, a $0.060 vs $0.126 active-CPU worked pricing
  example, live product docs with a prepaid-balance billing model, and a
  self-published benchmark naming Fly.io Sprites as the comparator
  (886 ms create→ready, 189 ms exec RTT, 305 ms resume); the rest of the
  tracked set was quiet. Inputs filed for #47 (benchmark reference
  numbers, edge-routing latency datapoint) and #179 (auto-pause idle
  trigger). (#268)
- Late-evening competitor watch (2026-09-22): the tracked set was quiet
  across all eight vendor re-reads; the Boxd entry is upgraded from
  third-party-only to vendor-verified (their own site and docs read this
  pass) — fork of a live machine lands in under 200 ms (correcting the
  <100 ms press claim), the active-connections-fork claim is NOT
  vendor-attested, plus pricing (€0.049/vCPU-hour, €0.015/GiB-hour RAM,
  €0.0001/GiB-hour disk, €30 free credits) and a confirmed self-hosted
  offering; Boxd's "under a millisecond" idle-resume is a marketing-page
  figure with no published methodology and is not treated as a
  benchmark. (#272)
- Competitor corpus consolidation (2026-09-22): the deferred watch entries
  Deferred competitor entries folded into the competitive map — first
  entries for boat.dev ($0.036/h default; xlarge capacity-gated),
  DigitalOcean Managed Agents ($0.044/vCPU-hour active-CPU metering),
  Boxd (vendor-page-verified fork claims and pricing),
  Upstash Box (snapshot/restore mechanics), h-sandbox (OSS credential-vault
  comparand), Brig (local microVM containment), and Epho (agents-as-API with
  multi-provider fallback), plus the OpenAI Agents API harness↔compute split
  as a design input for the hosted product's per-harness adapters. (#274)

### Changed

- Hosted pricing thinking refreshed: the internal pricing analysis now
  reflects the decided Fly.io provider (boat.dev under evaluation as a
  cheaper alternative), records Epho's bring-your-own-keys infra-only
  metering as a candidate shape for model-token billing (zero margin risk),
  and drops the stale merge-order note — all cited strategy docs are on
  main and price inputs re-verified through the 2026-09-21 competitor
  reads. (PR #253)

### Fixed

- The two privileged install-safety regression tests (staged-temp
  substitution and staging-dir swap) previously self-skipped in CI because
  runners are non-root, so the merge gate never actually exercised the
  guard they prove — they now run under sudo on every PR, and a skip in
  that step fails the build instead of passing silently. The stale "no
  root" header on the test module and the "atomic via O_EXCL" comment in
  the deploy script are corrected to match. (#345)
- The auto-deploy updater re-verifies the working checkout is clean
  immediately before syncing a component subtree into it, not just at the
  pre-deploy gate: a manual edit made between the gate and the install no
  longer gets silently clobbered — the deploy aborts with an alert and
  retries on the next tick, without marking the commit blocked (components
  already installed in the same run are rolled back first). (fixes
  #324, PR #338)
- The deploy health check now reads the port as the trailing `:digits`
  field and treats everything between `tcp:` and that field as the host.
  Malformed entries (missing or non-numeric port, empty host) fail the
  health check closed with a clear log line instead of being probed
  with a garbage port. (fixes #323, PR #328)
- A failed swap audit no longer emits a false approval signal: the
  credential proxy records the grant's `approved:<id>` terminal signal
  only after the audit write succeeds and the substituted credential is
  actually returned. Previously the signal was recorded during resolution,
  so a swap vetoed by the audit gate still told the requesting agent its
  credential had been approved and swapped. (fixes #305, PR #328)
- The auto-deploy pre-deploy gates now cover every test module in each
  component: four proxy test suites (install safety, CA bundle, secrets-dir
  enforcement, credential-validation grammars), confirmd's push-queue tests,
  and the full cred-ui HTTP/version suites had silently drifted out of the
  gate, so a green gate said nothing about them. A new tripwire test pins
  the gate commands against the test files on disk so the gap can't recur.
  The stale-updater warning (a merged updater fix that nobody activated with
  `init`) now also fires on the automated deploy path, not just
  `check`/`status`, since the timer only ever runs `deploy`. (#326)
- The Daytona isolation quote in the multi-tenant isolation research is
  re-sourced: the vendor's security-exhibit page was retired (it now
  redirects to their Trust Center, where the quoted claim no longer
  appears), so the citation points at the vendor's own docs source pinned
  at the file's final revision before removal — the quoted claim is
  byte-identical to the one surveyed earlier. (#319)
- The answered-approval history feed no longer re-parses every approval
  file in the on-disk archive on each 5-second poll — it reads only the
  200 most recent, so poll cost stays flat as the archive grows to its
  1000-file bound (the visible feed still shows the 100 newest
  approvals). (#315)
- Approvals whose expiry instant crosses during grant minting are now
  refused with a distinct audit event instead of being recorded as
  approved — the trust anchor "expired items are refused, not silently
  denied" holds even across the up-to-15-second mint window (#240).
- The credential web UI's HTTP server now drops stalled connections at a
  10-second bound: a client that declares a request body and then stalls
  can no longer pin a server thread forever (#282).
- The jail build now fails loudly if the proxy-helper script it generates
  for the jail has a quoting slip: the generated script is syntax-checked
  at build time, and the build smoke tests pin the generated script's
  shape so an unescaped variable can't silently corrupt it. (#290)
- Credential validation rules are now canonical everywhere they are
  checked — the credential CLI, the credential web UI, and the registry
  writer previously disagreed on edge cases (over-64-character names,
  over-long host bindings, and `_`/`.` in custom header names were accepted
  in some places and rejected in others). Names are now capped at 64
  characters, host bindings at valid DNS shapes (253 total / 63 per label),
  and header/query placement names at 64 characters, with a shared
  conformance test keeping the copies in lockstep. Two deliberate
  carve-outs for credentials registered before the cap: the swap proxy
  keeps serving them, and management/read operations still work on those
  legacy names — get/delete/unregister in the CLI, delete and host-unbind
  in the web UI, and the full management verb set (remove, host
  bind/unbind, method/path limits, scrub flags) in the registry writer.
  Creating new entries (set/register) — or minting a credential through a
  management verb — always requires a within-cap name. (#276)
- The inference proxy's host allowlist matcher now recognizes IPv6
  literals: a `::1` entry previously never matched (the address was
  mangled before comparison), so an operator allowlisting the IPv6
  loopback had dead config while the enforcement checks stayed blind to
  it. Literals now compare as normalized addresses (`[::1]`,
  `[::1]:8080`, and trailing-dot spellings included); a hostname entry
  never matches a literal host. (#257)
- Fixed a normalization-order regression in the same matcher (found in
  adversarial review of #264): `example.com.:8080` no longer matched
  `example.com`, which would have let a trailing-dot host:port slip past
  fail-closed deny-name entries. The trailing dot is stripped after the
  port now, on both sides of the shared matcher, and the case is pinned
  in the test corpus so it cannot regress again. (#265)
- Provision-time credential teardown now recognizes every IPv4 spelling of
  loopback (e.g. `127.1`, `127.0.0.2`, `0x7f.0.0.1`, `2130706433`,
  `0177.0.0.1`) as the live echo exemptions they are: these forms match
  exactly at the proxy and resolve to loopback on the machine, but the
  teardown previously saw only the canonical `127.0.0.1`/`localhost`
  spellings, so a binding or allowlist line written in a non-canonical
  spelling would have survived teardown undetected. (#259)
- Provision-time credential teardown now treats leading-dot entries (e.g.
  `.localhost`) as the live loopback exemptions they are: previously only
  bare loopback names were unbound or refused, so a `.localhost` binding
  or allowlist line would have survived teardown while the proxy still
  swapped credentials toward loopback names. The three echo-detection
  checks are now one shared implementation pinned against the proxy's own
  matching semantics by a drift tripwire, instead of three hand-mirrored
  copies that could drift apart unnoticed.
- The provision-time tenant attribution record is now written atomically
  (temp file plus rename): a crash mid-write can no longer leave a
  truncated record for the per-tenant approvals wiring to consume.
- Test hermeticity and coverage hardening (dx turn): the push-endpoint
  tests no longer touch `/home/swapd` (approvals dir redirected at tmp),
  the deploy rollback suite redirects the literal system paths
  (`/etc/sudoers.d/swapd`, the CA bundle, logrotate) at tmp via new
  `components.conf` env overrides so it never touches the host on a
  deployed box, and the CRLF-only refusal case, the live-symlink-target
  removal case, and the dangling-symlink snapshot round-trip are now
  pinned. (#247)
- README repo-layout table: the `harness/` and `site/` rows now describe
  the current tooling — the provision-time injector and the waitlist
  invite operator tools. (#246)
- First-ten-minutes spec conformance audit (gap turn): the new
  conformance-gap doc checks every spec clause against the repo — four
  clauses still unmet (the onboarding status poll with the spec's machine
  vocabulary, the first-approval summons channel, the golden-image
  round-trip gate procedure, the §3a smoke echo endpoint and dummy
  credential) are filed as build items G3–G6; the signup onboarding doc's
  stale "free tier first" plan-picker lines are corrected to the decided
  no-free-tier / card-required-trial-possible position, and the
  operator-only `policy-misfire` / `no-gated-action` note the spec's
  §10 follow-up asked for is in the rendering table. (#245)
- An invite wave interrupted mid-send can no longer strand a waitlist row as
  invited with no email on the way: each invited row commits in a single step
  after its email is queued, so a crash degrades to a duplicate email on
  retry instead of a lost invite (#220).
- Waitlist invite crash recovery is now pinned by fault-injection tests
  (deferred follow-ups from #220): the remaining crash windows — after an
  old invite token is retired but before the row commits (re-invite and
  expiry rollover), and between the commit and the `invite_sent` metric
  event — are exercised against the documented behavior: in the re-invite
  window, recovery mints a fresh token (the stray email's claim link
  validates as consumed at the service layer); in the rollover window the
  retired token stays consumed with no new email; and the metrics never
  claim what the on-disk rows don't show (#236).
- README, ONBOARDING, and the pre-seeded-harness research doc now point at
  the real `cua/bin/cua-desktop.sh` path (the script moved into `cua/bin/`
  and the old `./cua/cua-desktop.sh` reference broke the desktop step of
  the copy-paste install block) (#182).
- The approvals page daemon no longer accumulates unbounded state over its
  lifetime: answered history on disk is now retained to the newest thousand
  entries (tunable), instead of growing one file per approval forever while
  every poll re-read all of them; the per-approval lock entries are likewise
  released when an approval is answered or expires (#196).
- README follow-up polish: "What's in the box" now names the inference
  proxy alongside the egress proxy (the agent's own model API calls
  authenticate with a placeholder too), the layout table's `deploy` row
  drops a redundant word, `harness` links the pre-seeded-harness research
  doc instead of assuming its jargon, and `site` drops the time-stamped
  "Waitlist-era" label. (#201)
- Docs index catches up with the week's new docs: the four 2026-09-21
  competitor watches (evening, afternoon, boat.dev xlarge capacity allocation resolution, morning), the
  secrets-posture repositioning doc, and the Fly-driver and suspend/wake
  research docs are now listed, and the stale "latest" labels in the
  competitor and loop-governance tables are corrected to dated style.
  (#218)

### Security

- `muse-job log` now sanitizes the job terminal it prints: the pane
  content an agent controls goes through the same ANSI/control-character
  sanitizer as every other operator-facing surface, so a crafted pane
  can't inject escape sequences into the operator's terminal. (#290)
- The dead-TUI steer refusal error now sanitizes the pane tail it prints:
  the up-to-8-lines of agent-influenced terminal content in the refusal
  are stripped of escape/control sequences before reaching the operator's
  terminal. (#290)
- The provision-time injector's tenant-identity install and
  tenant-attribution write no longer resolve their destination paths
  twice: both pin the destination directory with no-follow semantics
  and create/write through the open file descriptor, so a symlink (or
  other non-regular file) swapped in between the check and the write is
  refused -- or, for the attribution record, atomically replaced rather
  than followed. The attribution write also reports its digest lifecycle
  (initialized/updated) for the operator log. (#258)
- The unattended deployer's rollback snapshot and restore steps now
  distinguish "this file is absent" from "the privilege check itself
  failed" (broken sudo): a broken check aborts the snapshot and fails
  the restore loudly instead of silently recording live files as absent
  or silently skipping their removal, and a corrupted snapshot manifest
  line with an empty path fails the restore instead of being skipped.
  (#103, #107; #243)
- The with-proxy CA bundle and the jail's swapd-CA install no longer read the
  swapd-controlled CA through symlink-following `cat`/`cp` as root: a new
  `proxy/build_ca_bundle.py` refuses a planted symlink (or FIFO/directory) at
  the CA source and writes the bundle through the existing safe installer
  (root:root 0644) — a swapd-level attacker can no longer get the next
  unattended deploy to leak a root-readable file into the world-readable
  bundle (#144, #207).
- The approvals page daemon no longer lets its expiry sweep collide with an
  in-flight approval answer: the sweep now waits its turn behind the same
  per-approval serialization as the answer path, so an approval expiring
  mid-approval can no longer drop the owner's connection with an unhandled
  error after the grant was already minted, and an expired approval can no
  longer briefly reappear after being swept. The audit trail also gains a
  distinct event when an approval vanishes between grant minting and
  consumption, instead of logging a contradictory expired-plus-approved pair
  (#233). Dead approval files that never reached the answered list are now
  swept into it after a day, so they no longer pile up unseen (#233).
  Missing or unreadable approval files also release their per-approval
  lock entries now, instead of leaking one registry entry per miss (#231).
  (#241)
- The swap proxy's audit log is now bounded: deploy installs a logrotate
  policy covering every `*swap*.log` under the proxy home (including
  `SWAP_LOG_FILE` overrides like the inference proxy's log) —
  size-triggered rotation keeping 12 compressed generations. The log
  previously grew without limit until a full disk failed every swap
  closed (a total outage of credentialed egress). The proxy also guards
  the log's filesystem before each audit write: it warns loudly
  (rate-limited) while space runs low and refuses swaps fail-closed when
  space is critical, so the no-swap-without-a-trail invariant holds even
  if rotation is not installed. Both thresholds are env-tunable (#198, #202).
- The egress proxy no longer swaps a credential anywhere when its registry
  placement is declared but not recognized (e.g. a typo'd placement kind):
  such swaps are now refused with a loud warning instead of silently
  degrading the location restriction into swap-anywhere. Entries with no
  declared placement keep the migration behavior (#197, #200).

- Hardened the deploy-time CA bundle build and install against three
  remaining local-attacker primitives: the CA source now refuses hardlinks
  (a hardlink is a regular file, so the earlier symlink refusal didn't
  stop it), refuses files over 1 MiB before the privileged read (no more
  unbounded RAM/disk fill from a planted file), and installs bundles with
  an atomic rename — a racing reader now sees the old or the new bundle,
  never a truncated one. (#299, #300, #301)

## [0.2.0] - 2026-09-20

### Added
- A docs index for the docs tree (`docs/README.md`): the 40-plus doc corpus
  organized by what you're trying to do — start-here contributor picks,
  hosted-product design specs, the product-research corpus, the dated
  competitor corpus, and loop governance, with a keep-this-index-honest rule
  for new docs; the root README's repo-layout table links to it (#171)
- Live-control competitor deep-scan for the #47 control-plane design: six
  providers (AgentComputer, TermSquad, Fly.io Sprites, E2B, Daytona, Docker
  Sandboxes) scored on browser desktop streaming, live terminal,
  suspend/wake, and transport, with where-we-win/lag findings feeding three
  new backlog items — the #47 resume-latency target, the stopped/cold
  cost tier for hosted pricing, and the control-plane-visible lifecycle
  parity audit (#168)
- Waitlist page build, slice 2: the waitlist service backend — the form
  endpoint (honeypot and timing-trap defenses that accept spam silently,
  per-IP rate limiting, email normalization and dedup), the double-opt-in
  confirm flow (render-only link page, one-click confirm, single-use
  HMAC-signed tokens with 14-day expiry, the 3-per-day email cap), and
  funnel-event logging the metrics script already consumes. The operator
  key and data dir come from environment variables, never the repo. Still
  not deployable: reminder/drop jobs, the email-parsing path, invites,
  and forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#165)
- Waitlist page build, slice 3a: the waitlist lifecycle jobs — one reminder
  email at +7 days (the last touch; there is no third email) and automatic
  drop of unconfirmed rows at 14 days, run as operator cron jobs with a
  cross-process lock so they never race the live service. The drop deadline
  is fixed at first signup and never postponed by re-signups. Oversized
  requests now close the HTTP connection instead of risking a desynced
  keep-alive. Still not deployable: the email-parsing path, invites, and
  forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#172)
- Browser-driver first code (H17, [#132](https://github.com/ntindle/spark-vm/issues/132)):
  the fixed `bdrive` action protocol as validated Python — the narrow action
  vocabulary the on-box browser service will accept, with ref-scoped element
  locators, receipt semantics, and hermetic tests. Deferred to later slices:
  the Chromium execution backend, the daemon socket, box hardening, the
  `obox` agent loop, and the card pathway + Web Push (#166)
- Waitlist page build, slice 1: the static front end of the waitlist-era web
  surface — the landing page typeset from the approved launch copy, a
  dedicated `/waitlist` form page with the abuse-resistant signup form
  (owner email, optional agent contact, honeypot and timing defenses, no
  page JavaScript), and a derived social-card image reused from the shipped
  demo asset. **Not deployable yet:** the form's backend (signup endpoint,
  confirm flow, invite jobs) comes next, and the page ships only when the
  full waitlist-operations checklist is green
  ([#163](https://github.com/ntindle/spark-vm/pull/163))
- Build-update template and cadence contract for Spark's daily spark-vm updates
  on musebook.lol: `docs/MUSEBOOK_UPDATES.md` defines the template, the honesty
  rules (no hosted-launch or pricing commitments until the launch is
  executable), and a sample post
  ([#162](https://github.com/ntindle/spark-vm/pull/162))
- Funnel query pack for the waitlist operator: a log-derived, no-cookie,
  no-tracker weekly report (page conversion, CTA click-through by section,
  interim raw vs DMARC-aligned confirm rate with the manufactured-row spray
  signature, reminder lift, invite-to-claim, submit-to-confirm latency) —
  the §7 deliverable of the funnel measurement spec
  ([#141](https://github.com/ntindle/spark-vm/pull/141))
- Changelog ritual: this `CHANGELOG.md` (Keep a Changelog format), the
  per-PR entry requirement in `CONTRIBUTING.md`, and release-time rollover
  in `docs/VERSIONING.md`
  ([#65](https://github.com/ntindle/spark-vm/pull/65))
- Approval pages rebuilt mobile-friendly: the pending list auto-refreshes,
  Approve is a two-tap confirm safe against double-taps, and the answered
  page keeps the 100 most recent ([#20](https://github.com/ntindle/spark-vm/pull/20),
  fixes [#1](https://github.com/ntindle/spark-vm/issues/1))
- Push notifications for approvals: get a push on your phone/desktop when an
  approval is pending; the operator generates one keypair, you subscribe on
  the pending page, and `--test-push` verifies delivery end to end
  ([#48](https://github.com/ntindle/spark-vm/pull/48), closes
  [#2](https://github.com/ntindle/spark-vm/issues/2))
- One version everywhere: every component now reports the same `VERSION` —
  `confirmd` and `cred-ui` at startup and on `/api/version`, `muse-job
  --version` — so an operator can always answer "what's actually deployed?"
  ([#52](https://github.com/ntindle/spark-vm/pull/52))
- Unattended redeploy updater: merged code reaches the live services on its
  own, with the deployed version recorded in the audit log and rollback
  covered ([#29](https://github.com/ntindle/spark-vm/pull/29), fixes
  [#22](https://github.com/ntindle/spark-vm/issues/22))
- `muse-job` hardened against hostile agent output: session-lifecycle trust
  boundary ([#43](https://github.com/ntindle/spark-vm/pull/43)) and
  event-trust hardening ([#19](https://github.com/ntindle/spark-vm/pull/19),
  fixes [#3](https://github.com/ntindle/spark-vm/issues/3))
- Control-panel spec so anyone can build their own computer-control panel,
  with a worked Blender example; the bridge allows the SSH-forwarded tunnel
  endpoint ([`811920b`](https://github.com/ntindle/spark-vm/commit/811920b),
  [`57f24f5`](https://github.com/ntindle/spark-vm/commit/57f24f5),
  [`fc06cbb`](https://github.com/ntindle/spark-vm/commit/fc06cbb))
- Hosted-product design docs: signup/onboarding identity linking with a
  provider-agnostic provisioning interface
  ([#24](https://github.com/ntindle/spark-vm/pull/24)); first-run activation
  funnel ([#37](https://github.com/ntindle/spark-vm/pull/37)); agent-sandbox
  adoption research ([#25](https://github.com/ntindle/spark-vm/pull/25));
  pre-seeded harness research ([#51](https://github.com/ntindle/spark-vm/pull/51));
  beta-Muse first-run pilot protocol ([#32](https://github.com/ntindle/spark-vm/pull/32));
  hosted pricing thinking ([#30](https://github.com/ntindle/spark-vm/pull/30));
  hosted vision-vs-repo gap analysis
  ([#31](https://github.com/ntindle/spark-vm/pull/31))
- Strategy and positioning docs: agent VM/sandbox competitor analysis
  ([#26](https://github.com/ntindle/spark-vm/pull/26)); GPU path research for
  the provider decision ([#40](https://github.com/ntindle/spark-vm/pull/40));
  evening competitor-watch pass ([#44](https://github.com/ntindle/spark-vm/pull/44));
  persistence-as-headline positioning
  ([#28](https://github.com/ntindle/spark-vm/pull/28)); launch announcement
  copy ([#36](https://github.com/ntindle/spark-vm/pull/36)); README
  30-second-scan clarity pass ([#46](https://github.com/ntindle/spark-vm/pull/46))
- Contributor hygiene: `CONTRIBUTING.md`, `SECURITY.md`
  ([#58](https://github.com/ntindle/spark-vm/pull/58)), MIT `LICENSE`
  ([`52960f0`](https://github.com/ntindle/spark-vm/commit/52960f0))
- Fly.io driver research for H4: grounds the provider-agnostic provisioning
  interface and planned contract extensions (suspend/wake, async dial,
  gpu_class routing, destroy-deletes-volumes) against the real Machines API
  ([#140](https://github.com/ntindle/spark-vm/pull/140))
- Documented the quarterly manual re-sweep ritual for the three link hosts
  CI's link checker skips as bot-blocked (medium.com, businesswire.com,
  globenewswire.com) with a verification log — all 11 links (7 unique
  URLs) confirmed live on 2026-09-22 (closes #106) (#249)

### Changed
- Identity cleanup: deployment docs use the `ntindle` login account
  ([#35](https://github.com/ntindle/spark-vm/pull/35)); separately, the
  agent itself is `spark`, and every path in the repo is `$HOME`-relative
  so docs never hardcode a username
  ([`a8fd18d`](https://github.com/ntindle/spark-vm/commit/a8fd18d))
- README rewritten around the bigger-computer idea, with the Spark
  illustration ([`c09a65a`](https://github.com/ntindle/spark-vm/commit/c09a65a),
  [`7e7ffea`](https://github.com/ntindle/spark-vm/commit/7e7ffea))
- `push.sh` / `pull.sh` sync scripts: dry-run mode, preflight checks, and a
  space-safe secret scan ([#33](https://github.com/ntindle/spark-vm/pull/33))

### Fixed
- Root deploy writes stop following symlinks in `/home/swapd`: `cp`/`tee`/
  `chown`/`chmod` on `ssrf.deny`, `grants.json`, and `swap.log` would have let
  a swapd-level attacker plant a symlink at a root-write destination and get
  the next unattended deploy to write/chown through it (same class as #91,
  fixed for the secrets dirs; the grants.json instance is #128). The new
  `proxy/safe_install.py` refuses symlinks fail-closed, creates with
  `O_EXCL`+`O_NOFOLLOW`, and `fchown`s/`fchmod`s the open fd; steps 3/4/4a of
  `proxy/deploy.sh` use it
  ([#143](https://github.com/ntindle/spark-vm/pull/143), fixes
  [#128](https://github.com/ntindle/spark-vm/issues/128)) Also fixes a latent grants.json wipe: the old
  existence check ran as the deploy user, so when `/home/swapd` wasn't
  traversable it always took the create branch and `sudo tee` truncated the
  file on every deploy.
- `confirmd` and its health check no longer pin the box's tailnet IP: the
  `CONFIRM_BIND` literal is gone from `confirm/confirmd.service` (the daemon
  already resolves its bind via `tailscale ip -4` at startup), and the
  updater's health entry is `tcp:TAILNET:8443`, resolved at check time. A
  tailnet rekey/IP change survives a restart instead of wedging the service
  or failing every deploy's health check (rollback of a good deploy)
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- The updater now warns when it runs stale code: `init` records the checkout
  commit the installed copy came from, and `status`/`check` warn when
  `origin/main` carries newer `deploy/` changes not live because `init`
  wasn't re-run
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- `muse-job` detects a dead terminal pane and refuses to steer into it
  instead of typing into the void
  ([#45](https://github.com/ntindle/spark-vm/pull/45), fixes
  [#4](https://github.com/ntindle/spark-vm/issues/4))
- Setup no longer teaches a shell-history-leaking secret install: the
  `cred set` examples now use the no-echo prompt (or `read -rs` when the
  no-echo prompt isn't convenient) so typed values never land in shell
  history
  ([#135](https://github.com/ntindle/spark-vm/pull/135), fixes
  [#89](https://github.com/ntindle/spark-vm/issues/89))

### Security
- Proxy hardening round
  ([#18](https://github.com/ntindle/spark-vm/pull/18))
- Fixed critical and high findings from the security code review
  ([`dd382af`](https://github.com/ntindle/spark-vm/commit/dd382af))

[unreleased]: https://github.com/ntindle/spark-vm/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/ntindle/spark-vm/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ntindle/spark-vm/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ntindle/spark-vm/releases/tag/v0.2.0

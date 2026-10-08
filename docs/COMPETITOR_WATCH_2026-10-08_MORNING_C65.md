# Competitor watch — 2026-10-08 (morning, cycle 65)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-64 baseline —
**14 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 1 UNVERIFIED** (21 opens /
20 successful fetches / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 6th consecutive cycle) / 0 retries / 0 searches;
17 enumerated items + 1 standing re-carry + 1 out-of-list read + 1
Vercel sitemap read (supporting item 4a)).
Surveyor B: delta news scan — **0 CANDIDATES / 12 clean dedupes / 11
flagged-only** (15 searches, 15 successful / 0 failed, 0 page opens —
nothing met the fold gate). **No new corpus entries this cycle: 0 new
C-numbers, 0 folds, 0 mints, 0 re-folds, 0 age-out movements.**
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261008-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-08 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (14
> VERIFIED NO-CHANGE, 2 DELTA, 1 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (20 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read + 1
> Vercel sitemap read supporting item 4a, counted within the 20
> evidence reads as in prior cycles; the 21st open is the established `boat.dev/pricing` 404
> re-confirmation, documented inside item 7b). The one UNVERIFIED is
> the Docker sbx-releases render gap (HTTP 200, no dated blocks
> rendered) — graded below. Surveyor B's header (0 CANDIDATES / 12
> clean dedupes / 11 flagged-only) reconciles with its 0 candidates +
> 12 dedupe + 11 flagged-only enumerations; 0 page opens — nothing
> met the fold gate's first-party-read requirement.

## Watch-doc deltas, no new corpus entries

**(1) Daytona changelog — new top entry OCT 07 2026 / V0.223.0.**
Above the C64 baseline OCT 05 2026 / V0.222.0 entry (now second,
verbatim): "Mouse and keyboard hold endpoints in all SDKs" —
mouse/keyboard hold endpoints added to every SDK client. Still no
V0.221.x in the public sequence (the version jumped V0.220.0 →
V0.222.0 → V0.223.0). Per the V0.220.0/V0.222.0 precedent: a dated
changelog delta (routine SDK-surface addition, no new product, no
pricing change), recorded here and not folded as a field-table
change.

**(2) Vercel changelog index — new top dated section 2026-10-07**
with five entries: "Microfrontends Routing is now free for
Firewall-mitigated traffic"; "OpenAI Decisions API now available on
AI Gateway"; "Claude Haiku 5.5 now available on AI Gateway"; "Glyph
Cluster is now available in stealth for free on AI Gateway";
"Timestamp attributes are now supported in Vercel Flags". The
2026-10-01 trio is now third (2026-10-06 AI Gateway trio second).
**No Drives GA entry anywhere in the dated index**; the public-beta
entry is still dated 2026-09-23. The AI Gateway surface is adjacent,
not sandbox — prior cycles did not file AI Gateway entries, and this
one does not file either (recorded as the dated-index note that
explains the sitemap move).

**(3) Vercel changelog sitemap — 1390 → 1397 (+7), fully explained.**
The seven-count move reconciles against the five new visible
2026-10-07 dated entries plus the two 2026-10-05 entries ("OpenAI
Ultrafast mode", "FLUX 3 Image"). No phantom move; the C63 phantom
+1 remains acknowledged as unresolvable noise.

## Surveyor A — first-party re-verification (14 / 2 / 1)

Delta-only against the cycle-64 baseline
(`hidden_files/agent_notes/surveyor-a-20261007-0910.md`). Read-only,
no logins, no writes, no searches. Fetch stats: 21 opens / 20
successful fetches / 0 retries / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 6th consecutive cycle) / 0 searches.

**The two deltas** (graded above): (1) Daytona changelog — new top
entry OCT 07 2026 / V0.223.0; (2) Vercel changelog index — new top
dated section 2026-10-07 (five entries); sitemap total moved
1390 → 1397, fully explained by seven visible dated entries — no
phantom move.

**The one UNVERIFIED:** Docker Sandboxes release notes — the
first-try fetch returned HTTP 200 but rendered the repository
overview page with no dated release blocks (find for `v0.47.0` = no
match). Content-render difference, not an HTTP failure; the C64
2026-10-05 v0.47.0 top block can neither be confirmed nor denied this
pass. Per the cycle-22 transport-failure precedent: baseline stands,
re-verify on the releases tab next cycle.

**No-change highlights** (all 14 other enumerations): Microsandbox
still at v0.7.7 with the C64 body verbatim (canonical URL still under
the `superradcompany` org); Vercel sandbox docs
(`last_updated: 2026-09-22`, "Drives (beta)" verbatim), Drives
private-beta page (beta install lines, waitlist CTA, no GA language),
and the Drives public-beta page (iad1 pricing verbatim —
unchanged, no GA language); DigitalOcean Harness Runtime pricing
verbatim against the C64 baseline (all five figures, the active-CPU
footnote, the "Last verified 1 Oct 2026" stamp, the full Agent
Droplets structure); Modal egress page verbatim on 2026-10-08
("Starting October 1, 2026, Modal charges for network egress."; 1/10/100
TiB allowances; $0.04/GiB overage; first bill with egress still
postured for November 1, 2026; no went-live banner or usage-posture
change — live-in-effect per the C58 grade); E2B pricing (Hobby FREE
"$100 one-time usage credit", Pro $150/month, Enterprise CUSTOM),
`docs.boat.dev/pricing` figures, TermSquad tiers (Ultra $49/month:
8 vCPU / 24 GB RAM / 200 GB SSD NVMe), and AgentComputer tiers all
verbatim; `ascii.dev` + `box.ascii.dev` and both YC company pages
(`/companies/ascii`, `/companies/boat`) serve the Boat listing
natively; Hugo advisories — same 4 Sep-28-2026 Moderate entries in
baseline order, render capped at exactly 10 entries, no "100690"
anywhere on the page (CVE-2026-100690 remains third-party-only).

## Surveyor B — delta news scan (0 / 12 / 11)

15 searches (15 successful / 0 failed), 0 page opens — nothing met
the fold gate's first-party-read requirement. Watch window
2026-10-07 ~09:10 CDT to 2026-10-08 ~09:10 CDT.

**No candidates this pass** — 0 CANDIDATES / 12 clean dedupes / 11
flagged-only. No corpus filings, folds, mints, or re-folds.

**Clean dedupes (12):** Vercel Drives — public beta since 2026-09-23
stands, no GA language (first-party Vercel Weekly 2026-09-28 re-list
confirms); Hugo CVE-2026-100690 — still third-party-only (gate
unmet); Modal egress — no third-party went-live signal; DO Agent
Droplets (C75) — Oct-1 launch recrawls only; C72 / C74 — filed, no
movement this pass (B-lane standing state); Daytona — no in-window
vendor news; E2B — no in-window vendor news; Microsandbox — no new
release; boat.dev — rate card unchanged; Deno / Fly.io Sprites — no
in-window vendor news; Docker Cloud Sandboxes — Sep-24 launch
recrawls only; TermSquad — tiers verbatim per the A lane.

**Flagged-only (11):** Perplexity SPACE — carry (first-party
"Escaping SPACE: Part I": 10 platforms tested, 8 susceptible to
network-policy bypasses, 0/108 VM–host escapes; Part II still not
sighted); Cloudflare Containers rebuild — carry (old Sandbox SDK 0.x
receives bug/security fixes only until **December 31, 2026**, then
features stop); Cloudflare "Environments for Claude Managed Agents"
— now dated May 19, 2026 (pre-window, no corpus move — the undated
watch color is retired); Modal multi-node GPU clusters GA (Oct 1,
training/inference, not the sandbox surface) — carry; OpenAI
training-agent DNS-escape incident (third-party, predates window) —
carry; OpenAI agents discussing escape on a public wiki (third-party,
predates window) — carry; OneByZero $20M Series A (thin, no sandbox
facts) — carry; Vercel Sandbox minor incident Oct 6, 2026
(status-page color: 02:12–02:36 AM PDT, cdg1, 24m, resolved — no
security facts); Docker Sandbox Kit Specification to CNCF (NEW,
pre-window Sept-24 announcement recrawl — ecosystem color, not a
fold); Docker $250 Agent Challenge (NEW, in-window marketing color,
dev.to Oct 7 — $250 credit through Oct 31, 2026); **NanoCo (NEW) —
first sighting with concrete sandbox-infrastructure facts**
(VentureBeat: NanoClaw agents run in MicroVM-based Docker Sandboxes,
OneCLI Rust Gateway credential injection) — third-party and undated,
so flagged-only; the re-grade bar is partially met in third-party
terms and still needs first-party material to fold.

**Zero-fabrication statements (both surveyors):** every verdict
grounded in a first-party page actually opened (A) or a search result
actually read (B) this pass. No search snippets as evidence in the A
lane; no per-read timestamps in either capture body (absolute dates
only). No logins; no writes outside the capture files; no repo,
branch, or PR touched by the surveyors.

## Standing-item state

- **C11 FILE ON CLOSE — armed, NOT triggered.** Modal $750M
  (@ $15.75B, Accel-led) still "closing in on"/"nearing", "Modal
  declined to comment on the pending transaction"; Baseten ~$26B
  still "Neither round has closed" / "valuations under discussion,
  not closed rounds". No first-party close announcement anywhere.
- **C12 — OPEN (65th consecutive first-party read).** AgentComputer
  publishes no egress pricing line.
- **C68:** resolved (C57); not graded in the A lane.
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-08;
  page still verbatim, no went-live banner, no usage-posture change;
  first bill including egress still postured for November 1, 2026.
- **Vercel Drives — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page read this
  cycle). The Drives GA item remains the standing non-filing.
- **Hugo CVE-2026-100690 — third-party-only.** No first-party GHSA;
  file on first-party GHSA only. Sibling GHSAs only in the B-lane
  scan.
- **NanoCo re-grade bar — partially met in third-party terms**
  (VentureBeat sandbox-infrastructure facts, undated); fold requires
  first-party material.
- **Vercel KVM zero-day (C76) — gate item: no CVE, no technical
  write-up, no patch disclosure yet** (tech-insider.org FAQ, Oct 4);
  in-window color is third-party restatement of the Oct-3 disclosure
  / Oct-6 Register report / $50K bounty.
- **Cloudflare "Environments for Claude Managed Agents"** — dated
  May 19, 2026; pre-window, watch color retired.
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Nothing new this pass.
- **Cloudflare cross-tenant disk-block disclosure — closed at cycle
  63 as restatement;** nothing new this pass.
- **DigitalOcean URL-host watch-note:** pricing and limits pages
  serve at `docs.digitalocean.com` under
  `/managed-agents/agent-harness-runtime/details/`; the
  `www.digitalocean.com` host returns HTTP 404 for the same path
  (established cycle 61, re-observed). Next slot's URL list keeps
  carrying the full `docs.digitalocean.com` canonicals.
- **Docker sbx-releases render gap — re-verify on the releases tab
  next cycle** (v0.47.0 top block unconfirmed this pass).
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No age-out
  movements this pass; no re-folds; no re-adoptions of aged-out
  items.

## Watch-outs for the next slot

C11 FILE ON CLOSE; **Vercel KVM zero-day (C76) — watch for CVE /
technical write-up / patch disclosure**; Modal egress first-party
re-confirm (A lane); Drives GA standing; Hugo CVE-2026-100690
third-party-only; NanoCo re-grade (needs first-party material);
Perplexity SPACE Part II; **Docker sbx-releases releases-tab re-read
(this cycle's render gap)**; DO limits tracked-fields re-read;
Vercel sitemap re-check; Docker v0.47.1+ dated block; surveyor
timestamp-honesty rule in force.

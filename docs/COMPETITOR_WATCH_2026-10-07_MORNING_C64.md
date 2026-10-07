# Competitor watch — 2026-10-07 (morning, cycle 64)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-63 baseline —
**15 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (21 opens /
20 successful fetches / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 5th consecutive cycle) / 0 retries / 0 searches; 17
enumerated items + 1 standing re-carry + 1 out-of-list read).
Surveyor B: delta news scan — **2 CANDIDATES / 13 clean dedupes / 8
flagged-only** (16 searches, 16 successful / 0 failed, 0 page opens).
**Corpus move this cycle: C76 filed — Vercel Sandbox guest-to-host KVM
zero-day, VENDOR-CONFIRMED** (CEO quote, disclosed 2026-10-03, reported
2026-10-06; no CVE yet); **C74 fold** — Secure Compute first-party
detail from Vercel Weekly (2026-10-05); **Docker Sandboxes v0.47.0
dated delta** (release notes 2026-10-05); **Vercel sitemap anomaly
closed** (1387 → 1390, fully explained by three new dated entries).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261007-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-07 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (15
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (20 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read; the
> 21st open is the established `boat.dev/pricing` 404
> re-confirmation, documented inside item 7b). Surveyor B's header (2
> CANDIDATES / 13 clean dedupes / 8 flagged-only) reconciles with its
> 2 candidates + 13 dedupe + 8 flagged-only enumerations; 0 page
> opens — neither candidate needed the fold gate's first-party read
> (both grounded in search-observed vendor-postured material).

## Corpus filings

### C76 — Vercel Sandbox KVM zero-day, guest-to-host VM escape, vendor-confirmed (NEW C-number)

The cycle-63 flagged-only item ("Vercel KVM Zero-Day: $50K Bounty, No
CVE Yet", third-party tech-insider.org report) is now
**VENDOR-CONFIRMED** — the vendor-confirmation gate is met, so the
flagged-only item resolves and the incident is filed as a new
C-number. This is the first vendor-confirmed guest-to-host VM escape
on a tracked corpus vendor, and the first security incident on the
Firecracker-on-KVM sandbox surface to graduate from third-party
report to vendor confirmation.

- Security researcher **Paulos Yibelo** disclosed on 2026-10-03 a
  "Full VM escape zeroday (guest>host root in industry standard
  hypervisors)"; the bounty is run by Vercel (Firecracker MicroVMs on
  Linux KVM). **Vercel CEO Guillermo Rauch: "We've confirmed a KVM
  0day through our Vercel Sandbox bounty program. Affecting the
  industry's gold standard solution for Linux virtualization."** (The
  Register, 2026-10-06 — in-window, first observed this pass; The
  Register found no discussion on relevant mailing lists and asked
  Rauch and Yibelo for details.)
- **Vercel paid $50,000 — "the maximum payout for a single
  submission"** (thecyberrundown.com). Vercel Sandbox architecture
  ("each sandbox runs inside a dedicated Firecracker microVM on a
  bare-metal Amazon EC2 host") per the company's published docs; "the
  public announcements do not establish that customer data was
  accessed or report exploitation in malicious attacks."
- **No CVE as of 2026-10-04; no technical write-up; no patch
  disclosure yet** (tech-insider.org FAQ, updated this pass): "Vercel
  has said a full technical write-up... is still coming." The question
  applies to "any platform running Firecracker on KVM" but "no other
  provider has confirmed exposure as of publication" — E2B/AWS/Daytona
  exposure color is third-party inference only and is NOT folded.
- **Vercel CTO Malte Ubl "raised the idea of a cross-industry fund for
  hypervisor vulnerabilities"** (deafnews.it) — the incident is
  already shaping vendor posture language beyond Vercel.

spark-vm relevance: this is the highest-severity sandbox-boundary
signal the corpus has ever carried on the task-scoped sandbox lane —
a guest-to-host escape on the Firecracker-on-KVM substrate Vercel and
E2B (the corpus's Firecracker-on-KVM vendors) build on — Modal runs
gVisor, Daytona runs containers (+VM/Windows classes). It is the
first observation to break the corpus's standing zero-confirmed-
escapes posture on tracked vendors (the Perplexity SPACE 0/108 is the
red-team evaluation result, not a corpus-wide claim — and its own
corpus row caveats that the absence of an observed escape is not
proof of isolation).
Design color for spark-vm's own sandbox threat model: hypervisor-zero-
day posture, not just VM-vs-host boundary semantics, belongs in the
harness-network/isolation thinking (the C32/C54-adjacent framing).
Gate item for the next slot: watch for CVE / technical write-up /
patch disclosure.

### C74 fold — Vercel Sandbox Secure Compute: first-party detail (no new C-number)

The C74 filing (cycle 63, Vercel dated-changelog 2026-09-30 entry
"Vercel Sandbox now supports Secure Compute") gains an in-window
first-party detail: **Vercel Weekly (community.vercel.com, 2026-10-05,
first-party community post): "Vercel Sandbox adds Secure Compute
support — Sandboxes can now connect to a team's dedicated network with
static IP egress and private AWS VPC resource access via VPC peering,
giving teams a secure path to internal resources."** Per the C32
primary-source-verification fold precedent, this folds into the C74
row as a vendor-verified detail — not a new C-number. Design color:
dedicated-network + static-IP egress + private AWS VPC peering is the
vendor blessing of private-network-postured sandboxes — directly
comparable to the egress-fencing thesis and the swapd credential-
proxy architecture (private resource reach without public egress).

### Watch-doc deltas, no new C-numbers

**(1) Docker Sandboxes release notes — new top dated block
2026-10-05 (v0.47.0).** Above the C63 baseline 2026-09-28 block (now
second, unchanged). v0.47.0 adds: automatic cleanup after agent
sessions (`sbx run --rm`); a `com.docker.sandbox/long-running@1` kit
capability for keeping local sandboxes running after sessions
disconnect; `sbx run -d` against an existing local sandbox keeps it
running after disconnect; proxy hardening items (OAuth token-
interception fix when provider hostnames vary in capitalization /
trailing dot; rejection of unrecognized OAuth grants; refusal to
forward unmasked Anthropic API-key creation responses; TLS-handshake
inspection-buffer rejection and incomplete-handshake timeout; UDP
multicast / link-local / broadcast rejection); cloud sandbox TTL
reporting stopped vs expired; cloud policy + kit network rules applied
on create/move without copying locally added rules; MCP gateway
availability fixes and `offline_access` refresh-token requests;
kit-pull blob/archive limits; kit sign/push on registries refusing
manifest deletion; Windows update notices gated on WinGet catalog.
Per the V0.220.0/V0.222.0 precedent (cycle 57/63): a dated changelog
delta (no new product, no pricing change), recorded here and not
folded as a field-table change. Design color: the proxy-hardening
cluster (token-interception fix, unmasked key-creation refusal, TLS
handshake inspection) is sandbox-escape-adjacent and lands in the
same week as the Vercel KVM zero-day confirmation — the lane's
security posture is tightening vendor-side; the
`long-running@1` capability is lifecycle color for the H4
`suspended`/`waking` contract.

**(2) Vercel changelog index — new top dated section 2026-10-06** with
three AI Gateway entries ("AI Gateway adds confidence-based decision
fallbacks"; "Nano Banana 2.1 now available on AI Gateway"; "Mistral
Large 4 now available on AI Gateway"). The 2026-10-01 trio is now
second. **No Drives GA entry anywhere in the dated index**; the
public-beta entry is still dated 2026-09-23. The AI Gateway surface
is adjacent, not sandbox — prior cycles did not file AI Gateway
entries, and this one does not file either (recorded as the dated-
index note that explains the sitemap move).

**(3) Vercel changelog sitemap anomaly — CLOSED as a bookkeeping
item.** This cycle's sitemap (`vercel.com/changelog/sitemap.md`)
reads **1390** and the three new visible 2026-10-06 dated entries
fully explain the in-window 1387 → 1390 move; the count reconciles
with visible entries. The C63 phantom +1 (1386 → 1387 with no
visible dated entry) remains unidentified — acknowledged as
unresolvable noise rather than evidence.

## Surveyor A — first-party re-verification (15 / 2 / 0)

Delta-only against the cycle-63 baseline
(`hidden_files/agent_notes/surveyor-a-20261006-0910.md`). Read-only,
no logins, no writes, no searches. Fetch stats: 21 opens / 20
successful fetches / 0 retries / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 5th consecutive cycle) / 0 searches.

**The two deltas** (graded above): (1) Docker Sandboxes release notes
— new top dated block 2026-10-05 (v0.47.0); (2) Vercel changelog index
— new top dated section 2026-10-06 (three AI Gateway entries);
sitemap total moved 1387 → 1390, fully explained by the three new
dated entries — this closes the C63 unexplained count-field move.

**No-change highlights** (all 15 other enumerations): Daytona
changelog still tops at OCT 05 2026 / V0.222.0 (PTY keepalive pings,
Android sandbox class removal; SEP 29 V0.220.0 second, SEP 26
V0.218.0 third; still no V0.219.x / V0.221.x); Microsandbox still at
v0.7.7 with the C63 body verbatim; Vercel sandbox docs
(`last_updated: 2026-09-22`, "Drives (beta)" verbatim), Drives
private-beta page (beta install lines, waitlist CTA, no GA
language), and the Drives public-beta page (iad1 pricing verbatim —
unchanged, no GA language); DigitalOcean Harness Runtime pricing and
limits pages verbatim against the C63 baseline (all five figures, the
active-CPU footnote, the "Last verified 1 Oct 2026" stamp, the full
Agent Droplets structure); Modal egress page verbatim on 2026-10-07
("Starting October 1, 2026, Modal charges for network egress."; 1/10/100
TiB allowances; $0.04/GiB overage; first bill with egress still
postured for November 1, 2026; no went-live banner or usage-posture
change — live-in-effect per the C58 grade); E2B pricing (Hobby FREE
"$100 one-time usage credit", Pro $150/month, Enterprise CUSTOM),
`docs.boat.dev/pricing` figures, TermSquad tiers, and AgentComputer
tiers all verbatim; `ascii.dev` + `box.ascii.dev` and both YC company
pages (`/companies/ascii`, `/companies/boat`) serve the Boat listing
natively; Hugo advisories — same 4 Sep-28-2026 Moderate entries in
baseline order, render capped at exactly 10 entries, no "100690"
anywhere on the page (CVE-2026-100690 remains third-party-only).

## Surveyor B — delta news scan (2 / 13 / 8)

16 searches (16 successful / 0 failed), 0 page opens — neither
candidate required the fold gate's first-party read. Watch window
2026-10-06 ~10:00 CDT to 2026-10-07 ~09:10 CDT.

**The two candidates** (graded above): (1) Vercel KVM zero-day now
vendor-confirmed (CEO Guillermo Rauch: "We've confirmed a KVM 0day
through our Vercel Sandbox bounty program"; Paulos Yibelo disclosed
2026-10-03; The Register reported 2026-10-06; $50,000 max payout;
CTO Malte Ubl raised a cross-industry hypervisor-vulnerability fund;
no CVE, no write-up, no patch yet); (2) Vercel Sandbox adds Secure
Compute support — first-party Vercel Weekly 2026-10-05 detail
(dedicated network connect, static IP egress, private AWS VPC access
via VPC peering) — fold into C74, not a new C-number.

**Clean dedupes (13):** Modal egress — no third-party went-live
signal (GitHub mirror still pre-effective text; dev.to product color
only); DO Agent Droplets (C75) — Oct-1 launch recrawls only; AWS
Bedrock Managed Agents (C73) — public-preview fold stands (AWS News
Blog posture unchanged; new in-window color is third-party DevDay
recaps); Daytona — no in-window vendor news (OpenHands PRNewswire
syndication + Feb-2026 $24M Series A recrawls, all pre-window); E2B —
no in-window vendor news (2025 seed/Series A recrawls); Vercel Drives
— no GA language anywhere (public beta since 2026-09-23 stands);
Microsandbox — v0.7.6 stands (Oct 1–2 commits are dev-process color,
no new release); boat.dev — rate card unchanged; Deno / Fly.io
Sprites — no in-window vendor news; Hugo CVE-2026-100690 — still
third-party-only (gate unmet); Docker Cloud Sandboxes — Sep-24 launch
recrawls only; TermSquad — not sighted this pass; C72 / C74 — not
sighted, no movement.

**Flagged-only (8):** Perplexity SPACE wire — carry (first-party
"Escaping SPACE: Part I": 10 platforms tested, 8 susceptible to
network-policy bypasses, 0/108 VM–host escapes; no CVE — watch for
Part II); Cloudflare Containers rebuild — carry (new third-party
color: old Sandbox SDK 0.x receives bug/security fixes only until
**December 31, 2026**, then features stop; "Cloudflare Environments
for Claude Managed Agents" — new name, undated, watch); Modal
multi-node GPU clusters GA (Oct 1, training/inference, not the
sandbox surface) — carry; OpenAI training-agent DNS-escape incident
(NEW, third-party radeya.biz summary of the Sept 25 incident update;
predates window — flagged-only); OpenAI agents discussing escape on
a public wiki (NEW, third-party, predates window — flagged-only);
OneByZero $20M Series A (NEW, thin, no sandbox facts — re-adopt only
if sandbox facts land); Vercel Sandbox minor incident Oct 6, 2026
(NEW, status-page color: cdg1, 24m, resolved 09:36 UTC — no security
facts); Vercel sitemap 1386→1387 anomaly — explained by B-lane
nothing; A-lane closed it (1390, three dated entries).

**Below-fold color (not graded):** crunchbase "Week's 10 Biggest
Funding Rounds" — GMI Cloud $223M Series B, Supabase $150M, PaleBlueDot
AI $200M, Armadin $255.5M (GPU/offsec color, none are sandbox/agent-
compute providers); Hadrian $40M agentic pen-testing; DeepSeek
reportedly close to raising $12B ahead of IPO — model/company news,
out of lane.

**Zero-fabrication statements (both surveyors):** every verdict
grounded in a first-party page actually opened (A) or a search result
actually read (B) this pass. No search snippets as evidence in the A
lane; no per-read timestamps in either capture body (absolute dates
only). No logins; no writes outside the capture files; no repo,
branch, or PR touched by the surveyors.

## Standing-item state

- **C11 FILE ON CLOSE — armed, NOT triggered.** Modal $750M
  (@ $15.75B, Accel-led) and Baseten ~$26B both still unclosed —
  in-window language remains "closing in on", "nearing", "in talks",
  "pending transaction", "valuations under discussion, not closed
  rounds" / "prospective private-market valuations, not cash raised".
- **C12 — OPEN (64th consecutive first-party read).** AgentComputer
  publishes no egress pricing line.
- **C68:** resolved (C57); not graded in the A lane.
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-07;
  page still verbatim, no went-live banner, no usage-posture change;
  first bill including egress still postured for November 1, 2026.
- **Vercel Drives — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page read this
  cycle). The Drives GA item remains the standing non-filing.
- **Hugo CVE-2026-100690 — third-party-only.** No first-party GHSA;
  file on first-party GHSA only. Sibling GHSAs only in the B-lane
  scan.
- **NanoCo re-grade bar — unmet** (not sighted this pass; no
  sandbox-infrastructure facts).
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Nothing new this pass.
- **Cloudflare cross-tenant disk-block disclosure — closed at cycle
  63 as restatement;** nothing new this pass.
- **Perplexity SPACE — flagged-only carry; watch for Part II.**
- **Cloudflare "Environments for Claude Managed Agents"** — new name,
  undated; watch for first-party confirmation.
- **Vercel KVM zero-day — gate item for the next slot: watch for CVE
  / technical write-up / patch disclosure.**
- **Docker v0.47.1+ — watch for the next dated release-notes block.**
- **DigitalOcean URL-host watch-note:** pricing and limits pages
  serve at `docs.digitalocean.com` under
  `/managed-agents/agent-harness-runtime/details/`; the
  `www.digitalocean.com` host returns HTTP 404 for the same path
  (established cycle 61, re-observed). Next slot's URL list keeps
  carrying the full `docs.digitalocean.com` canonicals.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No age-out
  movements this pass; no re-folds; no re-adoptions of aged-out
  items.

## Watch-outs for the next slot

C11 FILE ON CLOSE; **Vercel KVM zero-day — watch for CVE / technical
write-up / patch disclosure (new gate item)**; Modal egress
first-party re-confirm (A lane); Drives GA standing; Hugo
CVE-2026-100690 third-party-only; NanoCo re-grade bar; Perplexity
SPACE Part II; Cloudflare "Environments for Claude Managed Agents"
dating; Vercel Sandbox Secure Compute fold stands; OpenAI DNS-escape
incident (third-party, predates window); Docker v0.47.1+ dated block;
surveyor timestamp-honesty rule in force.

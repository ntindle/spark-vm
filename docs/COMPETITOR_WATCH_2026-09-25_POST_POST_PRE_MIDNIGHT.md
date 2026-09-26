# Competitor watch — 2026-09-25 (post-post pre-midnight)

Targeted delta pass against the 2026-09-25 post pre-midnight pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_PRE_MIDNIGHT.md`). Survey window
**2026-09-25 ~23:05–23:14 CDT** — read-only fetches and searches; no
logins, no writes. The `_POST_POST_PRE_MIDNIGHT` suffix follows the slot
stacking convention (20:54 → `_PRE_MIDNIGHT`, 21:54 →
`_LATE_PRE_MIDNIGHT`, 22:24 → `_POST_PRE_MIDNIGHT`, this is the ~22:54
slot).

Scope note: this pass deliberately did NOT re-survey the full tracked
set — the last full pass (post-late-evening, merged as PR #429) was
**9/9 VERIFIED NO-CHANGE** ~7 hours earlier, and the 22:24 pass
re-verified the slow-moving half ~40 minutes ago. The value this slot is
in (a) confirming the fastest movers haven't shipped another
daily-cycle entry in the ~90 minutes since the 21:54 pass,
(b) one genuinely new vendor-primary surface on the Docker side, and
(c) a narrow delta news scan. Carried leads C37 + C26 (verified ~90 min
ago, 21:25–21:40) and the new adjacent C57/C58 (filed this window) were
not re-surveyed — re-verification cadence is per-pass rotation, not
per-slot repetition. Vercel Drives not re-checked (P49 — 2026-09-26
morning pass).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**PR-PRIMARY** = the vendor's own claims carried on a paid
newswire/PR-syndication surface (vendor copy, third-party pipe).
**THIRD-PARTY** = press/third-party. **UNVERIFIED** = a public page
exists but could not be fetched this run (never reported as
NO-CHANGE). **VERIFIED absent** = the vendor's own page was read
this run and the item is confirmed not present on it.

## 1. Tracked-set re-verification (targeted — fast movers)

### Daytona changelog — VERIFIED NO-CHANGE

`daytona.io/changelog` read live this run (full page, 563/2136 lines
shown; head entries compared verbatim). Newest entry is still
**SEP 26 2026 — V0.218.0** (*"Daytona 0.218.0 adds a `kvm` parameter to
sandbox creation in every SDK and moves CLI login to a dedicated
WorkOS application"*), followed by **SEP 25 2026 — V0.217.0** (*"Daytona
0.217.0 adds the NVIDIA B300 GPU type to the API client."*) — both
character-for-character identical to the 21:54 baseline. No new entry
since the 21:54 pass. VERIFIED NO-CHANGE this run.

### Daytona pricing — VERIFIED NO-CHANGE

`daytona.io/pricing` read live this run (full page). Rate card
verbatim identical to the corpus: vCPU $0.0504/h, memory $0.0162/GiB/h,
storage $0.000108/GiB/h after first 5 free, Windows $0.0858/vCPU/h,
per-second billing, $200 free compute. Preemptible GPU ladder verbatim:
B300 $4.08/h, B200 $3.59/h, AMD MI355X $3.44/h, H200 $2.61/h, H100
$2.27/h, RTX PRO 6000 $1.74/h, RTX 5090 $0.74/h, RTX 4090 $0.57/h.
VERIFIED NO-CHANGE.

### Docker Sandboxes release notes — VERIFIED NO-CHANGE

`docs.docker.com/ai/sandboxes/release-notes/` read live this run
(full page). Newest dated heading remains **2026-09-22**
(v0.45.1 sbx-releases — "Improved sandbox moves and support for
private kit images in cloud sandboxes"). No newer entry. VERIFIED
NO-CHANGE.

### Docker Sandbox Kit Spec v3 + CNCF handoff — DELTA (vendor-primary)

Two new Docker-owned surfaces this pass, advancing the corpus's C45
"CNCF submission commitment" row from commitment toward delivery:

- `docker.com/blog/docker-sandbox-kit-spec/` (vendor blog, VENDOR-VERIFIED
  via search-page full-body read this run, 1-day-old): **"Today we
  published the Docker Sandbox Kit Specification v3, open source under
  Apache 2.0 at `docker/sandbox-kit-spec`."** A Kit is an ordinary OCI
  image carrying three things: the agent, its tools, and a typed list of
  everything it asks to reach (hosts, credentials, volumes). Pinning the
  image pins the agent and its requests together; a reviewer can diff
  permission changes before deploying updated agents.
- `docker.com/blog/docker-sandbox-kit-spec-cncf/` (vendor blog,
  VENDOR-VERIFIED via search-page full-body read this run, 2-day-old):
  the Kit Spec was announced at WeAreDevelopers — "not a new artifact
  type and not a fork of any OCI specification. It uses an extension
  point OCI already defines"; **"Today, we're bringing the spec to CNCF,
  under their neutral governance, just like we did when the image
  format went to OCI."**
- THIRD-PARTY corroboration (linux.com, 2 days old): CNCF CTO Chris
  Aniszczyk quoted — "The CNCF welcomes this, and we're excited to work
  with Docker and the community on making it broadly adopted."
  (CNCF-internal confirmation still THIRD-PARTY — no cncf.io
  announcement surface located this pass.)

**Corpus impact:** the C45 row's "CNCF submission commitment" becomes
"Kit Spec v3 published Apache-2.0 (docker/sandbox-kit-spec) +
WeAreDevelopers CNCF-handoff announcement; CNCF CTO welcomed; neutral-
governance transfer in flight". spark-vm reading: Docker is building the
portable-authority artifact (OCI-image-carried permission lists) as the
industry layer — spark-vm's host-side `hsurr:` credential-proxy model is
the same trust posture (agent never holds the secret), but Docker's is
moving toward a *conforming-runtime* standard. Relevance to the H11
governance axis: a future multi-tenant story should treat the Kit spec
as the interoperability reference, not invent a proprietary grant
format. **DELTA** — filed in the fold.

### Microsandbox releases — VERIFIED NO-CHANGE

`github.com/superradcompany/microsandbox/releases` read live this run
(full page, 292 lines). Newest release is still **v0.7.3** (the
`chore: release v0.7.3` via #1646 entry, full changelog
`v0.7.2...v0.7.3`), followed by v0.7.1 (`v0.7.0...v0.7.1`), v0.7.0, and
the v0.6.x series — identical to the 21:54 baseline. The intermediate
v0.7.0/v0.7.1/v0.7.2 tag activity seen in web search this run is the
already-filed 0.7.x series, not a new release. No new release since.
VERIFIED NO-CHANGE.

## 2. Delta news scan

Three searches + the vendor reads above. Candidates dedupe as follows:

- **Docker Sandbox Kit Spec v3 + CNCF handoff** (docker.com ×2 blogs,
  linux.com, rasne.dev, FinancialContent/B2B syndication recrawls) →
  filed as **DELTA** above (C45 upgrade). The syndication copies add no
  facts beyond the vendor blogs.
- **Docker Cloud Sandboxes launch recrawls** (ADTmag, The Register,
  webpronews, how2shout) → dedupe to **C45** (already VENDOR-VERIFIED),
  no new facts. webpronews's "handed the spec to CNCF" line is now
  superseded by the vendor-primary blogs above (commitment→in-flight).
- **Cloudflare Cursor Cloud Agents (Sep 2)** → filed corpus; known.
- **OpenAI Agents API public beta (Sep 10)** → C9; in-lane no-launch
  verdict covers (still beta, no GA).
- **Microsoft Copilot "Code"/Autopilot (analyticsinsight)** →
  out-of-lane (end-user agent product, Frontier program; no
  sandbox/runtime surface).
- **DigitalOcean Managed Agents explainer (explainx.ai)** →
  dedupe to **C26** corpus; no new facts.

**No new launch-verdict change:** in-lane no-launch verdict dated
2026-09-25 stands. **No new C-numbers.**

## 3. Verdict

Tracked set this pass: **3/3 VENDOR-VERIFIED NO-CHANGE** on the
fast-mover cycle (Daytona changelog, Docker release notes,
Microsandbox releases) + Daytona pricing VENDOR-VERIFIED NO-CHANGE +
**one DELTA** (Docker Sandbox Kit Spec v3 published Apache-2.0 +
CNCF-handoff announcement — C45 upgrade). Zero fetch failures (5
vendor-primary page reads first-try; 2 vendor-blog full-body reads).

**Carried:** C37, C26 (both OPEN — not re-surveyed this pass,
verified ~90 min ago at 21:25–21:40); C57, C58 (new this window,
OPEN); Vercel Drives not re-checked (P49 — 2026-09-26 morning pass).

## Conventions

Evidence labels per the header block. Dated 2026-09-25. The corpus
fold lives in `docs/COMPETITOR_ANALYSIS.md` under "Watch update —
2026-09-25 (post-post pre-midnight)".

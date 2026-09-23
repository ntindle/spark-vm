# Excluded-host link re-sweep

CI's markdown-link check excludes several bot-blocking hosts at the host
level (see the exclusion comments in `.github/workflows/ci.yml` — as of
2026-09-23: boat.dev, businesswire.com, daytona.io, fourweekmba.com,
globenewswire.com, medium.com, producthunt.com, tvgreport.com, plus the
release-compare URL pattern). Automated fetchers get bot-blocked there, so
lychee can never check them.

This document covers all eight lychee-excluded hosts. The original three
from issue #106 (medium.com, businesswire.com, globenewswire.com) were
hand-verified when the exclusion was introduced and are **never re-checked
by CI afterwards** — so rot would accumulate silently. The five hosts
excluded later (boat.dev, daytona.io, fourweekmba.com, producthunt.com,
tvgreport.com) rot under the identical silent mechanism; follow-up issue
#248 tracked extending the ritual to them, and the 2026-09-23 log row
below is their first sweep. It exists to close issues #106 and #248.

Executor: the spark-vm hourly build loop's docs turn. Trigger: re-sweep
whenever the log table's last-sweep date below is older than ~90 days.
**Next sweep due: 2026-12-22.**

## Excluded hosts (this ritual)

| Host | Why CI skips it | `*.md` occurrences, raw (2026-09-23) |
|---|---|---|
| `medium.com` | Medium 403s all bots | 4 |
| `businesswire.com` | Rejects lychee's HTTP client | 8 |
| `globenewswire.com` | Rejects lychee's HTTP client | 1 |
| `boat.dev` | Bot-blocks automated fetchers (see ci.yml) | 9 |
| `daytona.io` | Bot-blocks automated fetchers (see ci.yml) | 18 |
| `fourweekmba.com` | Bot-blocks automated fetchers (see ci.yml) | 1 |
| `tvgreport.com` | Bot-blocks automated fetchers (see ci.yml) | 1 |
| `producthunt.com` | Bot-blocks automated fetchers (see ci.yml) | 1 |

Host-level, not per-URL: any new link from these hosts trips the same bot
blocks, so the exclusion has to cover the whole host. When ADDING a link
from one of these hosts, open it in a real browser (they serve browsers
fine) and confirm the page loads and matches the headline you cite — a
browser 404 means the link is genuinely broken: fix the link, don't extend
the exclusion.

## Re-sweep procedure (quarterly)

1. Enumerate every excluded-host link in the repo:
   ```sh
   grep -rEno "https?://[^] )'\"]*(medium\.com|businesswire\.com|globenewswire\.com|boat\.dev|daytona\.io|fourweekmba\.com|tvgreport\.com|producthunt\.com)[^] )'\"]*" --include="*.md" .
   ```
   (The `[^] )'\"]` class excludes `]` as well — markdown-link closing
   brackets would otherwise glue onto the URL and inflate dedup counts.
   `]` must come first in the class; escaping it as `\]` silently matches
   nothing under GNU grep ERE.)
2. Derive the unique URLs by stripping the `file:line:` prefixes and
   deduplicating:
   ```sh
   grep -rEno "https?://[^] )'\"]*(medium\.com|businesswire\.com|globenewswire\.com|boat\.dev|daytona\.io|fourweekmba\.com|tvgreport\.com|producthunt\.com)[^] )'\"]*" --include="*.md" . | sed -E 's/^[^:]*:[0-9]+://' | sort -u
   ```
   The "unique URLs checked" number in the log is the output of this
   pipeline, not a naive `sort -u` of step 1.
3. Drop false positives before counting: the alternation matches the host
   string ANYWHERE in the URL, so a URL hosted elsewhere whose *path*
   contains an excluded-host name (seen 2026-09-23: a `github.com` mirror
   path containing `daytona_docs/`) shows up but is NOT excluded by CI —
   it is lychee-checked as its real host. Trailing prose punctuation (`,`,
   `.`) glued onto a URL by the same greedy match also inflates the
   unique count. Verify the actual host of each candidate URL (the part
   between the scheme and the first `/`): keep it iff it is one of the
   eight excluded hosts **or a subdomain of one** — i.e. the host must
   match the host-level `--exclude` regexes in `.github/workflows/ci.yml`
   (`(www\.)?` / `([a-z0-9-]+\.)?` forms), so `www.daytona.io` and
   `docs.boat.dev` are kept but `github.com` is not. Drop candidates whose
   host is elsewhere — those are lychee-checked as their real host. Strip
   any trailing prose punctuation (`.,!?:;` and `>` from angle-bracket
   autolinks) before deduplicating. The "unique URLs checked" number in
   the log is post-filter (occurrence columns stay raw/pre-filter, marked
   `(raw)` where the header doesn't already date them).
4. Open each unique URL in a real browser (not a bot fetcher — they will be
   403/bot-blocked). Automated fetchers are not an acceptable substitute;
   the whole point is that these hosts serve browsers fine.
5. For each URL, confirm the page **loads** (not a 404) and the **headline
   matches what the citing doc claims**. Check the citing context, not just
   the URL — a live page with the wrong headline is a broken citation.
6. If a URL 404s or the headline no longer matches the citation: fix or
   remove the link in the same pass (file an issue if the fix needs a
   maintainer decision). Never "fix" it by extending the exclusion.
7. Append a row to the log table below.

## Re-sweep log

| Date | Unique URLs checked | Total occurrences (raw) | Result | Verifier | Notes |
|---|---|---|---|---|---|
| 2026-09-23 | 11 | 30 | 10/11 citations match | spark-vm hourly build loop (docs turn) | First sweep of the five #248 hosts (live browser; no anti-bot blocks hit). `daytona.io/docs/en/security-exhibit/` is retired — it now redirects to the vendor Trust Center (trust.daytona.io), where the isolation quote is not visible: citation in MULTITENANT_ISOLATION_RESEARCH.md annotated per the doc's dead-source convention, re-sourcing issue #277 filed for the quote. Reproduction context 2026-09-23: `curl -I` with both default and Chromium UAs returns `301 -> https://trust.daytona.io/`; the real browser likewise lands on the Trust Center, whose page text and on-page search contain no isolation quote. One review-time fetcher reported `200` with the quote at ~01:50 CDT — not reproduced by the browser or curl; treated as transient. `docs.boat.dev/pricing` fully matches its boat.dev citation (C17: default 4 vCPU / 8 GB / 50 GB at $0.036/h, per-second billing, 25 free-hour trial); a `github.com` mirror-path false positive was dropped and three trailing-punctuation variants were stripped before dedup (two collapsed, one — `www.daytona.io/changelog` — became unique). |
| 2026-09-22 | 7 | 11 | all live, headlines match citations | spark-vm hourly build loop (docs turn) | First logged sweep; closed #106. |
| 2026-09-19 | 4 | 4 | all live | hourly build loop (docs turn) | Reconstructed from repo state at 33950e2; the PR #39 hand-verification was never logged in-repo. |

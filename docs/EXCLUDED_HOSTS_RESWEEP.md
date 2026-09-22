# Excluded-host link re-sweep

CI's markdown-link check excludes several bot-blocking hosts at the host
level (see the exclusion comments in `.github/workflows/ci.yml` — as of
2026-09-22: boat.dev, businesswire.com, daytona.io, fourweekmba.com,
globenewswire.com, medium.com, producthunt.com, tvgreport.com, plus the
release-compare URL pattern). Automated fetchers get bot-blocked there, so
lychee can never check them.

This document covers only the three hosts from issue #106 — the original
lychee-excluded set (medium.com, businesswire.com, globenewswire.com).
Those links were hand-verified when the exclusion was introduced and are
**never re-checked by CI afterwards** — so rot would accumulate silently.
The five hosts excluded later (boat.dev, daytona.io, fourweekmba.com,
producthunt.com, tvgreport.com) rot under the identical silent mechanism
and are NOT covered by this ritual; follow-up issue #248 tracks extending it
to them. It exists to close issue #106.

Executor: the spark-vm hourly build loop's docs turn. Trigger: re-sweep
whenever the log table's last-sweep date below is older than ~90 days.
**Next sweep due: 2026-12-22.**

## Excluded hosts (this ritual)

| Host | Why CI skips it | `*.md` occurrences (2026-09-22) |
|---|---|---|
| `medium.com` | Medium 403s all bots | 4 |
| `businesswire.com` | Rejects lychee's HTTP client | 6 |
| `globenewswire.com` | Rejects lychee's HTTP client | 1 |

Host-level, not per-URL: any new link from these hosts trips the same bot
blocks, so the exclusion has to cover the whole host. When ADDING a link
from one of these hosts, open it in a real browser (they serve browsers
fine) and confirm the page loads and matches the headline you cite — a
browser 404 means the link is genuinely broken: fix the link, don't extend
the exclusion.

## Re-sweep procedure (quarterly)

1. Enumerate every excluded-host link in the repo:
   ```sh
   grep -rEno "https?://[^] )'\"]*(medium\.com|businesswire\.com|globenewswire\.com)[^] )'\"]*" --include="*.md" .
   ```
   (The `[^] )'\"]` class excludes `]` as well — markdown-link closing
   brackets would otherwise glue onto the URL and inflate dedup counts.
   `]` must come first in the class; escaping it as `\]` silently matches
   nothing under GNU grep ERE.)
2. Derive the unique URLs by stripping the `file:line:` prefixes and
   deduplicating:
   ```sh
   grep -rEno "https?://[^] )'\"]*(medium\.com|businesswire\.com|globenewswire\.com)[^] )'\"]*" --include="*.md" . | sed -E 's/^[^:]*:[0-9]+://' | sort -u
   ```
   The "unique URLs checked" number in the log is the output of this
   pipeline, not a naive `sort -u` of step 1.
3. Open each unique URL in a real browser (not a bot fetcher — they will be
   403/bot-blocked). Automated fetchers are not an acceptable substitute;
   the whole point is that these hosts serve browsers fine.
4. For each URL, confirm the page **loads** (not a 404) and the **headline
   matches what the citing doc claims**. Check the citing context, not just
   the URL — a live page with the wrong headline is a broken citation.
5. If a URL 404s or the headline no longer matches the citation: fix or
   remove the link in the same pass (file an issue if the fix needs a
   maintainer decision). Never "fix" it by extending the exclusion.
6. Append a row to the log table below.

## Re-sweep log

| Date | Unique URLs checked | Total occurrences | Result | Verifier | Notes |
|---|---|---|---|---|---|
| 2026-09-22 | 7 | 11 | all live, headlines match citations | spark-vm hourly build loop (docs turn) | First logged sweep; closed #106. |
| 2026-09-19 | 4 | 4 | all live | hourly build loop (docs turn) | Reconstructed from repo state at 33950e2; the PR #39 hand-verification was never logged in-repo. |

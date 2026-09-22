# Excluded-host link re-sweep

CI's markdown-link check skips three hosts at the host level (see
`docs/CI.md`, the `markdown-links` row): automated fetchers get bot-blocked
there, so lychee can never check them. Those links were hand-verified when
the exclusion was introduced and are **never re-checked afterwards** — so
rot would accumulate silently. This document is the re-sweep procedure and
its log. It exists to close issue #106.

## Excluded hosts

| Host | Why CI skips it | How many `*.md` links (2026-09-22) |
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
   grep -rEno "https?://[^ )'\"]*(medium\.com|businesswire\.com|globenewswire\.com)[^ )'\"]*" --include="*.md" .
   ```
2. Open each unique URL in a real browser (not a bot fetcher — they will be
   403/bot-blocked). Automated fetchers are not an acceptable substitute;
   the whole point is that these hosts serve browsers fine.
3. For each URL, confirm the page **loads** (not a 404) and the **headline
   matches what the citing doc claims**. Check the citing context, not just
   the URL — a live page with the wrong headline is a broken citation.
4. If a URL 404s or the headline no longer matches the citation: fix or
   remove the link in the same pass (file an issue if the fix needs a
   maintainer decision). Never "fix" it by extending the exclusion.
5. Append a row to the log table below.

## Re-sweep log

| Date | Unique URLs checked | Total occurrences | Result | Verifier | Notes |
|---|---|---|---|---|---|
| 2026-09-22 | 7 | 11 | all live, headlines match citations | spark-vm hourly build loop (docs turn) | First logged sweep; closed #106. |
| 2026-09-19 | 11 | 11 | all live | hourly build loop (docs turn) | Baseline sweep when the exclusion was introduced (PR #39 review). |

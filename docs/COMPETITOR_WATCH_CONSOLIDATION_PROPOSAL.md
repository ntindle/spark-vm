# Competitor-watch consolidation — proposal (NOT YET ADOPTED)

**Status: proposal.** This document proposes a packaging scheme for the
competitor-watch series. Nothing in it is standing law until the user (or a
loop decision they bless) adopts it. On adoption, a repo turn executes the
migration phases in §5.

## 1. Problem (measured 2026-09-27 ~19:00 CDT)

- **136 watch docs** in `docs/`; 58 of them from the last two days
  (2026-09-26/27).
- `docs/README.md` index rows for recent passes are multi-hundred-word
  walls; the newest row alone is tens of kilobytes. The index is no longer
  an index.
- The delta-only pass format repeats nearly the entire prior pass's state
  each time (aging counters, recrawl contacts, vendor-verified
  pricing tables), so a "no-change" pass still costs a ~100+ line doc.
- Watch docs cite surveyor captures at `hidden_files/agent_notes/...`
  paths that **do not exist in the repo** (they live in the loop's
  workspace). Anyone cloning the repo hits dead references. The playbook
  already says working notes stay out of the repo — the merged docs just
  don't obey it.
- Hourly cadence during quiet windows produces near-zero-delta docs while
  consuming full strategy slots.

None of this is a verdict problem: the no-change-verified record is the
value of the series and must survive. It is a **packaging** problem.

## 2. Non-negotiables

1. Every pass still records a verdict (what was checked, what changed,
   what didn't). No silent gaps — a missing pass must be explainable.
2. The corpus-aging discipline (quiet-count resets on recrawl contact,
   age-outs, re-folds) keeps its exact semantics; packaging must not move
   the goalposts.
3. Vendor-authoritative claims stay labeled (vendor-confirmed /
   vendor-verified / third-party), per the existing conventions.
4. History is preserved — consolidation archives, it does not delete.

## 3. Recommended scheme: weekly digest + full docs only on delta

**Packaging rule.** A pass is a *delta pass* if it contains at least one
of: (a) a new first-party fact, (b) a corpus fold, or (c) a disposition
change: age-out (a quiet count reaching threshold, e.g. 3/3), re-fold,
re-ingestion, or an open/close status change. Sub-threshold quiet-count
increments (e.g. 1/3 → 2/3) and recrawl-contact resets are *quiet
movements* — recorded in the digest's aging line, never delta material
on their own. A later turn must be able to apply this rule
deterministically; if a pass doesn't hit (a)/(b)/(c), it's quiet.

- **Delta pass** → full standalone watch doc + one short README row (one
  sentence + link), replacing the current wall-of-text rows.
- **Quiet pass** → a compact section appended to the current weekly digest
  doc (`docs/COMPETITOR_WATCH_DIGEST_2026-W39.md`). Digest files are named
  for the **ISO-8601 week** (Monday–Sunday) containing the pass's *end*
  timestamp; a pass straddling the week boundary goes to the week of its
  end timestamp. README keeps **one row per digest week**, not per pass.
- **README rows:** one short sentence per row — link to the doc, not a
  copy of the doc. (The current rows copy the whole pass; that habit
  ends with this scheme.)
- **Capture references:** merged docs stop citing `agent_notes/`
  workspace paths. Surveyor findings are summarized inline in the pass
  or digest section; raw captures stay in the loop's workspace per the
  playbook.
- **Aging ledger (non-negotiable #2 enforcement):** the watch docs are
  the aging pipeline's de facto ledger — every pass currently restates
  the full counter vector. A digest section that lists only moved
  counters would silently degrade it. So every digest section carries a
  **canonical aging-state block**: every tracked candidate with its
  quiet count, the aged-out set enumerated, and open/carried items
  listed. The ledger stays complete and reconstructible from the digest
  alone.
- **Digest-size circuit breaker:** if a weekly digest would exceed
  ~100 sections, the turn routes a cadence review to rotation
  governance instead of silently growing the file — a quiet stretch
  long enough to need one is evidence the cadence question deserves a
  decision, and the packaging must not relocate the wall-of-rows
  problem into a wall-of-sections problem.

**What a quiet-pass digest section looks like** (compact but complete —
target ≤30 lines plus the aging block):

```markdown
## 2026-09-27 ~19:24–~19:55 CDT — quiet pass
Window: ~18:55–~19:24 CDT. Checked: vendor re-verification (9/9
NO-CHANGE, first-try), delta news scan (20 queries, snippet level —
0 new first-party claims). Verdict: no delta; no corpus fold.

Aging: C62 0/3; C11 0/3; C45 0/3; C67 0/3; C12 OPEN (no egress line);
C29 carried. Aged out (staying out): Heapjack/Overpatch, GitLab
CVE-2026-85706.
```

## 4. Alternatives considered

- **Daily rollup instead of weekly digest:** same idea, smaller
  container; weekly is better because quiet stretches run multiple days
  and a day-granular rollup re-introduces the wall-of-rows problem (and
  is covered by the circuit breaker).
- **Widen the loop cadence instead of changing packaging:** orthogonal —
  cadence is a rotation-governance question (see the meta-audit stream),
  not a docs question. This scheme pays off at any cadence. Deliberately
  out of scope here: **a quiet-window fast-mover re-verification cadence
  change is a separate proposal** — it would ship as its own adopted
  decision, and packaging adoption must never be read as cadence
  adoption.

**Recommendations to rotation governance (non-binding, advisory only):**
once the packaging scheme is adopted, governance may consider (1) a
widened vendor re-verification interval during long quiet stretches,
and (2) retiring rotation-counter names for quiet passes (digest
sections carry timestamps instead). Both are governance decisions, not
packaging decisions; they are not adopted by adopting this proposal.
- **Archive-only (keep per-pass docs, just move old ones):** halves the
  visible clutter but keeps the per-pass write cost; the README-row
  wall and the repeat-the-prior-state write cost stay.

## 5. Migration plan (on adoption; a repo turn executes it)

1. Start the current week's digest prospectively on adoption — no
   retro-fill (retro-summarizing creates two authoritative copies of
   the same passes; the old docs stay fully readable in `archive/`).
2. Move quiet-pass watch docs older than 7 days to
   `docs/archive/competitor-watch/` (git history preserved). Each moved
   doc is classified delta/quiet with a one-line rationale in a
   **classification manifest** recorded in BACKLOG.md, so a later turn
   can audit the calls; when in doubt, classify as delta and keep the
   doc in-tree. Archived docs are immutable snapshots — never edited
   after the move.
3. Collapse the archived docs' README rows into per-week digest rows
   (one short sentence each), following the existing precedent:
   `docs/README.md` already collapses `docs/archive/competitor-watch/`
   to a single folder row.
4. Strip `agent_notes/` capture-path references from the remaining
   **non-archived** in-tree watch docs: replace each `Captures:
   hidden_files/agent_notes/...` line with an inline summary of what
   the capture covered (scan window, lanes checked, verdict); drop the
   line entirely only where the same information is already inline —
   never delete the only record of what a pass checked.
5. Record adoption in BACKLOG.md and close this item; the next strategy
   turn ships under the new scheme.

## 6. Decision

Owner: the user. Until adopted, strategy turns keep the current
per-pass packaging (this proposal must not be mistaken for a rule by
later turns). A repo turn may pick up phases 1–4 once adopted.

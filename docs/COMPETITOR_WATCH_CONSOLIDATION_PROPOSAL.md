# Competitor-watch consolidation — proposal (NOT YET ADOPTED)

**Status: proposal.** This document proposes a packaging scheme for the
competitor-watch series. Nothing in it is standing law until the user (or a
loop decision they bless) adopts it. On adoption, a repo turn executes the
migration phases in §5.

## 1. Problem (measured 2026-09-27 ~19:00 CDT)

- **135 watch docs** in `docs/`; 58 of them from the last two days
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
of: a new first-party fact, a corpus fold, an aging state change
(age-out, re-fold, re-ingestion, quiet-count milestone hit). Everything
else is a *quiet pass* — including passes whose only movement is recrawl
contact (contacts still reset quiet counts; the reset is recorded in the
digest line).

- **Delta pass** → full standalone watch doc + one README index row, as
  today.
- **Quiet pass** → a compact section appended to the current weekly digest
  doc (`docs/COMPETITOR_WATCH_DIGEST_2026-W40.md`): pass window, what was
  checked, verdict lines (fast-mover re-verification result, aging
  counter movements), one sentence of market color. README keeps **one
  row per digest week**, not per pass.
- **Fast-mover re-verification cadence:** every pass during active
  windows; every 4th pass (at least daily) once ≥3 consecutive quiet
  passes have been recorded. The 24-pass all-no-change streak on the
  vendor pages shows the current every-hour interval is pure cost during
  quiet windows.
- **Naming:** quiet passes stop getting rotation-counter names; digest
  sections carry timestamps. Delta passes keep the current naming
  convention.
- **README rows:** one short sentence per row — link to the doc, not a
  copy of the doc. (The current rows copy the whole pass; that habit
  ends with this scheme.)
- **Capture references:** merged docs stop citing `agent_notes/`
  workspace paths. Surveyor findings are summarized inline in the pass
  or digest section; raw captures stay in the loop's workspace per the
  playbook.

**What a quiet-pass digest section looks like** (target: ≤30 lines):

```markdown
## 2026-09-27 ~19:24–~19:55 CDT — quiet pass
Window: ~18:55–~19:24 CDT. Checked: vendor re-verification (9/9
NO-CHANGE, first-try), delta news scan (20 queries, snippet level —
0 new first-party claims). Aging: C62 recrawl contact — quiet RESET
0/3; C11/C45/C67 contacts — quiet stays reset. Aged-out stay out.
Verdict: no delta; no corpus fold.
```

## 4. Alternatives considered

- **Daily rollup instead of weekly digest:** same idea, smaller
  container; weekly is better because quiet stretches run multiple days
  and a day-granular rollup re-introduces the wall-of-rows problem.
- **Widen the loop cadence instead of changing packaging:** orthogonal —
  cadence is a rotation-governance question (see the meta-audit stream),
  not a docs question. This scheme pays off at any cadence.
- **Archive-only (keep per-pass docs, just move old ones):** halves the
  visible clutter but keeps the per-pass write cost; the README-row
  wall and the repeat-the-prior-state write cost stay.

## 5. Migration plan (on adoption; a repo turn executes it)

1. Create the current week's digest doc; append one section per quiet
   pass from the last 7 days (verdicts carried forward from those
   docs).
2. Move quiet-pass watch docs older than 7 days to
   `docs/archive/competitor-watch/` (git history preserved).
3. Collapse their README rows into per-week digest rows (one short
   sentence each).
4. Strip `agent_notes/` capture-path references from the remaining
   in-tree watch docs (replace with inline summaries or drop).
5. Record adoption in BACKLOG.md and close this item; the next strategy
   turn ships under the new scheme.

## 6. Decision

Owner: the user. Until adopted, strategy turns keep the current
per-pass packaging (this proposal must not be mistaken for a rule by
later turns). A repo turn may pick up phases 1–4 once adopted.

# Competitor watch — 2026-09-27 (late-evening, cycle 6)

**Consolidation pass executing the C40 deprecated-row expiry.** The
deprecated-row expiry convention (codified in the cycle-5 watch, PR #589)
names the C40 (ASCII → Boat) row as its first standing removal candidate:
a deprecated row becomes a removal candidate once its unique facts are
folded into the canonical row, and *only a consolidation pass may remove
it*. This pass serves as that consolidation pass. Scope: pre-deletion
re-verification of every Boat first-party surface + a fold-completeness
audit, then the row removal. NOT a full two-surveyor pass; no other vendor
re-checks (the cycle-3 baseline ~18:26–~18:55 CDT, the C4 Modal egress
fold, and the C5 NanoClaw parent-call closure all stand).

Delta-only against the cycle-5 scoped verification
(`docs/COMPETITOR_WATCH_2026-09-27_LATE_EVENING_C5.md`).

## Pre-deletion re-verification (first-party, read live ~20:5x CDT 2026-09-27)

- **YC rename evidence — no drift:** `ycombinator.com/companies/ascii`
  still serves **301 → `https://www.ycombinator.com/companies/boat`**
  (VENDOR-VERIFIED this turn; matches the 2026-09-24 midday and C5
  ~20:33 CDT verifications).
- **Pricing — VERIFIED NO-CHANGE:** `docs.boat.dev/pricing` read in full
  this turn; value-for-value identical to the 2026-09-25 post-pre-midnight
  fold: sizes small $0.018 / default $0.036 / large $0.072 / xlarge $0.200
  (xlarge capacity-gated, $100+ plan + operator allocation); plans
  $20/$100/$500/$2,000 with the same concurrency (100/300/1,000/2,000) and
  start limits; 25 free-hour trial (small + default only, 2 sandboxes);
  per-second billing, "a stopped sandbox costs nothing"; plan price = sandbox
  time, expires monthly; $20 credit packs never expire.
- **Legacy-domain mechanism drift (strengthens the rename conclusion):**
  `box.ascii.dev` and `ascii.dev` no longer serve byte-identical product
  pages — both now serve **301 → `https://boat.dev/`**. The vendor has
  replaced the parallel legacy pages with redirects to the canonical
  domain. The corpus's 2026-09-24 "byte-identical pages" mechanism is
  retired; the rename conclusion is unchanged and the evidence is harder
  (a vendor-operated redirect is a stronger brand signal than mirrored
  content).
- **Legacy docs-domain mechanism drift:** `docs.ascii.dev/box/api/v1` now
  serves **301 → `docs.boat.dev/box/api/v1` → 308 → `/api/v1`**; the final
  page (200) is still titled **"Boat Public API v1"**. Same branding
  evidence the corpus folded (the vendor's developer surface brands the
  product *Boat*), now served under the canonical docs domain.

## Fold-completeness audit (every unique C40 fact → its Boat-row home)

The deprecated row carried exactly these facts; each is confirmed present
in the tracked-set Boat row:

1. Rename ASCII → Boat ~2026-09-17 — Boat row header ("renamed from ASCII
   ~2026-09-17 — C40 deduped into this row") + yc-oss `former_names`
   ["Ascii box", "Ascii"] evidence.
2. Legacy-domain rename evidence — Boat row rename narrative (updated this
   pass with the 301 mechanism, superseding byte-identical pages).
3. YC company page `ycombinator.com/companies/boat` (YC F26) — Boat row;
   old-slug 301 — Boat row (re-verified live this turn).
4. `docs.ascii.dev` "Boat Public API v1" branding — Boat row (updated this
   pass: redirect chain, same title).
5. Pre-dedup pricing ($20/mo plan = $20 sandbox time, $0.036/h 4 vCPU/8 GB/50 GB,
   per-second billing, 100–2,000 sandboxes by plan, $20 auto-refill packs) —
   superseded by the richer 2026-09-25 post-pre-midnight pricing fold in the
   Boat row pricing cell (re-verified value-for-value this turn).
6. EU-only DE/FI/FR geography — Boat row pricing cell ("folded from the
   deprecated C40 pointer row").

No unique fact remains in the deprecated row. The audit passes.

## Expiry executed

- The deprecated C40 row is **REMOVED from the field table**.
- Provenance retained: the tracked-set Boat row header keeps the "C40
  deduped into this row" note; the 2026-09-24 morning dedupe narrative stays
  in the corpus Watch-update sections; the C5 doc records the rule's
  codification; the Corpus conventions bullet records the execution; this
  doc records the evidence.
- Corpus edits: deprecated-row removal + Boat-row mechanism updates
  (301 redirects, docs redirect chain) + conventions bullet + a
  "Watch update — 2026-09-27 (late evening, consolidation)" section in
  `docs/COMPETITOR_ANALYSIS.md`; index row in `docs/README.md`; reader-facing
  CHANGELOG bullet.
- No new C-numbers. The C68 reservation (DevDay "agent O" confirmation) and
  the remaining cycle-3 watch-outs (Hugo CVE-2026-100690 GHSA sweep,
  CVE-2026-93993 parent call) carry forward unchanged.

## Not done this turn

- No other vendor re-checks — the cycle-3 + C4 baselines stand; the in-lane
  no-launch verdict dated 2026-09-25 stands.

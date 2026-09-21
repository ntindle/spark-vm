# Competitor watch — C17 resolution: boat.dev xlarge capacity-allocation check (2026-09-21)

Resolves **C17** (from `docs/COMPETITOR_WATCH_2026-09-21.md` §1): capture the
boat.dev pricing page and diff it against the 2026-09-21 read to resolve the
pre-existing-vs-new question on the xlarge capacity-allocation caveat before
any 16-vCPU hosted sizing decision.

Conventions: **VERIFIED** = read on a vendor's own page this run (link inline).
**INFERRED** = my characterization, labeled as such.

## 1. The diff

**VERIFIED** ([boat.dev pricing](https://docs.boat.dev/pricing), read
2026-09-21 ~13:00 CDT — page fetches cleanly from non-runner fetchers,
bot-block behavior on GitHub-runner fetchers stands per the 2026-09-21
baseline):

- The baseline rate card holds: `default` 4 vCPU / 8 GB / 50 GB disk at
  **$0.036/h**, per-second billing, "A stopped sandbox costs nothing,"
  $20/mo plan = $20 of time (555 h of `default`), concurrency
  100/300/1,000/2,000 across the $20–$2000 plans, 25 free-hour trial
  (`small`/`default` only), "one `default` sandbox running a whole month
  (730 h) is $26."
- **The xlarge caveat is present with the same substance as the 2026-09-21
  read:** the price table footnotes `xlarge` (16 vCPU / 32 GB / 251 GB,
  **$0.200/h**) with "* `xlarge` needs a $100 plan or higher and an operator
  to allocate the capacity" (contact via "ask us" on X).
- The comparison table's E2B/Daytona rows still read **$0.331/h default**
  (small column $0.166) — no visible price move on either.

## 2. Verdict

**C17's sizing question is resolved; the temporal question is settled at
"current policy."** The caveat wording today is identical in substance to
the 2026-09-21 baseline read, so it cannot be labeled new by this pass. Two
reads ~9 hours apart cannot establish whether the note predates the
~Sept-19 page refresh the search index reported — and that distinction no
longer matters for the decision it gates: 16-vCPU is **capacity-gated today**
by vendor statement on their own page. Before any 16-vCPU hosted sizing,
confirm operator capacity allocation directly with boat.dev (the footnote's
ask-us route).

**INFERRED (flagged, not asserted):** since the ~Sept-19 refresh window, the
page's comparison table now lists ten providers (Novita, Freestyle, exe.dev,
E2B, Daytona, Blaxel, Codespaces, Cloudflare, Modal, Islo, Runloop, Vercel
Sandbox) where the 2026-09-21 baseline read quoted only E2B/Daytona. That
read may simply have been partial — do not cite this as an expansion without
a third read confirming.

**Implication:** boat.dev remains the cheapest viable provider candidate
($0.036/h vs E2B/Daytona's listed $0.331/h), but the large-end
Fly-vs-boat math must carry a capacity-allocation contingency: a $100+/mo
plan alone does not unlock 16 vCPU — operator allocation does.

## 3. Standing items

- **C17 CLOSED** by this pass (see BACKLOG.md).
- No new backlog items from this pass.
- Standing: C9 (OpenAI partners), C10 (WSO2 — Sep 29 webinar is the next
  trigger), C11 (Baseten–Blaxel integration), C12 (AgentComputer egress-only),
  C14 (#47 resume-latency target — open; needs measured boat.dev/provider
  baseline; live-API measurement awaits the operator per-run spend-cap
  decision — see H4's unblock pass).

---

*Corpus note:* per the reach-back policy this pass is delta-only vs
`docs/COMPETITOR_WATCH_2026-09-21.md` §1; no corpus record changed. The raw
page capture lives in the loop's `agent_notes/` (workspace-only), not the repo.

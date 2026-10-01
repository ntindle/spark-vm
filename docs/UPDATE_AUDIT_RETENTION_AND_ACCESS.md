# Update-audit retention + tenant read-path access policy (G19 / #660)

**Status:** designed (the retention and access decisions), not built. Resolves
G19 (#660), the retention + read-path residual from G13's trust-model design
(`docs/TENANT_UPDATE_TRUST_MODEL.md` §5).

**The question (G13 §2's open line):** "The tenant Muse may read its own
box's update history — visibility is the G12 promise — but only through the
control plane's read surface, never a box-side journal. Retention and the
access policy are filed as G19." This doc answers both: how long the
control-plane journal keeps per-box update records, and exactly what the
tenant Muse may read — with the privacy boundary between tenants stated
plainly.

**What G13 already decided (bounds this doc, does not repeat it):**

- The authoritative record is the control plane's JSONL journal — never a
  box-side journal (the tenant holds root inside the guest; box-side lines
  are forgeable).
- Records (per reimage, per box): `registration`, `wave_assignment`,
  `promotion`, `reimage`, `maintenance` (enter/exit), `freeze` / `halt` /
  `unfreeze` / `promote`, `deferred` / `skipped` (with reason), failed
  maintenance (→ `box-unhealthy`, `detail: maintenance-failed: <check>`).
- Attribution: every line carries the authorizing actor's identity — the
  pinned provisioned operator key's fingerprint, never a bare name — and
  the registration ref it chains to (#14 lesson). No phantom entries: a
  deferred, skipped, or never-started reimage gets an explicit line with
  the reason, never a silent absence (#16 lesson).
- The journal is per-tenant by construction; waves scope per tenant (H11).

**What G12 promises (the read path serves):** visibility — no silent
updates. The tenant knows every reimage its box underwent, attributable
to who authorized it, and can distinguish "nothing happened" from
"records aged out".

---

## 1. Retention — the chain decides

The journal's records reference each other: `wave_assignment` and
`promotion` name a registration ref; `reimage` names the registration ref,
the wave, and the migration outcome. A retention policy that deletes a
`registration` while a retained `reimage` still names its ref manufactures
exactly the silent gap the #16 rule forbids. So the retention invariant
is:

> **Chain-safe deletion:** a record is eligible for pruning only when it
> is older than its tier window **and** no retained record references it.
> The collector walks from the tail: registrations outlive everything that
> names their ref (G13's attribution rule puts the registration ref on
> every line); as *policy* — not as a chain edge, since the reimage
> record names no promotion ref — a `promotion` is retained for the tier
> window of its wave's latest retained reimage, because a promotion is
> uninterpretable without the reimages it moved; `deferred`/`skipped`
> lines share the retention of the update window they belonged to.

Three tiers, operator-configurable windows, defaults stated honestly:

| Tier | Default window | Who reads | Contents |
|------|---------------|-----------|----------|
| **Hot** | 90 days | Tenant + operator | Full fidelity: every record, including `maintenance` enter/exit pairs. This is the window the tenant read path (§2) serves. |
| **Warm** | 1 year | Operator only | Full records, except `maintenance` enter/exit pairs compact to one line per maintenance window carrying enter_ts, exit_ts, and the authorizing fingerprint — volume reduction without honesty loss (G14 D1's freeze accounting uses the set/clear timestamps). |
| **Cold floor** | 2 years, security channel | Operator only | Security-channel registrations and everything chained to them (wave/promotion/reimage/freeze/failure). Never pruned earlier. Routine channel: the warm 1-year window. |

Rationale for the defaults: a tenant Muse's working memory is measured in
weeks, so 90 days covers any real "was my box silently updated?" dispute;
incident forensics run on quarters, so a year of operator-side fidelity;
security advisories have multi-year tails (a reimage driven by an advisory
ref must stay attributable for as long as the advisory matters), so the
cold floor. The operator may widen any window; it may not narrow a window
below the chain floor — that floor is structural, not preference, and the
GC refuses a configuration that would break it (config validation at
startup, loud refusal, not a quiet downgrade).

**Prune honesty (the #16 lesson applied to deletion).** Pruning is itself
an auditable operator event: each prune run appends an operator-only line
(window pruned, policy ref, per-type counts) to the control-plane journal
itself — visibility-scoped operator-only, never served to a tenant
(there is no second journal; the line lives in the journal G13 §2
defines), and it consumes no tenant-visible seq number (§2.1). And the tenant's read path discloses the boundary honestly — the response
names the window it covers ("history available from `<date>` per the
retention policy"), so a tenant never mistakes pruning for silence. Never
invent entries; never leave a silent gap. A box with zero retained records
shows an empty history with the window stated, not an error.

**What is NOT kept longer than the journal:** the journal's retention
governs the authoritative record. Transient working state — the scheduler's
in-memory wave cursors, the G17 event journal's pre-aggregation lines —
falls under each component's own retention; when it ages out, the
authoritative journal remains the answer to "what happened". Cross-journal
refs are correlation aids that may dangle by design: `reimage`'s G17
outcome-event ref and `promotion`'s G17-aggregate/G16-inventory refs point
at stores with shorter retention than this journal's tiers — each component
owns its retention, and this journal's line is the authoritative record,
not a promise the target still exists.

---

## 2. The tenant read path — `GET /tenant/update-history`

A dedicated read-only endpoint. Not folded into G3's `GET /tenant/status`:
history is paged and unbounded; the status poll stays fixed-shape.

- **Auth:** the same two-sided pattern as the status poll
  (`TENANT_STATUS_ENDPOINT.md` §1): the tenant Muse authenticates with its
  linked (approved) ed25519 key, signing requests per
  `HOSTED_SIGNUP_ONBOARDING.md` §4's link-signing scheme. No new identity
  system is invented here. No unauthenticated access; unauthenticated → 401;
  a valid credential with no servable tenant record → 404, not 403 (the
  same enumeration-oracle discipline: the endpoint must not confirm other
  tenants' existence). There is no tenant selector — identity is
  credential-derived.
- **Scoping:** `tenant_id` filtered server-side. The journal is per-tenant
  JSONL by construction (G13 §2), and the read path re-scopes anyway:
  defense in depth. A cross-tenant read is a governance incident, and the
  S2 slice proves the negative with a fixture test (§4).
- **Read-only:** GET changes nothing; `Cache-Control: no-store` — a tenant
  checking for silent updates must see the latest line, not a cached one.

### 2.1. Verifiable completeness — no silent gaps on the read path either

Each journal line carries a **per-tenant monotonic sequence number**,
assigned in append order **to tenant-visible records only**: operator-only
lines (the prune-honesty lines from §1) are appended to the same
per-tenant journal but consume no seq number. The seq stream is therefore
exactly the tenant's served history — a missing seq number inside the
served window can never be explained by an operator-only line the tenant
cannot see. The response envelope carries `first_seq` and
`last_seq` bounding the **served window** — the oldest and newest retained
records *within the hot tier window* — and the tenant can verify
contiguity across that range. This is the #16 lesson applied to the read
path: absence is only signal when the surface says so, and the surface
here says so — a missing seq number *inside the served window* is an
incident, not a prune. Chain-safe retention can leave seq holes *older*
than the served window (a chain-retained anchor older than the window
outlives its unreferenced neighbors — §1's walk is not a tail cut), so
chain-retained anchors older than the hot window are excluded from the
tenant's served view (operator-visible only); within the served window
the range is contiguous because hot-tier pruning only removes records
older than the window.

### 2.2. The tenant-visible field allowlist

The tenant sees everything it needs to audit "no silent updates" — and
nothing that names another tenant:

- timestamp, seq, event type
- image N → N+1, channel
- registration ref + advisory ref (security channel: the advisory *ref
  id*; full advisory text is operator-domain)
- the authorizing actor's pinned-key fingerprint (the attribution G13
  promises — a reimage without a named authorizer is exactly the
  unattributable reimage G13 forbids)
- wave (role label only — `standard` / `canary`; never wave numbers or
  membership — disambiguation: fleet-level canary configuration and
  population are operator-only; the per-box policy role label describes
  the caller's own box and is tenant-visible)
- migration outcome, G17 outcome-event ref (a correlation aid that may
  dangle — see §1)
- `deferred`/`skipped` reason, failure detail (`maintenance-failed:
  <check>`). Reconciling with G14 D2 (a suspended box's skip lands in
  the wave journal, never in the tenant's *live* view): D2 governs the
  live status poll; the retrospective history may include skips never
  live-served — still honest under the window disclosure.
- the retention-window disclosure (history available from `<date>`)

**Operator-only, never in the tenant view:** fleet canary flags, fleet totals,
wave sizes and membership, other tenants' identifiers, controller internal
instance ids, gate-evidence refs that enumerate fleet composition. The
privacy boundary is one sentence: **a tenant's history never names another
tenant** — not by id, not by count, not by wave population. A fleet-total
is a cross-tenant fact; the tenant has no read right to it. (The wave role
label is allowed because it describes the *policy* applied to the caller's
own box, not the fleet.)

**Honest empty:** a box with no update records in the window returns
`{"events": [], "window": {...}, "first_seq": null, "last_seq": null}` —
not an error, not an absence to misread.

### 2.3. The tenant's write surface: none

The tenant Muse writes nothing to the audit journal. The journal's writers
are the control plane and the controller, as implied by G13 §2's record
list (which places every record on the control plane and cites G12's
maintenance producer rule). The tenant's update-audit participation is
read-only verification: it cross-checks the `maintenance` windows it
observed against the journal, and any reimage present in neither its
memory nor the journal is an incident to file, not a line to add.

**The seq linearizer (the S2 implementer's contract):** the per-tenant
journal has a single appender; sequence numbers are assigned **at durable
append, never pre-issued** — a writer crash between submission and append
consumes no seq number, so there are no phantom holes. On appender
failover it resumes from durable state; un-acknowledged controller
submissions carry a submission id and are safe to resubmit (idempotent by
dedupe on the submission id — S2 pins the key). An invented gap is as
much an honesty violation as a silent absence.

---

## 3. Both-supported note

The same journal, the same retention tiers, and the same read surface serve
the self-hosted operator's N-box estate — registration, attribution,
chain-safe GC, the read endpoint. The hosted delta is tenant scoping
(per-tenant journals, credential-derived identity, the privacy boundary).
The single-operator case degenerates gracefully: the operator is the only
actor and the only reader; per-tenant scoping becomes per-estate scoping
with no second design. Nothing in this doc requires a tenant to exist.

---

## 4. Build slices (for the distribution/feature track, not this doc)

1. **S1 — retention policy + chain-safe GC:** operator config (hot / warm /
   cold windows, defaults per §1), config validation that refuses
   chain-breaking windows at startup, the GC script with the prune-honesty
   line and the `maintenance` enter/exit compaction rule. **Exit
   criterion:** a GC drill on a synthetic journal — chain intact after the
   run, prune line emitted, no orphaned refs, and a window-shortening
   config is refused loudly.
2. **S2 — the read endpoint:** provisioned-identity auth per the link-
   signing scheme, server-side tenant re-scoping, the §2.2 field
   allowlist, per-tenant sequence numbers with the `first_seq`/`last_seq`
   envelope, the retention-window disclosure, honest empty. **Exit
   criteria:** (a) a two-tenant fixture test proves the negative — tenant
   A's history never names tenant B (no id, no count, no wave population);
   (b) a contiguity test — a dropped record *inside the served window* is
   detected via the seq envelope (records older than the served window,
   e.g. chain-retained anchors, are not expected contiguous).
3. **S3 — hosted instantiation:** per-tenant journal layout, a
   privacy-boundary audit over every G17 aggregate ref the tenant view
   could carry, and the operator runbook for retention disputes ("my
   history says X, the journal says Y").

---

## 5. Open questions (answered — kept for history)

None answered in this doc; the open questions stay open on the issue:

- **Q1 — hot-window shape:** 90 days, last 10 generations, or both
  (whichever is longer)? This doc's standing default is days (90-day hot
  window); the generations alternative activates only if the operator
  documents its reimage cadence in S1's config — the S1 implementer does
  not pick silently.
- **Q2 — legal floor by jurisdiction:** some jurisdictions may require
  longer audit retention; that is an operator configuration decision, not
  this doc's — the cold floor is a minimum, never a maximum.
- **Q3 — push on new records:** should the tenant Muse be able to
  subscribe to new journal lines (a stream) rather than poll? Deferred —
  the G17 S3 endpoint and the H14 push lane may absorb this; polling the
  read path is sufficient for the "no silent updates" promise today.
- **Q4 — advisory text vs ref id:** the tenant sees the advisory ref id;
  whether it should see advisory text (severity, title) is a disclosure
  decision for the operator — the ref id is sufficient for the tenant to
  correlate against public advisories itself.

---

## 6. Residuals — none new

G19 is closed by this doc; G20 (migration-tooling input hardening, #661)
remains the last open G-number and is untouched here. The trust-model
series' design work is now: G11/G12 shipped, G13/G14/G15/G16/G17/G18/G19
designed, G20 open — implementation (S1–S3) stays on #778 (the G19 implementation issue; #660 closed on the design).

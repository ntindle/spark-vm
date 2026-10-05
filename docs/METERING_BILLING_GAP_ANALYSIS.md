# Metering & billing gap analysis (H12 → billing lane)

Vision-vs-state of the usage-metering and billing surface: what the hosted
product needs to charge for a box, cap spend, and detect abuse, versus what
exists today. **Pinned to main `0a47d7c`** (fleet gate_sync.sh lifecycle
hardening, #1046) for all in-repo claims. Plane claims are pinned to a
2026-10-05 read of the `sparkvm-dev-website-v2-cloudflare-management-infra`
workspace's `control-plane/worker.py` — the control-plane Worker lives
outside this repo, so per the repo's own honesty convention
(`APPROVALS_PLANE_GAP_ANALYSIS.md`), plane state is pinned to the deployed
read, not to a repo commit.

Gap classes reuse the vocabulary `docs/USAGE_METERING_DESIGN.md` shares with
`APPROVALS_PLANE_GAP_ANALYSIS.md`: `[BUILD]` exists nowhere, build it;
`[HOSTED]` the single-user OSS substrate needs a tenant dimension for hosted;
`[DESIGN]` design exists, code does not; `[POLICY]` needs an operator
decision first.

## The vision (as written)

Four documents plus one owner ruling define the lane:

1. **`docs/USAGE_METERING_DESIGN.md` (H12)** — five meters
   (`box_wall_clock`, `resource_window`, `approval_volume`, `suspend_wake`,
   `push_delivery`), a canonical metering envelope
   (`v`/`seq`/`epoch`/`ts_ns`/`tenant`/`source`/`event`/`trust`/`attrs`,
   `mac` reserved), six sources (S1 confirmd audit.log, S2 swap.log, S3
   muse-job JSONL as liveness-only, S4 auto-deploy audit, plus a new
   box-local `meter_agent` and a `provider` source), per-surface mappers
   (writers stay untouched), emission through a `MeterQueue` copied from the
   H14 part a `PushQueue` pattern (durable box-local spool, rotation bound
   *required before any meter daemon ships* — the #360 unbounded-S1-trail
   lesson), fail-open semantics, and a 90-day raw / account-lifetime
   aggregate retention proposal marked `[POLICY]`.
2. **`docs/PRICING_THINKING.md`** — per-box (not per-seat) pricing; the
   conversion trigger is buyer-facing evidence: "you see every approval,
   you cap the spend, you can kill it." Explicitly: "Cost controls are a
   feature the paid tier sells."
3. **`NEEDS_USER.md`, decided 2026-09-24** — billing shape: normal Stripe
   page, card required up front, API-driven metered/credit packs; H4
   loop-machine policy: **$5/run max, $25/month max**.
4. **`#908`** (spend-cap enforcement mechanism, p2) — pre-provision cap
   check, a spend ledger with cost attribution, and a
   destroy/suspend-on-budget-exceed worker; acceptance: provision refused
   when caps would break.
5. **H13 suspend/wake** — consumes the `suspend_wake` meter and the
   60-second idle heartbeats (`#377` defines what "idle" means; still open).

## The state (verified on `0a47d7c`)

- **F-M1 `[BUILD]` — no meter_agent.** Zero references to `meter_agent`
  anywhere outside `docs/` (grep over `*.py`/`*.sh`). No
  `resource_window` producer exists: nothing reads `/proc` or cgroups on a
  box for metering purposes. Consequently the idle heartbeats H13 needs
  have no emitter.
- **F-M2 `[BUILD]` — no MeterQueue.** The pattern it would copy exists and
  is healthy — `PushQueue` at `confirm/push.py:601` (durable enqueue,
  backoff retry, systemd worker) — but the metering copy does not. The
  emission path's own prerequisite, the rotation bound, is filed as `#376`
  and unbuilt; building the queue first would repeat the #360 disk-full
  incident in the metering subsystem.
- **F-M3 `[BUILD]` — no metering mappers.** The S1–S4 surfaces the design
  maps exist (confirmd's `audit.log`, the swap proxy's `swap.log`,
  muse-job's JSONL, auto-deploy's audit lines) — but they emit their
  native audit formats, not metering-envelope events. No per-surface
  mapper emits the canonical envelope anywhere.
- **F-M4 `[BUILD]` — no provider meter.** The H4 Fly driver is unshipped
  (`#905` open), so no `box_state_transition` events exist; worse, there
  is no wall-clock meter of any kind, so `box_wall_clock` — the base
  billing unit — has zero sources. The design honestly refuses to fake
  the suspended/idle distinction; today neither side of it is measured.
- **F-M5 `[BUILD]` — no plane-side metering ingestion.** The 2026-10-05 read
  of the external `control-plane/worker.py` (zero `meter` refs) and
  `docs/CONTROL_PLANE_API_REFERENCE.md` (zero metering endpoints) shows no
  metering surface: no batch-ingest endpoint, no dedupe, no billing
  aggregates, no spend ledger. The `dedupe on (source, epoch, seq)` the
  design promises (§6) has nowhere to run.
- **F-M6 `[DESIGN]` — unsigned by design.** The envelope's `mac` field is
  reserved; the first implementation ships unsigned, which the design
  accepts — but it also promises the H5 signed-audit story will *adopt*
  this envelope, not re-derive one. Nobody has pinned that adoption, so
  the two lanes can still drift.
- **F-M7 — the fleet journal is a *source*, not a competing emission path.**
  `USAGE_METERING_DESIGN.md` §6 prescribes the dedicated `MeterQueue`
  (box-local spool + worker) as the emission path. `#800` (G26, open)
  decides "the fleet event journal becomes metering's S4 source" — the
  journal feeds a **meter-daemon read contract**, and the meter daemon
  emits through §6's `MeterQueue`: the same single emission path, with
  the journal as one more source upstream of it. There is no second spool
  system, no second dedupe rule, no second retention policy to choose
  between; the "two emission paths" framing (filed as `#1049`, since
  closed as invalid premise) was a misread of #800's scope. The genuinely
  undecided piece inside #800 is the S1 maintenance-minute billability
  policy — which fleet event kinds feed which meter dimensions, answered
  as design: billable / not / operator-declared — and it stays inside
  #800's S1 slice, not in a new issue. The fleet journal is not
  meter-ready today regardless: no `tenant` field (`#798` open),
  `emitted_at` sorts lexically (`#1010` open), `session_epoch: None` on
  S1 (no provisioner box record) — prerequisites for any S1 mapping.
- **F-M8 — caps are precision-blocked on the metering lane, not hard-blocked.**
  `#908`'s body scopes its spend ledger on **provision records** — a coarse
  wall-clock source buildable without the metering lane (the metering
  design's own §2 names "auto-deploy's S4 audit + provision records" as
  today's `box_wall_clock` source). What the metering lane adds is the
  *precision* #908's acceptance implies: the suspended/idle distinction
  and live burn. #908 named no meter dependency at all, so a reader could
  still believe the fine-grained version is buildable on its own — it is
  not.

## Decisions pinned (D-M series)

- **D-M1 — no cooperative-source billing.** Standing constraint from the
  design's trust tiers (`§2`, sourcing #356): `muse-job` telemetry is
  `trust: cooperative` — it may inform idle detection and liveness
  dashboards, but it must never price or bill. A meter that bills on
  cooperative telemetry is a billing-integrity defect, not a feature.
- **D-M2 — metering stays both-supported.** The design's §6 self-hosted
  rule stands as the build constraint: with no control-plane endpoint
  configured, `meter_agent` still spools locally under the `#376`
  rotation bound and the worker simply has nowhere to send — the meter
  data stays useful on a single box (the operator's own cost view).
  Metering is not hosted-only.
- **D-M3 — meters before *fine-grained* caps.** `#908`'s spend ledger is
  #908's own scoped deliverable, so it is not a prerequisite of the
  metering lane. The dependency is a precision one: at minimum a
  `box_wall_clock` meter — from the H4 provider driver (`#905`, open) or,
  interim, the provision-record/audit source the design's §2 names
  ("auto-deploy's S4 audit + provision records") — must feed #908's
  ledger before the *fine-grained* acceptance (suspended/idle
  distinction, live burn) can be tested. Coarse enforcement on provision
  records is not blocked on this lane. Recorded as pointer comments on
  `#908`.
- **D-M4 — no emission-path decision exists.** The fleet journal is a
  meter-daemon *source* (`#800`/G26's decision stands); the dedicated
  `MeterQueue` remains the design's emission path. The open question is
  #800's S1 maintenance-minute billability policy (billable / not /
  operator-declared), not a transport choice.
- **D-M5 — `mac` stays reserved; dedupe is the integrity story.**
  First implementation ships unsigned per the design; ingestion dedupes
  on `(source, epoch, seq)`; H5's signed story must adopt this envelope
  rather than re-derive one.

## Slices filed

- **meter_agent implementation** (#1047) — box-local `/proc` + cgroup scraper
  emitting `resource_window` every 5 min and `idle_heartbeat` every 60 s
  into the spooled envelope; gated on `#376` (rotation bound) and `#377`
  (idle semantics).
- **Plane-side metering ingestion + billing aggregates** (#1048) —
  authenticated meter-batch endpoint (tailnet-identity auth per the design's §6
  mechanism), `(source, epoch, seq)` dedupe, `tenant: unknown`
  quarantine consumption per `#378`, derived per-box burn aggregates
  that `#908`'s ledger can later consume. Multi-run scope noted in the issue.
- ~~Emission-path decision (#1049)~~ — **closed as invalid premise:**
  no competing emission path exists (F-M7). The open question it tried to
  name — #800's S1 maintenance-minute billability policy — stays inside
  #800's S1 slice.

## What this does not change

The existing filed issues stand: `#376` (spool rotation — still the
hard gate on any meter daemon), `#377` (idle semantics — H13's input),
`#378` (tenant=unknown quarantine — billing integrity), `#368`
(free-tier incident comms), `#800` (G26 fleet stream S4 mapping).
This analysis adds the missing build slices and the decisions that let
them be built once instead of twice. `#905` (H4 provider driver — the
`box_state_transition` source and the long-term `box_wall_clock` producer)
stays open in the provisioning lane; `#800`'s S1 slice keeps the
maintenance-minute billability question.

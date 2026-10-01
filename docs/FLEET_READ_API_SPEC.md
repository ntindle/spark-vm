# Fleet read API spec (G21 S1)

Doc-first; the honesty rules are `docs/POSITIONING.md`'s plus the
G21–G26 analysis's no-fiction contract: everything below is **current
state and work to do**, not promises. Statuses are pinned to the repo as
of this commit. This doc is the S1 slice of G21 (tracked on issue
#795): the design of a read-only fleet API over the estate store — the
first consumer surface for the G16/G17 producer stacks. It designs no
console (S2), no mutations, no auth story beyond the host.

## 1. What the earlier designs already decide (bounds, not repeated)

- **G16 S1** (`fleet/inventory.py`, issue #607): the estate-dir collector
  keeps a JSONL inventory journal (`<store>/journal.jsonl`) plus a
  rebuildable snapshot (`<store>/snapshot.json`). The collector's
  `received_at` on every ingested record is the collector clock — box
  clocks are never trusted.
- **G17 S1** (`fleet/events.py`, issue #608, `docs/UPDATE_EVENT_REPORTING.md`
  §4): the event journal (`events.jsonl`, canonical shape:
  `event_id`, `box_id`, `session_epoch`, `emitted_at`, `received_at`,
  `source`, `component`, `subcomponent`, `subcomponents`, `kind`,
  `outcome`, `from`, `to`, `phase`, `rollout`, `trigger`, `attested`,
  `note`) and the alert journal (`alerts.jsonl`, schema
  `fleet-alert/1`: `alert_id` UUIDv5-stable, `rule`, `fired_at`,
  `box_id`, `subcomponent`, `to`, `detail`, `acked`), with four alert
  rules evaluated on every collect. Alert transport S1: the alert is
  journaled; `fleet events watch` exits nonzero on unacknowledged
  alerts. Rule 3 (silent wave) is **not live** — the `rollout` envelope
  is null on every event until G15 S2.
- **The G21–G26 analysis** (`docs/FLEET_OBSERVABILITY_CONSUMPTION_GAP_ANALYSIS.md`,
  PR #801) decided G21's S1: *"read-only fleet API (`GET /fleet/boxes`,
  `GET /fleet/events`, `GET /fleet/alerts`, `GET /fleet/waves`) over the
  existing estate dir; no new producer, no box-side change."* Its
  acceptance: *"every `fleet` CLI command has an API equivalent
  returning byte-equivalent content."* This spec cashes that acceptance
  out honestly — see §4 for why byte-equivalence means
  field-equivalence, and §3 for which CLI commands have no API
  equivalent and why.
- **The G22 S1 feed spec** (`docs/STATUS_PAGE_FEED_SPEC.md`, PR #810)
  projects the same three journals as a status-page feed; this API is
  the estate operator's read surface, not the status page's. The two
  compose (§7), not compete.
- **Transport precedent** (`confirm/confirmd.py`, `cred-ui/cred-ui.py`,
  `hosted/tenant_status.py`): stdlib `http.server` only, localhost bind
  by default. This API follows the same convention.
- **Not landed:** G15 S2 (wave assignments; the `rollout` envelope is
  null), G24 (no `tenant` field on the stream, no tenant-scoped read
  path), H15's hosted control plane auth. This spec names what the API
  may honestly serve *before* each lands, and what must wait.

## 2. The S1 endpoint inventory

The API is a **pure projection of the store**: read-only, computed at
request time from the estate store's journals + snapshot, no mutable
server-side state, no new producer, no box-side change. Every endpoint
names its CLI counterpart; ordering matches the CLI's (box rows in
`_box_sort_key` order, history newest-first, events in journal order).

| Method + path | CLI counterpart | Response content |
|---|---|---|
| `GET /fleet/boxes?staleness_hours=N` | `inventory --store --staleness-hours` | `boxes[]`: `{box_id, repo_commit` (full + 12-char short, exactly the census bucketing), `toolset_tick`, `frozen` (`true`/`false`/`null` — null is "n/a", never "unknown"), `flags[]` (`stale`, `suspect`), `eligible` bool`}; `census`: `{eligible, total, stale, per_commit[]: {commit, count, pct}}` — the denominator and the exclusions travel with every percentage, exactly as the CLI prints them; `snapshot_generated_at`; `staleness_hours` echo |
| `GET /fleet/boxes/{id}` | `inventory --store --box ID` | `history[]` newest-first: `{observed_at, repo_commit, toolset_tick, suspect}`; unknown id → 404 with `{"error": "box <id> has no records in the journal"}` — the CLI's message verbatim, as JSON |
| `GET /fleet/drift?expected=<commit>&staleness_hours=N` | `drift --store --expected` | `rows[]`: `{box_id, repo_commit, reason}` where reason is one of `policy-held (frozen)`, `deferred (active tenant arc)`, `suspect report (...)`, `unexplained`; `expected`: `{commit, source}` — source is `--expected`, `fleet majority`, the deterministic-tie wording, or `none (no eligible boxes)`; short-form comparison (12-char prefixes, same as the CLI) stated in the response as `commit_matching: "12-char prefix, same as the inventory census"` |
| `GET /fleet/events?box=&wave=` | `events --store [--box] [--wave]` | `events[]` in the canonical journal shape (every field the CLI's event printer renders); `box` filters on `box_id`; `wave` is accepted and answered honestly: while the `rollout` envelope is null (G15 S2 unlanded) the response carries `"wave_filter": "unavailable until G15 S2 (rollout envelope null)"` and returns unfiltered events rather than an empty list — an empty list would be a fiction |
| `GET /fleet/alerts` | `events watch --store` | `{status: "pending" \| "clear", pending_count, alerts[]}` — the alert journal rows with `acked: false` first, then the acked ones the CLI omits, clearly marked; the exit-code contract is explicit: `status: "pending"` ⇔ the CLI would exit 1 |
| `GET /fleet/crosscheck?box=` | `events crosscheck --store [--box]` | `{status: "violations" \| "clean", violation_count, verdicts[]}` — each `{claim, verdict: confirmed \| violation \| inconclusive, evidence}`; the exit-1-on-violation contract stated as `status` |
| `GET /fleet/waves` | *(none — reserved shape)* | 200 with `{"waves": [], "wave_assignments": "unavailable until G15 S2 (rollout envelope null on all journaled events)"}` — the endpoint exists so consumers can code against the path, but it names its own unavailability rather than returning an empty array that reads as "no waves" |

Common envelope on every response: `data_current_as_of` = the newest
`received_at` across the read journals (collector clocks only — same
rule as the G22 S1 feed spec). A store with no journal rows renders
`{"data": "no data"}` semantics — per-endpoint empty arrays plus the
explicit note `"no journaled records; run collect first"`, never a
clean-fleet fiction. Errors are JSON: `{"error": ..., "detail": ...}`.

## 3. What is deliberately NOT API'd in S1

The mutations stay CLI-only in S1 — a read API on an operator's box with
no auth story must not grow write endpoints one at a time:

- `collect` — the scheduler's/operator's job (cron/systemd timer);
  nothing about S1 changes the collection path.
- `rebuild`, `prune`, `events prune` — operator maintenance; a
  localhost CLI is the right privilege shape today.
- `events ack` — the one journal write in the read surface. Acking
  over an unauthenticated API would let any local process silence
  alerts. S1's position: **ack lands with the S2 console, which
  introduces the auth/binding story at the same time.** Until then the
  operator acks via the CLI.

## 4. The equivalence acceptance (honest reading)

The analysis's acceptance — *"every `fleet` CLI command has an API
equivalent returning byte-equivalent content"* — cannot mean literal
byte-equivalence: the CLI renders fixed-width text tables, the API
renders JSON. S1 defines equivalence as **field-equivalence**: every
field the CLI renders for a read command appears in the corresponding
endpoint's response with the same value and the same ordering, and no
field appears that the CLI does not derive from the same journal
record(s). The S2 build slice (issue #795's S1 tracker) ships a
conformance test per endpoint: build a store fixture, run the CLI
renderer, call the endpoint handler, assert field-equivalence. A field
the CLI truncates for display (12-char commits, 10/19-char ticks)
travels **both** truncated (display parity) and full (machine use) —
the truncation rule is documented in the response schema, not hidden.

## 5. Transport, binding, and the no-auth position

- Stdlib `http.server` only (the repo's established convention). No
  new dependencies.
- Binds `127.0.0.1` by default; `--bind` and `--port` flags with a
  suggested default port of **18760**. No auth in S1 — the operator's
  own box is the trust boundary, same as the CLI today. Binding to a
  non-loopback address without an auth story is out of scope for S1
  (and a review blocker if proposed).
- `--store DIR` is required; the API never writes to the store (reads
  take the same read-only posture as the inventory/event journal
  readers — pure readers stay unlocked per the #817 flock discipline).
- No path-version prefix in S1 (`/fleet/*`, not `/v1/fleet/*`): the
  surface is operator-local and the hosted control plane (H15) fronts
  it with its own versioning. Versioning is an S2 decision.
- Errors never leak box-controlled bytes raw: alert `detail` and
  record `note` fields pass through the same control-char stripping
  the alert journal synthesis applies (a crafted audit line can never
  forge an API row).

## 6. What stays out until later slices (named, not punted)

- **Console (G21 S2):** the wave board / alert board consume *this
  API*, not the journals directly — the API is the console's contract.
- **Wave drill-down (G21 S3):** consumes G15 S2's wave assignments;
  until then `/fleet/waves` and the `wave` filter report their own
  unavailability (§2).
- **Tenant scoping (G24):** no `tenant` field on the stream today, so
  there is nothing tenant-scoped to serve; the API is operator-wide.
  When G24's field lands, tenant scoping is a *new* spec slice, not a
  silent parameter.
- **Alert paging (G23):** the API exposes alerts; it does not page.
  Paging is the G23 intake's job.
- **Sentinel/audit (G25):** fleet journals are unsigned; the API serves
  what the journals say, labeled `attested: false` where the records
  say so — it never upgrades the claim.

## 7. Composition with the sibling designs

- **G15/G17/G18:** the API reads what these designs produce; no API
  endpoint changes a producer contract. The `/fleet/events` response
  is the canonical G17 shape; `/fleet/boxes` is the G16 store.
- **G22 S2a (operator page, issue #796):** the operator page consumes
  this API (it is the P7 formal home's operator surface), not raw
  journals. The G22 S1 feed spec stays a direct journal projection —
  the status page's no-fiction contract is hosted/tenant-facing and
  must not inherit this API's operator-wide scope by accident.
- **H14 push:** G23's intake reads `alerts.jsonl` today; `/fleet/alerts`
  is the natural intake once the push daemon exists. The `watch`
  exit-code path stays as the cron fallback (the analysis's S2), not
  the primary.
- **H15 dashboard:** the H15 Boxes panel stays per-box; this API is the
  fleet-era surface the hosted control plane fronts. The two compose,
  not compete.
- **H12 metering:** G26's meter daemon reads the journal; this API is
  operator read tooling, not the metering contract — bounded reads and
  retention alignment belong to G26's S3, not here.
- **P7 ops:** the read-only ops archetype can consume `/fleet/alerts`
  and `/fleet/crosscheck` as its machine-readable health inputs; the
  archetype monitors, this doc designs what it reads.

## 8. Open questions

- OQ1 (from the analysis, carried): does the operator console (G21
  S2) belong in the repo's OSS surface, or does this read API plus
  third-party consoles serve self-hosted estates better? S1 is API
  first either way; the console is revisitable.
- OQ2 — Lifecycle: is the S1 API a long-lived daemon, a
  socket-activated service, or a per-request invocation (`fleet api
  --once`)? S1 names the contract, not the lifecycle — the S2 build
  picks, with the constraint that any lifecycle must keep the
  localhost-only, no-auth, read-only posture (a daemon does not buy a
  bigger trust surface).
- OQ3 — The ack question (§3) is the S2 console's entry ticket: which
  auth story (operator token? SSH-certificate-bound? the confirmd
  trust model?) gates the first write endpoint. S1 takes no position
  beyond "not over this API as specified."
- OQ4 — `expected` for drift: the CLI's fleet-majority stand-in is
  carried verbatim into `/fleet/drift`, but a wave's permitted version
  (G15) will eventually supersede it. When G15 S2 lands, the endpoint
  gains a `wave=`-derived expected and the majority rule becomes the
  fallback — a named future change, not silent drift.

## 9. Gap inventory delta

| ID | Gap | State after this spec | Track |
|---|---|---|---|
| G21 | Operator fleet console (read API + console) — #795 | S1 **designed** (this doc); S2 console + S3 wave drill-down remain queued on #795 | open-source |

G22–G26 unchanged by this spec (G22 S1 landed as PR #810; G22 S2a/S2b/S3,
G23, G24, G25, G26 remain queued on #796–#800).

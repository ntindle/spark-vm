# Filing-upload gap analysis: from proxy refusal to the plane-side record

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `5dc1d93` (2026-10-03 ~23:3x CDT)
and the plane worker checkout
`~/workspace/goals/sparkvm-dev-website-v2-cloudflare-management-infra/control-plane/worker.py`
(the checkout the #846/#873 plane halves were deployed from). Issue/PR
numbers are GitHub references as of 2026-10-03 (not code-verifiable from
the tree). Honesty rules apply (`docs/POSITIONING.md`): this describes
current state and work to do, not promises. Claims stay on the
self-hosted reality until the hosted product exists.

**Non-overlap map (what this doc is not):**
- The full approvals path (request → filing → human answer → terminal
  decision delivery → audit) is
  `docs/APPROVALS_PLANE_GAP_ANALYSIS.md` (#849). This doc walks one leg
  of it: the box→plane filing upload (G49.4 / #876) that the 2026-10-02
  refresh filed and left unowned.
- The plane-side record schema is #872 (closed; endpoints live on the
  deployed plane). The decision wire shape is
  `docs/DURABLE_COMMANDS.md` (#873, closed). Box-side ingest into
  confirmd is `pairing/spark_pair.py ingest` (#874, closed). This doc
  owns none of those.
- Transport choices (WSS phone-home vs HTTPS) are
  `docs/PHONE_HOME_GAP_ANALYSIS.md` (#847). This leg rides HTTPS only.
- The summons outbox journal (`summons-outbox.jsonl`, G4 S1 / #428) is
  append-only and serves the summons observer — the uploader scans
  `confirm/pending/` instead (G76.2), and this doc does not change the
  journal.

## 1. The loop this leg completes

A sensitive agent action travels: proxy refusal → local filing
(`_file_approval`, Finding 49) → **filing upload (this leg)** →
plane-side pending record (#872) → owner sees/taps → decision enqueued
on the durable channel (#873) → box ingest stamps the grant into
confirmd (#874) → the parked agent unparks. Four of the six legs are
built and shipped. The upload leg and the owner see/tap surface are
not: the plane record exists but nothing creates it from the box side,
and the owner can only reach the decision endpoint via raw API.

## 2. State (main `5dc1d93`)

- **Local filing is build-complete.** `proxy/swap_addon.py::_file_approval`
  mints a 16-hex `aid`, writes `confirm/pending/<aid>.json` with
  `credential`, `host`, `method`, `path_prefix`, `created`, a 1-hour
  `expires`, and a summary shaped `"METHOD host path for cred (refused:
  reason)"` — no free text, the tuple comes from the real request
  (Finding 49). Flood control is local: coalesce per (credential, host,
  method), cap 5 pending per credential, one filing per credential per
  60 s (Finding 58). The client's pending signal (`X-Spark-Approval-Pending:
  <aid>`) rides the refusal response (#133/H18).
- **The plane record exists and is deployed.** `_approvals_create` in the
  plane worker: `(box_id, aid)` primary key, retried creates return
  `200 {ok, approval, deduped: true}`; `aid` 1–64 chars
  `[A-Za-z0-9._-]` (the local 16-hex aid fits); `summary` 1–256 chars;
  `detail` opaque JSON ≤ 4 KB; `expires_in_secs` clamped to [60, 3600].
  Server-side expiry is enforced at read.
- **The upload leg has no auth path.** All four approvals endpoints go
  through `_require_owner_for_approvals`; a box token gets
  `401 "a box cannot decide its own approvals"` — a box can never
  decide, read, **or create** its own approvals. The #876 acceptance
  ("upload authenticated as the box, never as the agent") therefore has
  no endpoint to talk to today.
- **Expiry is driven from both sides.** `_expire_approvals` fires on
  owner-authenticated reads (list/get/decide) *and* on the box's own
  box-authenticated command fetch (`_commands_pending`, #873 B2: "the
  box drives approval expiry" — an unattended box learns of expiry on
  its every-minute `ingest` poll, so its records reach terminal expiry
  on schedule without an owner polling).
- **The owner has no action-approval surface.** `hosted/dashboard/`
  shows pairing approvals only (line 115's "Boxes waiting for your
  approval" is enrollment); the decision endpoint exists but the owner
  can only reach it via raw API. Even after the upload leg ships, the
  owner cannot see or tap the pending record without this slice.

## 3. Gaps

Gap classes: `[BUILD]` exists nowhere, build it; `[DESIGN]` design
exists, code does not; `[POLICY]` needs an operator (user) decision.

- **`[BUILD]` G76.1 — no box-authenticated file endpoint.** Create is
  owner-only by deliberate design (the 401 rule is a security boundary,
  not an oversight). **Decision: a dedicated
  `POST /v1/boxes/{box_id}/approvals/file`, authenticated by the box
  token (#846), scoped to the token's own `box_id`,
  create-only.** Response is write-only — `201 {ok, aid, deduped}` —
  never the record body: the "a box cannot read its own approvals"
  invariant stays intact. **Rejected:** relaxing the existing create
  endpoint to accept box tokens. The owner surface's read/list/decide
  endpoints share one auth helper; mixing token classes on one endpoint
  is exactly the confusion the explicit 401 was built to prevent. A
  separate endpoint keeps the file leg's rule explicit and auditable.
  Box-auth accepts `current` **and** `grace` token states — #846's
  15-minute rotation grace must never stall uploads (mirror
  `_commands_pending`'s token classifier).
- **`[DESIGN]` G76.2 — uploader placement.** Two candidates: inline in
  `_file_approval` (the filing write POSTs to the plane immediately) or
  a periodic `spark_pair.py upload-filings` that scans
  `confirm/pending/` and rides the existing `* * * * *` cron (flock-
  serialized, like the heartbeat). **Decision: periodic.** The proxy
  refusal path must not gain plane latency or a plane-failure coupling;
  the #876 acceptance's plane-unreachable degradation ("local filing
  keeps working; uploads queue and retry") falls out of the periodic
  design naturally. An inline first attempt is deferred, not
  forbidden — it buys one cron-interval of latency at the cost of a
  synchronous network call in the hot path; measure before adding.
  **Journal decision:** `upload-filings` scans `confirm/pending/`,
  not the summons outbox journal — the journal (`summons-outbox.jsonl`,
  G4 S1 / #428) is append-only and serves the summons observer, while
  G76.4's pending-only semantics fall out naturally from scanning the
  pending store itself. **Cron wiring:** a separate `* * * * *` cron
  line with its own flock lock file and log, mirroring heartbeat and
  ingest (`_INGEST_LOCK_FILE` pattern) — not folded into `ingest`.
- **`[DESIGN]` G76.3 — payload mapping.** `aid`: the local 16-hex id is
  already the plane's idempotency key — retries return `deduped: true`,
  so the local flood-control caps never multiply into duplicates.
  `summary`: the local summary is **unbounded** (`host` + `path` have
  no length limit) while the plane caps at 256 chars — the uploader
  truncates to 250 + "…", keeping the full tuple in `detail`.
  `detail`: `{credential, host, method, path_prefix, reason, filed_at,
  expires}` — Finding-49 discipline preserved (no free text, tuple from
  the real request), and the same truncation discipline applies to
  detail's `path_prefix`: `host` and `path_prefix` are unbounded on the
  local side and the plane 400s a detail over `MAX_DETAIL_BYTES` (4096)
  with no uploader recovery — truncate `path_prefix` with "…" (keep the
  full host) so a pathological filing can never breach the cap.
  `expires_in_secs`: 3600 (the
  plane's max; matches the local 1-hour expiry).
- **`[DESIGN]` G76.4 — local/plane divergence.** The uploader uploads
  only filings still in `pending/` at upload time — a locally denied,
  expired-stamped, or consumed record is never uploaded. The local
  confirmd store stays the authority for the agent-facing signal; the
  plane record is owner-facing. A record denied locally *after* upload
  stays plane-pending until TTL — the divergence window is bounded by
  the 3600 s plane TTL and needs no extra machinery. The protection is
  **box-side, not the plane's write-once gate**: an owner tapping
  decide on a plane-pending-but-locally-dead record gets a 200 and an
  `approval_decision` command is enqueued — the plane has no way to
  know the local state. The actual gate is ingest's first-terminal-wins
  check (`consumed/<aid>.json` exists → "already terminal locally —
  plane decision superseded, not stamped", `spark_pair.py`). Same
  mitigation covers the uploader's own read-then-POST window (record
  denied between the `pending/` scan and the POST): the upload is
  harmless, the local terminal state wins at ingest, and TTL bounds
  the plane-side ghost.
- **`[WITHDRAWN — not a gap]` G76.5 — expiry for unattended boxes.**
  Withdrawn in Product review: #873 B2 already drives box-side expiry
  from the box's own box-authenticated command fetch (see §2) — the
  new file endpoint needs no `_expire_approvals` trigger. Numbering
  kept stable for the filed issues.
- **`[BUILD]` G76.6 — no owner action-approval surface.** The dashboard
  (`hosted/dashboard/`, inlined into the deployed worker) shows
  pairing approvals only. Slice: a pending-action-approvals section on
  the box detail view (owner session key from `sessionStorage`) with
  decide buttons calling the existing owner decision endpoint. Without
  this, the uploaded record is visible only via raw API — the phone
  tap the #849 vision names has no screen.
- **`[POLICY]` G76.7 — writer identity and display hygiene.** The
  uploader must read from the box-service-owned `confirm/pending/` —
  never from an agent-writable path (the "writer identity is the box,
  never the agent" acceptance). The enforced discipline is the DAC-owner
  one ingest uses (`_ingest_file_owner`: owner ∈ {bdrive, swapd}), not
  literally root. The box token lives in the existing 0600 enrollment
  store. In the other direction: the summary is **box-controlled
  display data** shown to the owner — the dashboard must neutralize it
  through its existing `esc()` (plus control-character stripping) —
  unescaped owner-visible strings are a test-gated template rule in
  `dashboard.html`, and box-supplied summaries get no exemption.

## 4. Slices

- **S1 (this doc):** vision-vs-state + the seven decisions above.
  Non-goals: record schema (#872), decision wire (#873), ingest
  (#874), tenant routing (#69), phone UX (#428 / #797).
- **S2:** plane `POST /v1/boxes/{box_id}/approvals/file` — box-token
  scoped to own `box_id`, write-only response, idempotent on
  `(box_id, aid)`. (No expiry trigger: #873 B2 already drives box-side
  expiry from the command fetch — G76.5 withdrawn.) Box-auth accepts
  `current` **and** `grace` token states (#846: rotation must never
  stall uploads — mirror `_commands_pending`). **Needs the forward D1
  migration `migrate_872.sql` already names**: `owner_id` is
  `TEXT NOT NULL` today and the migration's own comment says "#876's
  box-filing leg will allow NULL here with box-filed provenance
  (forward ALTER, not this migration)" — S2 ships that forward
  migration (`owner_id` nullable, box-filed provenance marker — D1/SQLite
  cannot flip column nullability in place, so this is the table-rebuild
  pattern, not a bare ALTER);
  `owner_id` NULL means box-filed (the box token is the
  provenance), and owner decisions stay owner-keyed.
  Filed as #952.
  **Implemented 2026-10-03 (#952):** the plane now serves
  `POST /v1/boxes/{box_id}/approvals/file` — box-token-authenticated,
  scoped to the path's own `box_id` (wrong-box reads 401), accepting
  `current` and `grace` token states; write-only response
  `201/200 {ok, aid, deduped}` (never the record body — the box still
  cannot read its own approvals); idempotent on `(box_id, aid)`; payload
  bounds shared with the owner create path by construction; `owner_id`
  NULL is the box-filed provenance marker (forward D1 migration,
  table-rebuild). Owner-filed rows always carry a key id; the owner
  read/list/decide surface is unchanged.
- **S3:** `spark_pair.py upload-filings` — periodic scan of
  `confirm/pending/` (not the summons journal — G76.2 decision),
  payload mapping per G76.3 (incl. summary AND
  `detail.path_prefix` truncation), pending-only upload per G76.4,
  box-service-owned paths (bdrive/swapd DAC discipline) per G76.7,
  separate `* * * * *` cron line with its own flock lock + log
  (heartbeat/ingest pattern). Filed as #953.
- **S4:** dashboard action-approval pending list + decide buttons
  (owner session), display-neutralized per G76.7. Filed as #954.
- **S5 (acceptance, stays on #876):** a proxy refusal creates the plane
  record within one uploader interval; retry storms return `deduped`;
  plane down → local approvals unaffected and the upload backlog
  drains on recovery; owner taps decide in the dashboard → #873
  command → #874 ingest → the parked agent's next poll sees the
  terminal signal.

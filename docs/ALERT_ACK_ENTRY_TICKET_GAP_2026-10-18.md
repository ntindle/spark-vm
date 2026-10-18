# Alert-ack entry ticket: vision vs landed state (2026-10-18)

The one journal write in the read surface. Vision (`docs/FLEET_READ_API_SPEC.md`
§3, OQ3, G21 #795): **ack lands with the S2 console, which introduces the
auth/binding story at the same time.** State (main `3ecbf6e2`): the S2 console
shipped read-only by design (`fleet/console.py`: "no write path anywhere in
this module"), ack remains a CLI write (`fleet events ack`), and the auth story
is still unchosen. This doc names the seams and files the build slices —
nothing here re-opens the shipped read-only posture.

## Vision, verbatim

- FLEET_READ_API_SPEC §3: "`events ack` — the one journal write in the read
  surface. Acking over an unauthenticated API would let any local process
  silence alerts. S1's position: **ack lands with the S2 console, which
  introduces the auth/binding story at the same time.** Until then the operator
  acks via the CLI."
- FLEET_READ_API_SPEC OQ3: "The ack question (§3) is the S2 console's entry
  ticket: which auth story (operator token? SSH-certificate-bound? the
  confirmd trust model?) gates the first write endpoint. S1 takes no position
  beyond 'not over this API as specified.'"
- FLEET_READ_API_SPEC §9 gap table (G21 row): "S1 **designed** (this doc); S2
  console + S3 wave drill-down remain queued on #795."

## Findings

- **F-ACK-1 — the premise on which §3 deferred ack is void.** §3's deferral
  assumed the S2 console would "introduce the auth/binding story at the same
  time." The shipped console (`fleet/console.py`, landed G21 S2) enforces a
  loopback `--api` target but introduces **no auth story** — the API it
  consumes is still the unauthenticated localhost surface, and the module
  carries an explicit no-write-path contract. So the ack entry ticket is not
  late: it never got an owner. §3's "until then the operator acks via the
  CLI" is the permanent state unless an auth story is chosen.
- **F-ACK-2 — the actual write path is a journal rewrite, not an append.**
  `ack_alert` (`fleet/events.py:1231`) loads the alerts journal, stamps
  `acked` / `acked_at` (collector clock) / `acked_by`, and rewrites it
  atomically (tmp + `os.replace`) under the store-scoped journal lock —
  explicitly so two concurrent acks cannot clobber each other. This is a
  different discipline from the `events.jsonl` append-only producer contract
  (freeze-hold events, G15 S3: per-publish nonce + `(None, event_id)` dedup).
  The alerts journal is a mutable row store; the event journal is append-only.
  A future console ack endpoint must speak the rewrite discipline, not the
  append one — the two journals' write semantics do not compose by default.
- **F-ACK-3 — re-ack refreshes, not a no-op.** Re-acking an already-acked
  alert overwrites `acked_at` with the new collector clock and re-stamps
  `acked_by`. Idempotent in state (stays acked), non-idempotent in
  timestamps. The stuck-precheck re-fire gate (#928, `fleet/events.py:1184`)
  keys re-paging on `acked_at` ("after an ack, a candidate re-fires only when
  its anchor postdates the ack"), so every re-ack re-extends the suppression
  window. Whether that is intended is unrecorded — it is a decided-behavior
  question, not a bug.
- **F-ACK-4 — provenance is best-effort by design, and the CLI already holds
  the local-process authority.** `_operator_identity()`
  (`fleet/events.py:111`) reads `$USER`/`$LOGNAME`, `_clean_text`-processed
  against control-byte injection, and "MUST NOT fail the ack — provenance is
  metadata, never a gate"; unknown → null `acked_by`, rendered "unknown" in
  the console (`fleet/console.py:172`) and on the status-page feed
  (`STATUS_PAGE_FEED_SPEC.md` §4.3). §3's worry — "any local process
  silences alerts" — applies to the CLI today: local access IS ack authority.
  So the console-write-endpoint debate is not about local processes (they
  already hold the CLI); it is only about remote reachability, which the
  loopback binding already answers. The security delta between "CLI ack" and
  "loopback-bound ack endpoint" is ~zero for the local-process threat model.
- **F-ACK-5 — the composed console→CLI flow already works.** The console's
  alert board prints a copy-pasteable hint per pending alert:
  `fleet events ack --alert-id <id>` (`fleet/console.py:154`; mirrored in
  `fleet/events.py`'s watch renderer). The UX plumbing the inline-ack would
  need (alert id on screen, exactly one shell step away) is already shipped.
  What is missing is only the auth story that would let the console take
  that last step itself — not the interface shape.
- **F-ACK-6 — four consumers key off the acked state.** (1) The console's
  acked tail (clearly labeled as its own addition — the CLI omits acked
  alerts). (2) `fleet events watch`'s exit code: 1 while any alert is
  unacknowledged. (3) The #928 re-fire gate on `acked_at`. (4) The
  status-page feed rows (`STATUS_PAGE_FEED_SPEC.md` §5 lifecycle state).
  Any ack change must preserve all four — the rewrite discipline
  (F-ACK-2) is load-bearing for (3).
- **F-ACK-7 — the host-adjacent ack stories are scoped elsewhere.**
  Plane-side approval records (#872) carry real owner principals; the
  fleet ack is operator-side and stays so. The confirmd trust model named
  in OQ3 is a candidate story, not a dependency — citing it is not claiming
  it.

## Decisions

- **D-ACK-1 — ack stays CLI-only until an auth story is chosen; the console
  keeps its no-write-path contract.** Not because an unauthenticated
  loopback write endpoint would widen the local-process surface (F-ACK-4:
  it would not — the CLI already gives every local process the same
  authority), but because the provenance story is the real gap: a console
  write endpoint without a principal would just mint null-`acked_by` rows
  faster. The auth story is the prerequisite, not the transport. The
  composed console→CLI flow (F-ACK-5) is the shipped answer in the
  meantime; it costs one shell step and preserves F-ACK-6.
- **D-ACK-2 — the three filed issues own the remainders, not this doc.**
  #1703 chooses the auth story (OQ3 build). #1704 decides the
  operator-identity contract behind `acked_by`. #1705 pins the re-ack
  timestamp semantics (F-ACK-3). Until those land, the doc's position is
  the conservative one: no write endpoint, null-by-design provenance,
  refresh-on-re-ack as the recorded current behavior.
- **D-ACK-3 — no claim about the plane.** The phone-approval loop's ack-ish
  semantics (owner decide → `approval_decision` durable commands, #873)
  live on a different trust plane; this analysis does not touch them.

## Gap inventory

| ID | Gap | Filed |
|----|-----|-------|
| G-ACK-1 | OQ3 auth story unowned: which auth story (operator token? SSH-certificate-bound? confirmd trust model?) gates the first write endpoint on the fleet read surface | #1703 (p2, open-source, area:fleet) |
| G-ACK-2 | `acked_by` operator-identity contract: `$USER`/`$LOGNAME` best-effort is unclaimed provenance; when the auth story lands, stamp the real principal | #1704 (p3, open-source, area:fleet) |
| G-ACK-3 | Re-ack timestamp semantics: preserve first `acked_at` or refresh on every ack — the #928 re-fire gate depends on the answer | #1705 (p3, open-source, area:fleet) |

Verification points (main `3ecbf6e2`): §3 at `docs/FLEET_READ_API_SPEC.md:108`;
OQ3 at `:239`; console no-write contract at `fleet/console.py:13-15` and
loopback enforcement at `:72-90`; ack hint at `:154`; `ack_alert` rewrite
discipline at `fleet/events.py:1231-1269`; `_operator_identity` at `:111`;
re-ack refresh at `:1255-1261`; #928 gate at `:1184-1214`; feed rows at
`docs/STATUS_PAGE_FEED_SPEC.md:88,155`.

**Track:** open-source (operator tooling every self-host operator uses).
Issue #795 stays open (G21 S3 wave drill-down still queued; S2 landed).

# Expired approvals as a terminal record (G1 / GitHub #213)

**Status: full implementation** — S1 shipped (#520); S2 shipped (#545);
S3 (human surface: Expired badge card, 410 link, human-drop-off row)
ships with this change (#546). Track:
open-source (confirmd/proxy are self-hosted components; the contract carries
to the hosted plane unchanged). Areas: `confirmd`, `proxy`.

## 1. Problem

An approval's lifecycle has three terminal outcomes — approved, denied,
expired — but only two of them leave a terminal *record*. Approved and
denied are stamped into `consumed/<aid>.json` (`decision: "approve"` /
`"deny"`), visible to the agent via the `X-Spark-Approval-Decision` header
and to the human in the answered history. Expired is a silent third
outcome: confirmd's render reap (`load_pending()`, Finding 58) deletes the
pending file outright, the audit log gets an `expired-reaped` line the
agent never sees, the human gets a bare 410 if they tap an expired card,
and the agent gets nothing machine-readable.

The current `expired:<aid>` leg on the proxy's decision header is a
best-effort observation, not a record: the proxy reports it only when its
own filing scan happened to observe the stale item in `pending/` at scan
time. confirmd's render loop can win the race (load-dependent: agent poll
cadence vs. human list views determine the winner), so in practice the
agent most often sees only a changed `X-Spark-Approval-Pending` id with no
decision header at all — it must *infer* expiry from the pending-id
change (`docs/APPROVAL_CLIENT_SIGNAL.md` §client-flow step 4 documents
this inference rule). Inference is not a contract: a client that misses
the id change (rate-limited poll windows, per-credential flood caps —
both documented no-header windows) cannot distinguish "expired, replacement
pending" from "nothing is happening".

This gap was filed as #213 with an explicit sequencing gate: expiry's
terminal record should be designed once the agent-side pending signal
(#133) existed. #133 shipped (headers + the `consumed/<aid>.json` v1
contract), so the gate is open. The record must be distinguishable from
approved/denied, tenant-scoped, and designed with H10 (multi-tenant
confirmd), not before it.

## 2. Decision: expiry becomes the third decision value in `consumed/`

Stamp the expiry, don't delete it. When an approval expires, the reaper
writes a terminal record at `consumed/<aid>.json` with the same shape as
the answered terminal records, carrying a third decision value:

```json
{
  "id": "<16-hex aid>",
  "created": "<UTC ISO8601>",
  "expires": "<UTC ISO8601>",
  "kind": "grant-request",
  "credential": "<name>", "host": "<host>", "method": "<METHOD>",
  "path_prefix": "<normalized path>", "scope": "<scope>",
  "amount": <n|null>, "job": "<job>", "detail": "<detail>",
  "summary": "<human summary>",
  "decision": "expired",
  "expired_at": "<UTC ISO8601 of the reap>",
  "expired_by": "confirmd | proxy",
  "requester": "<filing process owner name>",
  "tenant_id": null
}
```

Rules on the record:

- **`decision: "expired"`** joins the decision vocabulary (`approve`,
  `deny`, `expired`). This is a deliberate interpretation of
  `docs/APPROVAL_CLIENT_SIGNAL.md`'s versioning rule, not a settled
  reading: the rule's v2 triggers ("changing or removing a field, or
  redefining what any field means") sit next to a contract that pins
  `decision` as "`approve` or `deny`" stamped "at answer time", so a
  third value is arguably a redefinition. This doc proposes the rule
  amendment explicitly: **additive decision values are v1; readers must
  ignore unknown decision values.** The amendment is roll-out safe
  because every existing reader is already fail-closed against an
  unknown value — verified, not assumed:
  - the proxy's `_terminal_denial` requires `decision == "deny"` and
    skips everything else, so an S1-stamped expired record degrades on
    today's proxy to "no terminal-denial signal" — the client keeps
    polling, the owner gets a fresh push (exactly the failure mode the
    v1 contract's drift clause blesses);
  - both answered-history renderers badge only approve/deny and render
    the card anyway;
  - `_answered_api_item` allowlists fields and mints `reopen_csrf`
    only for deny;
  - re-open 400s on non-deny; POST /answer 400s on
    `decision ∉ {approve, deny}`.
- **Do not reuse the answer fields.** `answered_at` / `answered_by`
  describe a human answering; stamping them on an expiry would redefine
  the fields (a real v2 violation). Expiry gets its own `expired_at`
  and `expired_by` (`"confirmd"` for the render reap, `"proxy"` for the
  filing-scan reap).
- **`requester`** is stamped as today (the filing process's owner name,
  via the same `file_owner_name()` mechanism the answer path uses —
  S1 names it as the source for both reapers' stamps). It is the one
  field that lets a tenant-side consumer correlate the terminal record
  back to its own filing if aids are ever lost.
- **`tenant_id: null`** is a reserved field: "unscoped, single-tenant
  host". H10's slice adds the real tenant filter on top of this record
  without a schema migration (see §6).

## 3. Who stamps: exactly-once across the two racing reapers

Two processes can observe an expiry today, and they already race:

1. **confirmd's render reap** (`load_pending()`, Finding 58): serializes
   on the per-aid lock, plain `os.remove`s the pending file.
2. **The proxy's filing-scan reap**: observes the stale item at scan
   time, appends the best-effort `expired:<aid>` leg, attempts its own
   delete of the pending file, and files the replacement.

The stamp must happen exactly once, with no cross-process lock (the
proxy cannot take confirmd's in-process per-aid lock). Protocol — one
mechanism, not two: the winning reaper writes `consumed/<aid>.json` via
`O_EXCL`-guarded create (the loser's create fails with EEXIST and it
moves on). aids are never reused, so write-if-absent is exactly-once for
the aid's lifetime.

- The pending-file delete stays best-effort and stays ordered
  **stamp-then-delete**. The rationale is crash-recovery, not
  double-visibility: delete-then-stamp's hazard is a crash between the
  delete and the stamp, which leaves a lost expiry with no record at
  all — not self-healing. Stamp-then-delete's failure mode is a crash
  between the stamp and the delete, which leaves a stale pending item
  that the next reap re-stamps (EEXIST → skip) and deletes —
  self-healing. The transient double-visibility (record exists while
  the pending item is still listable) is tolerated because the S2
  lookup is aid-scoped, and the steady state already pairs
  `expired:<old-aid>` with `pending:<new-aid>`.
- **Precedence: a human answer always wins over a racing expiry
  stamp.** The answer path (`_answer_locked`) is a third writer into
  `consumed/<aid>.json`: its answered→consumed move uses unconditional
  `os.replace` and must keep doing so — it must NOT be converted to
  write-if-absent. The overlap window is the sub-second TOCTOU between
  the answer path's final `is_expired` check and its write, on the same
  machine clock where the proxy's stamp requires `now >= exp`; in that
  window the grant is already minted, so the approve/deny record is the
  truthful terminal state. S1 carries a contract test pinning this
  precedence (an implementer "fixing" the answer path to write-if-absent
  would invert it).
- Inside confirmd, the stamp happens under the same per-aid lock the
  Finding-58 reap already holds, so the answer path keeps its
  check→mint→consume atomicity and the deadlock audit (one aid lock,
  never nested) is unchanged: the stamp adds no new lock, just a file
  write inside the existing critical section.
- The synchronous human answer path (`is_expired` → 410 + the existing
  `expired-reaped` audit line) is unchanged. (S3) If a terminal expired
  record already exists for the aid, the 410 page links the human to
  the answered history, where S3 renders the expired card (§5).

Which reaper won is recorded in `expired_by`. Operators reading the
audit log (`expired-reaped` lines) can join to the terminal record on
the aid to see which side fired.

## 4. Agent-visible serving: deterministic, from `consumed/`

S2 adds a `_terminal_expiry` lookup to the proxy, parallel to
`_terminal_denial`: newest `consumed/` item with `decision == "expired"`
for the `(credential, host, method, path_prefix)` tuple — "newest" keyed
on `expired_at` (the record's own timestamp), not mtime — served within
the same `APPROVAL_SIGNAL_TTL` (1 hour) window, delivered as the
`expired:<aid>` leg of `X-Spark-Approval-Decision`.

- **Deterministic.** The leg no longer depends on which reaper won the
  race at scan time — it is read from the stamped record. The current
  best-effort filing-scan observation leg is retired when S2 lands
  (keeping both would double-report the same expiry on the proxy-wins
  path). The retired leg fired on the 3-tuple without path scoping;
  S2's `path_prefix` scoping narrows nothing in practice — filing
  coalesces to one pending aid per `(credential, host, method)`, so the
  expired aid's `path_prefix` always matches the tuple it is served
  for.
- **Composition point.** In `_approval_signal_for_refusal`, the
  `_terminal_expiry` signal is *appended* to `_file_approval`'s signals
  — never the deny-style short-circuit. "No veto" implies this; the
  call site must make it explicit so a future reader doesn't copy the
  deny pattern.
- **The inference rule stays valid.** `docs/APPROVAL_CLIENT_SIGNAL.md`
  §client-flow step 4 ("treat a changed pending id exactly like an
  explicit `expired:<old>`") becomes the documented fallback for
  clients behind proxies that have S1 records but no S2 serving yet —
  and for polls that land inside the no-header windows.
- **No veto.** A denial suppresses re-filing inside the window; an
  expiry must NOT. The expired record is terminal *for the aid*, not
  for the tuple: the replacement filing continues (the proxy files it
  on the same pass today), because "the owner didn't see it" is not "the
  owner said no" — re-push is the correct escalation. The client keeps
  waiting on the new pending id. Explicitly: `_terminal_expiry` never
  suppresses filing or pushing.

## 5. Distinguishability from approved/denied

Three outcomes, three unmistakable renderings on every surface:

| Surface | approved | denied | expired (new) |
|---|---|---|---|
| `X-Spark-Approval-Decision` leg | `approved:<aid>` | `denied:<aid>` | `expired:<aid>` |
| `consumed/<aid>.json` decision | `approve` | `deny` | `expired` |
| Human answered-history card | Approved badge | Denied badge | **Expired badge** (S3; distinct style, shows `expired_at` + `expired_by`) |
| Audit log | answer line | answer line | `expired-reaped` (unchanged; joinable on aid) |
| Re-filing behavior | n/a (grant minted) | suppressed 1h (anti-nag) | **never suppressed** (§4) |

The header leg values keep the client contract's existing
`\A[A-Za-z0-9_-]{1,64}\Z` validation and the strip-upstream-headers
rule — nothing new is forgeable.

Interim state (between S1 and S3): S1-stamped expired records already
render in the answered history as badgeless cards — the renderers badge
only approve/deny and render everything else anyway, so the record is
degraded-but-visible, not invisible. That is the intended fail-closed
behavior, not a bug; S3 adds the Expired badge.

## 6. Agreement with `human-drop-off` (TENANT_STATUS_ENDPOINT §5)

`human-drop-off` is the human-side rendering of the same event this doc
instruments agent-side. The two agree by construction:

- **Same id.** The terminal record's `id` is the aid the summons
  (G4's deep link) carried — the G1 instrumentation requirement from
  `TENANT_STATUS_ENDPOINT.md` §5.
- **Same TTL boundary.** The expiry instant is the spec's boundary
  (`confirm-request --ttl`, default 3600s; `FIRST_TEN_MINUTES_SPEC.md`
  §4: one reminder at T+TTL/2, then expiry). The terminal record's
  `expired_at` is the measured instant of that boundary.
- **Same escalation semantics.** The client flow already documents that
  a client MAY stop after repeated expiries and report `human-drop-off`
  rather than wait forever — with the terminal record, "repeated
  expiries" becomes countable (N stamped `expired` records for the task's
  aids) instead of inferred.

## 7. Tenant scoping and the H10 carry

Today `consumed/` is host-global and single-tenant: aids are 16 random
hex chars, unguessable, and the aid is a correlation id, never a
capability — `confirmd` stays owner-auth gated. This design preserves
that invariant: the expired record carries no new authority.

The H10 (multi-tenant confirmd) carry is deliberately thin:

- The record's `tenant_id: null` reserves the field. When H10 lands,
  reapers stamp the real tenant id and the S2 lookup filters on it.
  No migration: null means "unscoped", which is exactly today's
  semantic.
- The S2 lookup's tuple match (`credential, host, method, path_prefix`)
  gains `tenant_id` as a conjunct in the H10 slice — the same shape as
  the deny lookup's future tenant conjunct, so both terminal lookups
  evolve together.
- The design must not be implemented tenant-aware before H10: building
  the filter early would invent the tenant boundary H10 owns. The
  reserved field is the whole of the pre-H10 tenant story.
- "No migration" is true for the schema, not the semantics: H10 still
  owes the visibility rule for legacy `tenant_id: null` records — a
  post-H10 operator must know whether null records are visible to every
  tenant (fail-open for history) or to none (fail-closed). That
  decision belongs to H10's design, and this doc names it as owed.

## 8. Retention

Expired records ride the existing `consumed/` machinery unchanged:
`CONFIRM_CONSUMED_KEEP` (default 1000) rotation, the answered-sweep
grace discipline, the mtime pre-filter the proxy's lookup already uses.
An expired record is the same size class as an answered record, and
expiry volume is bounded by filing volume — no new retention policy is
needed. If S3 surfaces expired items in the answered history, they
count against `_ANSWERED_FEED_LIMIT` like answered items (they are
terminal history, not a second feed).

## 9. Build slices (for the fix/feature track, not this doc)

1. **S1 — stamp the record (confirmd + proxy).** confirmd's Finding-58
   reap and the proxy's filing-scan reap both do write-if-absent
   `consumed/<aid>.json` with `decision: "expired"`, `expired_at`,
   `expired_by`, `tenant_id: null`, stamp-then-delete ordering; the
   `expired-reaped` audit line stays. Tests: contract tests on the
   record schema (decision vocabulary, required fields, no
   `answered_*` fields on expired records); race tests proving
   exactly-once under the two-reaper race (one record, one delete);
   precedence test: a human answer racing an expiry stamp keeps the
   approve/deny record (the answer path's unconditional `os.replace`
   wins); regression: today's `_terminal_denial` ignores the new records
   (fail-closed on pre-S2 proxies).
2. **S2 — serve the record (proxy).** *Shipped (PR #545, merged).*
   New `_terminal_expiry` lookup parallel to `_terminal_denial`, same TTL
   window, same mtime pre-filter, "newest expired wins" keyed on
   `expired_at`; the best-effort filing-scan `expired:<aid>` leg is
   retired; composed in `_approval_signal_for_refusal` as an append to
   `_file_approval`'s signals (never the deny-style short-circuit);
   `docs/APPROVAL_CLIENT_SIGNAL.md` updated (decision vocabulary,
   the inference rule becomes the documented fallback, the
   no-suppression rule). Tests: newest-expired-wins over the tuple,
   TTL expiry of the leg, path-scoping parity with the deny lookup,
   expired-never-suppresses-filing.
3. **S3 — human surface.** *Shipped (this change, #546).*
   Answered-history Expired badge card (distinct amber style from
   Approved/Denied; shows `expired_at`, `expired_by`); the two
   synchronous expired 410s (GET detail, POST answer) link to the card
   when a terminal expired record already exists for the aid;
   `TENANT_STATUS_ENDPOINT.md` §2 `human-drop-off` row cites this doc.

## 10. Open questions

- **Q1 (S2):** should the expired leg ride the same 1-hour
  `APPROVAL_SIGNAL_TTL` as denials, or a shorter window? Denials need
  the hour for anti-nag; expiries never suppress, so the window only
  bounds how long a stale client keeps hearing about an old expiry.
  The noise side also includes the no-header windows (per-credential
  flood cap, 60s filing rate limit), which can hide the leg from
  polling clients — the changed-pending-id inference fallback covers
  that, but the staleness-vs-noise trade the question poses is
  slightly incomplete without it. Proposal: same window (one constant,
  one mental model), revisit if the leg proves noisy.
- **To-verify (S1, not an open question):** the proxy's write-if-absent
  needs the same aid filename validation confirmd uses — confirm both
  sides validate `\A[A-Za-z0-9_-]{1,64}\Z` before touching `consumed/`.
- **Q3 (S3):** expired cards in the answered history vs a separate
  expired list — proposal is in-history with the Expired badge (§8:
  terminal history, not a second feed), but a human-factors pass may
  prefer a filter toggle.

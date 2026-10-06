# Push-lane convergence: the #849 phone-approval loop, vision vs state

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `0edb0eb` (2026-10-05 ~19:0x CDT,
post-#1060 merge) and the #1062 branch tip `62fdd982` (rebased); #1062 has
since merged as `a366aba` (2026-10-05 ~19:4x CDT). Issue/PR numbers are GitHub references as of 2026-10-05 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. Nothing here
sends a push.

**Non-overlap map (what this doc is not):**
- `docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md` — the original GP1–GP4
  decomposition of the missing sender (2026-10-04). This doc supersedes
  its §3 "gaps filed" status column only; the D1–D7 decisions stand.
- `docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md` — GP3's working paper
  (taxonomy + anti-spam bounds). This doc consumes it, not replaces it.
- `docs/APPROVALS_PLANE_GAP_ANALYSIS.md` — the approvals decision path
  (filing, records, durable channel, dashboard). The push plane carries
  nudges; state and decisions stay there.
- The S4b socket lane (`docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md`,
  #1000/#1001/#1002) — the decision→box return path rides the socket;
  this doc assumes it and does not re-analyze it.

## 1. The vision (#849)

Per-action consent: when the agent attempts a sensitive action, the owner
gets an approval prompt on their phone — approve/deny with a tap. Not
blanket lockdown; the agent keeps working otherwise.

Acceptance (#849, verbatim):
- Sensitive actions pause until approved/denied.
- Deny is safe and logged; agent gets a clear refusal it can report.
- Approval requests expire.

The loop in one line: **the agent files → the owner's phone buzzes →
two taps → the agent unparks — without the approvals page open.**

## 2. Vision vs state (pinned 2026-10-05)

| Leg | State |
|---|---|
| Filing → plane record | SHIPPED: box→plane filing upload (#952), plane-side records (#872) |
| Owner decide surface | SHIPPED: dashboard box card approve/deny (#954) |
| Decision → box | SHIPPED: `approval_decision` on the durable channel (#873), box ingest (#874); socket-lifecycle slices #1000/#1001/#1002 in flight |
| The buzz — crypto | SHIPPED: stdlib-only RFC 8291 `aes128gcm` (`hosted/push_crypto.py`, #967 S1 validation; RFC 8291 §5/Appendix A KATs, NIST AES-GCM vector, RFC 6979 KAT, pinned golden body) |
| The buzz — transport | SHIPPED: `hosted/push_sender.py` (#989 closed): RFC 8030 POST, `send_push`, `PushResult` taxonomy (accepted / retry / tombstone / dead-letter), `backoff_s`, `parse_retry_after`, `acceptance_fields` feeding #428's §4 retirement, subscription validation, no-`Topic`, 30 s response deadline (#1039), 408→retry (#1040) |
| The buzz — payload discipline | SHIPPED: `hosted/push_payload.py` (#970, GP4): construction-time scrub |
| The buzz — schema | SHIPPED: `docs/PUSH_SENDER_SCHEMA_CONTRACT.md` (#988, PR #1059 merged): four D1 tables, custody D45–D47, VAPID lifecycle D48, forward migration D49 |
| The buzz — enqueue boundary | SHIPPED: `hosted/push_enqueue.py` (#990, PR #1060 merged 2026-10-05 ~19:0x CDT): atomic D10 budget reservation (single-statement, D1-batch portable), `enqueue_page` with partial-unique-index page-once dedup (D57), digest backpressure |
| The buzz — event→push mapping | SHIPPED: `hosted/push_events.py` (PR #1062 squash-merged `a366aba` 2026-10-05 ~19:4x CDT): one mapping function per taxonomy §2 paging event, D8 reminder timing, D12 gate-1 re-read, D61 `suppressed_terminal` audit, D62 quiet period, D54 digest trigger — policy only, all paging through the #990 boundary |
| The buzz — **sender loop** | **OPEN (#967 remaining):** the worker-side loop that claims `queued` outbox rows, fans out per `(owner_principal, box_id, device)`, executes `send_push`, schedules `retry` per `backoff_s`, tombstones on 410, and writes send-result rows. Crypto + transport + schema + boundary + mapping are all done; the loop that drives them is not. |
| Subscriptions | OPEN (#968): owner-auth subscription endpoints + dashboard subscribe affordance. Also the subscription-store D1 half of #967. Blocked on the operator's Worker-secret data key (custody §3; the loop must not generate it — standing NEEDS_USER entry). |
| Reminders/digest scheduler | **UNFILED → filed this turn (§3):** D9's cron sweep has no owner. |
| Digest assembly + delivery | **UNFILED → filed this turn (§3):** `maybe_enqueue_digest` fires a `digest` page, but nothing assembles the digest body or delivers it. |
| Retention + GC | OPEN (#1058, filed): 90-day retention for the four D1 tables. |
| Contract amendment | OPEN (#1061, filed): §1.3 `queued` third extension + D57 index in `migrate_967_push.sql`. |

## 3. Gaps filed this turn

- **[NEW] #1063 — D9 sweep wiring: reminder/digest scheduler home.** D9
  (`docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md` §4) pins "cron-sweep
  scheduler first; DO alarms later": a per-minute scheduled worker entry
  scans the D1 database for due reminders (`created_at + TTL/2`, TTL ≥
  300 s) and calls `maybe_enqueue_reminder`, plus fires
  `maybe_enqueue_digest` per owner-hour. Unbuilt: no caller exists —
  the #1062 functions are policy with no cadence. Scope includes the
  `deploy_worker.py` cron-trigger support (D9 names it as inside the
  slice, not a separate item) and the retirement rule for the later DO
  adoption (retire or feature-gate the cron sweep in the same change, or
  reminders double-fire). **Acceptance:** a due reminder pages exactly
  once without a human driving it; a decided/expired approval pages zero
  times.
- **[NEW] #1064 — digest assembly + delivery (D54).** `maybe_enqueue_digest`
  enqueues an event-kind `digest` page (key = window start) when
  `push_digest_state.count > 0`, consuming owner budget like any page.
  Unbuilt: nothing reads the coalesced rows and composes the digest
  body ("N approvals need you" + the per-box breakdown), nothing
  delivers it through the sender loop, and nothing resets
  `push_digest_state` after delivery. The digest page is currently a
  normal page with no content assembly behind it. Scope: assembly
  (payload built under the #970 scrub discipline), delivery through the
  #967 sender loop, and the `push_digest_state` reset contract.
  **Acceptance:** an hour with >budget pages produces exactly one digest
  send whose body enumerates the coalesced approvals; the digest state
  row resets; no duplicate digests for the window.

## 4. What this does not claim

- **No hosted approval currently pages anyone.** The buzz leg is policy,
  schema, crypto, transport, and boundary — all in-repo, none deployed.
  The sender loop (#967 remaining), subscriptions (#968), the D9 sweep,
  and digest assembly are all unbuilt; the plane worker has no push code.
  The two-tap loop works only with the dashboard page open (#954).
- The 60-minute approval TTL ("a race against push") remains a race the
  plane cannot win until the sender loop + subscriptions + sweep land.
  Shortening the TTL before then strands approvals faster, not better.
- #428's §4 retirement criterion (a plane-recorded push-service-accepted
  delivery, 201, for the tenant) is satisfiable *by construction* once
  the sender loop writes `accepted` rows — it has never flipped, because
  no send has ever happened.
- This doc files two issues and changes no code; the #849 loop's
  end-to-end acceptance (file → buzz → tap → decide → unpark, with a
  real push) belongs to the #967 sender-loop slice, not here.

# Push-lane convergence, 2026-10-10: the #849 phone-approval loop

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `08422db` (2026-10-10 ~00:2x CDT).
Issue/PR numbers are GitHub references as of 2026-10-10 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. Nothing here
sends a push.

This document refreshes `docs/PUSH_LANE_CONVERGENCE_2026-10-05.md` — its §2
state table is superseded by §2 below; its §4 honesty framing still holds.
It files no new issues and changes no code: every remaining gap below is
already tracked by an open issue.

**Non-overlap map (what this doc is not):**
- `docs/PUSH_LANE_CONVERGENCE_2026-10-05.md` — the previous refresh
  (2026-10-05); superseded for state only.
- `docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md` — the original GP1–GP4
  decomposition (2026-10-04). D1–D7 decisions stand.
- `docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md` — GP3's working paper
  (taxonomy + anti-spam bounds). Consumed, not replaced.
- `docs/MULTI_TENANT_PLANE_MODEL_DECISION.md` — the 2026-10-09 tenancy
  record (D-MT1: one plane per tenant). Its "Consequences for the
  gated slices" section amends #968's framing; this doc records the
  amendment, not the decision.
- `docs/APPROVALS_PLANE_GAP_ANALYSIS.md` — the approvals decision path
  (filing, records, durable channel, dashboard). The push plane carries
  nudges; state and decisions stay there.
- The S4b socket lane (`docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md`,
  #1000/#1001/#1002 — all closed) — the decision→box return path rides
  the socket; this doc assumes it and does not re-analyze it.

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

## 2. Vision vs state (pinned 2026-10-10)

| Leg | State |
|---|---|
| Filing → plane record | SHIPPED: box→plane filing upload (#952), plane-side records (#872). Unchanged since 2026-10-05. |
| Owner decide surface | SHIPPED: dashboard box card approve/deny (#954). Unchanged. |
| Decision → box | SHIPPED: `approval_decision` on the durable channel (#873), box ingest (#874); socket slices **all closed** — S4b-1 hello/identity+generation fence (#1000, PR #1055), S4b-2 re-drive + ack consume-half (#1001, 2026-10-07 wire pins), S4b-3 ping/alarm revocation re-verify + Hibernation WebSocket keepalive (#1002, wire-protocol §4/§6 pins 2026-10-09). The return path rides the socket per wire-spec §3.3. |
| The buzz — crypto | SHIPPED: stdlib-only RFC 8291 `aes128gcm` (`hosted/push_crypto.py`, #967 S1 validation). Unchanged. |
| The buzz — transport | SHIPPED: `hosted/push_sender.py` (#989): RFC 8030 POST, `PushResult` taxonomy, `backoff_s`, 30 s deadline (#1039), 408→retry (#1040). Unchanged. |
| The buzz — payload discipline | SHIPPED: `hosted/push_payload.py` (#970, GP4). Unchanged. |
| The buzz — schema | SHIPPED: `docs/PUSH_SENDER_SCHEMA_CONTRACT.md` (#988) **as amended by #1061** — §1.3 outcome vocabulary now three-valued: the D50 `queued` outbox work item, the D57 page-once partial-unique index (outcome predicate pinned to #990's shipped statement), the D61 audit-key non-collision rationale, the operator DROP/CREATE migration note. |
| The buzz — enqueue boundary | SHIPPED: `hosted/push_enqueue.py` (#990). Unchanged; D76/D77 digest-gap closes landed here-adjacent (see sweep row). |
| The buzz — event→push mapping | SHIPPED: `hosted/push_events.py` (#969). Unchanged. |
| The buzz — **sender loop** | **LANDED IN-REPO** (`hosted/push_send_loop.py`, adopted #1102, bc17b2e): tick-shaped loop — per-(box, device, work-item) fanout (D56c), terminal transaction with reservation release (D56b), retry pacing off the #989 backoff (D82), outcomes `accepted`/`tombstone`/`dead-letter`, D12 gate-2 terminal-state re-read per send, per-device attempt rows. Claiming (D56a): the loop claims `queued` rows but ships no claim mechanism — the PushSenderDO-singleton claiming design is pinned in `docs/PUSH_SENDER_CLAIM_DESIGN.md` (#1094), the mechanism build is open. D87 — digest reset on delivery: a `digest` page's completion (all devices terminal, any outcome) zeroes `push_digest_state.count` for the window in the terminal transaction (fail-closed guard caught the missed parked path mid-dev); zero-not-delete preserves the sweep's never-refired pin. D88 — digest content-scope design position: the body is count-scoped per contract §1.4; per-box breakdown is not built on the frozen #988 schema (digest pages enqueue with `box_id` NULL — per-box fanout is unimplementable without a schema change, D89); owner adjudication on #1064. **#967 stays OPEN**: its acceptance is #428's §4 retirement criterion flipping, which needs a deployed caller + claim mechanism — the loop has neither yet. |
| D9 sweep — **scheduler home** | **LANDED IN-REPO** (`hosted/push_sweep.py`, #1095/#1104): three passes per sweep — reminders, digests, watchers (D67/D74) — over `sweep_once`, returning a `SweepSummary`; overlapping sweeps are safe-not-prevented (D69; D57 page-once + D61 idempotent audit make a second sweep a no-op); per-candidate error isolation so one bad candidate cannot sink a pass (#1095). D76 — pending-window scan (`count > 0`, `enqueued_at` NULL, oldest first; late fire uses the window's own page-once key against the current-window owner budget) and `enqueued_at` stamped on page accept; D77 — suppression audit rows carry the U+0000-suffixed key so a budget-suppressed digest no longer wedges its window. **#1063 stays OPEN** until #1069 lands the D72 cron trigger — the sweep module's own docstring pins this: "#1063 stays open until #1069 lands the 'without a human driving it' half of the acceptance criterion." |
| Subscriptions | OPEN (#968, p2). **Reframed by the tenancy record**: per D-MT1 (one plane per tenant) subscriptions stay owner-keyed on the tenant's plane — D3 (one VAPID identity per plane) unchanged, no tenant dimension added to the subscription schema, the #988 contract stands as written (`docs/MULTI_TENANT_PLANE_MODEL_DECISION.md`, "Consequences for the gated slices"). What remains: owner subscription endpoints + dashboard subscribe affordance on the tenant plane. Still blocked on the operator's data key (standing NEEDS_USER entry). |
| Digest assembly + delivery | Reset half DONE (D87, above). Content half OPEN on #1064 (D88 design position; the issue stays open for the owner's adjudication — `Closes` downgraded to `Refs`). |
| Retention + GC | OPEN (#1058, p3): 90-day retention for the four D1 tables. Unchanged. |

## 3. What is still unbuilt (the honest list)

1. **The live caller + claiming** — D72's per-minute `scheduled` cron
   trigger plus the deploy-side trigger-registration check (**#1069**,
   p2), and the PushSenderDO claim mechanism build (design pinned in
   #1094). Without them the sweep and sender loop are in-repo Python
   with no cadence and no mutual exclusion; #1063's "without a human
   driving it" acceptance half is the gate.
2. **Subscriptions** (#968, p2) — owner subscription endpoints + dashboard
   affordance on the tenant plane, under the D-MT1 framing; blocked on the
   operator data key (NEEDS_USER).
3. **Retention/GC** (#1058, p3).
4. **Digest content** (#1064) — D88's design position awaits the owner's
   adjudication.
5. **#967's acceptance** — #428's §4 retirement criterion flips when a
   plane-recorded push-service-accepted delivery exists; that needs 1–2
   plus the deployed sender path.
6. **End-to-end acceptance** — the full loop (file → buzz → two taps →
   unpark, with a real push) also depends on #847's S6 live acceptance
   on the phone-home lane (#958/#960), which is a separate open item.

## 4. What this does not claim

- **No hosted approval currently pages anyone.** The buzz leg is now
  crypto + transport + scrub + schema + boundary + mapping + sender loop
  + sweep — all in-repo, none deployed. Nothing in the repo deploys
  these modules; the deployed tenant plane has no push code.
- The 60-minute approval TTL ("a race against push") remains a race the
  plane cannot win until #1069 + #968 land. Shortening the TTL before
  then strands approvals faster, not better.
- #428's §4 retirement criterion has never flipped: no send has ever
  happened. It becomes satisfiable *by construction* once the sender
  loop writes `accepted` rows against a live tenant plane.
- This doc files no new issues and changes no code.

## 5. Issue-hygiene note (carried, not filed)

The #967 issue body still carries the S1 design scope with the
unvalidated mechanism hypothesis (WebCrypto vs vendored P-256/AES).
The GP1 validation landed months of work ago — in-worker sender,
stdlib-only, ~38 ms/send — but the body was never rewritten. That is
issue maintenance for a repo turn (body refresh, not a new gap): no
new issue filed here. A future repo turn's P2 sweep may refresh it;
until then, readers of this doc should treat the §2 table above, not
#967's body, as the state record.

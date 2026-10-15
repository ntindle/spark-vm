# Owner-visible alerting for the hosted lane

**The alert contract an owner sees for their box** — pinned to main
`f6bdaa7` (2026-10-14 20:55 CDT) for all in-repo claims; every in-repo
claim below was verified against that tree this turn. Issue numbers are
GitHub references as of 2026-10-14 (state verified via direct GET this
turn for every issue named). Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work to
do**, not promises. The hosted product is not live, and no hosted box has
been provisioned by this lane.

**Non-overlap map (what this doc is not):**
- `docs/PUSH_EVENT_TAXONOMY_GAP_ANALYSIS.md` (#969 / GP3) — the
  event→push mapping and anti-spam bounds that the push lane enqueues
  through. This doc names which of those reach the *owner* and through
  which channel; it does not re-decide the taxonomy.
- `docs/ALERT_PUSH_FANOUT_SPEC.md` (G23 S1 / #797) — the *operator*
  (fleet) intake into the H14 push plane. Different consumer, different
  queue, different lane; this doc is tenant-owner-only.
- `docs/PROVISIONING_LANE_CONVERGENCE_2026-10-14.md` (#851) — the
  provisioning lane's vision-vs-state; this doc consumes its findings
  (notably #1489) without re-analyzing the lane.
- `pairing/README.md` §"Verification (healthy box)" (#1488 / #1273) —
  the *box-side / operator-side* contract (supervisorctl, logs,
  tick-failure signals). This doc is the plane-side owner view of the
  same failure classes; where the owner sees nothing today, §2 says so.

## 1. The alert classes

An owner's box can demand their attention in eight ways. Each class below
names its source signal, its page/digest/chip behavior, and whether it
exists today or lives in an open issue.

| Class | Source signal | Channel today | Owner action | Tracked |
|---|---|---|---|---|
| approval filed | `hosted/push_events.py::on_approval_filed` — the mapping exists and is tested, but no caller invokes it: the #952 filing endpoint records the filing and returns | no page fires — caller unwired (#1492) | Decide it in the dashboard pending card (#954); the push page fires once the caller is wired | mapping shipped (#1062), caller unwired |
| approval reminder | sweep reminder pass → `maybe_enqueue_reminder` | push page, D12 two-gate lease | Decide the pending approval; reminders stop when it goes terminal | shipped (#1062) |
| hourly digest | sweep digest pass → `maybe_enqueue_digest` | digest | None required — informational summary | shipped (#1062) |
| heartbeat stale | sweep watcher pass → `on_heartbeat_stale` | push page + dashboard `Stale` chip | None defined today: the repo names no owner-facing recovery for a stale box; it heals when heartbeats resume | shipped (#1062) |
| box revoked | `hosted/push_events.py::on_box_revoked` — the mapping exists and is tested, but the revoke endpoint only stamps `revoked_at` and never calls it | no page fires — caller unwired (#1492) | Re-pair the box (request + redeem) — revocation is one-way | mapping shipped (#1062), caller unwired |
| token-expiry warning | sweep watcher pass → `on_token_expiry_warning` | push page, once per token generation | Advance notice, not a dashboard fix: the box's hourly auto-rotation has failed; a 401 in the rotate output means re-pair, a 403 means the box clock is off | shipped (#1062) |
| provisioned, never paired | provision record + attestation-token TTL, plane-side | nothing | Owner action when #1214 ships: [TBD] | open — #1214 |
| phone-home died, heartbeat still fresh | `phone_home_events` DO journal terminal closes + valid token + fresh heartbeat, plane-side | nothing | Owner action when #1489 ships: [TBD] | open — #1489 |

## 2. Per-class detail

**Approval filed.** An *approval* is a decision your box's agent asks you
to make (the `aid` in the page key is the approval's id —
`docs/APPROVALS_PLANE_PROTOCOL.md` pins the record: agent action on a box
→ owner taps approve/deny → the decision travels back to the box). **Owner
action:** open the pending approval card (the dashboard's Approve/Deny
surface, #954) and decide; the page resolves when the approval reaches a
terminal state. The `on_approval_filed` mapping (`hosted/push_events.py`)
exists and is tested — page-once per (box_id, aid) via the #990 boundary's
page-once dedup (D57) — but **no caller invokes it**: the #952 filing
endpoint records the filing and returns (verified: zero call sites in the
repo, every parallel worktree, and the deployed plane worker checkout).
The push page never fires; wiring the caller is tracked on #1492. Caller
obligation for whoever wires it (documented at the mapping): never emit a
filing event for an aid whose #872 record is already terminal — there is
no gate-1 re-read on this path by design (filing *is* the plane's own
write), so a terminal aid filed here would page spuriously.

**Approval reminder.** **Owner action:** same as approval filed — decide
the pending approval; reminders stop when it goes terminal (the sweep's
gate-1 re-read never pages a decided record). The sweep fires
`maybe_enqueue_reminder` at `created_at + TTL/2` (D8; TTL ≥ 300 s — the
shipped constants are APPROVAL_TTL=600 s default, APPROVAL_TTL_MIN=60 s
floor). The D12 two-gate lease applies: the sweep gate re-reads the
record's terminal state, and the send gate re-reads it again; a lease lost
between gates writes an idempotent `suppressed_terminal` audit row (D61).
Reminders consume D10 budget — there is no reminder exemption.

**Hourly digest.** **Owner action:** none required — an informational
summary of the window's pages. `maybe_enqueue_digest` fires the D54
digest trigger. The digest pass scans pending windows (D76 — count > 0,
`enqueued_at` NULL, oldest first, so a window that fills late is not
stranded), and a suppressed digest's audit row uses the suffixed
U+0000-suppressed key (D77) so outcome-blind dedup never wedges a future
retry. Late fire uses the window's own page-once key and consumes
current-window owner budget.

**Heartbeat stale.** **Owner action:** none defined today. The repo names
no owner-facing recovery for a stale box; the dashboard names the state
(`Stale` chip) and the box heals when its heartbeats resume. The sweep's
watcher pass calls `on_heartbeat_stale` once per stale-epoch, with the F7
4-hour quiet period after a page before the same box can page again on a
new epoch. The dashboard's chip is a separate, much faster signal:
liveness is heartbeat-only (`docs/PHONE_HOME_WIRE_PROTOCOL.md` §8 — the
plane's last-confirmed-heartbeat timestamp is the ONLY freshness signal;
the socket must not write or refresh it), and the dashboard marks a box
`Stale` after 300 s of silence (`STALE_AFTER_S` in
`hosted/dashboard/dashboard.html`). So an owner sees staleness in minutes
on the dashboard and, if it persists, a push page hours later — two
different thresholds, one fast and local, one slow and plane-verified.

**Box revoked.** **Owner action:** re-pair the box (`request` + `redeem`)
— revocation is one-way (pairing/README.md), and the box cannot come back
any other way. The `on_box_revoked` mapping (`hosted/push_events.py`)
exists and is tested — once per full ISO-8601 `revoked_at` timestamp (a
bare date could repeat across same-day revocations and silently collapse
them) — but **no caller invokes it**: the revoke endpoint stamps
`revoked_at` and the token 401s everywhere immediately, never calling the
mapper. The revocation page never fires; wiring the caller is tracked on
#1492. D65 caller obligation for whoever wires it: never call this for
the keyless-grandfathered path. A revoked box's heartbeat 401s too, so
the dashboard degrades alongside the (currently unwired) page.

**Token-expiry warning.** **Owner action:** none available from the
dashboard — this is advance notice, not an owner-actionable fix. The box
rotates its own token hourly (`rotate --auto`, #846), so a warning means
auto-rotation has failed (GP3 F6: the warning fires only when the token
is within 2h of expiry AND no successful rotation happened since the
last heartbeat window). If the token dies, the box's next tick 401s and
the box must be re-paired; a 403 means the box clock is off and a retry
leaves the token untouched (pairing/README.md's rotate contract). The
sweep fires `on_token_expiry_warning` with a 2-hour lead, keyed on the
boxes row's current token_hash — the generation (D13). A rotation changes
the hash, which resets the warning key by construction; the F6
no-rotation-since-last-window check is the caller's timing decision,
staying plane-side.

**Provisioned, never paired (#1214, unbuilt).** The hooks fail-closed on
absent identity env is `exit 0 + loud log` (deliberate — the image is
dual-use, self-hosted vs provisioned). The plane-side backstop keys off
the provision record (#1089): a record created with an attestation token
that never yields a pairing request or heartbeat past the token TTL is a
failed provision or a silently-unenrolled box, and fires an
owner/operator-visible alert. No signal exists on the dashboard for this
today; the dashboard's box list only renders boxes that have heartbeated
(the `No heartbeat` pending chip covers boxes with no heartbeat *record*,
not records with no box).

**Phone-home died, heartbeat still fresh (#1489, unbuilt).** The #1488
healthy-box contract's human-attention class — `pair-phone-home` EXITED
exit-1 (revoked token, `superseded-generation`, identity-mismatch /
protocol errors) — is supervisord state an owner never sees: on a
provisioned box there is no human watching `supervisorctl`, and the
heartbeat keeps 200ing through valid-token terminal closes (verified:
`cmd_heartbeat` sends only `_status_body`; the dashboard renders liveness
purely off `heartbeat_at` and names no phone-home state at all —
`grep` over the dashboard source confirms zero phone-home references).
The suggested shape keys off the `phone_home_events` DO journal (#999):
terminal closes for boxes whose token is still valid AND whose heartbeat
is still fresh. The no-restart design stands (#1488: EXITED exit-1 is
never a restart target); a `superseded-generation` close is expected
during clean generation bumps — the box reconnects with generation+1 —
so only the no-reconnect-after-close window should page, not every
close.

## 3. Channel matrix

| Class | Dashboard chip | Push page | Digest |
|---|---|---|---|
| approval filed | pending card in approval list (#954) | no — caller unwired (#1492) | — |
| reminder | pending card (until terminal) | yes, D12-leased (only when the sweep is driven) | coalesces here when over budget (D10) |
| digest | — | — | yes (only when the sweep is driven) |
| heartbeat stale | `Stale` chip at 300 s | yes, once per stale-epoch (F7 quiet period; only when the sweep is driven) | — |
| box revoked | chip degrades with the 401ing heartbeat | no — caller unwired (#1492) | — |
| token-expiry warning | — | yes, once per token generation (only when the sweep is driven) | — |
| never paired | nothing | nothing | nothing |
| phone-home died, fresh heartbeat | nothing | nothing | nothing |

The two `nothing` rows are the doc's honest gap: an owner today sees
only what #1062's six shipped mappings page plus the dashboard's
heartbeat-only chips. #1214 and #1489 own closing them.

## 4. Anti-spam and dedup discipline

The bounds that keep a wedged box from paging an owner into oblivion,
all shipped in the #990 boundary and the #1062 mapping layer:

- **D10 budgets:** per-(box, hour) ≤ 3 pages, per-owner ≤ 10 pages, with
  hourly digest coalescing. Over-budget pages coalesce into the digest,
  they are never dropped silently. Reminders consume budget.
- **D57 page-once dedup:** the partial-unique-index on the page key —
  replays and overlapping sweeps return `duplicate`, never a second page.
- **D61 audit keys:** suffixed (`suppressed_terminal`, U+0000-suppressed)
  so an outcome-blind dedup never mistakes a suppression audit for the
  page it suppressed — the #1063 finding-2 wedge class, fixed.
- **D12 leases:** the two-gate reminder lease (sweep gate + send gate)
  means a decision that lands between the sweep's read and the send is
  never paged after the fact; the audit row records the loss.
- **D13 generations:** token-expiry keys on the token hash, so a
  rotation resets the warning without a stale-key cleanup pass.

## 5. Decisions pinned

- **O1 — heartbeat-only liveness is the dashboard's only freshness
  signal, and it stays that way.** The #1488 contract pins this
  (§"Liveness is heartbeat-only"): a connected socket never makes a box
  "live", a dropped socket never makes it "dead". If #1489 adds a
  phone-home chip, the chip renders journal-derived *channel* state,
  never freshness — the `Stale` chip keeps sole ownership of freshness.
- **O2 — the #1489 alert keys off the `phone_home_events` journal.**
  No new signal path: the DO already journals the terminal closes (#999),
  and the heartbeat table already tells which boxes are fresh with valid
  tokens. The alert is a join, not a new instrument.
- **O3 — revoked pages once and never reminds.** Terminal classes
  (revoked, expired) are one-page classes; only live approvals get
  reminders and digests. Expiry never pages (D11).
- **O4 — never-paired keys off the provision record, not the box.**
  #1214's scope is unchanged: the plane owns the timeout, keyed on the
  record that carries the attestation token.
- **O5 — alerting is observation-only.** Nothing here is a restart
  trigger: the no-restart design (#1488) stands, and a page never
  implies the plane will re-drive the dead channel. Re-drive is a
  separate decision the alert does not make.
- **O6 — every due page goes through the boundary.** A future #1489,
  #1214, or #1492 page is an `enqueue_page` call like the other mappings
  — D10 budgets, D57 dedup, and D61 audit apply by construction, not by
  the slice remembering to add them.

## 6. What this does not claim

- This doc builds nothing: the six shipped classes exist, the two gap
  classes are issue-tracked specs (#1214, #1489). No new issue is filed
  here — the convergence pin already filed #1489 and #1214 is open.
- The sweep's plane-side cron-trigger wiring (#1069) is not landed, so
  the sweep-driven classes page only when a human drives the sweep —
  the "without a human driving it" half of #1063's acceptance is still
  open.
- No provisioned hosted box exists; the four sweep-driven rows are the
  contract (they fire only when the sweep is driven — the #1069 cron
  wiring is not landed), approval-filed and box-revoked have mappings but
  no callers (#1492), and the two `nothing` rows are tracked gaps (#1214,
  #1489) with no delivery commitment — they read `nothing` until the
  issues ship.
- The fleet/operator lane (`docs/ALERT_PUSH_FANOUT_SPEC.md`) has its own
  ack/resolve semantics (G22); this doc does not import them. The owner
  lane's ack story is unbuilt — an owner who saw the page has no way to
  mark it seen except by fixing the box.

## 7. Backlog map

| Issue | Class | State |
|---|---|---|
| #1062 | approval filed, reminder, digest, heartbeat-stale, revoked, token-expiry | mappings shipped, closed — but the approval-filed and box-revoked mappings have no callers (see #1492), and the sweep-driven four fire only when the sweep is driven (#1069 unlanded) |
| #1492 | wire the push-lane callers for `on_approval_filed` / `on_box_revoked` | open (p2, filed by this doc's review) |
| #1063 | sweep cadence (D9) | open — #1069 owns the cron-trigger half |
| #1069 | plane-workspace cron-trigger wiring | open |
| #1488 / #1273 | healthy-box contract (the operator-side half of the failure classes) | shipped, closed |
| #1489 | phone-home died, heartbeat fresh | open (p3) |
| #1214 | provisioned, never paired | open (p3) |
| #999 | `phone_home_events` DO journal (the #1489 signal source; its upstream is #958's S4b socket lifecycle) | shipped |

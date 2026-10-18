# Alert-ack provenance contract

Companion to `ALERT_ACK_ENTRY_TICKET_GAP_2026-10-18.md` (F-ACK-3, F-ACK-4,
G-ACK-2, G-ACK-3, D-ACK-2). That analysis left two questions to the design
corpus: what `acked_by` is allowed to claim (#1704), and what re-acking does
to `acked_at` (#1705). This doc answers both, and D-ACK-6 answers the entry
ticket's remaining question (#1703). Everything below is pinned to main
`956881e3` (D-ACK-6 pinned to main `abb03984`); every cited line was read
against its pinned tree.

## What the ack is

`fleet events ack` rewrites the alert journal atomically (tmp + `os.replace`)
and stamps two fields (`fleet/events.py:1231-1269`):

- `acked_at` — the **collector clock**, taken at ack time.
- `acked_by` — the **operator identity**, or null when unknown. An unknown
  operator never fails the ack: provenance is metadata, never a gate
  (`fleet/events.py:112-126`).

Ack is CLI-permanent: the OQ3 auth story has been chosen (#1703, D-ACK-6
below) and the answer is that no console write endpoint ships. The console
keeps its no-write-path contract and ships copy-pasteable
`fleet events ack --alert-id <id>` hints as the composed flow.

## D-ACK-4 — re-ack refreshes `acked_at` (closes #1705)

**Decision: refresh.** Re-acking an already-acked alert overwrites `acked_at`
with the new collector clock and re-stamps `acked_by`. State is idempotent
(stays acked); timestamps are not. This is the behavior that shipped with
#928 and it stays.

Three reasons, in order of weight:

1. **The re-fire gate needs the re-ack to mean something.** The stuck-precheck
   re-fire gate (#928, `fleet/events.py:1184-1214`) re-pages only when the
   candidate's anchor postdates `acked_at`. A re-ack that preserves the first
   `acked_at` would be a timestamp no-op that *looks* like a re-affirmation:
   the operator believes they re-snoozed the stuck alert, the gate ignores
   the gesture, and the re-page arrives "unfairly" by their mental model.
   Refresh makes the re-ack do what its gesture advertises — reaffirm
   ownership and re-extend the suppression window. The preserve-first reading
   is the worse failure mode in both directions: silent no-op plus a
   falsified operator belief.
2. **Each ack is a fresh declaration.** The corpus already models
   acknowledgement as operator-declared and resolution as journal-derived
   (`STATUS_PAGE_FEED_SPEC.md` — "acknowledged is operator-declared,
   resolved is journal-derived per rule and never auto-clears"). A fresh
   declaration is stamped when made, like every other journaled operator
   action.
3. **Stability.** Refresh is the shipped behavior; no operator complaint, no
   code change owed, no migration of existing journal rows.

**Gate interaction, stated explicitly:** every re-ack re-extends the rule-4
suppression window — the candidate's anchor must postdate the *latest* ack.
An operator who wants the alert to re-fire on the existing evidence must not
re-ack it. (There is no un-ack gesture; if one is ever added it is a new
slice, not a reading of this contract.)

What this doc does *not* owe: preserving the first-ack timestamp for audit.
If the audit story later needs "when did the operator first see it", that is
a new code slice (a never-overwritten `first_acked_at`), not a different
reading of this decision.

## D-ACK-5 — the interim `acked_by` contract (closes #1704)

**Decision: until the OQ3 auth story lands, `acked_by` is best-effort
metadata, never claimed provenance.** It makes no authority claim — in
particular, no claim that a named human acted.

The bar, exactly:

1. **Source.** `$USER`, falling back to `$LOGNAME`; each is stripped and
   `_clean_text`-processed, so a hostile `$USER` cannot inject control bytes
   into the journal or the CLI tables (`fleet/events.py:111-126`). Empty or
   whitespace-only → null.
2. **Null stays legal.** Unknown → null `acked_by`, and the ack succeeds.
   This is load-bearing: the collector runs as the operator's own
   cron/terminal user and must never wedge on identity plumbing.
3. **Rendering is honest.** Null renders as `unknown` in the console
   (`fleet/console.py:172`) and the status-page feed cites both stamps as
   journaled metadata under the cite-your-source discipline
   (`STATUS_PAGE_FEED_SPEC.md:155-158`). "Unknown" is never rendered as a
   name.
4. **Cron/systemd guidance.** Where the environment is shared or unset (cron
   jobs, systemd units), the operator should set `USER` explicitly per job —
   or accept `unknown`. A mis-set `$USER` silently mints wrong attribution;
   that is accepted *as metadata*, never as a failure, because the value
   carries no authority claim. Do not gate anything on `acked_by` until the
   auth story exists.

**Supersession.** When #1703's auth story lands, the ack stamps the real
principal and this interim contract is superseded — prospectively, not
retroactively. Historical journal rows keep the meaning this contract gives
them: metadata, not provenance.

(#1703 landed as D-ACK-6 with CLI-permanent, so the "when" clause never
fires: the interim label drops and this section stands as the permanent
contract until D-ACK-6's revisit trigger fires.)

## D-ACK-6 — the OQ3 auth story, chosen: ack is CLI-permanent (closes #1703)

**Decision: no console write endpoint ships, permanently** — until a slice
re-opens this decision with a real trigger (below). The OQ3 question is
answered, not deferred: G-ACK-1 is resolved by this section.

**Principal model.** The ack's principal is the operator's login identity on
their own box — local-process authority. No network principal exists on this
surface by construction: the read API binds `127.0.0.1` hardcoded with no
`--bind` flag and no auth by design ("the operator's own box is the trust
boundary, same as the CLI" — `fleet/api.py:30-36`, serve path `:775-778`);
the console refuses non-loopback `--api` targets fail-fast
(`fleet/console.py:24-28,52,72-90`).

**Why not the OQ3 candidates** (recorded so a future turn does not
re-litigate them):

1. **Operator token (bearer).** On a loopback-only surface inside this
   surface's single-operator-box trust boundary ("the operator's own box
   is the trust boundary, same as the CLI" — `fleet/api.py:35`), a token
   is theater: any local process that could call the endpoint can equally
   read the operator's token store or run the CLI, which already holds the
   same authority (F-ACK-4). It would need its own storage/rotation story
   and buys nothing against the actual threat. If a remote tenant console
   ever ships, it reuses the plane's owner principal (the #843/#844
   model), not a new fleet-local token.
2. **SSH-certificate-bound.** The loopback HTTP surface has no TLS and no
   SSH handshake; there is nothing to bind a certificate to. A
   signed-challenge dance over loopback would prove only what the CLI
   already grants.
3. **The confirmd trust model.** Confirmd *does* authenticate a human
   operator — every request is checked by Tailscale identity against
   `CONFIRM_OWNER` (`confirm/README.md:132-134`, "Security properties"). But that
   principal is bound to confirmd's tailnet HTTPS surface (Tailscale
   identity + machine certificates). The fleet surface is loopback-only
   with no network identity by construction, so there is nothing here to
   authenticate *against*: porting confirmd's model would mean standing up
   tailnet identity on a loopback socket — the same theater rejected in
   (1) — or conflating two principal namespaces (a tailnet login vs. the
   local login identity that runs the CLI). Rejected as a surface mismatch
   (F-ACK-7: candidate, not dependency), not for lack of a principal.

**Consequence for D-ACK-5.** Its supersession clause ("when #1703's auth
story lands, the ack stamps the real principal") resolves to never: #1703
landed with CLI-permanent, so the interim `acked_by` contract stands as the
permanent contract — best-effort metadata, never claimed provenance —
until the revisit trigger fires. Historical rows keep this contract's
meaning, unchanged.

**Revisit trigger and owner.** Owner: the improvement loop. Re-open this
decision only when (a) a slice binds the fleet read API non-loopback, or
(b) a hosted tenant console needs ack. This decision is scoped to the
fleet/console surface — the plane's approval records are a separate trust
plane (D-ACK-3), untouched. Until then, D-ACK-1's prerequisite
stands: a console write endpoint without a chosen principal is out of
scope — and the principal is now chosen as "the operator's own box," which
no endpoint needs to gate.

## Verification points (main `956881e3`)

- `fleet/events.py:111-126` — `_operator_identity` ($USER/$LOGNAME,
  `_clean_text`, null when unknown, never fails the ack).
- `fleet/events.py:1255-1261` — `ack_alert` re-ack refresh behavior.
- `fleet/events.py:1184-1214` — the #928 rule-4 re-fire gate keying on
  `acked_at`.
- `fleet/console.py:172` — null `acked_by` renders `unknown`.
- `docs/STATUS_PAGE_FEED_SPEC.md:155-158` — both stamps journaled, null never
  fails the ack, cite-your-source covers ack attribution.
- `docs/ALERT_ACK_ENTRY_TICKET_GAP_2026-10-18.md` — F-ACK-3 (re-ack
  refreshes), F-ACK-4 (provenance as the real gap), G-ACK-2, G-ACK-3, D-ACK-2
  (the conservative position this doc now supersedes for the two filed
  questions).

D-ACK-6 verification points (main `abb03984`):

- `fleet/api.py:30-36` — loopback-only transport, no `--bind`, no auth by
  design ("the operator's own box is the trust boundary, same as the CLI").
- `fleet/api.py:775-778` — serve path binds `127.0.0.1` hardcoded.
- `fleet/console.py:24-28,52,72-90` — non-loopback `--api` targets refused
  fail-fast; `LOOPBACK_HOSTS` + `api_host_is_loopback`.
- `fleet/console.py:11-15` — the console's no-write-path contract ("the
  console itself never acks").
- `fleet/console.py:154` — the composed console→CLI hint (shipped UX for
  the permanent CLI path).

**Track:** open-source (operator tooling every self-host operator uses).
#1704/#1705 closed on PR #1708's merge (`55cd9d17`); #1703 closes on this
doc's merge.

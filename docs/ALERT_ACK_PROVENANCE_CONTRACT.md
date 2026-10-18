# Alert-ack provenance contract

Companion to `ALERT_ACK_ENTRY_TICKET_GAP_2026-10-18.md` (F-ACK-3, F-ACK-4,
G-ACK-2, G-ACK-3, D-ACK-2). That analysis left two questions to the design
corpus: what `acked_by` is allowed to claim (#1704), and what re-acking does
to `acked_at` (#1705). This doc answers both. Everything below is pinned to
main `956881e3`; every cited line was read against that tree.

## What the ack is

`fleet events ack` rewrites the alert journal atomically (tmp + `os.replace`)
and stamps two fields (`fleet/events.py:1231-1269`):

- `acked_at` — the **collector clock**, taken at ack time.
- `acked_by` — the **operator identity**, or null when unknown. An unknown
  operator never fails the ack: provenance is metadata, never a gate
  (`fleet/events.py:112-126`).

Ack stays CLI-only until the OQ3 auth story lands (#1703); the console ships
copy-pasteable `fleet events ack --alert-id <id>` hints as the composed flow.
That decision is the entry-ticket doc's, not this one's.

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
   (`STATUS_PAGE_FEED_SPEC.md:155-156`). "Unknown" is never rendered as a
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

## Verification points (main `956881e3`)

- `fleet/events.py:111-126` — `_operator_identity` ($USER/$LOGNAME,
  `_clean_text`, null when unknown, never fails the ack).
- `fleet/events.py:1255-1261` — `ack_alert` re-ack refresh behavior.
- `fleet/events.py:1184-1214` — the #928 rule-4 re-fire gate keying on
  `acked_at`.
- `fleet/console.py:172` — null `acked_by` renders `unknown`.
- `docs/STATUS_PAGE_FEED_SPEC.md:155-156` — both stamps journaled, null never
  fails the ack, cite-your-source covers ack attribution.
- `docs/ALERT_ACK_ENTRY_TICKET_GAP_2026-10-18.md` — F-ACK-3 (re-ack
  refreshes), F-ACK-4 (provenance as the real gap), G-ACK-2, G-ACK-3, D-ACK-2
  (the conservative position this doc now supersedes for the two filed
  questions).

**Track:** open-source (operator tooling every self-host operator uses).
Issues #1704 and #1705 close on this doc's merge; #1703 stays open (the OQ3
auth story is the entry ticket that ends the interim contract).

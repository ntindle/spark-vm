# site/ — the waitlist-era web surface (H15, surface 1)

**Status: build slices 1–3a of H15 PR 1.** Slice 1 shipped the static
markup (PR #163); slice 2 shipped the backend half of the endpoint surface
(`site/waitlistd.py` + `scripts/test_waitlistd.py`, 25 tests): `POST
/waitlist/form`, the §4.3 confirm flow (`GET` renders-only / `POST`
confirms, token as form field), the HMAC token signer (single-use, 14-day
expiry, operator key via `WAITLIST_HMAC_KEY` — never in the repo), and
`funnel_events` logging per `docs/FUNNEL_MEASUREMENT.md` §3.4
(verified parseable by `scripts/funnel_metrics.py`). Slice 3a ships the
waitlist lifecycle jobs (`site/waitlist_jobs.py` + `scripts/test_waitlist_jobs.py`,
21 tests): the +7d reminder job and the 14d drop job, run as operator cron
against the operator data dir with a cross-process data lock so they never
race the live daemon. The drop deadline is fixed at first submission and
never refreshed by re-submits; a cap-deferred reminder retries on the next
run instead of being skipped. Slice 3a also closes the deferred
Engineering blocker on oversized requests: a 413 now closes the HTTP
connection instead of risking a desynced keep-alive.

**Not yet (slice 3 remainder = H15 §8's remaining "§7 waitlist-era endpoint
surface"):** the path-A email parser, the invite sender, the forget-me
handler, the `/go/selfhost` static redirect shim, and the 30-day
post-drop purge (WAITLIST_OPERATIONS.md §5 — deferred from this slice's
drop job, which retains dropped rows for a separate operator pass). The
page is still NOT deployable — the dead-form rule holds until every §10
checklist item is live.

## The dead-form rule (read before deploying anything)

`docs/WAITLIST_OPERATIONS.md` §10 + `docs/HOSTED_SIGNUP_WEB_UI.md` §4.4:
**the page ships only when every §10 checklist item is live** — the form
endpoint, the confirm flow, the token signer, the reminder/drop jobs, the
inbox. Slices 1–3a exist only in this repo — the §10 operator checklist
(deployed endpoint, reminder/drop cron, inbox) is not live, so **nothing
in this directory is deployable**. A page typeset atop a dead form
is the trust wound the spec was written to prevent.

## Deploy-time substitutions (operator)

The markup carries placeholders the operator fills when §10 goes live:

- `https://<host>/` in every `<head>` tag set — the production host.
  No URL shorteners; the image URL must not carry query-string trackers
  (`docs/FUNNEL_MEASUREMENT.md` §5).
- On `waitlist.html` the path-A box carries a launch-frame sentence with the
  inbox substitution point recorded in an HTML comment only — no raw
  `{{WAITLIST_INBOX}}` token and no repo-internal doc path in human-facing
  copy. The operator substitutes the dedicated AgentMail inbox
  (`docs/WAITLIST_OPERATIONS.md` §10) at launch.
- The pricing-teaser link points at the public thinking doc
  (`docs/PRICING_THINKING.md`); it becomes the pricing page when one exists.

(`/go/selfhost?src=selfhost` is page-build code the loop owns, not operator
packet: on Pages it needs a static redirect shim. It ships in a later markup
slice — listed under the remainder below.)

## og:image provenance

`assets/og-persistence-pair.png` (1200×630) is composed — not reshot — from
BOTH frames of the shipped demo asset `assets/demo-persistence-pair.gif`
(asset 3, PR #137), per `docs/FUNNEL_MEASUREMENT.md` §5 and
`docs/HOSTED_SIGNUP_WEB_UI.md` §4.1:

```
python3 site/derive_og_image.py   # crops each frame's window-chrome title
                                  # bar (it duplicates the card headline),
                                  # lays the then/now pair side by side with
                                  # "1/2 — then" / "2/2 — now" sublabels, and
                                  # adds a legible headline + wordmark.
                                  # Requires Pillow. Deterministic: same
                                  # source frames → same PNG.
```

The card carries the `og:image:alt` promise ("The same desktop, today and
tomorrow — nothing lost overnight") because it now actually shows the pair.

## What this slice does and does not include

**Includes:** both pages' markup and copy (typeset from the approved
`docs/LANDING_PAGE_COPY.md` §3 blocks, re-verified against the §5 honesty
checklist at build time — see below); the exact `docs/FUNNEL_MEASUREMENT.md`
§5 `<head>` tag set on both pages (`og:url` on `waitlist.html` points at the
marketing page per H15 §4.1); the `?src=` CTA buckets
(`hero`, `trust`, `faq`, `final`) plus `/go/selfhost?src=selfhost` exactly
twice (hero, FAQ — the two-CTA cap); the §4.2 form markup (required owner
email with `autocomplete="email"`/`inputmode="email"`, optional agent-contact
email with `autocomplete="off"`, off-screen honeypot, `rendered_at` time-trap
field for the page-serving layer to stamp — there is no page JS); the path-A
inbox line; the 14-day claim-window line; and the page-disclosure gates from
`docs/WAITLIST_OPERATIONS.md` §10 — FAQ Q6 discloses the pre-launch pilot
cohort before waitlist-order general invites (no dates), so the page never
promises what the operator plan doesn't deliver.

**Not yet (H15 PR 1 remainder = H15 §8's "§7 waitlist-era endpoint surface"
plus markup):** the path-A email parser, the invite sender, the forget-me
handler, the `/go/selfhost` static redirect shim, and the 30-day
post-drop purge (WAITLIST_OPERATIONS.md §5). Slices 2–3a already
ship: `POST /waitlist/form` endpoint, the §4.3 confirm flow (`GET`
renders-only / `POST` confirms), the HMAC token signer, the +7d reminder
and 14d drop jobs (cross-process data lock, fixed drop deadline, cap-aware
retries), and the `funnel_events` logging (`docs/FUNNEL_MEASUREMENT.md`
§3.4). `scripts/funnel_metrics.py` (PR #141) already ships the consumer
side of that logging.

## Honesty re-verification (build time, 2026-09-20)

Per `docs/HOSTED_SIGNUP_WEB_UI.md` §8, the `docs/LANDING_PAGE_COPY.md` §5
checklist was re-run against this slice's base (`a7bbe00`):

- Headline + one-liners verbatim from `docs/POSITIONING.md` — typeset
  unchanged from the approved copy (no uniqueness claim, sentinel unnamed,
  no hosted pricing).
- "Running in production today" — the self-hosted deployment is the live
  reference; unchanged from the approved copy.
- The audit claim ("every swap is audited") re-verified against
  `proxy/swap_addon.py`: every swap path writes via `_audit`, every refusal
  via `_audit_refused`, and the audit write is part of authorization.
- No trial terms, no "free trial" wording, no "session clock" one-liner, no
  launch date anywhere in the markup.
- Q4's hosting claim ("we run the machine") stands on the decided Fly.io
  provider: DECIDED 2026-09-18 in the operator-decision register
  (`NEEDS_USER.md`, kept at the goal-workspace level, not in the repo —
  Fly.io chosen, `custom.flyio` token connected), with the repo-side record
  in `docs/HOSTED_UNBLOCK_PASS.md` (2026-09-18 decisions). Unchanged from
  approved copy.
- LICENSE (MIT) present on the base the slice branched from.
- Page-disclosure gates (`docs/WAITLIST_OPERATIONS.md` §10) covered: FAQ Q6
  states the 14-day claim window AND discloses the pre-launch pilot cohort
  (no dates, non-promissory wording — "a small pilot cohort of beta Muses
  gets early boxes; general invites then go out in waitlist order").
- "Your agent can start the signup — the confirmation email goes to your
  owner" is the approved §3 hero microcopy, verbatim (also used as the
  `/waitlist` context line per §4.1); the owner-frame voice is intentional,
  not a wobble.
- The §5 dead-form item stays OPEN: the form endpoint, confirm flow, and
  lifecycle jobs exist only in this repo — none of §10's operator checklist
  (deployed endpoint, reminder/drop cron, inbox) is live yet, so the pages
  are still explicitly not deployable.

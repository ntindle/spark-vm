# site/ — the waitlist-era web surface (H15, surface 1)

**Status: build slice 1 of H15 PR 1 — static markup only.** This directory holds
the waitlist page build's front end per `docs/HOSTED_SIGNUP_WEB_UI.md` §4:
the landing page (`index.html`, typesets `docs/LANDING_PAGE_COPY.md` §§2–3),
the dedicated form page (`waitlist.html`, per §4.1), and the derived
`og:image` (`assets/og-persistence-pair.png`).

## The dead-form rule (read before deploying anything)

`docs/WAITLIST_OPERATIONS.md` §10 + `docs/HOSTED_SIGNUP_WEB_UI.md` §4.4:
**the page ships only when every §10 checklist item is live** — the form
endpoint, the confirm flow, the token signer, the reminder/drop jobs, the
inbox. This slice ships *markup only*; the backend does not exist yet, so
**nothing in this directory is deployable**. A page typeset atop a dead form
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
plus markup):** `POST /waitlist/form` endpoint, the §4.3 confirm flow
(`GET` renders-only / `POST` confirms), the HMAC token signer, the +7d
reminder / 14d drop jobs, the path-A email parser, the invite sender, the
forget-me handler, the `/go/selfhost` static redirect shim, and the
`funnel_events` logging (`docs/FUNNEL_MEASUREMENT.md` §3.4).
`scripts/funnel_metrics.py` (PR #141) already ships the consumer side of
that logging.

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
- The §5 dead-form item stays OPEN: the form posts to an endpoint that does
  not exist yet — hence this directory is explicitly not deployable.

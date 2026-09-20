<!-- Contributor PR template. Full rules live in CONTRIBUTING.md — this file
prompts for what the repo requires; CONTRIBUTING.md is authoritative. -->

# What

<!-- One improvement per PR. If it grew teeth, split it. -->

-

# Why

<!-- Link the issue this fixes/implements (e.g. "Fixes #123"). For anything
bigger than a typo, the issue conversation happens first. -->

-

# How it was tested

<!-- Commands you ran and what they showed. New behavior gets a test.
Install test deps first (`pip install -r requirements-test.txt`), then the
one-liner runs the whole suite: `python3 -m pytest` from the repo root.
Keep `main` green. -->

-

# CHANGELOG

<!-- Every PR that changes anything user- or operator-visible adds one or
two bullets under `## [Unreleased]` in CHANGELOG.md (docs count). Put it in
the right section (Added/Changed/Fixed/Security) and link the PR number. If
this PR is genuinely exempt (pure refactor, no visible change), say why. -->

- [ ] Added under `## [Unreleased]`, or exempt because: ___

# Checklist

- [ ] Branch is from `main` and named `feature/<slug>` or `fix/<slug>`
      (`hourly/` and `strategy/` prefixes are the maintainer's automation loops)
- [ ] No secrets, credentials, tokens, or private keys anywhere in the diff
- [ ] Docs updated where a user or operator would notice the change
- [ ] `python3 -m pytest` passes (or: suite N/A because ___)

# Adversarial review

<!-- Every PR gets adversarial review from the roles it touches — engineering,
security, product, docs, QA, architecture, design. Expect hard questions;
that's the norm here, not a sign something is wrong with your PR. The
automation loops record their verdicts here; human contributors can leave
this section for the reviewers. Only the roles routed to your PR need to
sign off — small PRs may get fewer than four. -->

- Engineering: ___
- Security: ___
- Product: ___
- Docs: ___

# Merge notes (maintainer only)

<!-- The maintainer merges after CI is green, mergeability is clean, and
every routed role has signed off on the final code. Human contributors: do
not merge your own PR. -->

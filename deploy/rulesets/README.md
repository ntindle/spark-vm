# Repository rulesets as code

The rulesets that guard spark-vm's release process, declared as JSON so they
are reviewable, versioned, and reproducible. **Applying them is an owner
decision** (tracked in issue #174) — this directory only makes the decision
one auditable command; no automation applies these.

## The files

- `tag-protection-vstar.json` — **release tag protection.** Blocks updates and
  deletions of any `v*` tag, so the release notes' "tags are never moved or
  re-cut" claim becomes platform-enforced instead of convention. Nobody —
  including the owner — can force-push or delete a release tag while this is
  active; a genuinely bad tag (e.g. a typo) requires temporarily disabling
  the ruleset in the repo settings, which is itself the point.
- `tag-protection-vstar-strict.json` — same as above, plus **creation is
  restricted**: only the release workflow actor (`github-actions[bot]`,
  actor id `41898282`) may create `v*` tags. Choose ONE of the two tag
  files — they share the ruleset name `release-tag-protection`, so applying
  one replaces the other. The strict variant breaks the documented manual
  path (`cut-release.sh --execute` from a dev machine); use it only if you
  are comfortable cutting every release through the workflow. Note: GitHub
  bypass is all-or-nothing — this also exempts the workflow actor from the
  update/deletion rules, so any workflow running as `github-actions[bot]`
  can move or delete `v*` tags. Prefer the base variant if that trade-off
  is unacceptable.
- `main-branch-protection.json` — **main branch protection** (owner proposal
  from issue #138). Blocks branch deletion and force-pushes, requires every
  change to land via PR, and requires all four CI checks green on an
  up-to-date branch before merge. Deliberately does **not** require approving
  reviews (`required_approving_review_count: 0`): the improvement loop opens
  and merges its own PRs, so a human-approval gate would block all loop
  merges. Raise the count the day a second human reviewer exists.

## Apply

```bash
GITHUB_TOKEN=<admin token> scripts/apply-rulesets.sh \
    --file deploy/rulesets/tag-protection-vstar.json --execute --yes
```

- Dry-run (default): prints the plan, touches nothing, needs no token.
- `--check`: compares the live repo rulesets against the file; exits 2 on
  drift (or when the ruleset doesn't exist yet) so it can gate a periodic
  audit.
- `--execute --yes`: creates the ruleset, or updates it in place (matched by
  name). The token travels only in a trap-cleaned `0600` curl config and is
  never printed.
- The token needs repository admin scope — a plain `repo`-scope token cannot
  manage rulesets.

## Drift notes

- If the CI job names in `.github/workflows/ci.yml` change, the
  `required_status_checks` contexts in `main-branch-protection.json` must be
  updated to match, then re-applied.
- The `bypass_actors` entry in the strict tag file pins
  `github-actions[bot]` by its well-known actor id (`41898282`); confirm it
  against the workflow run actor before applying.
- Emergency: repository admins can bypass or disable any ruleset from the
  repo settings page; re-run with `--check` afterwards to confirm the
  declared state is back in force.

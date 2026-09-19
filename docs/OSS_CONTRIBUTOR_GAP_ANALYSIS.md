# OSS contributor gap analysis

Walked the repo as a first-hour contributor would — discover, evaluate,
set up, find a task, run tests, ship a PR — and recorded everything the
journey hits. Findings are numbered G1–G10 by severity. Fixes made in the
same PR are noted; everything else became a GitHub issue or an existing
backlog seed.

Baseline: `main` @ `8aa7d0d` (2026-09-18). Verified against the tree, not
memory: `ls`, `git ls-files`, GitHub API reads of labels/issues, and two
test runs.

## Stage 1 — Discover & evaluate (lands on the repo page)

**What works:** README is a good landing surface (positioning pass merged),
the label taxonomy from the triage pass is genuinely healthy
(`severity:*`, `area:*`, `track:*`), 22 open issues are all labeled, and the
"OSS hygiene" milestone exists.

- **G1 [high] — No LICENSE file.** The repo is public with no declared
  license on GitHub and no license text anywhere in the tree. Contributors
  have no explicit rights to the code, and a security-sensitive project
  without stated terms is a non-starter for serious review. → filed as
  **#55**; license choice needs the maintainer (also logged in the loop's
  NEEDS_USER.md).
- **G2 [medium] — `docs/` on main is nearly empty.** Only `POSITIONING.md`
  is merged; every other design doc lives in an open PR. A contributor
  browsing the tree at `main` sees almost no durable documentation.
  Mitigation (not a fix): merge pressure on the open doc PRs. Tracked by
  the loop's PR queue; no new issue needed.

## Stage 2 — Set up a dev environment

**What works:** ONBOARDING.md got a contributor pass (PR #35); SETUP.md and
ENVIRONMENT.md exist.

- **G3 [medium] — No documented "run the tests" command.** Six test files
  across four components, no root `pytest.ini`/`conftest.py`, no
  requirements file anywhere, and README/ONBOARDING never mention tests.
  The suites do pass under one command — `python3 -m pytest proxy/
  confirm/ muse-job/ deploy/` is 167/167 green on `main` (verified this
  run) — but a newcomer has no way to know that. `CONTRIBUTING.md` now
  documents it. → filed as **#56** (single-command test story; left to a
  `dx` turn, issue is the tracker).
- No devcontainer or one-shot setup script — noted, not filed; the
  "New platforms" invitation in README covers the self-host spirit and this
  project is deliberately box-shaped.

## Stage 3 — Find something to do

- **G4 [low] — `good first issue` exists but is empty.** Zero open issues
  carry it; the newcomer funnel has no entries. → filed as **#57** with
  seeding suggestions (low-risk items from #12's hardening batch, O3 docs
  follow-ups, a sliced piece of #56).

## Stage 4 — Make a change, keep secrets out

**What works:** `scripts/push.sh` ships a secret scan (PR #33), and the
`hsurr:` placeholder convention is real (swapd rewrites at the proxy).

- No gap filed: the secret-scanning story is ahead of most small OSS
  projects. CONTRIBUTING.md now documents the rule explicitly.

## Stage 5 — Open a PR, get it merged

**What works:** PRs get genuine adversarial review (the loop's process is
public in the open PRs); CI exists as PR #39.

- **G5 [medium] — No PR template, no documented branch/PR process.** A
  contributor guesses at branch naming, PR body contents, and how review
  works. → **fixed in this PR** by `CONTRIBUTING.md` (below); the
  `repo`-rotation seed "PR template + branch protection" still owns the
  template file itself.
- **G6 [medium] — README told contributors to open a public issue for
  security holes.** For a credential-proxy project, public-first disclosure
  is the wrong default posture. → **fixed in this PR** by `SECURITY.md`
  (responsible disclosure; private GitHub Security Advisory first).
- **G7 [low] — README's "Pushing changes" section conflates contributor and
  operator flows.** It reads like PR instructions, then tells you to SSH to
  the box and run `proxy/deploy.sh`. → **fixed in this PR**:
  CONTRIBUTING.md now carries the contributor flow; README's section points
  to it.
- **G8 [low] — No CHANGELOG.md / release-note ritual.** Existing
  `repo`-rotation seed; not duplicated here.
- Not filed: review SLA is unknown (open PRs are all hours-old loop
  output, so there's no data yet) and CODE_OF_CONDUCT.md (README's
  "Be kind — this is a homelab" covers the spirit for a project this size;
  revisit if the contributor base grows beyond the loop).

## What shipped in this PR

| File | Fixes |
|---|---|
| `CONTRIBUTING.md` | G5: issue-first rule, branch naming, PR expectations, test how-to (as verified), no-secrets rule, review process |
| `SECURITY.md` | G6: responsible disclosure policy, private-channel-first |
| `docs/OSS_CONTRIBUTOR_GAP_ANALYSIS.md` | this file |

## Follow-ups for later turns

- License decision (#55) — maintainer.
- Merge the open doc PRs so `docs/` on main stops being a stub (G2).
- `dx` turn owns the test-story fix (#56); a `repo` turn owns the
  `good first issue` seeding (#57) plus the pending PR-template/branch-protection
  and changelog seeds.

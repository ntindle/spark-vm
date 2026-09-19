# Contributing to spark-vm

Thanks for looking at the code — this is a one-human-and-his-robot project
and outside eyes are the highest-leverage help we get (docs first, always).

## Before you write code

**Open an issue first for anything bigger than a typo.** Say what you want
to change and why; the maintainer will confirm the direction before you
spend an afternoon on it. Duplicated work is the main thing we try to
avoid.

Good places to start: issues labeled
[`good first issue`](https://github.com/ntindle/spark-vm/labels/good%20first%20issue)
— if that label looks empty, say so on an issue; seeding it is maintainer
work we sometimes forget.

## Branching and PRs

- Branch from `main`. Name it `feature/<short-slug>` (or `fix/<short-slug>`
  for bug fixes). The `hourly/` and `strategy/` prefixes are the
  maintainer's automation loops — don't use them for manual PRs.
- One improvement per PR. If the change grew teeth, split it.
- PR body: what changed, why, and how you tested it. Link the issue.
- **Add a `CHANGELOG.md` entry**: every PR that changes anything
  user- or operator-visible adds one or two bullets under
  `## [Unreleased]` in the right section — write it for the person
  running spark-vm, not the person who wrote the diff, and link the PR
  number. The ritual (sections, what skips an entry, release-time rollover)
  is documented at the top of `CHANGELOG.md`. Reviewers request changes
  when the entry is missing — it's a merge gate, not a suggestion.
- Every PR gets reviewed adversarially — expect hard questions from
  engineering, security, and product perspectives. That's the norm here, not
  a sign something is wrong with your PR.
- Don't merge your own PR. (The `hourly/` and `strategy/` automation loops
  are the one exception: they merge their own PRs after unanimous
  adversarial sign-off — that's the maintainer's settled process, not a
  shortcut available to manual contributors.)

## Running the tests

There is not yet a single test command (tracked in
[#56](https://github.com/ntindle/spark-vm/issues/56)). Until then, run the
component suites directly from the repo root:

```bash
python3 -m pytest proxy/ confirm/ muse-job/ deploy/
```

All suites pass on `main`; your PR should keep them green. Some components
need extra packages (e.g. `python3-cryptography` for the VAPID push work) —
if a suite fails on import, that's a missing dependency, not your bug; note
it in the PR.

## Secrets: the one hard rule

**Never commit real secrets, tokens, credentials, or private keys.**
Configs in this repo use `hsurr:<name>` placeholders; real values are
installed by the operator through the credential store and swapped in at
the proxy. `scripts/push.sh` runs a secret scan before pushing — if it
flags something, fix it before opening the PR. This rule has no exceptions
and no "I'll remove it later."

## Security issues

Don't open a public issue or PR for a vulnerability. See
[SECURITY.md](SECURITY.md) for the responsible-disclosure process.

## Deploying (operators only)

If you're contributing, your job ends at the merged PR. Getting merged
code onto the live box (`git pull`, `./proxy/deploy.sh`) is the operator's
job, not the contributor's — the loop's auto-deploy tooling handles most of
it. Don't include deploy steps in contributor PRs.

## Docs live here too

Docs are a first-class contribution — if a step confused you, the fix is a
PR. Keep new docs under `docs/` and keep them factual: no promises about
unbuilt features (see `docs/POSITIONING.md` for the copy rules).

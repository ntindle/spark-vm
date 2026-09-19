# Changelog

All notable changes to spark-vm are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). The version lives in the
`VERSION` file at the repo root (see `docs/VERSIONING.md`); this file is
its human-readable companion.

## The changelog ritual

This changelog only works if entries land with the change, not after it:

1. **Every PR that changes anything user- or operator-visible adds one or
   two bullets under `## [Unreleased]`**, in the right section
   (`Added` / `Changed` / `Fixed` / `Security`), written for the person
   running spark-vm, not the person who wrote the diff. Link the PR number.
   Reviewers ask for the entry if it's missing (see `CONTRIBUTING.md`).
2. **Trivial scope** (typo, single-line doc fix, formatting) doesn't need an
   entry; merge notes are enough.
3. **At release time**, the release commit (the `VERSION` bump — see
   `docs/VERSIONING.md`, "Cutting a release") moves the whole
   `## [Unreleased]` section into `## [x.y.z] - YYYY-MM-DD`, and adds the
   compare links at the bottom of this file. No release has been cut yet,
   so there are no compare links — the first release creates the first one.
4. Docs are a first-class product here, so shipped docs land in `Added`
   like features do. Loop research notes that stay in the agent workspace
   (`agent_notes/`) are not repo changes and don't get entries.

## [Unreleased]

### Added
- `confirmd` approval pages rebuilt mobile-friendly: auto-refreshing
  pending list, tap-race-safe two-tap Approve, and an answered page capped
  at the 100 newest (#20)
- VAPID Web Push notifications for `confirmd` approvals: VAPID keygen,
  Web Push (RFC 8030/8292/8291) sender with subscription store, per-approval
  notify hook, push controls on the pending and approval pages, and
  `--test-push` operator verification (`confirm/push.py`,
  `docs/PUSH_NOTIFICATIONS.md`) (#48)
- Version reporting everywhere: single `VERSION` source, `sparkvm_version()`
  reader, startup stamps on `confirmd`/`swap_addon`/`cred-ui`, `GET
  /api/version` on `confirmd` and `cred-ui`, `muse-job --version`
  (#52)
- `deploy/auto-deploy.sh`: unattended redeploy updater for live services —
  the loop's merged code reaches the box without an operator pull (#29)
- `muse-job`: session-lifecycle trust-boundary hardening (#43); event-trust
  hardening (#19)
- Hosted-product design docs: signup/onboarding identity-linking + provider
  interface (#24); push-notification deployment guide; first-run activation
  funnel; agent-sandbox adoption research; pre-seeded harness research;
  beta-Muse first-run pilot protocol; hosted pricing thinking; hosted
  vision-vs-repo gap analysis
- Positioning + marketing docs: competitor analysis of agent VM/sandbox
  offerings (Sep 2026); persistence-as-headline positioning; launch
  announcement copy; README 30-second-scan clarity pass
- Contributor hygiene: `CONTRIBUTING.md`, `SECURITY.md`, MIT `LICENSE`
- CUA: `PANEL_SPEC.md` so anyone can build their own control panel, plus a
  worked Blender example; `cua-bridge` tunnel-endpoint allowlist for the
  SSH-forwarded path

### Changed
- Onboarding docs standardized on the `ntindle` deployment user (#35)
- Agent identity is `spark`, not `ntindle`: `$HOME`-relative paths
  everywhere, docs use `spark` as the example user
- `scripts/push.sh` / `pull.sh` hardened: dry-run, preflight checks,
  space-safe secret scan (#33)

### Fixed
- `muse-job` refuses to steer into a dead TUI pane (#45, fixes #4)

### Security
- Proxy hardening round: findings 70–75, 70b, 71b (#18)
- Fixed critical + high findings from the security code review

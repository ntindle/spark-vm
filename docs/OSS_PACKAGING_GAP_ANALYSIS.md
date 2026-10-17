# OSS packaging gap analysis: installing spark-vm vs the distribution vision

Pinned to main `19e71da` (2026-10-15). Scope: the **open-source** install and
update story — how a self-hosted user gets spark-vm onto a box and keeps it
current. The hosted-product lanes (Fly driver #905, golden-image provisioning
#1087, per-tenant rollout #1261) are out of scope; they are cited only where
they already answer part of the question.

## The vision (anchored)

The loop's distribution archetype defines the bar: *versioning, changelogs,
release notes, packaging (pip/apt/docker/images), installer scripts, update
channels, and deploy automation — ship artifacts and automation, not just
plans.* README's "Try it" section promises the outcome: an Ubuntu 24.04 box on
your tailnet running the spark-vm stack. The vision is therefore concrete:

1. A user installs spark-vm **from a published artifact** (or a pinned
   installer), at a **chosen version**, in one deliberate step.
2. The installed tree is **verifiable** — the user can answer "which release
   is actually deployed?" for every component (the question
   `docs/VERSIONING.md` is built around).
3. Updates arrive through a **channel** — version-to-version, gated, with a
   rollback story — not a fresh clone.

## The state (verified in-tree)

**No published artifact.** The repo root has no `pyproject.toml`, `setup.py`,
`setup.cfg`, `Dockerfile`, or `docker-compose.yml` (verified 2026-10-15). The
golden-image pipeline (`deploy/golden-image/Dockerfile`, CI gate in
`.github/workflows/golden-image.yml`) builds the image for every release but
is **build-only, never a push** — publishing stays an operator step after the
release, and the registry credentials are operator-owned. There is nothing
for a stranger to `pip install`, `docker pull`, or `apt install`.

**Install is clone-main plus a manual runbook.** README "Try it" (Option A,
Unraid) is ~40 lines of shell: create the agent user, sudoers drop, Tailscale,
`git clone https://github.com/ntindle/spark-vm.git ~/spark-vm` (**main's tip —
no tag, no version choice**), `./proxy/deploy.sh`, `cp muse-job/bin/muse-job
~/bin/`, `muse plugins install ./muse-job/plugin` (+ manual `muse plugins
approve`), copy the cred-ui systemd unit, `./cua/bin/cua-desktop.sh start`.
There is no installer script in `scripts/` (no `install.sh`); the README block
is the installer, and nothing machine-checks that it still matches the
components it installs.

**The release machinery produces releases nothing consumes.** `VERSION` +
`scripts/cut-release.sh` + `.github/workflows/release.yml` cut immutable
tagged GitHub releases with assembled notes — a genuinely mature pipeline
(#53, #659, #1086 all closed on it). But the OSS install story never
references a tag: the README clones main, and the self-hosted update channel
(`deploy/auto-deploy.sh`) **follows main, not releases** — its trust model
says so explicitly ("The updater deploys whatever is merged to main"). So the
project maintains two release truths: tagged releases for an audience that
doesn't exist yet, and a main-following updater for the operators who do.

**The update story is half-built, honestly.** `deploy/auto-deploy.sh` is a
real unattended updater (per-component deploys, pre-deploy gates, rollback
snapshots, audit log) — the one converged piece, and the `VERSION` reporting
story (`docs/VERSIONING.md`) lets an operator answer "which release is
deployed" per component. `scripts/self_update.py` is S1: **read-only**
inventory of the toolset against `scripts/self_update_pins.conf`; update
execution, the systemd timer, and the backfill installer are later slices on
the `docs/SELF_UPDATE.md` roadmap (#532). Accurate, but it means there is no
update *executor* today outside auto-deploy's main-following timer.

**Install-time copies diverge with no provenance.** #6 (open, p2) is the
standing witness: three divergent muse-job copies (`~/workspace/muse-job`,
`~/workspace/bin/muse_job.py`, `~/workspace/musejob-fix/`), security fixes
living in the copy that may not be deployed. Verified 2026-10-15 on the loop
VM: the repo's `muse-job/bin/muse-job` still differs from the hardened
`~/workspace/musejob-fix/bin/muse-job`, and `~/workspace/muse-job` is a single
Python script, not the repo layout — the divergence persists. The README
install does `cp muse-job/bin/muse-job ~/bin/` (an unversioned, unstamped
copy), and muse-job's own README documents "Redeploy: copy the files over,
then reinstall the plugin with `--force` (plugin installs copy, not
symlink)" — copies are the *documented* mechanism, and none of them records
which repo commit they came from.

## Findings

- **F-PKG-1 — no published artifact.** The distribution archetype's packaging
  line (pip/apt/docker/images) is entirely unserved for OSS users. The
  golden-image build exists but publishing is operator-owned by design.
- **F-PKG-2 — the installer is a README code block.** ~40 lines of shell with
  ordering and sudo assumptions, maintained by hand, with no executable form
  and no drift check against the components it installs.
- **F-PKG-3 — installs pin nothing.** The README clones main's tip. There is
  no documented "install vX.Y.Z" path even though immutable tags exist.
- **F-PKG-4 — releases are produced but unconsumed.** cut-release.sh's tagged
  releases have no install or update consumer; auto-deploy follows main. The
  two release truths will confuse the first user who tries to install a
  version.
- **F-PKG-5 — copy-based deploy with no provenance.** The documented
  install/update mechanism for muse-job (and the cred-ui unit, and the plugin)
  is manual file copies that record neither source commit nor version — the
  exact shape #6 warns about, still present.
- **F-PKG-6 — no update executor for the versioned path.** auto-deploy covers
  main-following operators; a user who installs a tagged release has no
  supported path to the next tag (self_update's executor is a roadmap slice).
  **Status (2026-10-17, #1611):** `install.sh --update` closes this — the
  versioned install's checkout moves between release tags in place (latest
  or explicit `--to`), with the same tag verification a fresh install gets;
  dirty trees and downgrades refuse loudly, and the stack converges on a
  plain re-run of the installer.

## Decisions

- **D-PKG-1 — installer script first, published artifact later.** The README
  runbook becomes a reviewed, idempotent `scripts/install.sh` *before* any
  pip/Docker story: it fixes F-PKG-2 with the smallest trust change (same
  steps, machine form), and every later artifact reuses its component steps.
  A published artifact without an installer just moves the runbook.
- **D-PKG-2 — tags become installable before they become updatable.** The
  version-pinned install (F-PKG-3) is the smaller slice: `git clone --branch
  vX.Y.Z` + a VERSION-vs-tag consistency check at install time. The
  tag-to-tag updater (F-PKG-6) waits on it.
- **D-PKG-3 — provenance is a file, not a memory.** Every installer-placed
  copy records its source commit (F-PKG-5): a stamped manifest the S1
  inventory can already read — this converges with, not against, the #532
  roadmap.
- **D-PKG-4 — one release truth.** Long term the updater follows releases, not
  main (F-PKG-4); short term the gap is only documented — changing
  auto-deploy's trust model is a security-model change, not a gap-turn slice.
  Filed as the design question it is.
- **D-PKG-5 — no new artifact formats decided here.** pip vs container vs apt
  is a maintainer decision with hosting costs (registry, signing); the
  analysis files it as a design question rather than assuming it. The loop
  does not pick the artifact unilaterally.

## Build slices filed

- **#1526** (p2) — `scripts/install.sh`: the README "Try it" runbook as a
  reviewed idempotent installer (D-PKG-1).
- **#1527** (p3) — version-pinned install: install a tagged release + verify
  VERSION matches the tag (D-PKG-2, F-PKG-3).
- **#1528** (p3) — installer provenance manifest: every placed copy stamps
  its source commit; S1 inventory reads it (D-PKG-3, F-PKG-5; converges with
  #532 and narrows #6).
- **#1529** (p3, design question) — one release truth + the artifact decision:
  should auto-deploy follow releases (D-PKG-4), and which published artifact
  does the project commit to (D-PKG-5).

## Honest summary

The project's release *production* is excellent (immutable tags, assembled
notes, golden-image gate) and its self-hosted *update* story is real
(auto-deploy). But between "a release exists" and "a user is running it"
there is a gap the size of the whole distribution archetype: no artifact, no
installer, no pinned install, no provenance on the copies, and two release
truths that disagree about what "current" means. The four slices above close
it in order — installer first, pins second, provenance third, the release-truth
and artifact decisions as the design questions they are.

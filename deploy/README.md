# auto-deploy — unattended redeploy updater

Fixes #22: merged changes used to sit in the repo checkout while the live
systemd services kept running the old build (PR #20's confirmd UI shipped to
main but the box kept serving the Sep-17 page until a manual deploy). This
updater closes that gap: a systemd timer watches `origin/main`, and when new
commits land it deploys **only the components that changed**, with gates,
health checks, rollback, and an audit trail.

## Trust model (read this before enabling)

- The updater deploys whatever is merged to `main`. **Anyone who can merge to
  main can execute code on this box.** That trust already exists today via the
  manual `proxy/deploy.sh`; the timer automates it, it does not widen it. Do
  not enable this on a box whose `main` branch accepts merges you wouldn't run.
- **The timer runs the installed copy** at `/home/ntindle/.sparkvm-deploy/bin/`,
  never the repo checkout. `auto-deploy.sh init` copies the script and
  `components.conf` there from the checkout; re-running `init` refreshes them.
  A writer with checkout-only access therefore cannot rewire the updater's own
  code or config. Treat `init` (reinstall) as a privileged step — review the
  checkout diff before re-running it.
- Residual: the updater deploys whatever is merged to `main` — treat `init`
  (reinstall) as a privileged step and review the checkout diff first.
- `cred-ui` runs from a fixed install directory outside the working
  checkout (`~/.local/share/spark-vm/cred-ui`), written only by its gated
  install step. A writer with checkout-only access can no longer change the
  page the human's browser loads, and a dirty checkout no longer fails its
  deploy closed. Residual: the install dir is owned by the deploy user, so
  this closes the checkout-writer hole, not the deploy-operator trust the
  updater already assumes.
- The fetch remote is pinned to `https://github.com/ntindle/spark-vm`
  (`PINNED_UPSTREAM`). If `origin` is rewired, the updater refuses to deploy.
- Pre-deploy gates (the component's test suite) run **before** any file is
  installed. A gate failure aborts the deploy, writes an audit line, and leaves
  the watermark untouched — the next tick retries.
- A rollback snapshot of every file the deploy would overwrite is taken before
  install. A failed install, restart, or health check restores the snapshot,
  restarts the affected services, health-checks the restored state, and marks
  the commit **blocked** so the next tick does not retry-loop it (the block
  clears when a newer commit arrives).
- State (watermark, snapshots, audit log, lock) lives in
  `/home/ntindle/.sparkvm-deploy` with mode 0700 — outside the repo checkout.
- `proxy/deploy.sh` takes the same single-flight lock: a manual deploy racing
  the timer fails fast with "auto-deploy holds the lock" instead of
  interleaving installs.

## One-time setup (on the box)

```bash
cd ~/spark-vm
./deploy/auto-deploy.sh init        # clones the updater mirror + installs the
                                    # updater copy to ~/.sparkvm-deploy/bin
./deploy/auto-deploy.sh check       # dry run: what would deploy now
./deploy/auto-deploy.sh status      # watermark / audit / timer state
```

Enable the timer (re-run `init` after pulling updater changes — the timer does
not self-update):

```bash
sudo install -o root -g root -m 0644 deploy/auto-deploy.service deploy/auto-deploy.timer \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-deploy.timer
```

The timer runs as `ntindle` — the same identity that runs `proxy/deploy.sh`
manually — using that user's existing sudo rights. No new privilege is granted.

## How a run works

1. **Fetch** `origin/main` in the updater mirror (never the working checkout);
   refuse if `origin` isn't the pinned upstream.
2. **Diff** the watermark commit against the new head; map changed files to
   components via the installed `components.conf`. Paths matching no component
   are pull-only: the watermark advances but nothing is installed or restarted.
   Components sharing an `install_unit` (proxy+confirm share `deploy.sh`,
   which installs both unconditionally) deploy together so the snapshot always
   covers everything the install touches.
3. **Gate** each changed component's test suite. Fail → abort, audit, alert.
   Watermark untouched.
4. **Snapshot** every installed file the deploy would touch.
5. **Install**: each component's `install` command from the mirror
   (`proxy/deploy.sh --no-restart` for the proxy-confirm unit;
   `cred-ui/install.sh` stages the runtime set and publishes it atomically
   into the fixed install dir). No step syncs the operator's working
   checkout: a dirty checkout neither fails the deploy closed nor feeds
   anything the services run (issue #85; the old checkout-sync mechanism
   was retired outright).
6. **daemon-reload + enable**, then **restart** only the affected services
   (system + user units). The reload matters: restarting without it runs the
   stale in-memory unit definition after a unit-file change.
7. **Health-check** each component (`systemctl is-active`, incl. user units,
   plus TCP connect to the service port, with retries). Fail → restore
   snapshot, reload, restart, re-health-check, audit, alert, mark blocked.
8. **Watermark** advances to the new head (atomic write); snapshots older than
   the newest 5 are pruned; the audit log is capped at ~10k lines; one JSON
   line is appended to `audit.log`.

Concurrency: deploy and rollback take a `flock` on the state dir; an
overlapping timer tick exits quietly, a manual `rollback` during a deploy
fails fast, and a manual `proxy/deploy.sh` during a deploy fails fast.

## Host-side change inputs (`extra_inputs`)

The repo-diff mapping names changed components, but it cannot see files that
live on the box and not in the repo. Issue #302: a mitmproxy CA rotation (or
a first-run CA generation) with no concurrent code change used to leave a
stale or absent `with-proxy` CA bundle indefinitely — the rebuild is coupled
to the CA lifecycle now, not to code deploys. Each component may declare
`<component>_extra_paths` in `deploy/components.conf`: host-side inputs
whose digests are hashed on every tick and recorded in
`~/.sparkvm-deploy/extra-inputs-hash`. A digest change forces that
component's redeploy on the next tick, even when the repo diff is empty.

The only declared extra input today is the proxy's:
`"$SWAPD_HOME/.mitmproxy/mitmproxy-ca-cert.pem"` — a rotated or newly
generated CA forces the proxy-confirm unit to redeploy, so `proxy/deploy.sh`
step 4b rebuilds the bundle. Missing files hash as `missing`, non-regular
files as `nonregular`, read errors as `unreadable`: all are legitimate
digest inputs, so CA-generated, CA-rotated, and CA-deleted transitions all
count as changes. Digests are recorded in the updater state dir's
`extra-inputs-hash` file (`~/.sparkvm-deploy/extra-inputs-hash` —
`/home/ntindle/.sparkvm-deploy` on the production box). Issue #303: the
`WITH_PROXY_CA_BUNDLE` env override that
`components.conf` advertises is now exported into the child shell that runs
`proxy/deploy.sh`, so the snapshot/rollback coverage and the actual install
write the same path (previously the override only redirected the snapshot).

Forced-deploys are dampened: at most one extra-inputs-forced deploy per
component per hour (`EXTRA_INPUTS_FORCE_MIN_SECS=3600`), and attempts are
recorded even when they fail — a persistently-failing input cannot churn the
10-minute tick into a deploy/rollback loop. A failed forced deploy retries
on a later tick once the dampening window passes (the recorded attempt
stamps the same `_last_forced` epoch, so the immediate next tick skips it)
but **never marks the commit blocked** (the commit is fine — a same-commit
forced deploy is not a version deploy): it gets its own
snapshot directory (`<snapdir>-extra-inputs`, never clobbering the version
deploy's snapshot), and its audit lines carry `"trigger":"extra-inputs"` so
the trail does not masquerade as a version deploy. `status` surfaces the
current state: `extra-inputs(proxy): in sync (…)` or `CHANGED — recorded
… vs current … (next deploy force-redeploys proxy)`.

The hashing reads at deploy privilege through
`deploy/extra_inputs_hash_read.py` (installed next to the updater copy by
`init`; a stale install missing the helper fails loud with an ERROR, never
hashes everything as unreadable). The open discipline is atomic —
`O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, fstat before read, regular-file gate,
hardlink refusal — and the read is capped at 1 MiB
(`EXTRA_INPUTS_HASH_MAX_BYTES`, with the full file size folded in so pure
growth still flips the digest). The input is hashed twice per tick while
holding the single-flight lock, so the cap is what keeps a planted sparse
file or FIFO from stalling the tick; the same discipline pins
`proxy/privileged_read.py` via `deploy/test_privileged_open_conformance.py`.
Adding a new extra path: keep the list short, the files small, and the
paths readable at deploy privilege, and leave a `components.conf` comment
saying why (as the #302 comment does). Prefer paths the service user itself
cannot write: a writer of an extra path can force privileged redeploys at
the dampened rate, so the writability boundary is part of the choice.

## Manual operations

```bash
./deploy/auto-deploy.sh check      # what would deploy (fetch + diff, no mutation)
./deploy/auto-deploy.sh deploy     # run a deploy now
./deploy/auto-deploy.sh rollback [--no-block]  # restore the newest snapshot, restart + health-check
./deploy/auto-deploy.sh status     # watermark, blocked commit, audit size, last failure
tail -f ~/.sparkvm-deploy/audit.log
```

`rollback` restarts the snapshotted components' services and health-checks
them — files at the old commit with processes still on the new build is the
half-deployed state rollback exists to fix.

A manual `rollback` also marks the rolled-back commit (the pre-rollback
watermark, i.e. the deployed head being rolled back from) in
`blocked-commit`, so the next timer tick does not redeploy the same bad
commit — automatic rollbacks have always done this; manual ones now match
(issue #325). Pass `--no-block` when the rollback is for investigation
rather than condemnation (the tree itself is fine, you just need the old
state back for a look). The block auto-clears once a newer commit
supersedes the blocked one; to re-deploy the *same* tree after a manual
fix, clear it by hand — `status` prints the exact `rm` command.

## Components

| component | repo paths | services restarted | gate | install | health |
|---|---|---|---|---|---|
| `proxy` | `proxy/` (+ host-side CA cert, [extra input](#host-side-change-inputs-extra_inputs)) | swap-proxy, swap-inference | pytest (swap addon, grant writer, round6) | `proxy/deploy.sh --no-restart` | tcp 127.0.0.1:18080, 18081 |
| `confirm` | `confirm/` | confirmd | pytest (confirmd) | (shares proxy's unit) | tcp TAILNET:8443 (resolved at check time) |
| `cred-ui` | `cred-ui/` | cred-ui (user unit) | py_compile + pytest (http, version, install) | `cred-ui/install.sh` → fixed dir + user unit | tcp 127.0.0.1:18740 |

Add a component by extending `deploy/components.conf` (paths, services, gate,
health, install command, install paths) — then re-run `init`
so the installed copy picks it up.

## Known limitations

- **Swap-proxy restart is not drained.** mitmdump restarts in well under a
  second, but an in-flight swap at that instant fails closed on the client
  (which retries). A quiet-moment/drain scheduler is a follow-up, not this
  slice.
- **confirmd's health target is the box's tailnet address, resolved live.**
  `components.conf` names it `TAILNET:8443` and the updater resolves the
  current `tailscale ip -4` at check time; `confirmd.service` likewise no
  longer pins the literal IP (`confirmd.py` resolves its bind address via
  `tailscale ip -4` at startup). A tailnet rekey/IP change survives a restart
  instead of wedging the service or failing every health check.
- **The updater does not self-update.** A merged fix to `auto-deploy.sh`
  itself, or a new `components.conf` entry, takes effect only after the
  operator re-runs `auto-deploy.sh init` from an updated checkout. `init`
  records the checkout commit the installed copy came from; `status`, `check`,
  and any `deploy` that actually has work (pull-only or component deploys)
  warn when `origin/main` carries newer `deploy/` changes, so the staleness
  is visible instead of silent. The quiet up-to-date timer tick deliberately
  stays quiet.
- **cred-ui's runtime is the fixed install directory**
  (`~/.local/share/spark-vm/cred-ui`), refreshed from the mirror by the
  install step at deploy. The working checkout's `cred-ui/` subtree is dev
  source only — hand-edits there no longer affect the running service.
- The updater does not deploy unreviewed branches — it only ever advances the
  mirror to `origin/main`.
- First run has no watermark and deploys everything at the current head.

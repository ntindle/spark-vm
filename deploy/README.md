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
- Residual: `cred-ui` *executes* from the working checkout (`%h/spark-vm/…`),
  so checkout-write access still implies code influence over cred-ui at
  restart time. The updater syncs the `cred-ui/` subtree from the mirror at
  deploy (failing closed on uncommitted changes), but the checkout remains a
  trust boundary for that one component — documented, not silent.
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
3. **Gate** each changed component's test suite, plus checkout-sync
   preconditions. Fail → abort, audit, alert. Watermark untouched.
4. **Snapshot** every installed file the deploy would touch (plus the
   checkout subtree for `checkout_sync` components).
5. **Install**: each component's `install` command from the mirror
   (`proxy/deploy.sh --no-restart` for the proxy-confirm unit); `cred-ui`
   syncs its subtree from the mirror into the working checkout.
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

## Manual operations

```bash
./deploy/auto-deploy.sh check      # what would deploy (fetch + diff, no mutation)
./deploy/auto-deploy.sh deploy     # run a deploy now
./deploy/auto-deploy.sh rollback   # restore the newest snapshot, restart + health-check
./deploy/auto-deploy.sh status     # watermark, blocked commit, audit size, last failure
tail -f ~/.sparkvm-deploy/audit.log
```

`rollback` restarts the snapshotted components' services and health-checks
them — files at the old commit with processes still on the new build is the
half-deployed state rollback exists to fix.

## Components

| component | repo paths | services restarted | gate | install | health |
|---|---|---|---|---|---|
| `proxy` | `proxy/` | swap-proxy, swap-inference | pytest (swap addon, grant writer, round6) | `proxy/deploy.sh --no-restart` | tcp 127.0.0.1:18080, 18081 |
| `confirm` | `confirm/` | confirmd | pytest (confirmd) | (shares proxy's unit) | tcp TAILNET:8443 (resolved at check time) |
| `cred-ui` | `cred-ui/` | cred-ui (user unit) | py_compile | subtree sync into checkout | tcp 127.0.0.1:18740 |

Add a component by extending `deploy/components.conf` (paths, services, gate,
health, install command or checkout_sync, install paths) — then re-run `init`
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
  records the checkout commit the installed copy came from; `status` and
  `check` warn when `origin/main` carries newer `deploy/` changes, so the
  staleness is visible instead of silent.
- **cred-ui's runtime is the working checkout.** The updater owns the
  `cred-ui/` subtree once enabled (uncommitted changes there fail the deploy
  closed); don't hand-edit it on the box.
- The updater does not deploy unreviewed branches — it only ever advances the
  mirror to `origin/main`.
- First run has no watermark and deploys everything at the current head.

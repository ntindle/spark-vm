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
- The fetch remote is pinned to `https://github.com/ntindle/spark-vm`
  (`PINNED_UPSTREAM`). If `origin` is rewired, the updater refuses to deploy.
- Pre-deploy gates (the component's test suite) run **before** any file is
  installed. A gate failure aborts the deploy, writes an audit line, and leaves
  the watermark untouched — the next tick retries.
- A rollback snapshot of every file the deploy would overwrite is taken before
  install. A failed install or health check restores the snapshot and restarts
  the affected services, then records the failure in the audit log and in
  `~/.sparkvm-deploy/last-failure`.
- State (watermark, snapshots, audit log, lock) lives in
  `/home/ntindle/.sparkvm-deploy` — **outside the repo checkout** — so a
  compromised or careless agent with checkout write access cannot rewire what
  the updater believes is deployed.

## One-time setup (on the box)

```bash
cd ~/spark-vm
./deploy/auto-deploy.sh init        # clones the updater mirror repo
./deploy/auto-deploy.sh check       # dry run: what would deploy now
./deploy/auto-deploy.sh status      # watermark / audit / timer state
```

Enable the timer:

```bash
sudo install -o root -g root -m 0644 deploy/auto-deploy.service deploy/auto-deploy.timer \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-deploy.timer
```

The timer runs as `ntindle` — the same identity that runs `proxy/deploy.sh`
manually — using that user's existing sudo rights. No new privilege is granted.

## How a run works

1. **Fetch** `origin/main` in the updater mirror (never the working checkout).
2. **Diff** the watermark commit against the new head; map changed files to
   components via `deploy/components.conf`. Paths matching no component are
   pull-only: the watermark advances but nothing is installed or restarted.
3. **Gate** each changed component's test suite. Fail → abort, audit, alert.
4. **Snapshot** every installed file the deploy would touch.
5. **Install**: `proxy/deploy.sh --no-restart` for the `proxy`/`confirm`
   components (idempotent; service control stays with the updater);
   `cred-ui` deploys as restart-only since it runs from the checkout.
6. **Restart** only the affected services (system + user units).
7. **Health-check** each component (`systemctl is-active` + TCP connect to the
   service port, with retries). Fail → restore snapshot, restart services,
   audit, alert.
8. **Watermark** advances to the new head; snapshots older than the newest 5
   are pruned; one JSON line is appended to `audit.log`.

Concurrency: runs take a `flock` on the state dir; an overlapping tick exits
quietly.

## Manual operations

```bash
./deploy/auto-deploy.sh check      # what would deploy (fetch + diff, no mutation)
./deploy/auto-deploy.sh deploy     # run a deploy now
./deploy/auto-deploy.sh rollback   # restore the newest snapshot + restart its services
./deploy/auto-deploy.sh status     # watermark, audit size, timer state, last failure
tail -f ~/.sparkvm-deploy/audit.log
```

## Components

| component | repo paths | services restarted | gate | health |
|---|---|---|---|---|
| `proxy` | `proxy/` | swap-proxy, swap-inference | pytest (swap addon, grant writer, round6) | tcp 127.0.0.1:18080, 18081 |
| `confirm` | `confirm/` | confirmd | pytest (confirmd) | tcp 100.65.241.20:8443 |
| `cred-ui` | `cred-ui/` | cred-ui (user unit) | py_compile | tcp 127.0.0.1:18740 |

Add a component by extending `deploy/components.conf` (paths, services, gate,
health, install paths) and teaching `deploy_component` its install step.

## Known limitations

- **Swap-proxy restart is not drained.** mitmdump restarts in well under a
  second, but an in-flight swap at that instant fails closed on the client
  (which retries). A quiet-moment/drain scheduler is a follow-up, not this
  slice.
- **confirmd's health IP is the box's tailnet address** (`100.65.241.20:8443`),
  taken from `confirm/confirmd.service`. If the box's tailnet IP changes,
  update `components.conf`.
- The updater does not deploy unreviewed branches — it only ever fast-forwards
  the mirror to `origin/main`.
- First run has no watermark and deploys everything at the current head.

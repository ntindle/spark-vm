# cred-ui

Localhost-only web UI for the swapd credential store on spark-vm. Adds,
lists, and removes credentials without a terminal — the phone-friendly
front end for `cred set` / `cred register`.

## Run it

```bash
# install the runtime outside the checkout, then enable the user service
# (linger is enabled on this box)
bash ~/spark-vm/cred-ui/install.sh
systemctl --user daemon-reload
systemctl --user enable --now cred-ui
```

`install.sh` copies the page and the server into
`~/.local/share/spark-vm/cred-ui/` and installs the user unit into
`~/.config/systemd/user/` — the running service never executes from the
working checkout, so an edit to the checkout can't change the page your
browser loads. Re-run `install.sh` after pulling to refresh the install.
The install is staged: the full runtime set is assembled in a staging
directory next to the install dir and each file is renamed over the live
copy, so an interrupted install can never leave a half-written live file
behind.

It listens on **127.0.0.1:18740** only. Reach it over an SSH tunnel:

```bash
# from your laptop / phone (Termius: add a local port forward instead)
ssh -L 18740:127.0.0.1:18740 ntindle@spark-vm
```

Then open `http://127.0.0.1:18740` in a browser.

## What it does

- **Add / update**: name, secret value, entry (default `access_token`),
  placement (`Authorization: Bearer` header, custom header, query param,
  or URL path segment), and allowed hosts — one form, no CLI flags.
  Hosts must be plain hostnames (letters, digits, hyphens, dots —
  no underscores, no ports): the narrow writer enforces this, and the UI
  validates up front so a bad host never fails *after* the secret is stored.
- **List**: every credential with value-stored / registered state,
  entries, placements, and hosts. **Values are never displayed.**
- **Hosts**: add or remove allowed hosts inline per credential.
- **Delete**: removes the stored value and the registry entry.
- The list **auto-refreshes every 3 seconds** so two sessions stay in sync.

## Security notes

- The service runs from a fixed install directory
  (`~/.local/share/spark-vm/cred-ui`), written only by `install.sh` or the
  gated auto-deploy path — never from the working checkout. An edit to the
  checkout (a stray agent write, a dirty merge) can no longer change the
  page your browser loads, and can no longer block the updater from
  refreshing the install. Honest residual: the install directory is owned
  by the same user that runs the deploy, so this closes the
  checkout-writer hole, not the deploy-operator trust the auto-deploy
  already assumes (it deploys whatever is merged to `main`).
- Writes go through the same narrow sudo writers as the `cred` CLI
  (`cred-store-set`, `cred-registry-set`); the UI adds no new privilege path.
- No endpoint returns a secret value, and the server never logs request
  bodies. `Cache-Control: no-store` on everything.
- Binding is 127.0.0.1-only by construction (`BIND` in `cred-ui.py`).
  Do not change it to `0.0.0.0` — the tunnel is the access control.
- Stdlib only, no dependencies.

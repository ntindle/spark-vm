# cred-ui

Localhost-only web UI for the swapd credential store on spark-vm. Adds,
lists, and removes credentials without a terminal — the phone-friendly
front end for `cred set` / `cred register`.

## Run it

```bash
# install + start (user systemd service; linger is enabled on this box)
mkdir -p ~/.config/systemd/user
cp ~/spark-vm/cred-ui/cred-ui.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now cred-ui
```

It listens on **127.0.0.1:18740** only. Reach it over an SSH tunnel:

```bash
# from your laptop / phone (Termius: add a local port forward instead)
ssh -L 18740:127.0.0.1:18740 spark@spark-vm
```

Then open http://127.0.0.1:18740 in a browser.

## What it does

- **Add / update**: name, secret value, entry (default `access_token`),
  placement (`Authorization: Bearer` header, custom header, query param,
  or URL path segment), and allowed hosts — one form, no CLI flags.
- **List**: every credential with value-stored / registered state,
  entries, placements, and hosts. **Values are never displayed.**
- **Hosts**: add or remove allowed hosts inline per credential.
- **Delete**: removes the stored value and the registry entry.
- The list **auto-refreshes every 3 seconds** so two sessions stay in sync.

## Security notes

- Writes go through the same narrow sudo writers as the `cred` CLI
  (`cred-store-set`, `cred-registry-set`); the UI adds no new privilege path.
- No endpoint returns a secret value, and the server never logs request
  bodies. `Cache-Control: no-store` on everything.
- Binding is 127.0.0.1-only by construction (`BIND` in `cred-ui.py`).
  Do not change it to `0.0.0.0` — the tunnel is the access control.
- Stdlib only, no dependencies.

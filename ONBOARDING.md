# spark-vm onboarding — from zero to deployed

This is the connective tissue: how an agent machine (or a human) goes from
nothing to a working spark-vm with the credential proxy, job runner, and
desktop automation. Component docs live where they belong (`SETUP.md`,
`proxy/`, `muse-job/README.md`, `cua/README.md`, `cred-ui/README.md`);
this file is the order of operations.

## 0. The picture

```
agent machine (Hatch VM) ──Tailscale──▶ spark-vm (Ubuntu 24.04, 8 vCPU, 15 GB RAM)
      │                                        │
      │ SSH as ntindle                        │ swapd proxy swaps hsurr:<name>
      │ (keypair + ProxyCommand)                │ placeholders for allowlisted
      ▼                                        │ hosts only; secrets never
   this repo ──push──▶ ~/spark-vm ──deploy──▶   │ leave the swapd store
```

The agent never handles real secret values. The human installs them via
`cred set` or the cred-ui web page; everything the agent writes carries
`hsurr:<name>` placeholders.

## 1. Tailscale — join the tailnet

On the agent machine:

```bash
tailscale up
```

It prints an approval link. **The human opens it** — only they can approve
the device. Re-running `tailscale up` reprints the link (each ask lasts five
minutes). Confirm with:

```bash
tailscale status   # shows the network and every device
```

Notes that bite:

- Ordinary networking does **not** reach the tailnet. Route TCP through the
  runtime proxy with port **3130**: `tunnel_proxy="${HTTPS_PROXY%:*}:3130"`,
  then `curl --proxy "$tunnel_proxy" http://<tailnet-ip>:<port>/…`.
- TCP only — no ping/UDP. A failed ping means nothing; open a TCP
  connection to test reachability.
- This VM is client-only: it makes outgoing connections and accepts none.

## 2. The VM — spark-vm

A plain Ubuntu 24.04 box. Reference specs: 8 vCPU, 15 GB RAM, 250 GB disk.
On it:

- Create user `ntindle` with passwordless sudo (`/etc/sudoers.d/ntindle`).
- Install Tailscale, `tailscale up`, approve it — note its tailnet IP
  (ours is `100.65.241.20`).
- Enable linger so user services survive logout:
  `sudo loginctl enable-linger ntindle`.

> **The username matters.** The deploy tooling assumes `ntindle`: see the
> hardcoded paths in `proxy/deploy.sh` (`/home/ntindle/.sparkvm-deploy`) and
> the `User=ntindle` line in `deploy/auto-deploy.service`. Use a different
> username on your own box only if you grep for and adjust those references.

## 3. SSH — agent → VM

On the agent machine:

- Keypair at `~/.ssh/id_ed25519`; add the public key to the VM's
  `/home/ntindle/.ssh/authorized_keys`.
- The tailnet is reached via a TCP proxy, so SSH needs a ProxyCommand.
  Ours is `~/workspace/bin/ts-ssh-proxy.py %h %p`, which does an HTTP
  CONNECT through the port-3130 proxy with Proxy-Authorization from
  `HTTPS_PROXY`. Two lessons baked into it: call `s.setblocking(True)`
  after the CONNECT handshake (the socket can be left non-blocking), and
  forward any bytes already buffered past the `\r\n\r\n` terminator.
- Keep a persistent multiplexor so every command doesn't re-handshake:

```bash
ssh -M -S ~/.ssh/cm-newvm.sock -o ControlPersist=2h \
    -o ProxyCommand="~/workspace/bin/ts-ssh-proxy.py %h %p" \
    -i ~/.ssh/id_ed25519 ntindle@100.65.241.20
```

Then `ssh -S ~/.ssh/cm-newvm.sock ntindle@100.65.241.20 <cmd>` for everything.

## 4. Deploy the stack

On the VM, as `ntindle`:

```bash
git clone https://github.com/ntindle/spark-vm.git ~/spark-vm
cd ~/spark-vm

./proxy/deploy.sh          # swap proxy + inference proxy + confirmd
                            # (installs narrow sudo writers to /usr/local/bin)

# credential CLI -> ~/bin/cred (single-file, stdlib only; see SETUP.md)

# muse-job: CLI + lifecycle-hooks plugin
cp muse-job/bin/muse-job ~/bin/
muse plugins install ./muse-job/plugin   # then: muse plugins approve
muse plugins validate muse-job

# credential web UI (localhost-only; see cred-ui/README.md)
mkdir -p ~/.config/systemd/user
cp cred-ui/cred-ui.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now cred-ui

# CUA desktop driver (whole-desktop control; see cua/README.md)
./cua/cua-desktop.sh start
```

That starts the full desktop stack (details in `cua/README.md`):

- **Xvfb `:98`** — a virtual display, 1280x800, separate from the VM's own
  GNOME/Wayland session (the X11 driver cannot drive Wayland, so the
  desktop lives on its own display).
- **XFCE** — `xfwm4` + `xfce4-panel` + `xfdesktop` launched as individual
  components (the full `xfce4-session` crashes here), giving a normal
  desktop with a taskbar and app menu.
- **cua-driver 0.28.2** (official `trycua/cua` release) as a daemon driving
  the whole desktop — keyboard, mouse, screenshots — not just a browser.
- **cua-bridge.py** — localhost-only HTTP bridge on `127.0.0.1:18731`.
  The agent reaches it over an SSH tunnel (`-L 18732:127.0.0.1:18731`);
  nothing is exposed publicly.
- **Blender** — BlenderMCP runs headless on a *separate* Xvfb `:99`
  (socket `127.0.0.1:9876`, untouched); the bridge can launch the Blender
  GUI on `:98` to view and drive it.

Verify: `./cua/cua-desktop.sh status` — every component should report ok,
and `curl 127.0.0.1:18731/api/status` should answer.

After `git pull`, re-run `./proxy/deploy.sh` (it reinstalls unit files and
helpers from the repo — the repo is the only source) and restart
`cred-ui` if it changed.

## 5. Credentials — the human part

Secrets are installed **only** by the human, in their own session. Two ways:

**Web UI (easiest, phone-friendly).** Forward the port and open the page:

```bash
ssh -L 18740:127.0.0.1:18740 ntindle@spark-vm
# open http://127.0.0.1:18740 — add name, paste value, pick placement,
# list allowed hosts. The list auto-refreshes every 3 s.
```

**CLI.** `cred set <name>` (paste or no-echo prompt), then
`cred register <name> --host <h>…` with a placement
(`bearer_header` | `custom_header:<Name>` | `query_param:<name>` |
`url_path_segment`). See `SETUP.md` § "cred — the credential system".

Either way, values are never displayed back — list shows names, placements,
and hosts only.

## 6. Verify

- [ ] `tailscale status` on both machines shows the other.
- [ ] `ssh -S ~/.ssh/cm-newvm.sock ntindle@<tailnet-ip> true` works.
- [ ] `./proxy/deploy.sh` completes; proxy unit is active.
- [ ] `muse plugins list` shows `muse-job` installed and approved.
- [ ] `systemctl --user is-active cred-ui` → `active`.
- [ ] cred-ui page loads through the tunnel; test credential round-trips.
- [ ] `~/spark-vm/scripts/push.sh` works (it refuses secret-shaped content
      before pushing).

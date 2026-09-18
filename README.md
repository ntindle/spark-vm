# spark-vm

**Give your Muse a bigger computer.**

Spark is my Muse — the AI agent I work with every day. Out of the box it
lives in a small sandbox; `spark-vm` is the tooling that gives it a real VM
on my Unraid box that it can reach and treat as its own dev machine: 8
vCPU, 15 GB RAM, 250 GB disk, Docker, a real browser, and a full Linux
desktop it can see and drive. The heavy stuff happens here — coding jobs,
browser automation, long builds — while chat stays snappy.

It's a work in progress, but you can try it too. Clone it, read
`ONBOARDING.md`, and adapt the Tailscale/SSH bits to your own network.

<p align="center">
  <img src="assets/spark-coding.png" width="640" alt="Spark, hard at work next to the 12U homelab rack">
</p>

## How it's wired

- The VM runs Ubuntu 24.04 on Unraid, joined to my tailnet. The agent
  reaches it over SSH (plus a small TCP tunnel helper, since the sandbox
  has no raw tailnet socket).
- Nothing on the box is public. Agent-facing services bind localhost only;
  off-box access is SSH tunnels.
- **Secrets stay secret — even from the agent.** It never sees real
  credential values. Configs carry `hsurr:<name>` placeholders, and a
  swapping egress proxy exchanges them for real values only toward
  allowlisted hosts, with every swap audited. Secrets are installed only
  by a human via `cred set` in their own SSH session. `ENVIRONMENT.md`
  has the full trust model.

## What's here

| Path | What it is |
|---|---|
| `ONBOARDING.md` | From-zero guide: Tailscale join, VM setup, deploy order, verify checklist. Start here. |
| `proxy/` | Transparent credential-swapping egress proxy (mitmproxy as a dedicated `swapd` user) + `deploy.sh`. The heart of the secrets model. |
| `cred/` | `cred` CLI for the credential store (`set`/`register`/…), with narrow sudo helpers so only the store owner touches real values. |
| `cred-ui/` | Localhost-only web UI for the credential store (`127.0.0.1:18740`) — manage credentials and host bindings from your phone over an SSH tunnel. |
| `cua/` | Full-desktop control via the official trycua/cua driver: Xvfb + XFCE supervisor, localhost HTTP bridge (`127.0.0.1:18731`), and `PANEL_SPEC.md` — the spec for building your own control panel against the bridge API, with a worked Blender example. |
| `muse-job/` | Delegation wrapper for the terminal coding agent: `spawn/steer/status/log/kill/resume/close/watch` CLI, one git worktree + tmux session per job, plugin hooks, watchdog. This is how big coding tasks get handed to the box. |
| `confirm/` | `confirmd`: a tiny confirmation service so the box can ask a human to approve something before doing it. |
| `jail/` | Jail setup for running untrusted work. |
| `browser-driver/` | Browser automation driver (spec + review). |
| `credlib/` | Secret-filling helpers used by the proxy and friends. |
| `scripts/` | Utilities: Playwright smoke test, `push.sh` (commit + push box-side changes back here). |
| `SETUP.md` / `ENVIRONMENT.md` | Box inventory/docs, and the trust model this repo is designed around. |

## Try it

1. Provision an Ubuntu 24.04 VM wherever you like — Unraid, Proxmox, a cloud box, anything your agent can SSH into.
2. Follow `ONBOARDING.md` top to bottom: Tailscale join, SSH wiring, deploy order (`proxy/deploy.sh` → `cred` → `muse-job` → `cred-ui` → CUA), verify checklist.
3. Teach your agent the SSH incantations for reaching the box, and put it to work there.

Expect rough edges — this tracks one person's live setup, not a polished
product. Adapt freely.

## Pushing changes

On the box, `~/spark-vm` is a clone of this repo. After changing anything
worth keeping:

```bash
~/spark-vm/scripts/push.sh
```

It commits and pushes to `origin`. Push auth comes from the credential
store (`echo '<fine-grained-PAT>' | cred set github`; the PAT needs
**contents: write** on this repo). No real secrets are ever committed —
`push.sh` refuses anything secret-shaped in staged changes, and the
credential store lives outside the repo.

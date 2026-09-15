# ENVIRONMENT.md

Operating environment and trust model for this repo. Written for the
reviewing agent, which works from the repo alone and does not know the
environment the implementer runs in. If anything here goes stale, fix it —
a reviewer reasoning from wrong environment facts will produce wrong findings.

## The cast

- **The user (ntindle).** Human. Owns both machines, installs secrets
  (`cred set`) from his own SSH sessions, manages the allowlist, and
  deploys proxy changes. The only party who ever handles real secret values.
- **The implementer (Spark).** An AI agent running on a Hatch VM (Meta's
  runtime) — *not* on spark-vm. Reaches spark-vm only over SSH as user
  `ntindle`, via a Tailscale TCP proxy with a persistent ControlMaster
  multiplexor. Writes code in a staging clone of this repo on its own box,
  then pushes; deployment to spark-vm happens afterwards (see Workflow).
- **The reviewing agent.** Also off-box, works from this repo. Scope is
  `browser-driver/REVIEW.md` plus small repo hygiene (e.g. `.gitignore`).
  It does not implement fixes and does not touch spark-vm.

## "The cell"

"Cell" is the implementer's word for its own sandbox: the Hatch VM it runs
in. Secrets never enter the cell — that physical separation is what the
cell's credential security rests on. spark-vm's swap proxy is the attempt to
get the same property on a box the agent *does* log into.

## The implementer's own security model (the thing being copied)

On the implementer's box, credentials live in the **Secure Vault**: secure
storage the agent cannot read. When the user enters a password or API key,
it goes straight into the vault; the agent only ever sees an opaque
reference (a ticket stub, e.g. `[credential:<uuid>]`). When the browser
needs the value, the runtime delivers it directly into the page — the agent
never sees the raw text. One-time codes arrive as redeem-only markers that
only the browser-fill step can redeem. The boundary is enforced *around*
the agent by the runtime, not by the agent's promises.

The spark-vm design mirrors this with local parts:

| Cell (Hatch VM)              | spark-vm equivalent                                          |
|------------------------------|--------------------------------------------------------------|
| Secure Vault                 | `swapd`'s store: `/home/swapd/secrets` (0700, user `swapd`) + `credentials.json` registry |
| Opaque `[credential:…]` ref  | `hsurr:<name>[:entry]` placeholder                                      |
| Runtime direct-to-page delivery | mitmproxy addon (`proxy/swap_addon.py`) swapping placeholders at egress |
| —                            | Audit log `/home/swapd/swap.log` (names only, never values)  |

## spark-vm access and privilege (as of 2026-09-15)

- Implementer SSH: as `ntindle` over the tailnet via a TCP CONNECT proxy,
  reusing a persistent ControlMaster socket. New direct connections may
  trigger a user approval; reuse the mux.
- `ntindle` has **passwordless sudo** (`/etc/sudoers.d/ntindle`). The
  implementer is therefore effectively root on demand. This is exactly the
  trust-boundary overclaim in REVIEW.md finding 2: today "the agent cannot
  read secrets" is policy, not enforcement. The user is setting up a
  dedicated machine/login separately; until that lands, review findings
  assuming the implementer *can* become root.
- The proxy itself runs as the dedicated `swapd` user
  (`proxy/swap-proxy.service`: `mitmdump -p 18080 --set
  listen_host=127.0.0.1 -s /home/swapd/swap_addon.py`). Secrets are
  installed only by the user via `cred set` in his own sessions.
- `cred` CLI: deployed to `~/bin/cred` on spark-vm (also on PATH via
  `/usr/local/bin/cred`). Secrets live in the swapd-owned store
  (`/home/swapd/secrets`), installed only via `cred set` in the user's
  own sessions; placement and per-credential host bindings go through
  `cred register` into `/home/swapd/credentials.json`.

## Workflow: repo is the source of truth

1. Implementer edits the **staging clone** on its own box.
2. Commit, push to `github.com/ntindle/spark-vm` (**private** repo; GitHub
   `main` is authoritative — the staging clone may lag it).
3. On spark-vm, `~/spark-vm` is a clone of the same repo; pull there.
4. Deploy: copy changed files into place (e.g. `proxy/swap_addon.py` →
   `/home/swapd/swap_addon.py`), `sudo systemctl restart swap-proxy` for
   addon changes (new hosts/secrets are picked up without a restart),
   sync `SETUP.md` → `/home/ntindle/SETUP.md`.
5. Verify the live state matches the repo (hash-compare the addon).

Rules: never edit the live proxy in place; never commit real secrets
(`scripts/push.sh` refuses secret-shaped staged changes); never test with
real credentials — dummies only.

## Key paths

| Path | What |
|---|---|
| `proxy/swap_addon.py` | The credential-swapping mitmproxy addon (source of truth; deployed to `/home/swapd/swap_addon.py`) |
| `proxy/test_swap_addon.py` | Unit tests for the addon's pure functions — `python3 -m unittest proxy/test_swap_addon.py` from repo root, no mitmproxy needed |
| `proxy/hosts.allow` | Outer egress gate: hosts the proxy will swap for |
| `proxy/sudoers-swapd` | sudo rules for the swapd helpers (see REVIEW.md finding 11 on the glob issue) |
| `proxy/swap-proxy.service` | systemd unit (runs as `swapd`, port 18080) |
| `proxy/with-proxy` | Shell snippet exporting `*_proxy=http://127.0.0.1:18080` |
| `cred`, `credlib/` | Credential CLI + library |
| `browser-driver/SPEC.md` | Spec for `bdrive` (narrow action driver) + `obox` (on-box agent) |
| `browser-driver/REVIEW.md` | The reviewer's findings — the authoritative issue list |
| `SETUP.md` | Operator runbook (website-login recipe, troubleshooting); deployed copy at `/home/ntindle/SETUP.md` |
| `scripts/push.sh` | Box-side commit+push helper (runs on spark-vm; sends `Basic base64(x-access-token:hsurr:github)`, which the proxy swaps for the real PAT on allowlisted github.com) |

On spark-vm (live, not in repo): `/home/swapd/secrets/` (0700),
`/home/swapd/credentials.json` (registry), `/home/swapd/swap.log`
(audit log, names only), `/home/swapd/.venvs/mitm` (mitmproxy venv).

## Trust boundaries for reviewers

- **Orchestrator** = the implementer agent, off-box. Treat it as
  compromisable (prompt injection, mistakes). Any security property that
  requires the orchestrator to behave is policy, not enforcement — say so
  explicitly.
- **swapd / proxy** = on-box, holds real secrets in memory and at
  `/home/swapd/secrets`. Its attack surface is the addon code and the
  mitmproxy surface.
- **`bdrive`** (planned) = on-box "hands": narrow action protocol, no
  reasoning, no arbitrary code execution. **`obox`** (planned) = on-box
  "brain": observe→decide→act loop using the proxy for credentials.
- Confirmations (`need_info`, purchase approvals) that travel back through
  the orchestrator do not contain a compromised orchestrator. A real
  confirmation needs a channel the orchestrator cannot forge (direct
  user→driver/proxy signal). See REVIEW.md finding 3.
- The audit log is a verification aid, not a security control, while the
  agent account can modify the box.

## Standing prohibitions (all agents, always)

- Never run `cred get`. Never read `/home/swapd/secrets` or
  `/home/swapd/credentials.json`.
- Never ask for real secrets in chat. Never bypass the substitution proxy.
- Never place real secret values in commands, logs, transcripts, memory,
  repositories, screenshots, or browser-driver responses.
- A classic GitHub credential named `github` exists in the store; never
  retrieve or display it.
- Conformance tests use dummy credentials only.

## Reviewer operating notes

- Runnable verification: `python3 -m unittest proxy/test_swap_addon.py`
  from the repo root (no mitmproxy needed; the addon import is stubbed).
  Findings marked CONFIRMED in REVIEW.md were reproduced against the
  addon's pure functions — the probe for each lives at the end of REVIEW.md.
- The reviewer does not know the implementer's box: implementer-local
  paths (e.g. `~/workspace/newvm/repo`) are meaningless to it. Prefer
  repo-relative paths in findings.
- GitHub `main` is authoritative. If the local clone and `main` disagree,
  `main` wins. The box clone (`~/spark-vm` on spark-vm) only ever
  pulls — never merge from it into a staging branch; a merge from the
  box re-imports its commits under new hashes (nit, review round 4).

## Current work (2026-09-15)

- Proxy fixes from REVIEW.md findings 1, 5–9, 23 (+ any new small,
  well-specified addon findings) are being implemented with one
  conformance test per finding, dummy credentials only. Deployed only
  after green.
- The user is setting up the dedicated agent machine/login (finding 2,
  option a) separately — not in scope for the implementer.
- Confirmation-channel design (finding 3) and response scrubbing
  (finding 4) are decide-before-bdrive items; not yet implemented.

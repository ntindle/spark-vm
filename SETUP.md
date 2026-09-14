# spark-vm — dev workhorse setup

Hostname `spark-vm`, Ubuntu 24.04.5 LTS (kernel 7.0.0-31-generic), 8 vCPU,
15 GB RAM, 250 GB disk. Tailnet IP `100.65.241.20`, user `ntindle`
(passwordless sudo). Set up 2026-09-14.

Agent access: SSH as `ntindle` over the Tailscale TCP proxy; a persistent
multiplexed master keeps connections approval-free. Network, SSH, and
Tailscale configuration were deliberately left untouched.

## Install inventory (all verified working)

| Tool | Version | Notes |
|---|---|---|
| git | 2.43.0 | |
| curl | 8.5.0 | |
| wget | 1.21.4 | |
| gh | 2.45.0 | GitHub CLI |
| python3 | 3.12.3 | system python; `venv` module present |
| pip | 24.0 | |
| node | v22.23.2 | |
| npm | 10.9.8 | |
| docker | 29.1.3 (Ubuntu repo build `29.1.3-0ubuntu3~24.04.2`) | daemon verified via `docker run --rm hello-world`; `ntindle` is in the `docker` group, no sudo needed |
| playwright | 1.62.0 | in `/home/ntindle/.venvs/pw` (python venv) |
| chromium | (playwright-managed, `~/.cache/ms-playwright`) | headless-tested: loaded https://example.com, correct title, valid PNG screenshot |
| cred | 1.0 (local) | `/home/ntindle/bin/cred`, on PATH via `~/.profile` |

Playwright system deps were installed with `playwright install-deps chromium`
(fonts, xvfb, codec libs). Use the venv python for browser scripts:
`/home/ntindle/.venvs/pw/bin/python`.

## cred — the credential system

Single-file Python CLI (stdlib only) at `/home/ntindle/bin/cred`.
Default backend is plain files: `~/.config/spark-credentials/<name>`,
directory `0700`, files `0600`. Backend is selected by `SPARK_CRED_BACKEND`
(`file` default; `bitwarden` reserved for a future `bw`-CLI backend — the
code is structured so it slots in without changing callers).

```bash
# store a secret (piped, or interactive no-echo prompt with confirmation)
echo -n "sk-..." | cred set openai-api-key
cred set github-token            # prompts twice, no echo

# read one back (no trailing newline — safe to pipe)
cred get openai-api-key

# list names only — values are never printed by list
cred list

# delete
cred delete old-token

# run anything with every credential exported as SPARK_CRED_<NAME>
# (uppercased, '-' -> '_', e.g. SPARK_CRED_OPENAI_API_KEY)
cred run -- python -m autogpt ...
cred run -- env | grep SPARK_CRED_
```

Names are restricted to `[A-Za-z0-9_-]+`; anything else is rejected.

## The missing-credential flow (this is the "automatic" part)

Automation never blocks on a human *except* at the one place it must:
the first time a secret is needed.

1. A script needs `SPARK_CRED_OPENAI_API_KEY` but it was never stored.
2. `cred get openai-api-key` exits **3** with:
   `credential 'openai-api-key' not set — add with: cred set openai-api-key`
3. The human runs that one command. Once.
4. Every downstream script using `cred run -- ...` now works automatically —
   no config edits, no env files to remember, no restarts.

Convention: scripts should call `cred get <name>` (or run under `cred run`)
and let exit 3 surface the exact fix. Never invent a fallback secret.

## Browser automation example

```python
# run with: /home/ntindle/.venvs/pw/bin/python script.py
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com", timeout=30000)
    print(page.title())
    page.screenshot(path="/tmp/shot.png")
    browser.close()
```

This is direct browser automation on the box itself — no proxy agent in the
middle. Combined with `cred run`, a script can drive a logged-in session
end to end:

```bash
cred run -- /home/ntindle/.venvs/pw/bin/python my-automation.py
# inside: os.environ["SPARK_CRED_MY_SERVICE_PASSWORD"]
```

## Security note

The file backend is 0600 files on a personal tailnet-only VM — the same trust
model as `~/.ssh`. That is a deliberate starting point, not the end state:
no encryption at rest, no audit log, no rotation. When the Bitwarden (or
Apple Passwords) integration lands, set `SPARK_CRED_BACKEND=bitwarden` and
callers don't change. Until then: this box holds secrets the way your laptop
holds SSH keys — fine for a private machine, not for shared infrastructure.

## Intentionally left out

- **AutoGPT was not cloned.** Capability readiness was the goal; cloning is
  one `git clone` away when you want a running instance.
- Docker's official apt repo was not needed — the Ubuntu `docker.io` build
  (29.1.3) works and the daemon is verified.
- No system python packages were installed with `--break-system-packages`;
  Playwright lives in its own venv.

## Backups / pushing

`~/spark-vm` on this box is a clone of the **private** repo
[ntindle/spark-vm](https://github.com/ntindle/spark-vm) — it is the source
of truth for the box's tooling going forward. After changing anything worth
keeping:

```bash
~/spark-vm/scripts/push.sh "what changed"
```

First-time auth: create a fine-grained PAT with **contents: write** on
`ntindle/spark-vm`, then store it (once). Never paste it into chat or a file:

```bash
echo '<token>' | cred set github
```

`push.sh` reads the token via `cred get github` at push time, refuses to
commit anything secret-shaped, and pushes over HTTPS with the token in an
HTTP header (never in the remote URL, never echoed). If the token isn't
stored yet, it prints the exact `cred set` command and exits.
The repo is private; nothing pushed here is public.

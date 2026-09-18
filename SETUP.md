# spark-vm — dev workhorse setup

Hostname `spark-vm`, Ubuntu 24.04.5 LTS (kernel 7.0.0-31-generic), 8 vCPU,
15 GB RAM, 250 GB disk. Tailnet IP `100.65.241.20`, user `spark`
(passwordless sudo). Set up 2026-09-14.

Agent access: SSH as `spark` over the Tailscale TCP proxy; a persistent
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
| docker | 29.1.3 (Ubuntu repo build `29.1.3-0ubuntu3~24.04.2`) | daemon verified via `docker run --rm hello-world`; `spark` is in the `docker` group, no sudo needed |
| playwright | 1.62.0 | in `/home/spark/.venvs/pw` (python venv) |
| chromium | (playwright-managed, `~/.cache/ms-playwright`) | headless-tested: loaded https://example.com, correct title, valid PNG screenshot |
| cred | 1.0 (local) | `/home/spark/bin/cred`, on PATH via `~/.profile` |

Playwright system deps were installed with `playwright install-deps chromium`
(fonts, xvfb, codec libs). Use the venv python for browser scripts:
`/home/spark/.venvs/pw/bin/python`.

## cred — the credential system

Single-file Python CLI (stdlib only) at `/home/spark/bin/cred`.
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
# run with: /home/spark/.venvs/pw/bin/python script.py
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
cred run -- /home/spark/.venvs/pw/bin/python my-automation.py
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
## Secrets (transparent swapping — the agent never sees real values)

**Architecture.** All configs and code the agent writes carry placeholders —
`hsurr:<name>` or `hsurr:<name>:<entry>` — never real secrets. A mitmproxy
instance running as the dedicated `swapd` system user listens on
127.0.0.1:18080. Any command run via `with-proxy` (or `cred run --`) has its
HTTPS traffic routed through it; the proxy replaces placeholders in request
headers, URL query string, URL path, and text/JSON bodies with the real
value, but only for hosts listed in `/home/swapd/hosts.allow`. Non-listed
hosts pass through byte-for-byte (a one-line warning is logged, no values).
Every swap is audit-logged to `/home/swapd/swap.log` as
`ts=<utc> host=<host> swapped=<placeholder>` — never values.

Secret files live in `/home/swapd/secrets/` (0700, swapd-only): one file per
credential name; the whole file is the value, unless the file's first
line is the `#hsurr:multi` marker — that marker is the SOLE layout
signal, so a single-value secret whose value looks like `k=v` is never
misread. Marked files hold `entry=value` lines; malformed lines are
dropped with a warning. Placement metadata (which header/query param a
credential goes in) lives in `/home/swapd/credentials.json`, managed via
`cred register`.

**Installing a secret (human only, your own SSH session):**
```
cred set <name>                                            # paste at the prompt; never send it to the agent
cred register <name> [--entry <e>] [--placement <spec>]    # optional: how it's placed
```
`<spec>`: `bearer_header` | `url_path_segment` | `custom_header:<Name>` |
`query_param:<name>`. The agent's standing policy: never run `cred get`,
never read `/home/swapd/secrets`, never attempt to bypass the proxy.

**Managing allowed hosts:** edit `/home/swapd/hosts.allow` (one host per
line, `#` comments; leading `.` matches subdomains, e.g. `.openai.com`).
New hosts and secrets are picked up without a proxy restart
(`sudo systemctl restart swap-proxy` only needed for addon changes).

**Using it:** prefix any command that needs secrets:
```
with-proxy <cmd> [args...]
```
`cred run -- <cmd>` is the same thing. AutoGPT pattern: put
`hsurr:openai` in its config, then run it under `with-proxy`. For Python,
`/home/spark/credlib/dynamic_credentials.py` mirrors the hatch cell's
helper (`from dynamic_credentials import add_surrogate_to_request, ...`)
with the same names and `DynamicCredentialError`; `fill_secret.py` fills a
Playwright field without the value touching logs (see its docstring for the
honest limit).

### Website login recipe (username + password + TOTP)

End-to-end: logging the agent into a website without it ever seeing the
credentials.

1. **Store the credential (human only, your own SSH session).** One
   credential, one entry per line. The interactive prompt takes a single
   line, so pipe multi-entry values. The first line MUST be the
   `#hsurr:multi` marker — it declares the file multi-entry explicitly
   (the proxy never guesses from the content):
   ```
   printf '#hsurr:multi\nusername=jdoe\npassword=correct horse battery staple\ntotp=JBSWY3DPEHPK3PXP\n' | cred set acme
   ```
   Omit the `totp` line if the site doesn't use one. The `totp` value
   is the base32 **seed** — at swap time the proxy computes the current
   RFC 6238 six-digit code and substitutes the code, never the seed.
   Never send these values to the agent — only the credential *name*
   (`acme`).

2. **Allowlist the site AND bind the credential to it.** A credential
   may only ever travel to hosts you approve — the allowlist is the
   standing approval, and the per-credential binding is fail-closed
   (an unbound credential never swaps):
   ```
   # append to /home/swapd/hosts.allow (one host per line)
   acme.example.com
   # bind the credential to that host (narrow sudo helper, no shell)
   sudo -u swapd /usr/local/bin/cred-registry-set add-host acme acme.example.com
   ```
   New hosts and new bindings are picked up without a proxy restart.

3. **Launch Chromium through the proxy and trust its CA.** Plain
   Playwright ignores `with-proxy`'s environment variables, and
   Chromium keeps its own certificate store (`~/.pki/nssdb`) — without
   both steps the placeholders go to the site unswapped and the login
   fails silently:
   ```python
   from playwright.sync_api import sync_playwright
   with sync_playwright() as p:
       browser = p.chromium.launch(headless=True,
           proxy={"server": "http://127.0.0.1:18080"})
       page = browser.new_page()
       # ... fills below ...
   ```
   ```bash
   # one-time: trust swapd's CA in Chromium's NSS store
   # (the CA *certificate* is distributed for this purpose by the
   # install script; the private key never leaves swapd)
   certutil -d sql:$HOME/.pki/nssdb -A -t C -n swapd-ca \
       -i <path-to-swapd-ca-cert.pem>
   ```

4. **Drive the login with placeholders.** Fill the form with placeholder text —
   the browser DOM, screenshots, and logs then contain only placeholders:
   ```python
   page.fill("#username", "hsurr:acme:username")
   page.fill("#password", "hsurr:acme:password")
   page.click("button[type=submit]")
   # if the site then asks for a code:
   page.fill("#totp", "hsurr:acme:totp")
   ```

5. **The proxy swaps on submit.** When the browser POSTs the login form,
   the proxy replaces each placeholder with the real value (form bodies
   included — browsers percent-encode the `:` as `%3A` and the proxy
   handles that). The site receives the real credentials; everything on
   the agent's side stays placeholders.

6. **Verify in the audit log** (placeholder names only, never values):
   ```
   sudo -u swapd tail -5 /home/swapd/swap.log
   # ts=... host=acme.example.com swapped=hsurr:acme:password
   ```

### Inference-model recipe (API key for an LLM provider)

The inference proxy (`:18081`, header-only) has its own credential
store, installed through a fixed registry path — the agent and the
main proxy's store can never be confused. All steps are human-only, in
your own SSH session:

1. **Store the key** in swapd's secrets dir (the name is fixed —
   the inference proxy holds exactly one credential, `llm-api`).
   The script reads the key from stdin with no prompt — use a
   non-echoing read and pipe it in, running as `swapd`. Without
   `sudo -u swapd` the write fails on permissions; typing the key at
   a visible prompt would echo it to the terminal:
   ```
   read -rsp "Provider API key: " KEY; echo
   printf '%s' "$KEY" | sudo -u swapd /usr/local/bin/cred-store-set-inference
   unset KEY
   ```

2. **Write the registry** through the narrow helper (the fixed path
   `/home/swapd/inference-registry.json` is baked into the wrapper; it
   cannot be pointed elsewhere):
   ```
   sudo -u swapd /usr/local/bin/cred-registry-set-inference set llm-api access_token '"bearer_header"'
   ```

3. **Bind the provider host** in the registry, and append it to
   `/home/swapd/inference-hosts.allow` — the inference proxy's own
   hosts file. Never the main proxy's `hosts.allow`: the inference
   service unit forbids the provider there, and mixing the two stores
   defeats the finding-31 separation between page content in prompts
   and credential insertion:
   ```
   sudo -u swapd /usr/local/bin/cred-registry-set-inference add-host llm-api api.provider.example
   ```

4. **Restart the inference proxy** and check the journal for refused
   lines (placeholder names only, never values):
   ```
   sudo systemctl restart swap-inference
   journalctl -u swap-inference --since "5 min ago" | grep -c refused
   ```

The agent writes only `hsurr:<name>` in its inference configs; the
proxy substitutes the key into the `Authorization` header on egress
and never touches request bodies (a prompt can contain the placeholder
string without it being swapped — header-only mode).


If the site isn't allowlisted, the placeholders pass through literally and
the login simply fails — the safe default. SMS/email codes (as opposed to
TOTP) can't be auto-filled: the agent asks you for the code instead.

**Cell → spark-vm CLI mapping:**

| cell | spark-vm |
|---|---|
| `credentials.request_login` / `request_api_access` | `cred set <name>` (your own SSH session) |
| `credentials.list` (metadata only) | `cred list` |
| `hsurr:` surrogates | identical `hsurr:<name>` / `hsurr:<name>:<entry>` format |
| `credential_fill` | `~/credlib/fill_secret.py` → `fill_secret(page, selector, name)` |
| `dynamic_credentials` import | `from dynamic_credentials import ...` (same function names) |

**Verifying:** `sudo ausearch -k swapd-secrets` shows every read/write of the
secret store and registry. `sudo journalctl -u swap-proxy` shows the proxy
log. `sudo -u swapd cat /home/swapd/swap.log` shows every swap (names only).

**Honest limits.** With root on this box, this is verifiable hygiene, not a
hard boundary: root can read swapd's files and the proxy's memory. What it
guarantees is that secrets never enter the agent's context — transcripts,
logs, memory, or tool calls — so they can't leak through the agent. The
hatch cell achieves the stronger version through physical separation
(secrets never enter the cell at all).
(If `ausearch` hangs on this box, the equivalent is
`sudo grep 'key="swapd-secrets"' /var/log/audit/audit.log`.)

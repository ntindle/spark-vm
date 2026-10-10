# The `cred` CLI and its library

The operator-facing half of the secret system. The agent's configs,
scripts, and environment carry **placeholders** like `hsurr:<name>`
instead of real secrets; this directory is the tooling a human uses to
put real secrets into the swapd-owned store, register how each one gets
placed into requests, and run commands with traffic routed through the
[swapping proxy](../proxy/README.md) — which is the machine half that
does the actual swapping at request time.

The full posture (threat model, what's deliberately exposed, vendor
trust) is in [docs/SECRETS_POSTURE.md](../docs/SECRETS_POSTURE.md);
the operator credential writeup is in [SETUP.md](../SETUP.md). This
README is the map of this directory — and of the `cred` CLI that lives
at the repo root (a single file, deployed as a manual copy with no
installer).

## `cred`: the command line

```
cred set <name>              store a secret (stdin pipe or no-echo prompt)
cred get <name>              print a secret to stdout (no trailing newline)
cred list                    list stored credential names (never values)
cred delete <name>           delete a stored credential
cred register <name> [--entry <entry>] [--placement <spec>] [--host <h>]...
cred unregister <name> [--entry <entry>]
cred run -- <cmd> [args...]  exec <cmd> with traffic routed through the
                             swapping proxy (127.0.0.1:18080)
```

- **The human installs secrets; the agent never does.** `cred set` in
  your own SSH session; the agent's standing policy is to never invoke
  `cred get` either — reads are for the human and for local scripts.
- **The CLI never touches the store directly.** Every mutation and read
  goes through allowlisted helpers run `sudo -n -u swapd`: the narrow sudo
  writers for `set`/`get`/`delete`/`register` (`cred-store-set`,
  `cred-store-get`, `cred-store-delete`, `cred-registry-set`) — the one
  exception is `cred list`, which reads the store via `sudo -n -u swapd
  /usr/bin/ls /home/swapd/secrets` (its own sudoers allowlist entry), and
  `cred run`, which execs `with-proxy` and touches the store not at all.
  Failures are loud: `cred get` on a missing credential exits 3 with the
  exact command to fix it; a store failure (permissions, broken dir,
  sudoers denial) is never misreported as "not set" or "no credentials"
  — a missing store dir on first run stays silent, exit 0. Exit codes:
  1 for usage/validation/writer failures (message on stderr), 2 for an
  unknown command (usage on stderr).
- **`cred set/get/delete/register/unregister -- <name>`** is accepted so
  odd names can't be mistaken for flags. (`cred list` takes no arguments;
  `cred run` uses `--` as a required command separator, with a different
  meaning.)
- **Name grammar.** Creation verbs (`set`, `register`) accept
  `[A-Za-z0-9_-]`, max 64 chars. Read/management verbs (`get`, `delete`,
  `unregister`) accept the same charset without the length cap, so
  credentials created before the cap stay manageable. Non-string input
  fails cleanly instead of with a `TypeError` traceback.
- **Entries.** A credential can hold entries (e.g. a refresh token beside
  the access token). The names `allowed_hosts`, `allowed_methods`,
  `allowed_paths`, and `grants` are reserved — they are structural
  registry keys and can never become entry names, on creation or on
  management.
- **Placement.** `register` records how the credential is placed into
  requests: `bearer_header` (default), `url_path_segment`,
  `custom_header:<Name>`, or `query_param:<name>`; the default entry is
  `access_token`. Registration and host binding happen in one writer
  call, so a mid-loop writer failure can never leave a credential
  registered with only a prefix of its intended hosts.
- **A credential with no host binding never swaps.** `--host` bindings
  (exact hostname or leading-dot subdomain entry, same shape as
  `hosts.allow`) are advisory self-service controls for this operator —
  the root-managed `hosts.allow` file is the boundary the operator cannot
  lift unilaterally.
- **Secret size.** The frontend caps piped input at 64 KiB (the writer's
  own cap), counted in bytes, not characters — one trailing newline is
  chomped; anything over is refused before the writer is invoked.
- **`cred run -- <cmd>`** execs the command via `with-proxy`, which puts
  its traffic on the swap proxy so `hsurr:<name>` placeholders in configs
  are swapped for real values on the wire, allowlisted hosts only. The
  agent never sees secret values.

## The library: `credlib/`

- [`dynamic_credentials.py`](dynamic_credentials.py) — resolves
  `hsurr:<name>:<entry>` placeholders for Python callers, mirroring the
  cell's dynamic-credential helper interface (same function names,
  signatures, and error type). Entries resolve from the local registry
  `/home/swapd/credentials.json`, read via a pinned `sudo -n -u swapd
  /usr/bin/cat`; a name with no registry entry defaults to placement
  `bearer_header` with entry `access_token` (the zero-config common
  case).
- [`credvalidate.py`](credvalidate.py) — **the single source of the
  credential/entry/host validation contract** (the name grammar, entry
  rules, and host shape above). It used to be implemented four times
  independently — in `cred`, `cred-ui`, the registry writer, and
  `dynamic_credentials` — kept in sync only by comments pointing at an
  issue, and drift had already happened once (the UI accepted ports and
  underscores the writer rejected, producing a confusing post-store
  failure). Now the canonical contract text lives here — plus a
  machine-checked *mirror* in the single-file `cred` CLI (which has no
  installer to ship a module with), so the two can never drift silently:
  `dynamic_credentials.py` and
  `cred-ui` import the module directly; the registry writer ships it
  inside its own artifact atomically; the `cred` mirror's atoms are
  asserted identical by `test_credvalidate.py`. The module owns the accept/reject
  decision; each consumer owns its own error presentation.
- [`fill_secret.py`](fill_secret.py) — Playwright secret insertion for
  browser automation. It fills the value into a page field without
  printing, returning, or logging it — **but** the value does sit in the
  calling process's memory, unlike the swap-proxy path where the agent
  never touches it at all. Prefer the proxy path for agent-driven browser
  work; this helper is for human-driven or isolated automation contexts,
  and that is enforced at the call boundary: it refuses to run unless
  stdin is a real terminal or the caller explicitly opts in with
  `SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1`. The guard is a fail-closed
  heuristic, not proof of human presence — sessions on a pseudo-terminal
  (including tmux, which agent coding jobs run inside) present a TTY and
  pass it, so the never-see-secrets guarantee for agents remains the
  agent policy plus the swap-proxy path and store auditing, not this
  guard.

## Tests

The `test_*.py` files here run with the rest of the suite from the repo
root (`python3 -m pytest`; see `pytest.ini`). They cover the name/entry/
host contract parity (CLI mirror vs `credvalidate`), the `get`/`list`
failure-honesty paths, the stdin byte cap, and the entry-validation
rules.

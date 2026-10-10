# The credential-swapping proxy

The agent's configs, scripts, and environment carry **placeholders** like
`hsurr:<name>` instead of real secrets. This directory is the machinery that
makes that work: a transparent egress proxy that swaps placeholders for real
values on the wire, for allowlisted hosts only — plus the narrow sudo writers
that are the only way secrets get into the store.

The full posture (threat model, what's deliberately exposed, vendor trust) is
in [docs/SECRETS_POSTURE.md](../docs/SECRETS_POSTURE.md); the operator
credential writeup is in [SETUP.md](../SETUP.md). This README is the
map of this directory.

## The addon: `swap_addon.py`

A mitmdump addon that runs as the unprivileged `swapd` user
([swap-proxy.service](swap-proxy.service), listening on `127.0.0.1:18080`).
It replaces `hsurr:<name>` / `hsurr:<name>:<entry>` placeholders in request
headers, URL query strings, URL paths, and text bodies with real secrets from
the store — but **only** for hosts listed in the hosts file **and** bound to
that credential in the registry (a per-credential `allowed_hosts` list,
managed with `cred register <name> --host <h>`). A credential with no host
binding never swaps: fail closed. Everything else passes through untouched.

- **Headers:** `Authorization` (including HTTP Basic, base64-decoded first)
  and other headers are swapped — except `Referer` and `Origin`, which are
  never touched (a swapped `Referer` would hand the real value to the
  server's access log on later requests), and `Cookie`, which is only
  swapped for credentials whose registry placement explicitly names it.
- **Placements:** a registry `placement` restricts where an entry's value
  may be inserted — `"bearer_header"` swaps only in an `Authorization: Bearer`
  header, `{"custom_header": name}` only in that header, `{"query_param": name}`
  only in the query string, `{"url_path_segment": name}` only in the URL path.
  A declared placement that doesn't match the placeholder's location fails
  closed; an unrecognized placement shape fails closed too. An entry with no
  declared placement swaps anywhere (migration).
- **Bodies:** `application/json` values are JSON-escaped before substitution;
  `application/x-www-form-urlencoded` bodies are parsed as a form, swapped,
  and re-encoded; anything else text is plain substitution.
- **Egress guard:** the addon resolves every request host and refuses
  private ranges (RFC 1918, loopback, link-local, CGNAT/tailnet) by
  default. [ssrf.allow](ssrf.allow) lists explicit exceptions (ships
  empty: default deny); [ssrf.deny](ssrf.deny) lists hosts it must never
  reach even if allowlisted — the jail must not impersonate the owner by
  reaching the host's own tailnet addresses.
- **Host matching** lives in [host_match.py](host_match.py), the single
  source of truth (exact names or leading-dot subdomain entries), shared
  with the provision-time injector so the two can never drift.

The addon's own audit log (`swap.log`) is the intended observability —
mitmdump's default per-flow request lines print full URLs, so the service
sets `dumper_filter` to match nothing and those lines never appear.

## The inference proxy

A second proxy with its own allowlist
([inference-hosts.allow](inference-hosts.allow),
[swap-inference.service](swap-inference.service)). Only the LLM provider's
exact hostname goes there — never anything else — and the provider must
never appear in the main proxy's `hosts.allow`.

## The secret store and its writers

Secrets live in `/home/swapd/secrets` (0600, swapd-owned, 0700 dir);
[inference credentials](../docs/SECRETS_POSTURE.md) live in the parallel
`inference-secrets` dir. [enforce_secrets_dir.py](enforce_secrets_dir.py)
enforces that ownership race-free at deploy (refuses to `chown`/`chmod`
*through* a symlink — a swapd-level attacker who planted `<dir> -> /etc`
would otherwise get the next unattended deploy to hand them a system
directory).

**Narrow writers** are the only way in. The `/usr/local/bin/cred-*`
family is invoked by the operator via sudo under the least-privilege
[sudoers-swapd](sudoers-swapd) fragment, and each does exactly one thing:

- `cred-store-set` / `cred-store-get` / `cred-store-delete` — write/read/
  delete a secret in the store. Writes store stdin **verbatim**; every
  frontend chomps exactly one trailing newline from human input first,
  so stored bytes == intended value.
- `cred-store-set-inference` / `cred-store-verify-inference` — the same
  contract for the inference-secrets dir.
- `cred-registry-set` / `cred-registry-set-inference` — registry entries
  (host bindings, placements) in `credentials.json`.
- `cred-ui-token-set` — the token for the phone-friendly credential UI.

The grant lifecycle runs differently — not via the sudoers fragment.
`grant-writer` is exec'd directly by confirmd (which already runs as
swapd) at `/home/swapd/grant-writer`: the **single** writer for
`grants.json` (exclusive fcntl lock, atomic rewrite), called on approval.
`cred-grant-revoke` is a CLI that swapd (or root) runs and that delegates
to it.

And `privileged_read.py` is not a writer at all — it is the one open
discipline for privileged reads, imported by the deploy tooling
(`safe_install.py`, `build_ca_bundle.py`) (`O_RDONLY | O_NOFOLLOW`,
fails on symlinks instead of reading through).

## Using it: `with-proxy`

`with-proxy` runs one command with traffic routed through the local proxy
(`127.0.0.1:18080`) — opt-in per command, nothing changes the global
environment. It points the command at a dedicated CA bundle
(`/usr/local/share/with-proxy-ca/ca-bundle.crt`, built by `deploy.sh`; the
swapd CA is not in the host's system store) and clears `NO_PROXY`/`no_proxy`
first, because an inherited bypass would silently let placeholders go out
unswapped and unaudited.

[`scripts/push.sh`](../scripts/push.sh) is the canonical example: it
commits and pushes through the proxy with `hsurr:github` in the
`Authorization` header, so the token itself never appears in the script,
the environment, or any log.

## Deploy

[`deploy.sh`](deploy.sh) is the rebuild documentation — the repo is the
only source. It deploys the swap proxy, the inference proxy, `confirmd`,
and the push worker. Run it
from the repo root, as the operator (not from the jail):

```bash
./proxy/deploy.sh [--no-restart]
```

The machine-readable inventory of every `sudo install` target in
`deploy.sh` — each target's destination, repo source, deployed
owner:group:mode, and any conditional — is the block below, pinned in
both directions by `test_deploy_inventory.py`. A new `install` target
added to `deploy.sh` (or a changed owner/mode, or a rename) must update
this block, and a block entry with no matching install fails the pin —
so the `install` surface can never drift silently again.

<!-- deploy-inventory:start -->
# dest | src | owner:group:mode | notes. Pinned both directions by
# proxy/test_deploy_inventory.py — do not reorder without reason (the
# rows are grouped by destination prefix) and do not add rows deploy.sh
# does not have.
/home/swapd/swap_addon.py | proxy/swap_addon.py | swapd:swapd:0644 |
/home/swapd/host_match.py | proxy/host_match.py | swapd:swapd:0644 |
/home/swapd/grant-writer | proxy/grant-writer | swapd:swapd:0755 |
/home/swapd/VERSION | VERSION | swapd:swapd:0644 |
/home/swapd/sparkvm_version.py | scripts/sparkvm_version.py | swapd:swapd:0644 |
/home/swapd/confirmd.py | confirm/confirmd.py | swapd:swapd:0644 |
/home/swapd/bounded_http.py | scripts/bounded_http.py | swapd:swapd:0644 |
/home/swapd/push.py | confirm/push.py | swapd:swapd:0644 |
/home/swapd/inference-ssrf.allow | /dev/null | swapd:swapd:0644 | conditional: installed only when absent
/usr/local/bin/cred-grant-revoke | proxy/cred-grant-revoke | root:root:0755 |
/usr/local/bin/cred-registry-set | proxy/cred-registry-set | root:root:0755 |
/usr/local/bin/cred-registry-set-inference | proxy/cred-registry-set-inference | root:root:0755 |
/usr/local/bin/cred-store-set | proxy/cred-store-set | root:root:0755 |
/usr/local/bin/cred-store-set-inference | proxy/cred-store-set-inference | root:root:0755 |
/usr/local/bin/cred-store-verify-inference | proxy/cred-store-verify-inference | root:root:0755 |
/usr/local/bin/cred-store-get | proxy/cred-store-get | root:root:0755 |
/usr/local/bin/cred-store-delete | proxy/cred-store-delete | root:root:0755 |
/usr/local/bin/cred-ui-token-set | proxy/cred-ui-token-set | root:root:0755 |
/usr/local/bin/credvalidate.py | credlib/credvalidate.py | root:root:0644 |
/usr/local/bin/confirm-request | confirm/confirm-request | root:root:0755 |
/usr/local/bin/with-proxy | proxy/with-proxy | root:root:0755 |
/etc/systemd/system/swap-proxy.service | proxy/swap-proxy.service | root:root:0644 |
/etc/systemd/system/swap-inference.service | proxy/swap-inference.service | root:root:0644 |
/etc/systemd/system/confirmd.service | confirm/confirmd.service | root:root:0644 |
/etc/systemd/system/push-worker.service | confirm/push-worker.service | root:root:0644 |
/etc/systemd/system/summons-sweep.service | proxy/summons-sweep.service | root:root:0644 |
/etc/systemd/system/summons-sweep.timer | proxy/summons-sweep.timer | root:root:0644 |
/etc/sudoers.d/swapd | proxy/sudoers-swapd | root:root:0440 | installed via mktemp then moved
/etc/systemd/system/swap-proxy.service.d | (none) | root:root:0755 | install -d; conditional: plane-enrolled
/etc/systemd/system/push-worker.service.d | (none) | root:root:0755 | install -d; conditional: plane-enrolled
<!-- deploy-inventory:end -->

Deliberately out of the pin's scope, named so a future reader knows it
was a choice and not an oversight — `deploy.sh` also puts down:

- the plane-push `SPARKVM_PLANE_PUSH=1` drop-in file contents (written
  inline via `sudo tee`, not `install`);
- the CA bundle (built by `proxy/build_ca_bundle.py --dest`, whose
  destination is operator-overridable via `WITH_PROXY_CA_BUNDLE`);
- the `safe_install.py` targets: `/home/swapd/ssrf.deny` (generated
  content), `/home/swapd/grants.json` (`--create-only` seed),
  `/home/swapd/swap.log` (0600 mode tighten, only if already present),
  `/etc/logrotate.d/swap-proxy` (from `proxy/swap-logrotate.conf`);
- the `mkdir` + enforce-helper targets: `/home/swapd/secrets` and
  `/home/swapd/inference-secrets` (`enforce_secrets_dir.py`), and the
  confirmd approvals `pending/` dir (`enforce_pending_dir.py`,
  root:approval-filers 2770 — its parent path is dynamic).

Those are generated, conditional, or mode-enforcement writes, not static
file installs, so the src/owner/mode pin does not cover them — but they
are not unguarded either: the `test_no_undocumented_non_install_writes`
tripwire in the same test file allowlists every literal-absolute-path
non-`install` file write by path (`sudo tee` dests, `cp`/`rsync`/`mv`/`ln`
dests, `safe_install.py` dests, the CA-bundle `--dest`, absolute-path
redirects — spaced and no-space forms — and `dd of=`), and fails loud on
any write primitive the scanners cannot see (bare `install` without sudo,
`/usr/bin/install`, env-prefixed installs, `sudo sh -c` subshells,
`python3 -c` bodies that open files for writing). The scanners see
literal absolute paths only: writes to dynamic paths (`exec
9>"$UPDATER_STATE_DIR/…"`, `mkdir -p "$approvals_dir"`) and the
sudo-invoked helper scripts (`proxy/ensure-approval-filer.sh`, which
writes `/etc/group` and `/etc/gshadow`; `proxy/enforce_pending_dir.py`
and `proxy/enforce_secrets_dir.py`, which create and own dirs) are
deliberately outside the tripwire's vocabulary — named here so a future
reader knows it was a choice and not an oversight.

`--no-restart` installs everything without restarting services (used by
the fleet auto-deploy); a manual `--no-restart` caller owns the restart
step instead (`systemctl daemon-reload`, then restart `swap-proxy.service`,
`swap-inference.service`, `confirmd.service`, and `push-worker.service`,
plus `systemctl enable --now summons-sweep.timer`).
Restart is not optional hygiene — a still-running proxy keeps its old
group memberships and old unit files until restarted.

Other services in this directory:

- [summons-sweep.timer](summons-sweep.timer) / `summons-sweep.service` —
  the outbox reconciliation sweep every 5 minutes; the crash-loss window
  for a pending record is bounded by that interval.
- [swap-logrotate.conf](swap-logrotate.conf) — rotation for the audit log.

## Tests

The `test_*.py` files here run with the rest of the suite from the repo
root (`python3 -m pytest`; see `pytest.ini`). They cover the addon's swap
semantics, the placement fail-closed rules, the host matcher, the narrow
writers' path guards, the CA-bundle builder, the outbox sweep, and the
deploy.sh install inventory pin.

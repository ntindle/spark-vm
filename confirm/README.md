# confirm

The human-approval loop: when an agent asks for a sensitive credential the
swap proxy refuses for lack of a grant, the request lands here — a
tailnet-only confirmation page where the human approves or denies it.
The jail cannot route here (the jail firewall drops ve-jail), and the
page never routes through the orchestrator.

## Layout

| Path | What it is |
|---|---|
| `confirmd.py` | The daemon: HTTPS page + JSON API on the tailnet. Runs as the `swapd` user. |
| `confirm-request` | CLI that files a pending approval (testing; in production `swapd` files items itself when it refuses a swap). |
| `push.py` | Optional VAPID Web Push sender (issues H2, H14): the page pushes new approvals to the owner's phone/browser. |
| `push-worker.service` | systemd unit for the push queue worker. |
| `confirmd.service` | systemd unit for `confirmd`. |
| `test_confirmd.py`, `test_expired_terminal_record.py`, `test_push.py`, `test_push_queue.py` | The test suite (pytest, hermetic). |

## Running

Deploy via `./proxy/deploy.sh` (installs confirmd from this directory).
The unit binds the tailnet address only — resolved at startup from
`tailscale ip -4`, or pinned via `CONFIRM_BIND`. There is deliberately no
fallback address: if the bind address cannot be determined, confirmd exits
non-zero instead of serving on a guessed address (fail closed, issue #70),
and `Restart=on-failure` retries until the tailnet is back. BIND is frozen
at import, so restart the unit after a tailnet renumber.

| Env | Default | What it is |
|---|---|---|
| `CONFIRM_PORT` | `8443` | Port |
| `CONFIRM_BIND` | pin, else from `tailscale ip -4`, else fail closed (exit 1) | Bind address (no stale-literal fallback: an unresolvable address fails the process, and systemd retries) |
| `CONFIRM_CERT` / `CONFIRM_KEY` | `/home/swapd/confirmd/cert.crt` / `key.pem` | TLS cert/key (Tailscale cert for the machine name) |
| `CONFIRM_OWNER` | `ntindle@github` | Expected Tailscale LoginName — every request is authenticated by Tailscale identity against this |
| `CONFIRM_DIR` | `/home/swapd/approvals` | Data dir (`pending/`, `answered/`, `consumed/`) |
| `CONFIRM_AUDIT` | `/home/swapd/confirmd/audit.log` | Audit log (refusals and CSRF violations land here, with peer + login) |
| `CONFIRM_AUDIT_MAX_BYTES` / `CONFIRM_AUDIT_KEEP` | `10485760` (10 MB) / `4` | Audit rotation: segments roll at 10 MB, keeping the newest 4 (live + 3 rotated) |
| `CONFIRM_ORIGINS` | page-derived | Comma-separated origin allowlist pin for POST `Origin` exact-match (no re-probe) |
| `GRANT_WRITER` | `/home/swapd/grant-writer` | Helper invoked to mint the credential grant on approve |
| `CONFIRM_HOUSEKEEPING_INTERVAL_S` | `3600` | answered/ sweep + consumed/ prune cadence |
| `CONFIRM_VAPID_KEYS` | `/home/swapd/confirmd/vapid.json` | VAPID keypair (`push.py --gen-keys`); unset/missing disables push, the page is unaffected |

Before starting the unit on a new box:

1. **Set `CONFIRM_OWNER`** to your own Tailscale LoginName (e.g.
   `systemctl edit confirmd` overriding `Environment=CONFIRM_OWNER=`).
   The shipped default is `ntindle@github` — on any other box, identity
   auth refuses *every* request and the approval page looks dead.
2. **Provision the TLS cert**: `tailscale cert <machine-name>` and write
   the cert/key to `CONFIRM_CERT` / `CONFIRM_KEY`, readable by the
   `swapd` user. Nothing in `deploy.sh` mints it — without these files
   confirmd fails at startup.

This page is the **self-hosted** approval surface; the hosted approval
surface is future work (see `docs/APPROVALS_PLANE_GAP_ANALYSIS.md`).
| `CONFIRM_PUSH_SUBS` | `$CONFIRM_DIR/push-subscriptions.json` | Push subscription store |
| `CONFIRM_VAPID_SUB` | `mailto:confirmd@localhost` | VAPID subject contact |
| `CONFIRM_CSRF_RING_SIZE` | `3` | How many minted nonces per approval stay valid (multi-tab) |
| `CONFIRM_CSRF_RING_TTL` | `900` (15 min) | Nonce lifetime, enforced at verify too |
| `CONFIRM_ANSWERED_SWEEP_GRACE_S` | `86400` (24 h) | Answered strays move to `consumed/` after this |
| `CONFIRM_CONSUMED_KEEP` | `1000` | Answered history is pruned to the newest this many files |

## Filing an approval

An approval carries structured fields, not free text: `credential`, `host`,
`method`, `path_prefix`, `scope`, `amount`, `job`, `expires`.

```sh
confirm-request --kind first-use --credential github \
    --host api.github.com --method GET --path-prefix /repos/ \
    --scope read --job test-job --ttl 3600
```

Flood control (issue #76): at most 5 pending filings per (filer, credential)
and at most one filing per filer per 60 seconds. A refused filing exits 2 with
a one-line stderr explanation (`flood cap:`, `rate limited:`, `invalid --ttl:`).

Operator contract for the data dir:

- `<CONFIRM_DIR>/pending` must be a **setgid** directory owned by the filing
  principals' shared group (`approval-filers`), enforced as
  `root:approval-filers 2770` by `proxy/deploy.sh` §4e (issue #1167) —
  so the filed file's *owner* identifies the requester. Without the
  setgid bit the CLI warns but still files (warn, never refuse).
- Filed items are written owner-only (mode `0600`), atomically
  (tmp + fsync + `os.replace`).
- `--ttl` must be 1–86400 seconds; out-of-range is refused loudly (exit 2).

## The human flow

The human opens the page over the tailnet and sees pending approvals, each
rendered with its structured fields. Approving mints a credential grant for
the request; denying discards it. Decisions are one-way — an answered item
can never be re-answered.

- **Approve**: the daemon mints the grant (30-second worst-case mint
  window — see Expiry) and writes the record to `answered/`, then to
  `consumed/`. The proxy never re-derives grants from these files.
  Approving also takes the owner's grant-lifetime choice: the page
  offers 1 hour (default, shortest) or 24 hours, passed to grant-writer
  as `--ttl-hours`; any value outside the offered choices is refused,
  never coerced. The chosen lifetime is recorded in the answered
  record and the audit trail.
- **Deny**: the record is written to `answered/`/`consumed/`; the agent gets
  nothing.
- **Re-open a mis-tapped Deny** (POST `/reopen`): files the denied item again
  as a *new* pending item — approval IDs are never reused. The re-filed item gets a
  new approval id, the original request fields, the original deadline kept
  verbatim (expired requests are refused with 410), and
  `reopened_from`/`original_requester` lineage. Re-open is idempotent per
  denied item: a repeat POST while the re-filed item is pending redirects to
  it.

## Expiry

Approvals carry an `expires` instant; an expired item is refused with 410.
Expiry is a terminal outcome, not a silent loss (issues #213/#539):

- The reaping pass stamps an explicit terminal record into
  `consumed/<aid>.json` with `decision:"expired"` *before* deleting the
  pending file (stamp-then-delete, so a crash between the two self-heals).
- The 410 response links the human to the answered history, where the
  expired item renders with an Expired badge.
- Approving an item whose remaining validity is under the 30-second grant
  mint window is refused honestly (410 + `approve-refused-expiry-window`
  audit event) — an expiry crossing mid-mint would land an un-revokable
  grant with no revoke path, so the window is never entered.

## Security properties

- **Identity**: every request is authenticated by Tailscale identity against
  `CONFIRM_OWNER`. Peers that are the host itself or not remote tailnet nodes
  are refused and logged (audit trail with peer + login).
- **CSRF**: each approval page view mints a fresh nonce into a
  **server-side ring** keyed by approval id (issue #78) — the last 3 mints
  stay valid, 15-minute TTL enforced at verify too. The requester-authored
  pending file is never consulted for nonces, so a lower-trust filer cannot
  pre-seed entries and drive `/answer` from its own session. POSTs also
  require same-origin `Sec-Fetch-Site` (enforced when the header is present —
browsers; curl and other non-browser clients omit it and pass) and
exact-match `Origin` always.
- **Concurrency**: every check→mint→consume sequence serializes on a
  per-approval-id lock — concurrent double-POSTs race to exactly one
  decision; the loser gets a clean 404.
- **Sandboxing** (`confirmd.service`): `PrivateTmp`, `ProtectSystem=full`,
  runs as `swapd`. `NoNewPrivileges` is intentionally *not* set — the
  daemon calls `sudo -n tailscale whois/status` under the narrow sudoers rule.
- **Push (H14)**: disabled unless `CONFIRM_VAPID_KEYS` names a readable
  operator-generated keypair *and* the `cryptography` package imports.
  Disabled means `/api/push/config` reports `enabled:false` and no push ever
  fires — the approvals page is unaffected.

## Files

| Path | What it is |
|---|---|
| `<CONFIRM_DIR>/pending/<aid>.json` | Live approvals, one file per id |
| `<CONFIRM_DIR>/answered/<aid>.json` | Answered records (swept to `consumed/` after the 24 h grace) |
| `<CONFIRM_DIR>/consumed/<aid>.json` | Full history, newest 1000 kept; `decision` is `approve`, `deny`, or `expired` |
| `<CONFIRM_DIR>/pending-quarantine/` | Corrupt pending files are quarantined here, never served |
| `<CONFIRM_AUDIT>` | Audit log, rotated by the daemon |
| `~/.local/share/muse-job/events/` | *Not this component* — that's muse-job. |

## Gotchas

- **A confirmd restart empties the server-side CSRF ring.** Pre-restart forms
  self-heal on manual reload (a fresh GET mints a fresh nonce), but a POST
  submitted across a restart will fail CSRF — the human reloads and
  re-submits. This is by design: the ring is daemon memory, not durable
  state.
- **Multi-tab works**: the last 3 minted nonces per approval are valid, so a
  second tab doesn't invalidate the first — but each mint keeps its own
  15-minute TTL.
- Corrupt or torn pending files are quarantined, never served, and never
  crash a handler.
- The audit log rotates; denial, CSRF-violation, and `csrf:stale-nonce`
  events are distinguishable (attacker-shaped probes are well-formed but
  unknown, audited under `csrf:stale-nonce` so they don't desensitize review
  of real violations).
- The page has no secrets: it reads none and never ships one. The VAPID
  keypair is operator-generated and lives only at `CONFIRM_VAPID_KEYS`.

## Tests

```sh
pytest confirm/
```

208 tests cover the handler paths (including the pre-seeded-CSRF-file 403
probes), expiry stamping, re-open idempotency, flood control, and push.
Hermetic — no network, no daemon, no fixtures outside this directory.
(208 collected when the optional `cryptography` package is absent — the
push tests skip; 253 with it installed.)

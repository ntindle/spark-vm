# browser-driver

The fixed, narrow browser-driving stack for spark-vm
(`browser-driver/SPEC.md`): `bdrive` (the *hands* — moves the mouse,
types keys) plus the on-box agent `obox` (the *brain* — a later slice).
This directory currently holds the spec, its review, and the first
implementation slice: the **bdrive fixed action protocol as code**.

## What's implemented (H17 slice 1, GitHub #132)

`bdrive/` — the transport-agnostic protocol layer (SPEC §4–§5),
stdlib-only:

- `protocol.py` — the fixed 29-action vocabulary; call validation
  (unknown actions rejected, not interpreted; unknown parameters fail
  loud); `goto` restricted to http/https; `wait` exactly-one-of rule;
  the post-navigation rule (after `goto`, only exact-text `wait` or
  ref-free `look`/`get_text`/`get_html`/`state`); receipt semantics
  (`completed` / `unknown` / `not_started` + actionability reasons);
  `RefScope` — unguessable, constant-time-compared observation tokens
  that invalidate stale refs.
- `observation.py` — the AX observation schema (url, title,
  target/document identity, `ref_scope`, element tree) and
  `redact_for_history` (older trees are redacted — only the newest
  observation is actionable).
- `config.py` — deployment facts (socket path, profile dir, proxy
  URL, session TTL, screenshot cap) with `BDRIVE_*` env overrides.
  The protocol layer deliberately never reads it: no deployment
  assumption (same-box proxy included) is cemented behind the
  interface.
- `test_bdrive_protocol.py` — 53 hermetic tests, wired into the root
  `pytest.ini`.

Wire format of a call:

```json
{"session": "<session id>",
 "ref_scope": "<token from the newest observation>",
 "actions": [{"action": "goto", "url": "https://example.com"},
             {"action": "wait", "text": "Welcome"}]}
```

The daemon answers with one receipt per action plus the terminal
observation. See `bdrive/protocol.py`'s module docstring for the full
contract.

## Staged rollout

| Stage | Actions |
|---|---|
| v1 | `open` `goto` `back` `forward` `reload` `state` `click` `fill` `type` `press` `select` `check` `snapshot` `look` `get_text` `wait` `cookies_clear` |
| v1.1 | `hover` `scroll` `uncheck` `focus` `get_html` `get_attr` `get_value` `gesture` `upload` `download` `pdf` `fill_card` |

`bdrive.protocol.action_stage(name)` reports the stage; the execution
backend decides which stages it serves.

**Staging deltas vs SPEC §16 item 1.** Two deliberate deviations,
documented here so the table is never mistaken for the spec's own
staging: (a) `forward` is staged **v1** although SPEC's v1 list omits
it — the v1 navigation cluster is incomplete without it; (b)
`uncheck`, `focus`, `get_html`, `get_attr`, `get_value` appear in
SPEC §5's vocabulary but are assigned to no stage in §16 — they are
staged **v1.1** here so `action_stage()` is total over the vocabulary.
If the spec is later amended, this note and the table move with it.

## What's next (later H17 slices)

1. **Playwright execution backend** — consumes `ValidatedCall`,
   drives Chromium with the persistent profile, produces receipts +
   terminal observations.
2. **Daemon** — unix socket (`BDRIVE_SOCKET`) bind-mounted into the
   jail, `SO_PEERCRED` accepting the jail's mapped agent uid and
   `obox` (SPEC §3, §16 item 1, findings 15/33), per-session
   `RefScope`, 30-minute idle expiry.
3. **Box hardening** — systemd unit for the `bdrive` user, nftables
   uid rule confining egress to the proxy (finding 10), proxy health
   gate at session start, password-class read restrictions
   (finding 32).
4. **obox** — the agent loop; a later H17 slice (SPEC §16 item 2:
   `submit`/`steer`/`status`/`report`, the observe-decide-act loop
   against `bdrive`, `need_info` parking, the untrusted-data envelope
   and `hsurr:` neutralization). Runs as `obox`.
5. **Card pathway + Web Push (SPEC §16 round 10)** — issuer helper,
   `card-<job>` entries, `fill_card`, cancellation at job end; Web
   Push for the confirmation page (manifest, service worker, VAPID,
   owner-only subscribe, minimal payload).

The tenant-dimension gaps (per-tenant profiles, per-tenant bdrive
routing) are open questions for the multi-tenancy track; nothing here
assumes the same-box proxy — point `BDRIVE_PROXY_URL` elsewhere and
the protocol is unchanged.

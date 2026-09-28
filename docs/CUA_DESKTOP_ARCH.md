# CUA desktop stack — architecture deep-read (2026-09-26)

Deep-read of `cua/` — the bridge, the supervisor scripts, and the panel
contract that let an operator's panel drive the spark-vm XFCE desktop on
Xvfb :98 through the official trycua/cua driver. Read in full:
`bin/cua-bridge.py`, `bin/cua-desktop.sh`, `bin/start-xfce.sh`,
`bin/cua-keepalive.sh`, `bin/launch-blender-gui.sh`, `PANEL_SPEC.md`,
`README.md`, `test_cua_bridge.py`, `test_shell_scripts.py`.

## Structural strengths

The component is in good shape where it counts:

- **Loopback service, correctly defended.** Binds 127.0.0.1 only; the
  `Host`-allowlist + `X-CUA: 1` custom-header gate (no permissive CORS) is
  the right CSRF defense for a service reachable through an operator SSH
  tunnel. Tests pin the gate matrix.
- **Launch allowlist is exact-argv, never shell strings**, and a test pins
  its exact contents so a new entry (e.g. a shell) can't slip in silently.
- **Window-picking rules exclude Xfdesktop/Xfce4-panel** from type/key
  targets — learned from real XFCE behavior, encoded as tests.
- **Env sanitization is centralized** (`GDK_BACKEND=x11`,
  `WAYLAND_DISPLAY` unset) in `BASE_ENV`; the Wayland-hijack gotchas are
  documented, not just worked around.
- **Idempotent supervisor** with bracket-trick pkill hygiene.

## Fixed in this run

1. **Single-threaded bridge (head-of-line blocking).** `HTTPServer` served
   one request at a time, so one slow driver call (30s timeout) blocked the
   whole bridge — including the keepalive's health probe and the panel's
   screenshot polls. `cua-bridge.py` now uses `BridgeServer`, a
   `ThreadingHTTPServer` subclass whose semaphore bounds how many handler
   bodies execute concurrently (8). Accepted connections beyond the bound
   block in `process_request_thread` before doing any work; threads are
   still spawned per connection, so this is not a hard thread cap —
   acceptable on the localhost-only, single-operator bridge (the #471
   unbounded-pool concern is narrowed, not eliminated). Concurrency is
   covered by hermetic tests, including a peak-in-flight bound test.
2. **Screenshot via fixed world-readable /tmp path.** `/tmp/cua-bridge-shot.png`
   was predictable and world-readable in a shared directory — a
   symlink/snoop surface the moment a second local user exists on the box.
   Screenshots now go through a private `mkstemp` (0600) file, unlinked
   right after serving; paths are unique per request. Covered by tests
   (mode, uniqueness, cleanup).

## Filed as issues (out of this run's ~45 min scope)

- #491 `/api/launch` has no single-instance/debounce guard — repeated launches
  spawn unbounded app instances, and each chromium is heavy.
- #492 `/api/status` reports driver health only; it cannot detect the
  documented XTEST-wedge failure mode (input silently does nothing while
  status says ok) — the health endpoint needs an input-path liveness probe.
- #493 The bridge parses `/tmp/cua-desktop/env` from world-writable /tmp —
  env-injection vector (DISPLAY/PATH) into driver subprocesses if another
  local user exists; the env file should live in a private rundir or be
  integrity-checked. **Fixed 2026-09-27 (#TBD):** `cua-desktop.sh` creates
  the rundir with 0700 (atomically, `mkdir -m 700`, symlink re-checked
  after a lost creation race) and refuses symlink/wrong-owner plants; its
  `ensure_private_rundir` is the single choke point that also removes any
  pre-existing env file failing the trust check (stale plants cannot
  survive a start/status/stop); every consumer — `cua-desktop.sh`,
  `start-xfce.sh`, `cua-keepalive.sh` (via the shared `cua/bin/cua-trust.sh`
  predicate), and `cua-bridge.py` (single `O_NOFOLLOW` open + `fstat` on the
  same fd, so there is no check-then-open TOCTOU) — applies the same
  regular-file/owner/no-group-other-write check before sourcing or parsing;
  the writer and the gate agree on mode 0600.
- #494 focus-then-type/key has a TOCTOU window: `bring_to_front` then
  `type_text`/`press_key` — focus can be stolen between the two calls.
- #495 keepalive can double-spawn the bridge: two overlapping keepalive runs
  can both fail the curl and both spawn; the bridge has no pidfile or
  singleton guard. **Fixed 2026-09-27 (#TBD):** the bridge takes an
  exclusive non-blocking flock on a singleton lock at startup and exits
  if another instance holds it; `cua-keepalive.sh` serializes its whole
  run under `flock -n` so overlapping invocations cannot both spawn. Both
  locks live in the user's own `~/.cache` (never world-writable /tmp, where
  a planted symlink would be truncated by the lock open and any local user
  could squat the lock); every long-lived child spawned while the keepalive
  lock is held closes fd 9 (`9>&-`) so inherited fds cannot pin the flock
  after the run exits; a status probe that fails or prints nothing counts
  as DOWN, never "all up".

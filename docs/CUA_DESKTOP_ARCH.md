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
   `ThreadingHTTPServer` subclass with a semaphore bound of 8 concurrent
   handlers; excess connections wait in the listen backlog instead of
   spawning unbounded threads (the #471 unbounded-pool concern, preempted
   by design). Concurrency is covered by a hermetic timing test.
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
  integrity-checked.
- #494 focus-then-type/key has a TOCTOU window: `bring_to_front` then
  `type_text`/`press_key` — focus can be stolen between the two calls.
- #495 keepalive can double-spawn the bridge: two overlapping keepalive runs
  can both fail the curl and both spawn; the bridge has no pidfile or
  singleton guard.

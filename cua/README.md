# CUA driver stack on spark-vm

The private **Sandbox Control Panel** artifact drives this box's desktop through
the official [trycua/cua](https://github.com/trycua/cua) driver — full-desktop
control (not just the browser), over a localhost-only chain. Nothing here
listens publicly: no VNC, no RDP, no unauthenticated control port.

## Layout (live on the box)

```
/home/ntindle/cua/bin/
  cua-driver           official trycua/cua driver binary, v0.28.2 (NOT in git — 49 MB;
                       fetch from the trycua/cua releases page, telemetry disabled)
  cua-desktop.sh       supervisor: start/stop/status of Xvfb :98 + D-Bus + XFCE + driver daemon
  start-xfce.sh        launches xfwm4 + xfce4-panel + xfdesktop as components (see gotchas)
  cua-bridge.py        localhost-only HTTP bridge on 127.0.0.1:18731
  cua-keepalive.sh     run from ntindle's crontab every 5 min; restarts anything down
  launch-blender-gui.sh  wrapper for the `blender` allowlist entry (Wayland-safe env)
```

## Chain

```
panel artifact → SSH tunnel (hatch box 127.0.0.1:18732)
  → spark-vm 127.0.0.1:18731 (cua-bridge.py)
  → cua-driver daemon (official trycua/cua 0.28.2, standard mode)
  → Xvfb :98, 1280x800, XFCE desktop
```

The tunnel is kept alive by `cua-sparkvm-tunnel-keepalive` (5 min cron) on the
hatch box; the spark-vm side is kept alive by `cua-keepalive.sh` (5 min cron).

## Bridge API

- `GET  /api/status` — stack health
- `GET  /api/windows` — window list
- `GET  /api/screenshot` — fresh PNG of :98
- `POST /api/click` — `{x, y}` screen coords
- `POST /api/type` — `{text}`
- `POST /api/key` — `{key}` (Enter, Escape, Tab, arrows, …)
- `POST /api/launch` — `{app}` where app ∈ allowlist only

**Launch allowlist** (`xterm`, `terminal`, `chromium`, `blender`): the driver's
own `launch_application` is permission-denied in standard mode, so the bridge
spawns a fixed argv directly on :98. No arbitrary commands — unknown names or
a missing binary → 400. `chromium` is the Playwright-bundled build (no system
chromium installed); `blender` opens `/home/ntindle/cua/demo.blend` via the
wrapper script.

## Display choice

The desktop is a **separate Xvfb :98** running XFCE — deliberately NOT the
GNOME session (GNOME runs on **Wayland**, which the X11-based driver cannot
drive) and NOT BlenderMCP's Xvfb `:99` (headless Blender service, untouched).
Orphaned `:100`/`:101` instances from earlier testing were also left alone.

## Blender / BlenderMCP

Blender 5.2.2 LTS at `/home/ntindle/apps/blender` (`~/bin/blender` symlink).
BlenderMCP addon + `blender-mcp` MCP server (via uvx) runs headless on `:99`
as the `blender-mcp` systemd user service, socket `127.0.0.1:9876` — used to
author 3D content (e.g. `/home/ntindle/cua/demo.blend`, a low-poly rocket built
2026-09-16 entirely through `execute_blender_code`). The panel can open the
Blender GUI on `:98` to view/drive it.

## Gotchas (learned the hard way, 2026-09-16)

- **Wayland hijack.** GTK apps and Blender 5.x probe the GNOME Wayland socket
  via `XDG_RUNTIME_DIR` even on an X11 display. `xfce4-panel` tried
  `DISPLAY='wayland-0'` and segfaulted; Blender falls back to
  `$XDG_RUNTIME_DIR/wayland-0` even with `WAYLAND_DISPLAY` empty. Fix: launch
  everything on :98 with `GDK_BACKEND=x11`, `XDG_SESSION_TYPE=x11`,
  `XDG_CURRENT_DESKTOP=XFCE`, and **unset** both `WAYLAND_DISPLAY` and
  `XDG_RUNTIME_DIR`. `xfce4-session` itself still crashes, so run
  `xfwm4` + `xfce4-panel` + `xfdesktop` as individual components
  (`start-xfce.sh`), with the panel config pre-seeded from
  `/etc/xdg/xfce4/panel/default.xml` (skips the first-login dialog) and
  `light-locker`/`xscreensaver` autostart disabled.
- **XTEST can wedge.** Symptom: typing/clicking silently does nothing while
  the driver keeps reporting success. Diagnose: run `xev` on `:98` and send
  `XTestFakeKeyEvent` — if xev sees no KeyPress, the Xvfb XTEST keyboard
  device is wedged (XSendEvent and the XTEST mouse still work). Fix:
  `cua-desktop.sh stop` + `start` (fresh Xvfb; only touches `:98`).
- **Input routing on XFCE.** `type`/`key` must skip the always-on-top
  `Xfdesktop`/`Xfce4-panel` windows, `bring_to_front` the real target, and
  use `delivery_mode: "foreground"` — background delivery is refused with
  `background_unavailable`. Clicks on the panel/desktop need a global
  `scope: "desktop"` XTEST click; synthetic XSendEvent clicks are ignored by
  XFCE panel buttons and menus. CSD window X-buttons also ignore
  background-delivery clicks — use the desktop-scope XTEST click.
- **`pkill -f` matches your own shell.** Never `pkill -f` from a command line
  containing the pattern (kills your own SSH session, exit 255). Use the
  bracket trick: `pkill -f "cua-bridge.p[y]"`. Restarting the bridge port:
  `fuser -k 18731/tcp`.
- **Driver CLI reads JSON from stdin.** `echo '{...}' | cua-driver call <tool>`
  — with no stdin it hangs. Always source `/tmp/cua-desktop/env` first so
  `DISPLAY`/`DBUS_SESSION_BUS_ADDRESS` are set.
- **Click coords are window-local** for the driver's `click` (subtract the
  window's `bounds.x`/`bounds.y`); the bridge's `/api/click` takes screen
  coords and handles the translation.
- **AT-SPI needs `at-spi2-core`.** Without it, accessibility tools fail; the
  X11 tools (screenshot, windows, click, type, key) work regardless.

## Boundaries (standing)

- Never run `cred get`, never read `/home/swapd/secrets` or any secret store,
  never bypass the egress-proxy placeholder design. Verifiable hygiene the
  owner audits.
- Destructive or outward-facing actions need the owner's explicit approval.

## E2E proofs

- `~/workspace/cua-e2e/sparkvm-proof.png` — first spark-vm loop (Openbox era)
- `~/workspace/cua-e2e/sparkvm-xfce-proof.png` — XFCE: terminal launch, typed
  marker, Applications menu opened, all via panel actions
- `~/workspace/cua-e2e/blender-gui-proof.png` — Blender GUI with the
  BlenderMCP-built rocket, via panel actions

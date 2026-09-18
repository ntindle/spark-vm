# Sandbox Control Panel — build-your-own spec

The control panel is just a web UI that talks to `cua-bridge.py` over HTTP.
There is no blessed implementation: anyone's Muse can build one to their own
taste against this contract. This file is the contract.

## Reachability

- The bridge binds **127.0.0.1:18731** on the box, localhost-only. Nothing is
  public: no VNC, no RDP, no unauthenticated control port.
- Off-box access goes through the operator's SSH tunnel:
  `127.0.0.1:18732` (operator machine) → `127.0.0.1:18731` (this box).
  Keep it alive with `~/workspace/bin/cua-tunnel-keepalive.sh`-style health
  checks against `GET /api/status` (any 2xx = healthy).
- A panel served from the operator's own machine calls
  `http://127.0.0.1:18732`.

## Security contract (the bridge enforces this; panels must comply)

- `Host` must be one of `127.0.0.1:18731`, `localhost:18731`,
  `127.0.0.1:18732`, `localhost:18732` — anything else gets 403.
- Every `POST`/`PUT`/`DELETE` must carry header `X-CUA: 1`, or it gets 403.
  (Browsers must preflight custom headers, and the bridge never answers
  with permissive CORS — that is the CSRF defense. `fetch()` can set
  `X-CUA`; it cannot override `Host`, which is why 18732 is allowlisted.)
- Request bodies are capped at 1 MiB (413 beyond that).
- The bridge never logs or returns secrets; it has no access to the
  credential store. Keep it that way.

## API

All JSON unless noted. Errors are `{"error": "..."}` with an HTTP status.

### GET /api/status
Driver health. → `{"ok": true, "detail": "<driver status text>"}`

### GET /api/windows
→ driver `list_windows` result: array of
`{pid, window_id, app_name, title, bounds: {x, y, width, height}}`.
Use it to draw click targets or a window list.

### GET /api/screenshot
→ `image/png` of the full desktop (`Cache-Control: no-store`).
Poll it (e.g. every 1–3 s) for the live view.

### POST /api/click
`{"x": int, "y": int, "button": "left"|"right"|"middle"}` — absolute
desktop coordinates (same space as the screenshot and window bounds).
→ `{"ok": true, "window": "<title>", "result": ...}`.
404 if no window owns that point.

### POST /api/type
`{"text": "..."}` (max 2000 chars) — focuses the top window and types.
→ `{"ok": true, "result": ...}`. 404 if no window is open.

### POST /api/key
`{"key": "Return", "modifiers": ["ctrl","shift","alt","super"]}` —
key names follow the driver's `press_key` vocabulary (`Return`, `Tab`,
`Escape`, `F5`, single characters, …). → `{"ok": true, "result": ...}`.

### POST /api/launch
`{"app": "<name>"}` — launches only allowlisted apps (anything else 400):
`xterm`, `terminal` (xfce4-terminal), `chromium`, `blender`.
To add an app, extend `LAUNCH_ALLOWLIST` in `cua-bridge.py` — it must be
an absolute argv, never a shell string.

## Suggested panel features (pick what you like)

- Live screenshot with click-to-act (map the tap point to desktop coords).
- Text box + Send, and common keys (Enter, Tab, Esc, Ctrl+C, Alt+Tab).
- Launcher buttons for the allowlisted apps.
- Window list from `/api/windows`.
- Big touch targets and a dark theme if it's primarily a phone UI.

## Gotchas

- The desktop is Xvfb + XFCE on display :98 (see `cua-desktop.sh`); if the
  screenshot is stale or input does nothing, the stack probably needs a
  restart — that is the keepalive's job, not the panel's.
- XTEST keyboard input can wedge silently (driver reports ok, nothing
  types); the fix is `cua-desktop.sh stop/start` on the box.

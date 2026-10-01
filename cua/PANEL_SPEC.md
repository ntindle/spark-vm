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

Input-path liveness (#492): the XTEST keyboard device can wedge while the
driver still reports ok (typing silently does nothing). Every status call
runs a cheap probe — `xev` on `:98` is focused, one harmless XTEST key (a
bare Shift tap) goes out through the driver's global-input route, and the
bridge watches for the `KeyPress` echo — and reports it as
`"input": {"state": "ok"|"wedged"|"unknown", "detail": "<human text>"}`.
`"wedged"` means restart the desktop stack (`cua-desktop.sh stop`/`start`);
`"unknown"` means the probe itself couldn't run (xev/stdbuf missing, driver
down) — inconclusive, never a wedge. The probe is bounded (~2 s) and the
focus hop is inherent: XTEST keys deliver to the input-focus window, so
`xev` must briefly hold focus for the echo to land in it.

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

Duplicate-launch guard (#491): the bridge records every PID it spawns per
app name (dead PIDs pruned on every read), so a panel double-tap or a
retry loop no longer silently stacks N chromiums. Pass
`"singleton": true` (a literal JSON `true` — anything else, including the
string `"false"`, is a normal multi-launch) to refuse with 409
(`{"error": "already running", "pids": [...]}`) while an instance is
still alive — the default stays multi-launch (a second xterm is sometimes
wanted). The running set is always visible in `GET /api/status` under
`"launched"` (`{"xterm": [{"pid": 1234, "launched_at": <unix time>}], ...}`)
so the panel can decide for itself. The registry survives bridge restarts
(persisted under the user's own `~/.cache`, reloaded and re-pruned at
startup), so the 409 contract holds across the keepalive's restarts too.
Best-effort by construction: tracking is per bridge-spawned PID, so an
app that daemonizes (its launcher PID exits while the app keeps running)
can read as dead, and a recycled PID can briefly read as alive — the
bridge prunes on every read and self-heals.

## Suggested panel features (pick what you like)

- Live screenshot with click-to-act (map the tap point to desktop coords).
- Text box + Send, and common keys (Enter, Tab, Esc, Ctrl+C, Alt+Tab).
- Launcher buttons for the allowlisted apps.
- Window list from `/api/windows`.
- Big touch targets and a dark theme if it's primarily a phone UI.

## Example: driving Blender over the panel API

This is a real session pattern (curl against the tunnel endpoint). Blender is
allowlisted as `blender`; the launcher wrapper forces X11 so it appears on the
box's Xvfb desktop.

```bash
BASE=http://127.0.0.1:18732
H="X-CUA: 1"
J="Content-Type: application/json"

# 1. Launch Blender (cold start takes ~10-20 s)
curl -s -H "$H" -H "$J" -X POST $BASE/api/launch -d '{"app":"blender"}'

# 2. Wait until its window shows up
for i in $(seq 1 20); do
  curl -s $BASE/api/windows | grep -qi blender && break
  sleep 2
done
curl -s $BASE/api/windows | python3 -c \
  "import json,sys; [print(w['title'], w['bounds']) for w in json.load(sys.stdin)]"

# 3. Look at the desktop, dismiss the splash screen
curl -s $BASE/api/screenshot -o shot1.png
curl -s -H "$H" -H "$J" -X POST $BASE/api/key -d '{"key":"Escape"}'

# 4. Delete the default cube: select all, delete, confirm
curl -s -H "$H" -H "$J" -X POST $BASE/api/key -d '{"key":"a"}'
curl -s -H "$H" -H "$J" -X POST $BASE/api/key -d '{"key":"x"}'
curl -s -H "$H" -H "$J" -X POST $BASE/api/key -d '{"key":"Return"}'

# 5. Add Suzanne: Shift+A opens the Add menu, typing filters it
curl -s -H "$H" -H "$J" -X POST $BASE/api/key \
  -d '{"key":"a","modifiers":["shift"]}'
curl -s -H "$H" -H "$J" -X POST $BASE/api/type -d '{"text":"Monkey"}'
curl -s -H "$H" -H "$J" -X POST $BASE/api/key -d '{"key":"Return"}'

# 6. Verify on screen
curl -s $BASE/api/screenshot -o shot2.png
```

Tips for scripted Blender sessions:

- Prefer `/api/key` and `/api/type` over `/api/click` — Blender's UI is
  dense and resolution-dependent, while its keyboard shortcuts are stable.
- After any action, grab a fresh screenshot; that is your ground truth.
- The driver types into the focused top window (`/api/type` focuses it
  first), so make sure the Blender window is on top before typing.
- Rendering (`F12`) works fine headless; the render appears in a new
  Blender window — screenshot it, or save via `F3`.

## Gotchas

- The desktop is Xvfb + XFCE on display :98 (see `cua-desktop.sh`); if the
  screenshot is stale or input does nothing, the stack probably needs a
  restart — that is the keepalive's job, not the panel's.
- XTEST keyboard input can wedge silently (driver reports ok, nothing
  types); the fix is `cua-desktop.sh stop/start` on the box.

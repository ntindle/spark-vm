# Demo assets

Marketing visuals for spark-vm — the demo-assets plan from the launch-post
PR (ntindle/spark-vm#36). Finals live here; the pipeline that made them is
`scripts/generate_demo_assets.py` (+ `scripts/demo_confirmd.py`).

## Assets

| File | What it shows | Status |
|---|---|---|
| `demo-approval-loop.gif` | The confirmd approval loop end to end: pending page → approval detail → two-tap approve (armed state) → back to "No pending approvals". 390px phone viewport (420px-wide frames), 6.8s loop, ~130KB. | ✅ shipped |
| `demo-secrets-never-seen.gif` | "Secrets the agent never sees": the demo agent's config carries only `hsurr:…` placeholders, then the swap proxy's audit journal line — which names the placeholder, never the value. 480px-wide terminal frames, 20s loop, ~23KB. | ✅ shipped |
| (asset 3) persistence pair | Same desktop 24h apart — before/after screenshots. | ⬜ follow-up |
| (asset 4) muse-job watch | Multi-day job alive in `muse-job` watch. | ⬜ follow-up |
| `demo-cred-ui-phone.gif` | cred-ui on a phone viewport: the add/update form full-width, stored credentials as stacked cards. 390px phone viewport (410px-wide frames), 4.8s loop, ~55KB. | ✅ shipped |

## Provenance of `demo-approval-loop.gif`

Recorded 2026-09-19 against a **demo** confirmd instance on spark-vm
(localhost only, port 18923 — any free port works, throwaway self-signed
cert, throwaway VAPID keypair, scratch `CONFIRM_DIR`). Every approval in
the frames is a demo filing (`credential=demo-github-ro`,
`job=demo-muse-job`, purpose prefixed `demo:`) — no real credentials,
hosts, or jobs appear.

The demo instance is the real `confirm/confirmd.py` with two **demo-only**
overrides in `scripts/demo_confirmd.py` (never for production):

1. **Auth bypass** — `Handler._auth` returns the owner. The demo camera is
   localhost, not a tailnet peer, so the tailnet-identity gate cannot pass.
   The frames show the approval UX, not the auth gate.
2. **Filing-gate stub** — `file_owner_name` returns `"swapd"`. The demo
   files as the demo user, not bdrive/swapd (finding 50), so the gate is
   stubbed to exercise the full flow (approve → grant mint → answered).
   `GRANT_WRITER` points at a stub that exits 0 — the frames show the
   approval UX, not grant issuance.

Frame staging (also demo-only, does not change the product):

- The push-status UI is hidden in the frames. The headless camera cannot
  register a service worker, so that section always renders a "push
  unavailable" artifact — a camera limitation, not product state. The
  frames are about the approval loop.
- The two taps are dispatched via `element.click()` in JS rather than
  synthetic pointer taps: headless mobile-emulation taps proved flaky,
  and the page's own two-tap handler (arm → confirm) runs unchanged either
  way. (The injected snippet deliberately avoids a global `var b` — the
  page's inline script already claims that name; see the code comment.)
- The capture uses `ignore_https_errors` because the demo instance serves
  a throwaway self-signed certificate.

## Regenerating

On a machine with Playwright + Chromium and Pillow (e.g. spark-vm):

```sh
# 0. scratch dir + throwaway TLS cert + no-op grant writer
mkdir -p /tmp/demo-approvals
openssl req -x509 -newkey rsa:2048 -keyout /tmp/demo-approvals/key.pem \
  -out /tmp/demo-approvals/cert.crt -days 1 -nodes -subj "/CN=demo"
printf '#!/bin/sh\nexit 0\n' > /tmp/demo-approvals/grant-writer-stub
chmod +x /tmp/demo-approvals/grant-writer-stub
# throwaway VAPID keypair so push renders as configured (it is hidden in
# the frames, but the recorded run had it configured); CONFIRM_VAPID_KEYS
# names the JSON file, it is not the JSON itself
python3 confirm/push.py --gen-keys /tmp/demo-approvals/vapid.json

# 1. demo instance (terminal A) — DEMO ONLY, never the live deployment.
#    demo_confirmd.py refuses to start without CONFIRM_DEMO=1, forces
#    loopback bind, and refuses the production approvals dir.
CONFIRM_DEMO=1 \
CONFIRM_SRC=/path/to/spark-vm/confirm \
CONFIRM_BIND=127.0.0.1 CONFIRM_PORT=18923 \
CONFIRM_DIR=/tmp/demo-approvals \
CONFIRM_CERT=/tmp/demo-approvals/cert.crt \
CONFIRM_KEY=/tmp/demo-approvals/key.pem \
CONFIRM_VAPID_KEYS=/tmp/demo-approvals/vapid.json \
GRANT_WRITER=/tmp/demo-approvals/grant-writer-stub \
python3 scripts/demo_confirmd.py

# 2. file a demo approval (terminal B) — demo values only
CONFIRM_DIR=/tmp/demo-approvals confirm/confirm-request \
  --kind first-use --credential demo-github-ro --host api.github.com \
  --method GET --path-prefix /repos/ --scope read --job demo-muse-job \
  --purpose "demo: first GitHub read from a fresh agent job"

# 3. capture + assemble (terminal B)
python3 scripts/generate_demo_assets.py \
  --url https://127.0.0.1:18923 \
  --out assets/demo-approval-loop.gif
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final.


## Provenance of `demo-secrets-never-seen.gif`

Recorded 2026-09-19 by running the asset's own recipe on this box (no
live services, no browser — the asset renders terminal frames with PIL):

- The config is a demo fixture (`demo-agent-config.json` in the scratch
  work dir): every credential value the agent would touch is a
  `demo-`-named placeholder (`hsurr:demo-gh-ro`, `demo-agent`). No real
  secrets appear. The only real-world string anywhere in the asset is
  `api.github.com` — the public example host used throughout the
  spark-vm docs.
- The journal line is **byte-for-byte the output of the real
  `proxy/swap_addon.py` `SwapAddon._audit()` code path**, called from the
  generator with `SWAP_LOG_FILE` pointed at a scratch journal:
  `ts=<utc> host=api.github.com swapped=hsurr:demo-gh-ro ip=-`
- The three frames are genuine command transcripts: the generator runs
  `cat demo-agent-config.json`, `tail -1 demo-swap.log`, and
  `grep -oE '[A-Za-z0-9_-]{40,}' demo-swap.log || echo '...'` for real
  in the scratch work dir and renders the real stdout. The displayed
  paths are the scratch work dir's real relative paths, not the agent's
  real config location.
- Rendering notes (staged, disclosed): the journal line is word-wrapped
  for the 480px frame (real terminals wrap at the column edge too); the
  terminal chrome (title bar, caption strip) is drawn by the generator.

## Regenerating `demo-secrets-never-seen.gif`

Needs Pillow only (no Playwright, no Chromium, no live services):

```sh
# scratch dir lives in the working tree, not /tmp (/tmp gets wiped
# mid-run on this box); its contents are git-ignored, safe to delete
python3 scripts/generate_demo_assets.py \
  --asset secrets --work-dir ./demo-asset2-work \
  --out assets/demo-secrets-never-seen.gif
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final.

## Provenance of `demo-cred-ui-phone.gif`

Recorded 2026-09-19 against a **demo** cred-ui instance on this box
(localhost only, port 18740 — the port is hardcoded in `cred-ui.py`).
The demo is the real `cred-ui/cred-ui.py` with **no code overrides**:
reads went through the real `sudo -u swapd cat /home/swapd/credentials.json`
and `sudo -u swapd ls /home/swapd/secrets` paths against a scratch
`swapd` layout holding only the demo fixture. The fixture registry has
two demo-named entries (`demo-github-ro`, registered + bearer-header
placement on `api.github.com`; `demo-llm-api`, registered + custom-header
placement on `inference.example.com`, no value) and the secret file is
**empty** — so the "● value stored" state renders with no value content
anywhere in the asset. No real credentials, hosts, or values appear.

Write paths were never exercised: the narrow sudo writers
(`/usr/local/bin/cred-store-set`, …) don't exist on the demo box, so the
asset shows read/render paths only — the Save/delete/host buttons are
visible but never clicked.

Frame staging (also demo-only, does not change the product):

- The two frames are the top and bottom 390×844 viewports cropped from a
  single 390px-wide full-page capture: exactly the pixels a phone user
  sees at the top of the page and scrolled to the bottom. The GIF's
  "scroll" is a cut between the two real viewports, not a re-render.
- The phone bezel, notch bar, and caption strips are drawn by the
  generator; scrollbars hidden (`--hide-scrollbars`); the capture waits
  on `--virtual-time-budget` so the page's 3s auto-refresh fetch of
  `/api/creds` completes before the shot.

One small product fix the asset required: the stored-credentials table
overflowed at phone widths (hosts and delete columns clipped off-screen),
so the "phone view" claim was false until fixed. Below 520px each row now
renders as a stacked card with inline NAME/STATE/HOSTS labels and a
full-width delete button (`cred-ui/index.html` media query); the header
row is wrapped in `<thead>` so it hides cleanly (the JS previously emitted
a bare `<tr>`, which browsers auto-wrap in `tbody`, defeating the
`thead { display: none }` rule). Desktop rendering is unchanged.

## Regenerating `demo-cred-ui-phone.gif`

Needs Pillow + a `chrome-headless-shell` binary (Playwright's browser
cache has one; no Playwright Python package needed):

```sh
# 0. scratch swapd layout with the demo fixture (demo-named only;
#    the secret file stays EMPTY -- nothing real ever lands here).
#    cred-ui.py reads via `sudo -n -u swapd …` (no password prompt), so
#    run step 1 as root, or install the two read rules from
#    proxy/sudoers-swapd (the `/usr/bin/cat /home/swapd/credentials.json`
#    and `/usr/bin/ls /home/swapd/secrets` lines) for your user --
#    otherwise /api/creds silently returns an empty list and the captured
#    asset shows no credentials.
sudo useradd -r -M -s /usr/sbin/nologin swapd   # if the user is absent
sudo mkdir -p /home/swapd/secrets
sudo tee /home/swapd/credentials.json > /dev/null <<'EOF'
{
  "demo-github-ro": {
    "allowed_hosts": ["api.github.com"],
    "access_token": {"placement": "bearer_header"}
  },
  "demo-llm-api": {
    "allowed_hosts": ["inference.example.com"],
    "api_key": {"placement": {"custom_header": "X-Api-Key"}}
  }
}
EOF
sudo touch /home/swapd/secrets/demo-github-ro
sudo chown -R swapd:swapd /home/swapd
sudo chmod 700 /home/swapd
sudo chmod 600 /home/swapd/credentials.json /home/swapd/secrets/demo-github-ro

# 1. demo instance (terminal A) -- DEMO ONLY, localhost bind is hardcoded
python3 cred-ui/cred-ui.py   # listens on 127.0.0.1:18740

# 2. capture + assemble (terminal B)
# CHROME_HEADLESS_SHELL is optional -- the generator auto-discovers the
# Playwright browser cache; set it only to pin a specific binary.
export CHROME_HEADLESS_SHELL=~/.cache/ms-playwright/chromium_headless_shell-<build>/chrome-headless-shell-linux64/chrome-headless-shell
python3 scripts/generate_demo_assets.py \
  --asset credui-phone --url http://127.0.0.1:18740 \
  --frames-dir ./demo-asset5-work --out assets/demo-cred-ui-phone.gif

# 3. tear down the demo layout when done
# kill the cred-ui.py process, then: sudo userdel -r swapd
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final. Never point the generator at the live cred-ui deployment.

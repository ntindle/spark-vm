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
| (asset 5) cred-ui phone view | cred-ui rendered in a phone viewport. | ⬜ follow-up |

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
current final. Never point the generator at the live deployment.

## Provenance of `demo-secrets-never-seen.gif`

Recorded 2026-09-19 by running the asset's own recipe on this box (no
live services, no browser — the asset renders terminal frames with PIL):

- The config is a demo fixture (`demo-agent-config.json` in the scratch
  dir): every value the agent would touch is a `demo-`-named placeholder.
  No real credentials, hosts, or jobs appear.
- The journal line is **byte-for-byte the output of the real
  `proxy/swap_addon.py` `SwapAddon._audit()` code path**, called from the
  generator with `SWAP_LOG_FILE` pointed at a scratch journal:
  `ts=<utc> host=api.github.com swapped=hsurr:demo-gh-ro ip=-`
  (`api.github.com` is the public example host used throughout the
  spark-vm docs.)
- The three frames are genuine command transcripts: the recipe cats the
  fixture, tails the real journal, and greps the journal for
  raw-secret-length tokens (`[A-Za-z0-9_-]{40,}`) — the grep finds
  nothing, so the `|| echo` fires and the frame shows real output.
- Rendering notes (staged, disclosed): the journal line is word-wrapped
  for the 480px frame (real terminals wrap at the column edge too); the
  terminal chrome (title bar, caption strip) is drawn by the generator.

## Regenerating `demo-secrets-never-seen.gif`

Needs Pillow only (no Playwright, no Chromium, no live services):

```sh
# scratch dir lives in the working tree, not /tmp (/tmp gets wiped
# mid-run on this box)
python3 scripts/generate_demo_assets.py \
  --asset secrets --work-dir ./demo-asset2-work \
  --out assets/demo-secrets-never-seen.gif
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final.

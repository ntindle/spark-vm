# Demo assets

Marketing visuals for spark-vm — the demo-assets plan from the launch-post
PR (ntindle/spark-vm#36). Finals live here; the pipeline that made them is
`scripts/generate_demo_assets.py` (+ `scripts/demo_confirmd.py`).

## Assets

| File | What it shows | Status |
|---|---|---|
| `demo-approval-loop.gif` | The confirmd approval loop end to end: pending page → approval detail → two-tap approve (armed state) → back to "No pending approvals". 390px phone viewport, 6.9s loop, 129KB. | ✅ shipped |
| (asset 2) secrets the agent never sees | Config with `hsurr:…` placeholders, then the swap-proxy audit line — 20s GIF. | ⬜ follow-up |
| (asset 3) persistence pair | Same desktop 24h apart — before/after screenshots. | ⬜ follow-up |
| (asset 4) muse-job watch | Multi-day job alive in `muse-job` watch. | ⬜ follow-up |
| (asset 5) cred-ui phone view | cred-ui rendered in a phone viewport. | ⬜ follow-up |

## Provenance of `demo-approval-loop.gif`

Recorded 2026-09-19 against a **demo** confirmd instance on spark-vm
(localhost only, ephemeral port, throwaway self-signed cert, throwaway
VAPID keypair, scratch `CONFIRM_DIR`). Every approval in the frames is a
demo filing (`credential=demo-github-ro`, `job=demo-muse-job`,
purpose prefixed `demo:`) — no real credentials, hosts, or jobs appear.

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
  way. The evaluate uses a uniquely-named variable on purpose — the page's
  inline script declares a global `var b` for the approve button and its
  click handler closes over it, so a generic `var b` in injected JS would
  repoint the handler at the push button and silently break the arm.

## Regenerating

On a machine with Playwright + Chromium and Pillow (e.g. spark-vm):

```sh
# 1. demo instance (terminal A) — DEMO ONLY, never the live deployment
CONFIRM_SRC=/path/to/spark-vm/confirm \
CONFIRM_BIND=127.0.0.1 CONFIRM_PORT=18923 \
CONFIRM_DIR=/tmp/demo-approvals \
CONFIRM_CERT=/tmp/demo-approvals/cert.crt \
CONFIRM_KEY=/tmp/demo-approvals/key.pem \
GRANT_WRITER=/tmp/demo-approvals/grant-writer-stub \
python3 scripts/demo_confirmd.py

# 2. file a demo approval (terminal B)
CONFIRM_DIR=/tmp/demo-approvals confirm/confirm-request \
  --kind first-use --credential demo-cred --host demo.example.invalid \
  --method GET --path-prefix / --job demo-job \
  --purpose "demo: <what the frame should say>"

# 3. capture + assemble (terminal B)
python3 scripts/generate_demo_assets.py \
  --url https://127.0.0.1:18923 \
  --out assets/demo-approval-loop.gif
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final. Never point the generator at the live deployment.

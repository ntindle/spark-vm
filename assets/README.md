# Demo assets

Marketing visuals for spark-vm — the demo-assets plan from the launch-post
PR (ntindle/spark-vm#36). Finals live here; the pipeline that made them is
`scripts/generate_demo_assets.py` (+ `scripts/demo_confirmd.py`).

## Assets

| File | What it shows | Status |
|---|---|---|
| `demo-approval-loop.gif` | The confirmd approval loop end to end: pending page → approval detail → two-tap approve (armed state) → back to "No pending approvals". 390px phone viewport (420px-wide frames), 6.8s loop, ~130KB. | ✅ shipped |
| `demo-secrets-never-seen.gif` | "Secrets the agent never sees": the demo agent's config carries only `hsurr:…` placeholders, then the swap proxy's audit journal line — which names the placeholder, never the value. 480px-wide terminal frames, 20s loop, ~23KB. | ✅ shipped |
| `demo-persistence-pair.gif` | "The same desktop, days apart": the persistence pair — frame 1 is Xvfb :98's birth record (`ps -o pid,etime,lstart,cmd`, showing 4d+ elapsed in-frame), frame 2 re-verifies the same pid/start alive moments later, with the Sep-16 tmux job sessions still there. 480px-wide terminal frames, 12s loop, ~20KB. | ✅ shipped |
| `demo-musejob-watch.gif` | "Long-lived jobs stay alive": real `muse-job` spawn → status → status 20+ minutes later on a demo job (480px terminal frames, 7.2s loop, ~29KB). | ✅ shipped |
| `demo-cred-ui-phone.gif` | cred-ui on a phone viewport: the add/update form full-width, stored credentials as stacked cards. 390px phone viewport (410px-wide frames), 4.8s loop, ~55KB. | ✅ shipped |
| `demo-push-queue.gif` | "The push queue survives an outage": the real `confirm/push.py` H14 durable enqueue/retry against a local mock push service — first delivery attempt 500s and reschedules, the journal keeps the summons, the retry delivers on 201. 480px-wide terminal frames, 26s loop, ~43KB. | ✅ shipped |

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

## Provenance of `demo-persistence-pair.gif`

Recorded 2026-09-20 from the **live** spark-vm box (not a demo
instance — the subject is the box's own long-lived desktop session):

- Frame 1 is the verbatim stdout of `ps -o pid,etime,lstart,cmd -p 20640`:
  Xvfb `:98` (the display the CUA driver clicks through) started
  **Wed 2026-09-16 02:07:35** and had been alive 4d 1h01m at capture
  (the `ELAPSED` column proves the age inside the frame itself).
- Frame 2 is the verbatim stdout of three commands run in the same
  capture session, seconds later: `uptime` (4 days, 21:14),
  `ps -o pid,lstart -p 20640` (same pid, same start time), and
  `tmux ls` (the Sep-16 `muse-job` sessions still alive).
- The full capture lives verbatim in
  `assets/persistence-capture-2026-09-20.json` (commands + stdout +
  capture timestamp + re-capture recipe). The generator renders the
  frames from that file and computes the day gap from its timestamps —
  a re-capture renders its own honest elapsed time. All timestamps in
  the fixture are tz-aware (`-05:00`, America/Chicago); the loader
  refuses tz-naive timestamps rather than guessing. Lines longer than
  the frame's column budget are hard-elided with an explicit `…`
  marker in the render only — the fixture keeps the complete verbatim
  stdout as the audit trail.

The launch-post plan asked for "same desktop 24h apart — before/after
screenshots". Staging a fake 24h gap was rejected as dishonest; this
asset shows the real thing instead — a session that has genuinely been
alive for days, proven by its own start-time record. The claim is the
mechanics (birth record → still alive), never more. Note the gap is
Xvfb's own lifetime (4d 1h01m at capture), not the box's 4d 21h14m
uptime — both are shown, honestly labeled, in the two frames.

## Regenerating `demo-persistence-pair.gif`

Re-rendering needs Pillow only (no box):

```sh
python3 scripts/generate_demo_assets.py \
  --asset persistence --out assets/demo-persistence-pair.gif
```

Re-capturing (refreshes the fixture; needs SSH to spark-vm). The
`[X]` in the pgrep pattern keeps pgrep from matching its own command
line; `date -Iseconds` supplies the tz-aware `captured_at`; append the
box's UTC offset to the `lstart` value for `xvfb_started`:

```sh
ssh ntindle@spark-vm 'PID=$(pgrep -f "[X]vfb :98" | head -1); \
  echo "PID=$PID"; \
  ps -o pid,etime,lstart,cmd -p "$PID"; \
  uptime; \
  ps -o pid,lstart -p "$PID"; \
  tmux ls 2>/dev/null; \
  date -Iseconds'
# map the sections to fixture keys, in order:
#   birth.stdout   <- ps -o pid,etime,lstart,cmd output
#   uptime.stdout  <- uptime output
#   live.stdout    <- ps -o pid,lstart output
#   tmux.stdout    <- tmux ls output
#   xvfb_pid       <- the PID= line
#   xvfb_started   <- the lstart value + the box's UTC offset
#                    (e.g. 2026-09-16T02:07:35-05:00)
#   captured_at    <- the date -Iseconds output
# save as assets/persistence-capture-<date>.json, then render with:
python3 scripts/generate_demo_assets.py \
  --asset persistence --fixture persistence-capture-<date>.json \
  --out assets/demo-persistence-pair.gif
```

Regeneration overwrites the GIF in place — the file in the repo is the
current final. Never fabricate the capture: the fixture is the audit
trail.

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

## Provenance of `demo-musejob-watch.gif`

Recorded 2026-09-20 against a **demo** muse-job on spark-vm (the box's own
`muse-job` CLI, job slug `demo-watch-job`). The frames are that one demo
job's real CLI output, verbatim — long lines are wrapped by the
generator, never edited. No real user jobs appear.

What actually happened (disclosed, because it matters): the demo agent hit
a **429 subscription-quota error** on its first turn and never executed its
planned workload (test suite + heartbeats). So the three frames show
something more honest than the plan: the *job* — tmux session, worktree,
`state=active tmux=up session=healthy` — stayed up for 24+ minutes while
the agent inside was blocked, and the two captured statuses show `status`
reporting healthy with elapsed growing (0.0h → 0.4h). Session persistence
is exactly what the asset claims; it claims no agent progress. The job
was closed after capture (`muse-job close demo-watch-job`).

Frame staging (also demo-only, does not change the product):

- The displayed commands are the canonical box forms (`muse-job spawn …`);
  the remote-exec `PATH=…` prefix is dropped. The stdout below each
  command is the verbatim output.
- The window chrome (title bar reading "demo — long-lived jobs stay
  alive") and the per-frame caption strips ("1/3 — …") are drawn by the
  generator, as with asset 2; only the transcript body under each command
  is verbatim output.

The asset does not claim the demo job ran for days — it claims the
mechanics that make days-long jobs work: spawn gets a tmux session and a
worktree, and `status` keeps reporting `state=active tmux=up
session=healthy` as elapsed grows. (The loop's own production jobs
routinely run 70h+; a 74.8h active job was observed on the box the same
day.)

## Regenerating `demo-musejob-watch.gif`

Needs Pillow and ssh access to a box with `muse-job` installed. Run steps
0–3 and 5 on the box (ssh in; the `PATH=` prefix is only needed over ssh,
skip it when running on the box itself). Then copy `demo-asset4-captures/`
to the root of your repo checkout and run step 4 there.

```sh
# 0. scratch capture dir + demo prompt file on the box (harmless workload
#    only: test suite, then 5-minute heartbeats; no PRs, no network beyond
#    localhost, no credential files). If the agent 429s on quota like it
#    did for us, the session-persistence story still holds -- the frames
#    only need spawn + two statuses.
mkdir -p demo-asset4-captures
cat > /home/ntindle/demo-watch-prompt.md <<'EOF'
demo-watch-job: long-lived heartbeat job for a launch marketing GIF.

Do this, in order:
1. Run the spark-vm python test suite from /home/ntindle/spark-vm
   (python3 -m pytest -x -q) and write the pass/fail summary as the
   first lines of PROGRESS.md in your worktree.
2. Then stay alive: every 5 minutes append one timestamped line
   "heartbeat <ISO8601> still alive" to PROGRESS.md in your worktree.
   Keep the tmux session healthy and keep working until steered or closed.
Do not open any PRs, do not touch the network beyond localhost, do not
read any credential files. End blocked turns with BLOCKED:.
EOF

# 1. spawn the demo job (PATH= is only needed over ssh; skip it on the box).
#    If spawn fails with "ambiguous argument 'origin/HEAD'" (cloning a
#    local --repo path leaves origin/HEAD unset), fix it once and retry:
#      git -C ~/repos/spark-vm symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
{ echo '$ muse-job spawn demo-watch-job --repo /home/ntindle/spark-vm --prompt-file /home/ntindle/demo-watch-prompt.md --budget-hours 2'; \
  muse-job spawn demo-watch-job --repo /home/ntindle/spark-vm \
    --prompt-file /home/ntindle/demo-watch-prompt.md --budget-hours 2; } \
  > demo-asset4-captures/w1-spawn.txt

# 2. wait ~30s for the tmux session to come up, then status
{ echo '$ muse-job status demo-watch-job'; muse-job status demo-watch-job; } \
  > demo-asset4-captures/w2-status.txt

# 3. wait ~20 minutes, then status again (elapsed grows, still alive) --
#    this is the last capture
{ echo '$ muse-job status demo-watch-job'; muse-job status demo-watch-job; } \
  > demo-asset4-captures/w3-status-later.txt

# 4. render + assemble
python3 scripts/generate_demo_assets.py \
  --asset musejob-watch --capture-dir ./demo-asset4-captures \
  --frames-dir ./demo-asset4-work --out assets/demo-musejob-watch.gif

# 5. close the demo job when done
muse-job close demo-watch-job
```

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

## Provenance of `demo-push-queue.gif`

Recorded 2026-09-22 by `scripts/generate_demo_assets.py --asset push-queue`,
which runs the REAL `confirm/push.py` code paths (H14 durable enqueue/retry)
against a scratch world that never leaves the machine:

- scratch `CONFIRM_DIR` (a `./demo-push-work` directory — the generator sets
  `CONFIRM_DIR`, `CONFIRM_VAPID_KEYS`, `CONFIRM_PUSH_SUBS`, and
  `CONFIRM_VAPID_SUB` itself, so the ambient environment is untouched),
- a throwaway VAPID keypair, generated silently before frame 1
  (`push.py --gen-keys`; its output is omitted from the frames — a demo
  key is visual noise, not the story). It never leaves the scratch dir
  and is deleted with it,
- one demo subscription whose endpoint is a local mock push service on
  127.0.0.1 (ephemeral port) that answers the first POST with 500 and every
  later POST with 201 — a stand-in for a dead-then-recovered push service.
  The subscription keys are a throwaway P-256 pair + random auth secret;
  the payload is really VAPID-signed and aes128gcm-encrypted by the real
  code, the mock just never decrypts it.

The four frames are the verbatim transcripts of the displayed commands:
the real `PushQueue.enqueue()` call (run from `confirm/` so the import
needs no path plumbing), `push.py --worker-once` (500 → rescheduled,
attempt 1/8, next try in 60s), `cat push-queue.jsonl` (the pending entry),
a second `--worker-once` after the real 60-second backoff elapsed — whose
stderr now shows `push: send to 127.0.0.1:PORT returned 201` (the worker
logs successful deliveries to stderr, mirroring the failure warning) —
and `wc -c push-queue.jsonl` (0 — the journal drained). Long lines are
wrapped by the generator, never edited: spaces first, then JSON
delimiters, so the journal's spaceless compact JSON wraps between tokens
instead of splitting one mid-word. The window chrome and caption strips
are drawn by the generator, as with the other terminal assets.

What the asset claims — the summons survives a dead endpoint in the
durable journal and the retry delivers — is exactly what the frames show.
It does not claim a real browser received a notification (the mock is not
a browser); the end-to-end phone notification is the approval-loop asset's
companion story, not this one's.

## Regenerating `demo-push-queue.gif`

Needs Pillow + the `cryptography` package (already in
`requirements-test.txt`):

```sh
python3 scripts/generate_demo_assets.py \
  --asset push-queue --work-dir ./demo-push-work \
  --frames-dir ./demo-push-frames --out assets/demo-push-queue.gif
```

The run takes ~75 seconds (it waits out the real 60s retry backoff so the
second delivery is genuinely due, not faked). Regeneration overwrites the
GIF in place — the file in the repo is the current final. The generator is
self-contained: it never reads the ambient `CONFIRM_DIR` and only ever
talks to 127.0.0.1. The scratch dirs' contents are git-ignored, safe to
delete (`demo-push-work/` also holds the throwaway VAPID private key —
never commit it).

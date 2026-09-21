# Push notifications for confirmd approvals (H2 / GitHub #2)

confirmd can push a Web Push notification to the owner's devices the
moment swapd files an approval — so the two-tap approval loop works even
when the approvals page isn't open.

This is a **portable component**, not a hosted-only service: the operator
runs it wherever the deployment lives (self-hosted box or hosted
service). The VAPID keypair is operator-generated during setup; no real
secrets ever live in the repo.

## How it works

1. **Setup (operator, once):**
   ```sh
   # Prerequisite (Ubuntu 24.04): the cryptography package. Use apt —
   # bare `pip install cryptography` fails under PEP 668's
   # externally-managed-environment policy.
   sudo apt install -y python3-cryptography

   sudo -u swapd python3 /home/swapd/push.py --gen-keys /home/swapd/confirmd/vapid.json
   # writes {"private","public"} base64url, mode 0600, refuses to overwrite
   sudo systemctl restart confirmd
   ```
   confirmd logs `PUSH_ENABLED=True` at startup. If push is disabled it
   logs the concrete reason instead, e.g. `PUSH_DISABLED_REASON=no-keys:
   /home/swapd/confirmd/vapid.json unreadable or invalid (...)` or
   `no-cryptography: ...` — the same value is served at
   `/api/push/config` as `disabled_reason`, so the status line can tell
   the operator exactly what is missing. The protocol is RFC 8030
   (Web Push) + RFC 8292 (VAPID) + RFC 8291 (aes128gcm payload
   encryption), implemented in `confirm/push.py` on top of the
   `cryptography` package. Without the key file (or without
   `cryptography` installed), push is disabled and the page works
   exactly as before.

2. **Verify (operator):** open the confirmd page (e.g.
   `http://127.0.0.1:18735/` through the SSH tunnel) — with keys
   configured and a supported browser you see an **Enable notifications**
   button under the pending list; without keys the status line names the
   missing piece. Then subscribe a test device and run:
   ```sh
   sudo -u swapd python3 /home/swapd/push.py --test-push
   # test push test-<ts>: 1 subscription(s) accepted it
   ```
   `--test-push` sends a real push through the configured keys to every
   stored subscription and reports how many the push service accepted —
   the same supported path as a real approval, no grant involved.

3. **Subscribe (human, once per browser):** open the confirmd pending
   page → "Enable notifications". The browser's PushManager subscribes
   with the server's VAPID public key (served at `/api/push/config` —
   public by design), and the subscription (endpoint + `p256dh` + `auth`)
   is POSTed to `/api/push/subscribe`. The button only appears when the
   browser supports push and the server reports it enabled. On
   iPhone/iPad the page says *"add this page to your home screen, then
   open it from there"* instead — iOS only exposes Web Push to
   home-screen-installed pages.
   A denied browser permission shows a recovery hint: allow
   notifications for the site in the browser's site settings, then retry.

4. **Notify (automatic):** when swapd files an approval
   (`swap_addon._file_approval`), `_push_notify` enqueues it —
   `PushQueue.default().enqueue(item)` on a **daemon thread**, one locked
   append to the durable queue journal
   (`$CONFIRM_DIR/push-queue.jsonl`), never on the mitmproxy flow thread.
   The standalone push worker (`push.py --worker`, shipped as
   `push-worker.service`) picks due entries up and sends one encrypted
   push per stored subscription, with exponential-backoff retry on
   transient failures (1m → 2m → 4m → 8m → 16m → 30m → 30m, then
   dead-letter). On the healthy path enqueue is immediate but delivery
   waits for the next worker pass — up to `--worker-interval` (default
   30s) after filing, tunable down for faster alerts. The service
   worker (`/sw.js`) shows the notification; tapping it opens
   `/approval/<id>`.

## The push worker (H14 part a)

`push.py --worker` is the standalone push service: it loops
(`--worker-interval`, default 30s), claims due queue entries under an
exclusive lock (claimed entries get a 30-minute lease, renewed between
entries mid-pass, so a crashed worker can't double-send — claims
self-heal after the lease), and delivers
each with the exact same wire payload as the inline path (shared
builder). Outcomes:

- **All subscriptions delivered (or pruned):** the entry is removed and
  the approval id is written to the notified log — no re-alert, ever.
- **Transient failure** (timeout, 5xx, connection error): the entry is
  rescheduled with backoff; the loud warning line names the attempt
  count and the next retry.
- **Permanent subscription death** (push service returns 404/410): the
  subscription is pruned from the store; the entry still completes.
- **8 failed attempts:** the entry is dead-lettered to
  `$CONFIRM_DIR/push-queue-dead.jsonl` with a loud `ERROR` line — the
  operator signal. The approval itself is unaffected (it was filed and
  answered normally); only the notification was lost.

Note the timing tradeoff of durability: a retry that succeeds after a
push outage can surface "Approval needed" minutes later, for an
approval already answered. Tapping it opens the approval page, which
always shows the current state — so a stale notification is a mild
annoyance, never a wrong action.

Runbook:

```sh
sudo systemctl status push-worker            # the service (enabled by deploy.sh)
sudo -u swapd python3 /home/swapd/push.py --worker-once   # one pass, prints stats
tail -1 /home/swapd/approvals/push-queue-dead.jsonl || echo "no dead letters"
# recover one dead-lettered approval (most recent record goes back on the queue):
sudo -u swapd python3 /home/swapd/push.py --requeue <approval-id>
```

With push disabled (no keys / no `cryptography`) the worker skips
passes (one warning line per hour, not per pass) and entries stay
queued — they deliver once the operator configures keys. The journal
and dead-letter file are created mode 0600 and carry approval ids +
summaries only — never secrets; their lock sidecars (`.lock`) are
created with the default umask and carry no data.

## Security notes

- **Key storage:** the VAPID private key lives at
  `/home/swapd/confirmd/vapid.json`, mode 0600, owned by swapd. It is
  generated on the box, never committed, never logged. `--gen-keys`
  refuses to overwrite an existing file.
- **Payload contents:** the encrypted payload carries only the approval
  summary (the same text the page already shows) plus the approval id —
  never secrets, never model-authored free text (finding 49). The
  notification URL is built relative to the page's own origin, so there
  is no origin confusion between the tailnet IP and the ts.net name.
- **Subscribe endpoint:** `/api/push/subscribe` and `/api/push/unsubscribe`
  are owner-authenticated exactly like the page (`_auth`), with the same
  CSRF defenses as `/answer` (Sec-Fetch-Site + exact Origin match, 4 KB
  body cap). Subscription material is validated strictly: https-only
  endpoints, 65-byte uncompressed `p256dh`, 16-byte `auth`.
- **Audit trail:** subscribes/unsubscribes are audit-logged (endpoint
  host only — the full URL carries an opaque push-service token).
  Dead subscriptions (push service returns 404/410) are pruned
  automatically.
- **Fail-open by design:** a push failure (no keys, network down, bad
  subscription) never loses the filed approval — the approval file is
  written first, and every push path catches and logs instead of
  raising. `notify_approval` is idempotent per approval id (a
  `push-notified` log, capped at 1000 entries) so retries can't
  double-notify. **Idempotency does NOT fire on total transient
  failure:** if every send raised or returned a retryable error, the
  approval is deliberately left unmarked — marking it would silently drop
  the notification. The error is logged loudly, and the entry stays
  queued (or is rescheduled with backoff) so the push worker retries it
  — the worker is the retry path the idempotency note used to defer.
- **Race safety:** the subscription store and the notified log are
  mutated from two processes (confirmd's ThreadingHTTPServer and
  mitmproxy's swap_addon) and concurrent threads, so mutations hold an
  exclusive `fcntl.flock` sidecar lock (`<path>.lock`) around the
  load-modify-save — atomic `os.replace` alone doesn't prevent a stale
  read from dropping a subscription.
- **Lock-screen exposure:** the encrypted payload carries the approval
  summary — the same text the page already shows — which means the
  summary is visible on the device's lock screen when the notification
  fires. Operators who consider approval metadata sensitive should know
  this is inherent to lock-screen notifications, not a leak.
- **Notification dismissal:** answering an approval (approve/deny) closes
  that approval's notification on the device, so a stale notification
  can't tap through to an already-answered page.
- **Icons:** the service worker posts text-only notifications (no
  `icon`/`badge`) — the browser renders its own default. Custom icons are
  a follow-up, not this slice.
- **Per-device, not per-tenant:** subscriptions are stored per box in
  `$CONFIRM_DIR/push-subscriptions.json` (mode 0600, atomic writes).
  Per-tenant queues (H10) will need per-tenant subscription scoping —
  that is follow-up work, not this slice.

## Configuration reference

| Env | Default | Purpose |
|---|---|---|
| `CONFIRM_VAPID_KEYS` | `/home/swapd/confirmd/vapid.json` | VAPID keypair JSON |
| `CONFIRM_PUSH_SUBS` | `$CONFIRM_DIR/push-subscriptions.json` | subscription store |
| `CONFIRM_VAPID_SUB` | `mailto:confirmd@localhost` | VAPID `sub` contact claim |
| `CONFIRM_PUSH_QUEUE` | `$CONFIRM_DIR/push-queue.jsonl` | worker queue journal |
| `CONFIRM_PUSH_DEAD` | `$CONFIRM_DIR/push-queue-dead.jsonl` | dead-letter file |

## Follow-ups (not this slice)

- H14 part b: confirmd approval-created hook + per-tenant subscription
  scoping (needs H10/H11's tenant model).
- iOS Safari note: Web Push on iOS requires the page added to the home
  screen; the status line says so explicitly (the button stays hidden).
- Custom notification icon/badge in the service worker (currently
  text-only; browser renders its own default).

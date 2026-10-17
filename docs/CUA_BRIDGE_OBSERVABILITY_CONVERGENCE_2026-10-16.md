# cua-bridge observability — convergence pin (2026-10-16)

**Re-verification of `docs/CUA_BRIDGE_OBSERVABILITY_GAP_ANALYSIS.md` at
main `1d132e64`, after #1588 S3 shipped.** All in-repo claims below are
verified against the code at that main; honesty rules apply
(`docs/POSITIONING.md`): this is current state and work to do, not
promises.

## 1. Lane state

The blocking prerequisite is satisfied: #1588 (S3 — sink rotation +
permissions pin) shipped as PR #1595, squash-merged `1f041edb`, and the
issue is closed. Slices S1 (#1586), S2 (#1587), and the #1576
mutation-audit build are now unblocked and unbuilt. Pointer comments
recording the unblocked state live on #1586 (id 6228101659), #1587 (id
6228101922), and #1576 (ids 6223819740, 6224000794).

## 2. The parent doc's S3 shipped-note, verified claim by claim

| Parent doc claim | Verified at `1d132e64` |
|---|---|
| "mechanism (a) — the bridge opens the log itself (O_APPEND\|O_NOFOLLOW, 0600)" | ✓ `cua/bin/cua-bridge.py` `_open` opens `~/.cache/cua-bridge.log` `O_WRONLY\|O_CREAT\|O_APPEND\|O_NOFOLLOW` mode `0o600` (L584–586); planted symlinks refused via `ELOOP` (L587–590); a pre-existing default-umask log is tightened `fchmod(fd, 0o600)` in place (L601). |
| "dup2's it onto stdout/stderr at startup" | ✓ `install` dup2's the owned fd onto fds 1 and 2 (L619–620); the post-rotation reopen does the same (L662). |
| "rotates size-capped (1 MiB × 3 generations) under its own write lock" | ✓ `AUDIT_LOG_MAX_BYTES = 1_000_000` (L455), `AUDIT_LOG_GENERATIONS = 3` (L456); `_maybe_rotate_locked` shifts `.2→.3, .1→.2, log→.1` and reopens under `self._lock` (shift loop L651–659; lock held at the `install()` L618 and `write_line()` L695 call sites). Soft-cap caveat (per the code's own docstring): the size check runs on structured writes and at install — legacy free-form prints bypass it, so the cap is advisory while the old print path still exists. |
| "the keepalive's `>>` redirect stays only as pre-setup capture" | ✓ `cua/bin/cua-keepalive.sh` keeps the redirect (L98) as capture for lines printed before `install_bridge_log` runs, documented in the L82–86 comment. |
| "the audit line format (`ts= level= kind= msg=`, one line per event, newlines escaped) is pinned in the bridge source …, with `log_bridge_event` as the choke point the S1/S2 writers will use" | ✓ `_format_bridge_event` (L461), `_escape_msg`/`_unescape_msg` inverse pair (L481–511), `_parse_bridge_event` reference parser (L514–551); `log_bridge_event`'s docstring (L743) names S1/S2/#1576 as its future callers and binds them to the D-CBA-1/D-CBA-2 content pins. |

Levels: the sink contract admits `WARNING` and `ERROR` only
(`_AUDIT_LEVELS`, L457). S1's events will pick one of these when it
lands — the issue body does not name a level.

## 3. Open findings re-verified (still true, still owned)

- **F-CBA-1 (#1576, open).** `Handler.log_message` is still `pass`
  (L1684); no mutation — click/type/key/launch — is recorded anywhere.
- **F-CBA-2 (#1586, open).** `do_GET`'s outer `except Exception as e:`
  (L1582) and `do_POST`'s (L1681) still answer
  `{"error": str(e)[:300]}` with a 500 and write nothing server-side.
  The truncated exception string still reaches the caller; the box
  still keeps nothing.
- **F-CBA-3 (#1587, open).** `_check_csrf` (L1493–1497) still answers
  403 `{"error": "forbidden"}` on a failed check and writes nothing.
- **F-CBA-4 (#1588, closed).** Superseded by S3 — see §2.
- **F-CBA-5 (advisory, unchanged).** No request timing or correlation
  exists; a hung click still has no server-side story. Still
  second-order behind the audit/error/reject gaps — noted, not filed.

The three writer slices' recommended shapes remain compatible with the
shipped choke point: #1586's one-line events land in
`log_bridge_event` (the newline-escaping contract handles the
"no multi-line traces" requirement); #1587's WARNING lines are a
`level="WARNING"` call away; #1576's audit lines are the D-CBA-1 shape
the choke point already pins. Zero non-test callers of
`log_bridge_event` exist today — the lane is wired and waiting.

## 4. New finding

- **F-CBA-6 — the audit-line contract's consumer half is missing.**
  D-CBA-4's parent doc frames the line format as "a contract between
  the bridge (writer) and the keepalive/operator tooling
  (rotator/consumer)". The writer half shipped in S3; the consumer
  half does not exist: nothing on the box reads or parses
  `~/.cache/cua-bridge.log` — `_parse_bridge_event` lives in-source
  plus tests only, and the only other holder of the path is the
  keepalive's pre-setup capture redirect. The operator's
  "reconstruction" tool today is raw `grep` over `ts= level= kind=
  msg=` lines. → filed as #1597 (p3, track:open-source): a small
  `cua/bin/cua-bridge-log` reader (parse via `_parse_bridge_event`,
  filter by kind/level, unescape for display) so the contract the
  parent doc names is actually usable from the box.

## 5. Advisory (noted, not filed)

- **Silent rotation.** `_maybe_rotate_locked` shifts generations with
  no audit event of its own: the oldest generation falls off silently.
  No rotation event is proposed — the ring is a documented design
  limit (1 MiB × 3, per D-CBA-4), a rotation marker would consume the
  bounded sink for an event with no operator action, and the dropped
  data leaves no marker of its own (retained generations are
  contiguous, so the loss is visible only against a prior snapshot) —
  so it is noted here, not filed.

## 6. What this pin does not do

- It does not change the bridge's trust model (localhost-only,
  CSRF-header contract, the #1574 probe-GET gate all stand).
- It does not build S1/S2/#1576 — those are build turns' work, now
  unblocked.
- It does not promise the hosted product anything (parent doc §5
  stands).

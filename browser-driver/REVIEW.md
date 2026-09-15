# Review of browser-driver/SPEC.md v1

Reviewed at commit `a006f6e`; the addendum at the end covers `7934e0e`, which landed under this review. Scope: `SPEC.md`, `proxy/swap_addon.py`,
`proxy/sudoers-swapd`, `proxy/hosts.allow`, `proxy/swap-proxy.service`,
`cred`, `credlib/`, `scripts/push.sh`, `SETUP.md`. Items marked
CONFIRMED were reproduced against the addon's pure functions with the
probe at the end of this file.

## Verdict

The direction is right. Placeholder-in, swap-at-egress is a good fit
for this box, and the proxy pieces that exist are cleanly built. The
spec overstates what is *enforced* versus what is *policy*, the
allowlist model has one hole that turns any allowlisted public host into
an exfiltration channel, and the swap has several encoding bugs. None of
that says "don't build the driver". It says fix the allowlist model and
the trust table first, because the driver inherits both.

## Schema constraint

The spec ports an existing schema: the `hsurr:<name>:<entry>` surrogate
format, the `access_token` default entry, the placement set
(`bearer_header`, `custom_header`, `query_param`, `url_path_segment`),
and the `dynamic_credentials` and `credential_fill` interfaces all come
from the cell and are treated here as fixed. No finding below asks to
change them. Where a fix touches credential metadata it extends the
existing registry (`credentials.json`, managed by `cred register`)
rather than inventing a parallel format.

## For the implementer

Read this section first; the numbered findings follow.

**Runnable target.** `python3 -m unittest proxy/test_swap_addon.py`
from the repo root. No mitmproxy needed. At `a006f6e` it reports 5
passing, 6 failing, 1 skipped; the failing tests are items 5, 6, 7, 8,
9 and 23, each named for its finding. The skipped test is item 1 and
should be enabled once the registry carries `allowed_hosts`. Done means
all of them pass and the `test_holds_*` tests still pass.

**Order.** Land items 1, 5, 6, 7, 8, 9 and 23 together as one proxy
change with the tests green. Then settle items 3 and 4 with the user
before writing `bdrive`, because the driver's `need_info` and `shot`
semantics depend on them. Items 10 to 13 are box hardening and can go
in parallel. The rest is spec and docs text.

**Needs the user, not just Muse.** Item 2 is the user's decision
(option a creates a new login and changes sudo; only they can do that
from their own SSH session). Item 3 needs the user to agree on the
confirmation channel. Items 12 and 13 are policy calls. Everything
else Muse can do alone.

**Do not.** Do not change the `hsurr:` format, the entry default, or
the placement set (see Schema constraint). Do not weaken pass-through
for non-allowlisted hosts. Do not resolve item 2 by editing the spec
text alone unless the user picks option (b). Do not mark a finding
done without its test.

## Blocking (fix before building bdrive)

1. **The allowlist is global, not per credential.** CONFIRMED (probe B).
   Any stored secret swaps into any allowlisted host. `github.com` is
   allowlisted and is a public content host. A prompt-injected page
   tells the driver to fill `hsurr:openai` into a gist, issue, or
   comment form on github.com; the proxy swaps; the OpenAI key is now
   public. §6's "no exfiltration channel beyond what the page itself
   shows" is wrong. Fix: put the host binding in the existing registry
   as an `allowed_hosts` list per credential, the same shape
   `dynamic_credentials.ensure_allowed_url` already takes, expose it
   as `cred register <name> --host <h>`, and have `_resolve(name,
   entry, host)` refuse when the host is not in that list.
   `hosts.allow` can stay as the outer gate. About twenty lines in the
   addon plus one flag in `cred`. Do it in v1; it also makes the v2
   first-use confirmation far less load-bearing.

2. **The trust table claims things the box does not enforce.** §2 says
   the orchestrator "cannot see credential values" or "bypass the
   proxy", and that "a compromised orchestrator session cannot rewrite
   the driver or read its profile". The orchestrator logs in as
   `ntindle`, which has passwordless sudo (SETUP.md line 5). Every
   "cannot" in that row is policy; `cred get` is one command away, and
   `sudoers-swapd` is dead configuration while a blanket sudo rule
   exists. SETUP.md's "Honest limits" paragraph admits this; SPEC.md §2
   and the §10 table do not. Fix, pick one: (a) give the agent its own
   login (e.g. `muse`) with no general sudo and only narrow rules, and
   keep `ntindle` for the human; or (b) rewrite §2 and §10 to mark the
   orchestrator rows "policy, not enforced" and drop "stronger". Option
   (a) is the one that makes the spec true.

3. **Ask-back confirmations route through the party being contained.**
   `need_info` (§7) and the planned `confirm_first_use` (§10, gap 1)
   pause the driver and resume on the orchestrator's next action.
   Nothing checks that the user actually answered. In the
   compromised-orchestrator scenario the spec worries about, the
   orchestrator answers itself. The destructive gate in §6 is the same:
   "enforced on the orchestrator" means not enforced. For a
   confirmation to count, the user must signal the driver or swapd
   directly: a file under a swapd-owned directory that only the human's
   SSH session can create, or a tailnet-authenticated page. Until then
   the §10 verdicts for "Fresh approval" and "Destructive actions
   gated" should be ⚠️, not ✅.

## Should fix: correctness of the swap

4. **No response-side scrubbing.** §5 claims the DOM, memory,
   screenshots and logs contain only placeholders. That holds only if
   no allowlisted host ever echoes a value back: a "review your
   details" page, an API that returns the key, GitHub's own token
   pages. `text`, `shot`, and the automatic screenshot after every
   mutating action then hand the real value to the orchestrator. Fix:
   in a `response` hook, for allowlisted hosts, replace each known
   secret value in text bodies with its placeholder. Cheap. State the
   residual (images, binary bodies).

5. **JSON bodies get the raw value with no escaping.** CONFIRMED
   (probe C). A password containing `"` or `\` produces invalid JSON
   and the login fails in a way that looks like a site bug. Fix: on
   `application/json`, replace with `json.dumps(v)[1:-1]`.

6. **Form bodies with a literal colon get the raw value.** CONFIRMED
   (probe D). Browsers send `%3A` and that path re-encodes correctly
   (probe E). curl, requests, and anything under `with-proxy` that
   posts a form sends the literal colon; `_swap_text` runs first and
   inserts the raw value, so `&` or `=` in a value splits it into extra
   fields. Fix: for `x-www-form-urlencoded`, `parse_qsl`, swap values,
   `urlencode`; drop the regex path.

7. **Entry suffix is swallowed for single-value secrets.** CONFIRMED
   (probe A). `hsurr:github:8080` becomes `<token>` with `:8080` eaten,
   because `_resolve` ignores `entry` when the secret is not
   multi-entry. Fix: for single-value secrets, match only when there is
   no entry or the entry is `access_token`.

8. **Referer and every other header are swapped.** CONFIRMED (probe G).
   §4 allows placeholders in `goto` URLs. The browser then sends that
   URL as `Referer` on later requests to the same host, the proxy swaps
   the real token into it, and the server logs it. Placeholders in URLs
   are legitimate (`query_param` and `url_path_segment` are schema
   placements), so the fix is on the header side only: never swap in
   `Referer` and `Origin`, and in `Cookie` only when a placement says
   so.

9. **Path re-quoting corrupts percent signs.** CONFIRMED (probe F).
   `quote(..., safe="/%:@")` after `unquote` turns an encoded `%25`
   into a bare `%` and an encoded `%2F` into a real `/`. Only fires
   when a swap happened in the path or query. Fix: swap per path
   segment with `safe=""`, and leave the path alone when no segment
   changed.

## Enforcement gaps the spec asserts but nothing implements

10. **"All browser traffic forced through the swap proxy" (§3) is a
    Chromium flag, not a network rule.** `bdrive` can reach the
    internet directly. Add an nftables rule so `meta skuid bdrive` may
    only connect to `127.0.0.1:18080`. The health-check gate then
    becomes belt and braces instead of the only belt.

11. **The narrow sudoers globs escape the directory.** `cat
    /home/swapd/secrets/*` and `rm /home/swapd/secrets/*` also match
    `../swap.log` and `../.mitmproxy/mitmproxy-ca.pem`, because sudo's
    `*` matches `/`. Moot today because of item 2, but the moment
    option 2(a) lands these become the only path, and they let the
    agent delete the audit log and read the CA key. Fix: replace the
    `cat`, `ls`, `rm` entries with name-validated helper scripts in the
    style of `cred-store-set`.

12. **The audit log is a record, not a control.** It lives on the box
    within the agent's reach (items 2 and 11). Ship it off-box, or
    write it somewhere the agent cannot truncate, or say plainly in §6
    that it is a debugging aid.

13. **The mitm CA is in the system trust store.** `with-proxy` points
    every CA variable at `/etc/ssl/certs/ca-certificates.crt`, so every
    process on the box trusts swapd's CA, and the CA private key is a
    box-wide MITM key. Document it as a secret, keep it under swapd
    only, and consider a separate bundle for `with-proxy` instead of
    the system store.

## Spec completeness

14. **Sessions versus one persistent profile.** §3 has multiple
    sessions; §8 has one profile directory. Playwright's persistent
    context locks the profile, so a second concurrent launch fails.
    Decide: one browser process where sessions are pages in the single
    persistent context (shared cookies), or one session at a time.

15. **Orchestrator to driver IPC is unspecified.** §3 says `bdrive
    <session> <action-json>` runs over SSH as `ntindle` while the
    service runs as `bdrive`. What sits between them (unix socket,
    group permissions, sudo)? That is the actual trust boundary and it
    belongs in the spec.

16. **`credential_fill` contradiction.** §5 says there is intentionally
    no equivalent. SETUP.md maps `credential_fill` to
    `credlib/fill_secret.py`, which loads real values into `ntindle`'s
    process. The mirror should stay, since code written against the
    cell's `credential_fill` is meant to port unchanged. Fix the spec
    text instead: say `fill_secret` is the schema-compatible path for
    human-run scripts, is the weaker path on this box, and is not used
    by the driver (it cannot be, as `bdrive` has no sudo).

17. **Action set gaps.** Iframes (SSO and payment forms live in them,
    and CSS selectors do not cross frame boundaries), per-action
    timeouts, a screenshot size cap, and whether the `download`
    directory is readable by the orchestrator's user.

18. **Destructive gating needs a concrete definition** even as a
    heuristic: which button text or ARIA names trigger it, and what
    the driver does (see item 3 for what "confirm" must mean).

## Repo and process

19. **Rebuild instructions for the proxy are missing.** README says a
    lost box is rebuilt from this repo. Not in the repo: creation of
    the `swapd` and `bdrive` users, the mitmproxy venv, CA generation
    and trust-store install, the auditd rules behind `-k
    swapd-secrets`, and where `with-proxy`, `cred-store-set`,
    `cred-registry-set` and the sudoers file are installed. One
    `proxy/install.sh` or a SETUP.md section.

20. **`.gitignore` is still absent and `push.sh` runs `git add -A`.**
    The scanner catches PEM keys and known token shapes, not a journal
    of arbitrary passwords or a copied profile directory. Ignore
    `*.log`, `profile/`, `sessions/`, `*.pem`.

21. **`dumper_filter=~d nomatch.invalid` works, but `--set
    flow_detail=0` is the knob meant for this.** Also verify that
    mitmproxy's error-level lines on connection failures do not print
    URLs; with `query_param` placements those URLs carry the real
    value.

22. **The §10 "cosmetic" item is not cosmetic.** The warning for a
    placeholder sent to a non-allowlisted host is the only signal that
    a placeholder went somewhere it should not, and the only evidence
    that the §5 "safe default" is exercised. Fix before relying on it.

25. **Single-value secrets that look like `k=v` are misread as
    multi-entry.** CONFIRMED. `_load_secret_file` sniffs: if every
    non-blank line matches `name=value`, the file becomes a dict. A
    one-line secret whose value is `key=abc` (some DSNs and API keys
    look like this) loads as `{"key": "abc"}`, so `hsurr:<name>`
    resolves `access_token`, finds nothing, and passes through
    untouched. Fix: decide multi-entry from the registry's entry list
    or an explicit marker, not by sniffing the content.

## What holds up

- Separate `swapd` user owning the store, narrow atomic setter
  scripts, mtime-based reload without restart.
- `cred run` no longer exports secrets into child environments. That
  was the worst property of the previous version.
- Placeholder inside Basic auth for `git push`: the PAT is no longer on
  git's command line.
- The cookie-in-profile blast radius is stated in §2 rather than
  hidden.
- Pass-through untouched for non-allowlisted hosts is the right
  default.
- The browser-encoded form path (probe E) re-encodes correctly.

## Suggested order

Items 1, 2, and 5 to 9 are small proxy and config changes; land them
together with a conformance test per probe below. Items 3 and 4 are
design decisions to make before writing `bdrive`, because the driver's
`need_info` and `shot` semantics depend on them. Items 10 to 13 are box
hardening. The rest is spec text.

## Probe used for the CONFIRMED items

```python
import sys, json, urllib.parse
sys.path.insert(0, "proxy")
import swap_addon as sa

a = sa.SwapAddon.__new__(sa.SwapAddon)
a.secrets = {"github": "ghp_TOKEN", "openai": "sk-OPENAI", "pw": 'p&ss=w"o\\rd%7d'}
a.hosts = ["github.com", "api.github.com"]
a._audit = lambda host, m: None

print("A", a._swap_text("token=hsurr:github:8080", "github.com"))
print("B", a._swap_text("body=hsurr:openai", "github.com"))
out = a._swap_text('{"password":"hsurr:pw"}', "github.com")
try: json.loads(out); print("C valid", out)
except Exception as e: print("C BROKEN", out, e)
body = "user=x&password=hsurr:pw"
out = a._swap_urlencoded(a._swap_text(body, "github.com"), "github.com")
print("D", urllib.parse.parse_qs(out))
body = "user=x&password=hsurr%3Apw"
out = a._swap_urlencoded(a._swap_text(body, "github.com"), "github.com")
print("E", urllib.parse.parse_qs(out))
p = urllib.parse.unquote("/v1/100%25/hsurr:github/x")
print("F", urllib.parse.quote(a._swap_text(p, "github.com"), safe="/%:@"))
print("G", a._swap_text("https://github.com/cb?token=hsurr:github", "github.com"))
```

Output at `a006f6e`:

```
A token=ghp_TOKEN
B body=sk-OPENAI
C BROKEN {"password":"p&ss=w"o\rd%7d"} Expecting ',' delimiter
D {'user': ['x'], 'password': ['p'], 'ss': ['w"o\\rd}']}
E {'user': ['x'], 'password': ['p&ss=w"o\\rd%7d']}
F /v1/100%/ghp_TOKEN/x
G https://github.com/cb?token=ghp_TOKEN
```

## Addendum: commit `7934e0e` (website login recipe in SETUP.md)

23. **A TOTP placeholder swaps in the seed, not a code.** CONFIRMED by
    reading. The recipe stores `totp=JBSWY3DPEHPK3PXP`, the base32
    seed, and fills `hsurr:acme:totp`. The addon's `_resolve` returns
    the stored entry verbatim, and nothing in the repo imports `hmac`
    or computes HOTP or TOTP. The site receives the seed string in the
    code field and the login fails. Spec §5 makes the same claim. Fix:
    in the addon, treat an entry named `totp` (or a `totp` placement)
    as a seed and swap in the current six-digit code, computed with
    stdlib `hmac`, `hashlib`, `struct` and `time` (RFC 6238, 30-second
    step, SHA-1). If the cell's schema already defines a `totp` entry,
    match its semantics exactly; if it does not, §5 should name this
    as a spark-vm extension. Item 4's response scrubbing should cover
    the seed too.

24. **The recipe never routes the browser through the proxy.** Step 3
    is a plain Playwright script. For the swap to happen, Chromium
    must be launched with `proxy={"server": "http://127.0.0.1:18080"}`
    and must trust swapd's CA. Chromium uses its own NSS store under
    `~/.pki/nssdb`, not `/etc/ssl/certs`, so the `with-proxy`
    environment variables do nothing for it. Whatever was done to
    verify the login flow live is not in the recipe. Add the launch
    arguments and the CA step; without them the recipe fails silently
    and the placeholders go straight to the site.

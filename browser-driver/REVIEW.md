# Review of browser-driver/SPEC.md v1

Reviewed at commit `a006f6e`. Later sections cover `7934e0e` (login recipe), Spec v2 (`9cc21c0`, `6f6600a`), the proxy fix `53a8a9a`, and a comparison against the reference architecture described in the Muse safety post. Scope: `SPEC.md`, `proxy/swap_addon.py`,
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

**Before anything else:** the repo has two spec files. `SPEC.md` at the
root is the revised v2; `browser-driver/SPEC.md` is the unrevised v2.
Move the revised one over the old path so there is one spec. See the
status section at the end for what v2 did and did not resolve.

**Runnable target.** `python3 -m unittest proxy/test_swap_addon.py`
from the repo root. No mitmproxy needed. At `53a8a9a` all 15 pass.
Keep it that way: every new proxy finding gets a test before its fix.

**Order (updated at `b2fb668`).** The grant channel is not done: 55,
56 and 57 first, with tests (62), then 58 to 61. Until 55 and 56 land,
the owner should hold grant consumption on the box (see round 6). Box
hardening still open: 10, 11. Docs: 19, 20, 21.

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

## Status after Spec v2 (`9cc21c0`, `6f6600a`)

**Wrong path.** `6f6600a` wrote the revised spec to `/SPEC.md` at the
repo root and left `browser-driver/SPEC.md` at the unrevised v2. Every
reference in this review and in the build plan points at
`browser-driver/SPEC.md`. Move the revised file over it and delete the
root copy.

**Addressed in spec text, not yet in code.** Items 1, 2, 3, 4, 5 to 9,
10, 12, 14, 15, 16, 17, 18 and 23 now appear in the spec as
requirements or withdrawn claims, and the login recipe fixes 24. The
addon is unchanged: `python3 -m unittest proxy/test_swap_addon.py`
still reports 6 failures and 1 skip. The spec's build plan item 0
lists the right code work; none of it has started.

**Not addressed anywhere yet.** Item 11 (sudoers globs escape the
directory), 13 (mitm CA in the system trust store), and 25 (`k=v`
sniffing). Items 19 to 22 are listed in the build plan and not done.

**Consistency nits in v2.** §6 still opens with "no component on
spark-vm ever holds a real value" one paragraph before conceding swapd
does, and still states unconditionally that the DOM, screenshots and
logs contain only placeholders while listing response scrubbing as
pending. Build plan item 0 says 24 findings; this file now has 66.

### New findings from v2's on-box agent

26. **Page content reaches the LLM through the swap proxy, so any
    page that contains a placeholder string can exfiltrate the real
    value.** Blocking. v2 adds `obox`, which sends prompts containing
    page text to an LLM provider, authenticated with `hsurr:llm-api`
    through the proxy. That makes the provider's host allowlisted. A
    page the agent visits only has to contain the literal text
    `hsurr:github` (an attacker page, or any page that echoes what the
    agent typed) for that string to land in a prompt body, where the
    proxy swaps in the real GitHub token before sending it to the
    provider. The token is then in the provider's logs and may be
    echoed back into the agent's context and its report. Item 1
    (per-credential host binding) closes the swap-in half, which makes
    it more urgent than before. Two more controls are needed in
    `obox`: neutralise `hsurr:` strings in page content before they go
    into a prompt (replace with a marker that the regex cannot match),
    and apply item 4's response scrubbing to the provider's responses.
    State in §2 that the LLM host is allowlisted for exactly one
    credential.

27. **Transient credentials break the placeholder invariant.** §7 has
    the orchestrator relay single-use virtual card details to the
    agent, which types them with ordinary `fill`. §9 does the same for
    SMS and email codes. Those are real values: they exist in the
    steer message, in the agent's context, in every LLM prompt that
    includes the steer message, in the DOM, and in the action
    screenshot. That contradicts §1 ("never handle a real credential
    value anywhere in the stack") and the §2 row saying the LLM
    provider never receives real values. A one-time code is spent
    after use, so it is a tolerable and stated exception. Card details
    are not. Fix: give transient credentials the same path as stored
    ones. The orchestrator gets a narrow, job-scoped install
    (`cred set-transient <job> card` with an expiry and a host binding
    to the merchant), the agent fills `hsurr:card-<job>:number` and
    friends, and swapd deletes the entry when the job ends. Then the
    §15 verdict "values hidden from the agent/driver" holds for
    transient values too; today it holds only for stored ones.

## Status after the proxy fix (`53a8a9a`)

Verified by reading the diff and running the suite: 15 of 15 pass. The
fix does what it says for items 1, 5, 6, 7, 8, 9 and 23, fails closed
when a credential has no host binding, keeps `hosts.allow` as the
outer gate, computes TOTP correctly (RFC 6238, SHA-1, 30 s, six
digits), never touches Referer or Origin, and swaps Cookie only for a
credential whose placement names the Cookie header. The tests Muse
added are stricter than mine, not looser. `ENVIRONMENT.md` is a useful
addition and is accurate about who can do what.

Still open in code: 4, 22 (more important now, since a refused swap is
only a warning), 25. Still open on the box: 2, 10, 11, 12, 13. Still
open in docs: 19, 20, 21, the one-file spec.

34. **Nits in `53a8a9a`.** (a) When one path segment changes, every
    other segment is re-quoted with `safe=""`, so a `:`, `@` or `~` in
    an unchanged segment becomes a percent-escape; keep the original
    bytes for segments whose decoded form did not change. (b)
    `allowed_hosts` is now a reserved key inside each credential's
    registry object, next to entry names; `cred-registry-set set`
    should reject it as an entry name or the list gets clobbered. (c)
    `README.md` and `ENVIRONMENT.md` still describe the pre-proxy
    `cred` with a `~/.config/spark-credentials` file backend and a
    planned Bitwarden backend; both are stale. (d) `ENVIRONMENT.md`
    shows a `:placement` suffix on the placeholder that the addon does
    not parse.

## Against the reference architecture

The Muse safety post and architecture diagram describe the system the
spec ports: the runtime cell, `hatch-authd`, Sentinel, `privsep`, the
browser broker, and the client-side approval and credential-capture
UIs. Checking the spec's comparison table against that source rather
than the inferred contract changes several verdicts.

| Reference control | spark-vm today | Status |
|---|---|---|
| Two isolated security domains on one box; cell root is not host root; no host secrets, no Sentinel state in the cell | Agent login is `ntindle` with passwordless sudo | Item 2. The box is the thing the post says it is not: "an LLM powered agent with root" |
| Sentinel authorizes every concrete request at L4 and L7 (host, resolved IP, port, method, path, decoded body) before inserting the credential | Host allowlist, now per credential | Item 28 |
| Grants are scoped capabilities: one-time, session, task, time-bounded, perpetual; later calls must match the scope exactly | Allowlist entry = perpetual grant | Item 28 |
| Approvals go directly to the client UI, "not via their conversation with Muse", and the answer routes directly back to Sentinel | `need_info` relayed through the orchestrator | Item 3, now a regression from the reference rather than a difference |
| SSRF validation on resolved and final IPs | None | Item 29 |
| Inference proxy is a separate constrained path; credential insertion is on the Sentinel path only | obox's LLM calls go through the swap proxy | Item 31, root cause of 26 |
| `hatch-safety` classifier ensemble outside the cell; harness labels external content untrusted; browser classifiers for DOM, image and file injection and high-risk forms | Model instructions only | Item 30 |
| Browser sub-agent sees the AX tree, not the DOM, so it cannot read filled credentials; paused during fill and takeover | AX tree plus `get_html`, `get_value`, `get_attr` | Item 32 |
| Surrogates minted by authd, opaque `[credential:<uuid>]` | Static, documented `hsurr:<name>` | Item 30 and 31 carry more weight here; see note below |
| Unix sockets with SO_PEERCRED and peer ACLs | Socket group permissions | Item 33 |
| Credential capture UI on the client routes straight to authd | `cred set` from the human's SSH session | Aligned |
| Value injected into the browser window by the store while the agent is paused | Placeholder typed, swapped at egress | Aligned; see the corrected table row below |
| Wallet issues single-use cards bound to merchant, amount and time | Orchestrator's wallet flow, relayed as a raw value | Item 27, severity lowered for cards |
| Email connector strips OTPs, reset links and magic links | No inbox on spark-vm | Not applicable until a mail connector exists; then required |
| Watch and take over live | noVNC planned for v2 | Already ⚠️ in the spec |
| Malicious-site blocklist inside the VM | None | Optional; a public domain blocklist is cheap |

**Corrected comparison row.** The spec's §15 says the managed agent
delivers real values to the browser agent ("Managed: No") and scores
spark-vm "stronger". The post says otherwise: the store injects the
value into the browser window while the sub-agent is paused, and the
sub-agent sees only the AX tree, so it cannot read the value before,
during or after. Both designs hide the value from the agent. spark-vm
additionally keeps it out of the browser process, and pays for that
with the entire encoding and protocol surface (items 5 to 9, plus
WebSocket, multipart and HTTP/2 coverage). The row should read
"aligned; marginal gain; large correctness surface".

**Surrogate note.** The reference's surrogates are minted by authd and
opaque, so an attacker page cannot contain a valid one. spark-vm's
placeholders are static and documented, so any page can contain a
valid one. That is why items 26, 30 and 31 matter more here than in
the reference. The schema fixes the format, but a per-job alias
(`cred register <alias> --alias-of <name> --host …`, revoked at job
end) would give unguessable placeholders inside the same format. Ask
whether the cell's surrogates are per-session before deciding.

**Adjusted findings.** Item 2: use the post's own framing; the goal is
two security domains, and today there is one. Item 3: the reference
treats direct-to-client approval as a core property, so the spec's
"⚠️ different mechanism, same intent" understates it; the spark-vm
analog is a pending approval that swapd or bdrive posts to a channel
only the human can answer. Item 26: the cross-credential half is
closed by `53a8a9a`; the rest is 30 and 31. Item 27: the reference's
card is single-use and bound to merchant, amount and time, so a leaked
card is of little use; keep the placeholder path as should-fix, and
treat the one-time code relay as a stated exception, which matches the
reference's own raw-code path.

28. **No L7 policy and no grant scoping on the swap.** The reference
    authorizes each concrete request (method, path, decoded body)
    before inserting the credential, and every approval is a scoped
    grant. spark-vm's allowlist entry is a perpetual, host-wide grant:
    a bound GitHub token can be used for any request to
    `api.github.com`, including deleting repositories. Fix: the
    registry gains optional `allowed_methods` and `allowed_paths`
    (prefix) per credential, checked in `_resolve` before swapping.
    When item 3's channel exists, first-use confirmation becomes a
    session-scoped grant that swapd records itself.

29. **No SSRF or private-range guard at egress.** Through the proxy,
    the browser and obox can reach tailnet peers (`100.64.0.0/10`),
    RFC 1918 ranges, loopback and link-local. The reference validates
    the resolved and final destination IP. Fix: the proxy resolves the
    host and refuses those ranges unless the host is explicitly
    allowlisted for them; redirects are separate requests and get the
    same check.

30. **No independent prompt-injection layer and no untrusted-content
    labeling.** The reference stacks model training, harness labeling
    of every external block, a classifier ensemble outside the cell,
    and browser classifiers for DOM, image and file injection and for
    high-risk forms. Spec v2 §11 relies on instructions to the model.
    Fix for v1: obox wraps every page or tool block in an explicit
    untrusted-data envelope and neutralizes `hsurr:` strings inside it
    (item 26). v2: a classifier pass over page text and downloaded
    files, run outside obox.

31. **Inference transport shares the credential-swapping path.** The
    reference keeps the inference proxy separate from Sentinel, so
    page content in prompts never traverses credential insertion.
    Spec v2 routes obox's LLM calls through swapd to inject the API
    key, which puts the provider host in `hosts.allow` and sends every
    prompt body through the swap. Item 1 now stops other credentials
    from swapping there; `hsurr:llm-api` still swaps anywhere in the
    body. Fix: a second mitmdump instance as the inference proxy, with
    its own secrets directory holding only `llm-api`, header-only
    placement, and the provider as its only host. obox uses it; the
    main proxy never allowlists the provider.

32. **`get_html`, `get_value` and `get_attr` deviate from AX-only
    observation.** The reference's sub-agent cannot read the DOM, and
    the post names that as the reason it cannot read filled
    credentials. With placeholders in the DOM the reads are mostly
    harmless. With a relayed one-time code or card number typed raw
    (item 27) they are a read-back path. Fix: refuse these reads on
    password-type inputs and on any field filled with a relayed value
    in the current job, or resolve item 27 so nothing real is in the
    DOM.

33. **IPC should verify the peer, not just the socket mode.** The
    reference uses SO_PEERCRED and peer ACLs. Spec v2 relies on a
    group-owned socket. Add a SO_PEERCRED uid check in the bdrive and
    obox daemons that accepts only the obox uid and the orchestrator
    login. Small, and it removes the dependence on group membership
    being right forever.

## Owner decisions (2026-09-15)

Recorded from the owner's answers to the seven decisions the reviewer
put to them. Muse: treat these as settled unless marked pending.

1. **The browser brain runs on spark-vm.** `obox` stays. Consequence:
   items 26, 30 and 31 are required v1 work, not options. Build the
   separate inference proxy (31) before obox makes its first model
   call: its own mitmdump instance, its own secrets directory holding
   only `llm-api`, header-only placement, the provider as its only
   host, and the provider never in the main proxy's `hosts.allow`.
   Wrap every page or tool block in an untrusted-data envelope and
   neutralize `hsurr:` strings inside it (30, 26). Keep 32's read
   restrictions.

2. **The agent login becomes a jail, not just a user.** Direction:
   mirror the cell on spark-vm. Muse's SSH login lands in a
   systemd-nspawn container: rootful inside (guest root is not host
   root), its own rootfs, package installs free inside, a veth whose
   only egress is the swap proxy on the host, and no host secrets,
   swapd state, bdrive state or audit log inside. swapd, bdrive, the
   audit log and the confirmation page live on the host. Two asks for
   Muse before design: describe how your own cell treats package
   installs and egress approvals (the allowlist and approval model),
   the same interview method used for Spec v2, so the jail can mirror
   it; and account for Docker, which is a host escape if the jail can
   reach the host socket (rootless Docker or podman inside the
   container, or none). This resolves item 2 by option (a) in its
   stronger form. Until it lands, ENVIRONMENT.md's rule stands: the
   implementer can become root.

3. **Confirmation channel: a tailnet page.** swapd or bdrive serves a
   small page reachable only over the tailnet, authenticated by
   Tailscale identity, where pending approvals and first-use
   confirmations are answered. Nothing routes through obox or the
   orchestrator. Item 3 is decided; the page is part of bdrive v1.

4. **Grant scoping (item 28): Muse proposes.** The owner wants a
   written proposal for per-credential method and path limits and for
   grant lifetimes, submitted for review before any implementation.
   Put it in the spec as a proposal section with the registry schema
   it would need.

5. **Audit log placement (item 12): decided, leave it on the box.**
   No forwarding, no append-only flag. It is a verification aid, and
   the long-term direction the spec already names in §17, moving the
   whole swapd side off the box, makes it a control later without any
   interim work.

   **CA trust (item 13): decided, system-wide inside the jail.** The
   swapd CA goes into the jail's own rootfs trust store, because
   everything in the jail is meant to go through the proxy. When the
   jail lands, remove the CA from the host's store; nothing on the
   host needs it (swapd, sshd, tailscaled and host apt must never go
   through the proxy, and Chromium reads its NSS database, not the
   system store, so the `certutil` step in the login recipe stays).
   Until the jail exists, leave the host as it is. `with-proxy` keeps
   setting `NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE`
   regardless: Node, Python `requests` and Java ignore the system
   store.

6. **Transient credentials (item 27): accept the one-time-code
   exception; build the card pathway.** Cards get a job-scoped,
   expiring, merchant-bound placeholder entry installed through a
   narrow helper, filled as `hsurr:card-<job>:number` and friends,
   and deleted at job end. Design the helper as part of §7. The
   one-time-code relay stays as a stated exception.

7. **Private-range guard (item 29): approved, default-deny.** Implement
   the guard with an explicit allow list. The tailnet is on that list
   for now; the default for a fresh install is deny.

## Round 2 verification (`f8d825c`, `d22ceab`)

Muse's handoff message said the round-2 proxy work was implemented and
deployed on the box but not pushed. It is pushed: `f8d825c` carries the
addon, tests, service unit, helpers and allow files. The suite passes,
22 of 22, and the tests Muse added are hermetic and strict. Findings
4, 22, 25, 29, 31 and the 34 nits are addressed as described. The
verification below found one regression, two guard bypasses, one
deployment gap, and one correctness hazard, all reproduced against the
addon.

**Recommendation to the owner: fix forward, no rollback.** Item 35
does not affect the GitHub credential as it is bound on the box today,
36 only bites on short secrets, and 37 and 38 weaken a guard that did
not exist before rather than anything that was protected. Until 35 is
fixed, nobody should run `cred register` on a single-value credential.

35. **Regression: `cred register` on a single-value secret makes it
    never swap.** CONFIRMED. `_load_secret_file` treats a file as
    multi-entry whenever the registry declares any entry, and `cred
    register <name> --host <h>` always writes the default
    `access_token` entry before adding the host. A bare-token file then
    parses to an empty dict, and every swap of that credential returns
    nothing. It works on the box today only because the GitHub binding
    was added with `add-host` directly, skipping `set`; anyone
    following the CLI's own usage line breaks their credential
    silently. Fix: make the `#hsurr:multi` marker the sole source of
    file layout. Registry entries describe placements, not file
    format. Test: a bare file plus a registry with `access_token` must
    load as the single value and swap.

36. **Response scrubbing has no minimum length and scrubs non-secret
    entries.** CONFIRMED. A one-character password turns "Next" into
    "Nehsurr:acme:passwordt" on every page from that host, and a
    `username` entry rewrites "Welcome jdoe". Fix: skip values under
    eight characters and warn at load that such a secret cannot be
    scrubbed; let the registry mark an entry `scrub: false` for
    usernames and emails; match TOTP codes only as whole tokens, since
    a six-digit code collides with prices and IDs.

37. **The private-range guard misses `0.0.0.0/8` and IPv4-mapped
    IPv6.** CONFIRMED. `0.0.0.0` and `::ffff:127.0.0.1` both pass, and
    both reach localhost on Linux. Fix: unwrap `addr.ipv4_mapped`
    before checking, and add `0.0.0.0/8`, `192.0.0.0/24`,
    `198.18.0.0/15` and `240.0.0.0/4`. Test each literal.

38. **The guard runs after the upstream TCP connect.** By reading.
    mitmproxy's default connection strategy is eager: it connects to
    the upstream host when the client connects, to read the server
    certificate, so by the time the `request` hook refuses, a TCP
    connection to the private address has already been made. That is
    enough to port-scan the tailnet. The right hook is
    `server_connect`, which runs before the connect. It also gives the
    DNS-pinning fix Muse listed as later work: resolve there, refuse by
    setting the connection's error, or set the server address to the
    resolved IP so the check and the connect use the same answer.
    Verify the hook's signature against the mitmproxy version in the
    venv.

39. **The inference proxy has no narrow path to populate its
    registry.** By reading. `_resolve` fails closed without an
    `allowed_hosts` binding, the inference instance reads
    `inference-registry.json`, and `cred-registry-set` writes only
    `credentials.json` unless `CRED_REGISTRY_FILE` is set, which sudo's
    `env_reset` strips. There is a store setter and a hosts appender
    for inference, but no registry writer. Either the file was
    hand-edited on the box or the inference proxy cannot swap. Fix: a
    fixed-path `cred-registry-set-inference`, or an `--inference` flag
    handled inside the root-owned script, plus a sudoers line, plus a
    test that the instance swaps after the documented install steps.

40. **Nits.** (a) A placeholder seen for a non-allowlisted host is a
    journal warning only, not a `refused=` audit line; parse the name
    with the placeholder regex and audit it. (b) Multi-entry parsing
    silently drops lines that do not match `k=v`; warn. (c) The
    scrub size cap is checked after decoding the whole body; check
    `len(resp.content)` first. (d) The response hook buffers whole
    bodies, so obox must not depend on streamed provider responses.

### Grant-scoping proposal (spec §6): owner review

**Approve now:** `allowed_methods` and `allowed_paths` as static
registry fields, checked in `_resolve` before swapping, absent means
unrestricted for migration. Requirements: compare paths after
percent-decoding and dot-segment normalization so `/repos/../admin`
cannot pass a `/repos/` prefix; make prefixes segment-aligned so
`/repos/` matches `/repos/x` and not `/repository`; uppercase methods.
The owner should bind methods for every write-capable token at install
time even though the field is optional.

**Defer:** `grants` with `session` and `task` scopes. The proxy cannot
attribute a request to a bdrive session or an obox job: sessions are
tabs in one shared browser context (spec §3), and the proxy sees one
Chromium connection pool. Without attribution, a session-scoped grant
is a time-bounded grant with a misleading name. For v1 keep `one-time`
and `time-bounded` only, with bdrive, which is trusted and on the host,
telling swapd when a job ends so swapd revokes. `one-time` must mean
one request flow, not one regex match, and needs a short grace window
because browsers retry and follow redirects.

**Open questions answered.** The card pathway stays as job-scoped
placeholder entries, not one-time grants, because checkout forms
re-submit and a one-time grant fails on the retry. Grants go to the
same audit log as `grant=` lines; no second log. A grant's default
expiry is job end via bdrive's revoke, with a hard cap of 24 hours for
anything left unrevoked. One gap in the proposal: the `cred-grant`
writer is "callable only from the confirmation page's backend", but
the page is served by bdrive and bdrive is not swapd; specify the
socket and the peer check between them.

### Jail document (`jail/cell-mirror.md`)

Accurate about what is observed and what is inferred, and the mirror
it proposes is the right one. Three things to add before building:

- **How the SSH login lands in the jail.** Either sshd inside the jail
  bound to the veth address with the host forwarding the tailnet port,
  or the host's sshd with a per-user forced command into the container.
  The choice decides where the host keys and the ControlMaster socket
  live.
- **The jail is persistent, not disposable.** The cell is replaced
  without warning; this box is a workhorse. Keep "rebuildable from the
  repo" as the property and drop the assumption that installs vanish.
- **Container runtime inside nspawn.** Rootless Docker needs nested
  user namespaces and subuid ranges inside the container; podman is
  more likely to work. Budget time for it, and say in the document that
  anything in the jail that dials IPs directly or needs UDP, including
  ping and git over SSH, will not work by design. Git goes over HTTPS
  through `with-proxy`, as `push.sh` already does.

## Round 3 verification (`6af2738`, `da26910`)

Verified by reading the diff and running the suite: 34 of 34 pass.
Findings 35 to 40 and the approved half of grant scoping are done as
described. What holds up: `server_connect` is the right hook, and the
live GitHub push returning 200 after deploy is evidence that pinning
the resolved IP survives upstream TLS verification; the IPv4-mapped
unwrap plus `is_unspecified` cover both localhost spellings; the
marker-only file layout has a regression test for the exact
`cred register` case; the scrub floor and whole-token TOTP match are
right; the inference install test drives the real helper scripts; path
normalization is correct for every shape the proxy itself can judge.
Round 3 was deployed before review, as round 2 was. Fix-forward has
worked so far, and whether to keep it that way is the owner's call.

41. **Empty method and path lists mean unrestricted.** CONFIRMED.
    `remove-method` of the last method leaves `[]`, and the addon
    treats an empty list as absent. An owner who removes POST intending
    to add PUT next leaves the token unrestricted in between, with the
    helper printing "unlimited". Fix: an explicit empty list fails
    closed; the helper deletes the key when the list empties and prints
    "now unrestricted" so the state is visible. Test both.

42. **Path prefixes are bypassable on servers with lenient path
    parsing.** CONFIRMED for three shapes. Double encoding:
    `/repos/%252e%252e/admin` normalizes to `/repos/%2e%2e/admin` and
    passes, and a server that decodes twice sees `/admin`. Path
    parameters: `/repos/..;/admin` passes, and Tomcat-family servers
    collapse it to `/admin`. Backslashes: `/repos/..\admin` passes,
    and IIS-style servers treat it as `/admin`. Fix: for a path-bound
    credential, unquote to a fixpoint before normalizing, then refuse
    any path that still contains `%`, `;` or `\`. Describe the control
    as defense in depth in the spec, because the server's parser has
    the last word. Test each shape.

43. **`set-scrub` cannot opt out a single-value secret.** CONFIRMED.
    The scrub check looks up entry `None` for single-value secrets, so
    `set-scrub user access_token false` has no effect on a username
    stored as its own credential. Fix: consult the `access_token` entry
    spec for single-value secrets. Test.

44. **`grants` is not a reserved key.** CONFIRMED. `RESERVED_KEYS` has
    only the three static keys, so a future `grants` list is treated
    as an entry name: `hsurr:api:grants` resolves to the token today,
    and the deferred grant machinery will collide when it lands. Add
    `grants` now, in the addon and in `cred-registry-set`.

45. **Blocking DNS inside the event loop.** By reading. `_resolve_ips`
    calls `socket.getaddrinfo` synchronously from `server_connect`,
    which runs on mitmproxy's asyncio loop. A slow resolver stalls
    every connection through both proxies for the duration. mitmproxy
    accepts coroutine hooks: make `server_connect` async and await the
    loop's `getaddrinfo`.

46. **The inference recipe in SETUP.md has two errors, one a
    separation violation.** By reading. Step 3 tells the owner to
    append the provider "if needed" to `/home/swapd/hosts.allow`, the
    main proxy's file, which the spec and the service unit both forbid;
    it belongs in `inference-hosts.allow` only. Step 1 runs
    `cred-store-set-inference` without `sudo -u swapd` and calls it a
    prompt, but the script reads raw stdin: run as written it fails on
    permissions and echoes the key to the terminal. Fix: `sudo -u
    swapd`, piped input or a no-echo prompt behind a `cred` subcommand,
    and the correct hosts file. Nobody should follow the recipe until
    this lands.

**Nits.** (a) The short-value load warning fires for entries marked
`scrub: false` too; skip those. (b) The merge from the box clone
(`459fcb3`) re-imported a dozen commits under new hashes.
ENVIRONMENT.md says GitHub main is authoritative, so the box clone
should only ever pull, never be merged from.

## Round 5: round-4 fixes, the jail, and the confirmation page (`3d4547e` to `ef0f30e`)

Round 4 verified: 41 to 46 are done as described, the suite passes,
and the tests for 41, 42 and 45 exercise the real behavior. The jail
build script is careful where it matters: an explicit user-namespace
range with the `[Files]` placement caught, proxy-only nftables ahead of
the Docker and Tailscale chains, no bind mounts, no DNS, key-only sshd
limited to one user, and the CA moved out of the host store. The
confirmation page is the right shape and the right owner, and it has
three problems that must land before an answer ever becomes a grant.

47. **The jail can reach the confirmation page through the proxy, and
    the page would see the host's own identity.** By reading; verify
    on the box. confirmd authenticates by peer address. The proxy
    connects from the host's own tailnet address, and `tailscale
    whois` resolves that address to the owner's login. The jail has no
    DNS, but the proxy resolves names for it, so from the jail
    `with-proxy curl https://spark-vm.<tailnet>.ts.net:8443/` goes:
    proxy, SSRF guard (the tailnet is on the allow list), TLS verified
    against the ts.net name, confirmd, whois on the host's address,
    owner login, 200. The IP-literal test that returned 502 failed on
    the certificate name, not on any block. If this reproduces, the
    jail can list and answer its own approvals. Fix, all three parts:
    confirmd refuses any peer address that belongs to the host itself
    (the `tailscale ip` list) or is not a remote tailnet node; the swap
    proxy hard-denies the host's own addresses and the page's name and
    port regardless of `ssrf.allow`, a deny list that beats the allow
    list; and confirmd writes every 403 with peer and login to the
    audit log. Test from the jail with the hostname, not the IP.

48. **No CSRF protection on `/answer`.** By reading. Authentication is
    by source address, the forms carry no token, and the POST handler
    checks neither `Origin` nor `Sec-Fetch-Site`. Any page open in a
    browser on one of the owner's tailnet devices can submit
    `id=…&decision=approve`, and the agent knows the ids because it
    files the requests. That is the agent-content-on-your-device
    problem, now concrete. Fix: mint a random nonce per pending item
    when `/approval/<id>` is served, store it in the pending file,
    require it on POST; and reject any POST whose `Sec-Fetch-Site` is
    not `same-origin` or whose `Origin` is not the page's own. Test:
    a POST with a valid id and no nonce is refused.

49. **Approvals are free text, not bound to a request.** By reading.
    A pending item is `{kind, summary, detail, requester}`. Nothing
    structured says which credential, host, method, path prefix or
    amount is being approved, so the deferred grant record would have
    to be built from prose the requester wrote. Fix: the item carries
    structured fields (`credential`, `host`, `method`, `path_prefix`,
    `scope`, `amount`, `job`), the page renders those, and any
    agent-supplied purpose text is shown labeled as untrusted. Better:
    swapd files the item itself when it refuses a swap for lack of a
    grant, so the tuple comes from the actual request and no
    model-authored text is in the approval at all. That is how the
    reference's Sentinel produces the "user-visible purpose".

50. **The requester is self-declared.** By reading. `confirm-request
    --requester bdrive` writes a field, and the writers are whoever can
    write the pending directory. Fix: record the requester from the
    peer, SO_PEERCRED over a socket or the file owner via a setgid
    directory, never from an argument, and accept only bdrive and
    swapd. obox must never file approvals directly.

51. **`route_localnet=1` is set on every interface.** By reading. The
    DNAT to 127.0.0.1 needs it only on `ve-jail`. On `all`, the kernel
    accepts packets addressed to 127/8 arriving on any interface, which
    turns every loopback-bound service into something a same-L2 peer
    can address. Set `net.ipv4.conf.ve-jail.route_localnet=1` from the
    veth drop-in's `ExecStartPost` and leave `all` and `default` at 0.

52. **Verify the agent's key is gone from `ntindle`.** The jail only
    works if the agent can no longer log in as `ntindle`. Its old key
    must be out of `/home/ntindle/.ssh/authorized_keys` and the
    ControlMaster socket that reused it must be closed; otherwise the
    jail is a second door beside an open one. Confirm, and add the
    check to the README's verify list.

53. **Nits in confirmd.** (a) Expired items stay listed, and approving
    one silently records a deny and redirects with no message; show
    "expired", refuse, and reap. (b) Expiry compares ISO strings; parse
    to datetimes. (c) `HTTPServer` is single-threaded and whois can
    take ten seconds; use `ThreadingHTTPServer`. (d) `Content-Length`
    is unbounded; cap it. (e) Refused requests are not logged anywhere.
    (f) The bind address is hardcoded; read it from `tailscale ip -4`.
    (g) If swapd runs `tailscale whois` through `tailscale set
    --operator=swapd`, that grants swapd full control of tailscaled
    including `tailscale serve`; prefer the narrow sudoers rule the
    design already mentions.

54. **The scanner pattern `LLM_[0-9]+` matches any `LLM_` plus a digit,
    documentation included.** Harmless, but
    `LLM_[0-9]{3,}_[A-Za-z0-9-]{16,}` would avoid false refusals.

### Grant channel: owner decisions (round 5)

- **The page stays as swapd.** The split is not worth specifying now;
  the trust boundary is the owner's Tailscale identity on the request,
  with 47 and 48 fixed.
- **Who files an approval.** swapd itself, when it refuses a swap for
  lack of a grant (49), or bdrive over a peer-checked socket (50).
  Never obox, never a self-declared requester.
- **What a grant is.** `{credential, host, method, path_prefix, scope,
  expires, approval_id, job}`, checked in `_resolve` before the static
  lists, audited as a `grant=` line in the swap log, reaped on expiry,
  revoked by bdrive at job end through the same peer-checked socket,
  hard-capped at 24 hours. One-time means one request flow with a
  short grace window for retries and redirects.
- **Order.** 47 and 48 land and are verified from the jail before any
  answer is consumed as a grant.

## Round 6: the grant channel (`ee96bb0` to `b2fb668`)

Findings 47, 48, 51, 53 and 54 are done as described, and the
structured approval shape from 49 and the owner-based requester from
50 are in place. The grant channel itself, the part that turns an
answer into a swap, has four confirmed defects, two of them severe,
and no tests. It must not be treated as done, and the owner should
hold consumption on the box until 55 and 56 land.

**Process.** Round 5 was deployed before review, with "unit-verified"
claims for code that has no tests in the repo, and three of the four
confirmed findings below are exactly what those tests would have
caught. During 52 the agent also truncated the owner's
`authorized_keys` with a bad pipeline and restored the owner's key
from its transcript. That is the class of event the jail exists to
make impossible, and it happened on the way in. From here: nothing in
the grant path lands without a test in the repo, and the owner
reviews the grant path before deploy, not after.

55. **Grants override per-credential host binding, and the agent can
    file the request for it.** CONFIRMED. `_credential_allows_request`
    checks grants before `allowed_hosts` and returns on a match, and
    `_file_approval` fires on every refusal including `unbound-host`.
    Chain: the agent sends `hsurr:openai` to github.com, the swap is
    refused, a pending item "POST github.com/gists for openai" appears
    on the page, one mistaken tap mints a grant, and the OpenAI key is
    posted to GitHub. Finding 1's guarantee now rests on the human
    never mis-tapping. Fix: host binding is checked first and no grant
    can override it; grants only widen methods and paths within bound
    hosts; `_file_approval` fires only for `method-not-allowed` and
    `path-not-allowed`, never for `unbound-host`.

56. **Reaped and revoked grants resurrect on the next reload.**
    CONFIRMED. `_consume_answers` derives grants from `answered/` minus
    the ids currently in the grants list, so a grant reaped at the
    24-hour cap or removed by `cred-grant-revoke` is recreated from its
    answered file on the next request. The cap and revocation are both
    ineffective. Fix: consumption is one-way. Move the answered file
    into `consumed/` at consumption, or keep a persistent consumed-id
    set, and never re-derive from `answered/`.

57. **Legitimate approvals are refused by the Origin check.**
    CONFIRMED. The page is served at its ts.net name, browsers send
    `Origin: https://spark-vm.<tailnet>.ts.net:8443` on every form
    POST, and the handler accepts only origins starting with the IP
    literal. Every real approve or deny returns 403 "csrf: Origin".
    That fails closed, so it is harmless, but it means the flow has
    never worked end to end, which the missing browser test would have
    shown. `startswith` without the port also matches
    `100.65.241.200`. Fix: exact match against the set of the page's
    own origins, port included.

58. **Approval flooding.** By reading. Dedup is on the full normalized
    path, so the agent creates one pending item per distinct path it
    tries, pending items are reaped only when opened, and the page
    fills until the human mis-taps. `_file_approval` also lists the
    whole pending directory on every refusal. Fix: cap pending items
    per credential, rate-limit filing, reap expired items when the list
    is rendered, and coalesce by credential, host and method.

59. **Every request re-reads every answered file.** By reading.
    `_maybe_reload` runs `_consume_answers` and `_reap_grants` on every
    request, connect and response, each listing and parsing
    `answered/`, which grows forever. Fix: gate on the directory's
    mtime like the other inputs; with 56's `consumed/` move, the
    directory stays small.

60. **Three writers, one registry, no lock.** By reading. The proxies'
    `_save_registry`, `cred-registry-set` and `cred-grant-revoke` each
    read, modify and write `credentials.json`, so concurrent writes
    lose updates: a removed method comes back, a grant disappears. The
    inference instance also consumes answers into its own registry
    because it inherits the default approvals directory. Fix: grants
    live in their own file with a single writer that confirmd and the
    revoke path call; proxies read it; the inference instance gets no
    approvals directory at all.

61. **`ssrf.deny` is not in the repo.** The file that makes 47 hold
    exists only on the box, so a rebuild from the repo loses it
    silently. Add `proxy/ssrf.deny` (the tailnet name is not secret)
    and have the addon warn at load when the file is missing.

62. **No tests for any of round 5.** The suite is the same 43 tests as
    round 4; the diff adds two attributes to a fake. The deny list,
    self-peer refusal, nonce, Origin check, requester check, grant
    match, consume, reap, revoke and approval filing have no tests.
    Nothing in round 5 counts as done until each has one, and the
    Origin check needs a test that uses the ts.net origin.

63. **Nits.** (a) `_consume_answers` trusts any file in `answered/`;
    verify `answered_by` is the owner and `decision` is `approve`, and
    make `answered/` writable only by confirmd's uid. (b) `tailscale
    ip` in confirmd runs without sudo while whois needs it; if the
    socket is unreadable, the self-peer set silently collapses to the
    bind literal. (c) The README's key check greps for "hatch"; list
    fingerprints instead. (d) `Sec-Fetch-Site` is enforced only when
    present, which is fine because the nonce exists; say so.

**Owner action until 55 and 56 land.** On the box, in your own
session: move `/home/swapd/approvals/answered` aside, remove any
`grants` list from `/home/swapd/credentials.json`, restart
`swap-proxy`, and verify your own key's fingerprint in
`~/.ssh/authorized_keys`. Do not approve anything on the page; the
button does not work yet (57), and when it does, an approval could
widen a credential beyond its bound hosts (55) and never expire (56).

### Round 6 addendum: what the hold found on the box

The owner moved `answered/` aside and found one grant in
`credentials.json`: `credential: null, host: null, method: ""`,
`path_prefix: "/"`, expiring 24 hours after consumption. It could
never match a request, so it was harmless by luck. It was minted from
a free-text test answer left over from round 4, marked `approve`,
which no human made. The inference registry held none. Restarting the
services produced systemd's "unit file changed on disk, run
daemon-reload" warning for both proxies.

64. **Consumption does not validate the tuple.** CONFIRMED on the box.
    `_consume_answers` mints a grant from any `approve` file, even one
    with no credential, host or method. Fix: refuse to mint unless
    `credential`, `host` and `method` are present and the credential
    exists in the registry, and audit the refusal. Part of 62's tests.

65. **An approve answer existed that the owner never gave.** The
    round-4 report said the page was "tested: owner views/answers";
    the round-5 report said an end-to-end approval was impossible
    without the owner's device. Both cannot be true of the same file.
    Muse should say which test wrote it and how it was marked
    approved, and confirm no other answered or pending items of that
    origin remain.

66. **Deploys skipped `daemon-reload`.** Unit files were replaced on
    disk without reloading systemd, so the running proxies may carry
    old unit definitions, including environment lines. `deploy.sh`
    must run `systemctl daemon-reload` before restarting anything, and
    the owner should run it once now.

**Owner decision (round 6): Web Push for the confirmation page.** The
owner has added the page to the iOS home screen. After 55 to 64 land,
confirmd gains Web Push: a manifest with `display: standalone`, a
service worker at root scope, a subscribe endpoint reachable only by
the owner's identity, a VAPID keypair stored under swapd at 0600,
subscriptions stored the same way, and a push sent when an approval
is filed. The payload says only that an approval is pending; tapping
opens the fixed page URL. Sending goes from the host to Apple's push
endpoint directly, not through the swap proxy. The Muse-app card, when
it exists, links to the same fixed URL and never carries an approval
id.

## What is left, and how the browser gets used (round 6 planning)

**Built and verified:** the swap proxy with every correctness finding
closed, per-credential host binding, static method and path limits,
the inference proxy, the private-range guard with a deny list (repo
copy pending, 61), response scrubbing, TOTP, the jail for the agent
login, and the confirmation page with structured approvals. The
GitHub token and the model key are installed and bound.

**In progress:** the grant channel (55 to 66), which must land with
tests and be deployed by the owner before any approval is consumed.

**Not built:** everything in the spec's build plan from `bdrive`
onward.

- `bdrive`, the driver: Playwright plus Chromium as its own user with
  the persistent profile, AX snapshots with `ref_scope`, the action
  protocol with receipts, screenshots, downloads, per-action timeouts,
  the proxy health gate, the socket with SO_PEERCRED (33), and the
  nftables uid rule that forces its egress through the proxy (10).
- `obox`, the brain: brief, steer, status and report; the
  observe-decide-act loop; `need_info` parking; the untrusted-data
  envelope and `hsurr:` neutralization (26, 30); the read
  restrictions (32); model calls through the inference proxy with
  `stream: false`, `store: false` and an explicit reasoning effort.
- The card pathway helper (decision 6), Web Push (round 6 decision),
  `deploy.sh` (19, 66), `.gitignore` additions (20), `flow_detail=0`
  (21), and the v2 items: noVNC watch and a classifier pass.

**A spec gap the jail exposed.** The spec's IPC is a unix socket on
the host with group permissions. The jail has no bind mounts and no
route to host services except the two proxy ports, so neither the
orchestrator in the jail nor a future `bdrive` client there can reach
`/run/bdrive/bdrive.sock` or obox's socket as specified. Two shapes:
bind-mount the sockets into the jail (`[Files] Bind=`), with the
daemons accepting the jail's mapped uid range via SO_PEERCRED; or
expose them as ports on the veth gateway with DNAT and nftables
rules, like the proxy ports. Recommendation: the bind-mounted sockets,
which keep the "no network to host services" rule and match 33.
Owner to confirm.

**A residual to state plainly.** There is no egress policy beyond
the private-range guard: the jail, and any browser inside it, can
reach every public host through the proxy. The reference governs
every request through Sentinel with taint tracking and a
personal-data egress classifier; spark-vm has neither. What bounds it
today is per-credential binding, so secrets cannot travel anywhere
but their own hosts. What does not bound it is anything the agent
already holds, such as session cookies in a browser profile it owns.

**Two ways to get the browser in use.**

1. *Now, inside the jail.* The agent installs Chromium in the jail,
   trusts the swapd CA in Chromium's NSS database (the recipe step),
   launches Playwright with `proxy={"server":
   "http://10.99.0.1:18080"}`, and drives sites with placeholders.
   The proxy, the allowlist, the binding and the SSRF guard all
   apply. What is missing versus the spec: the agent owns the browser
   profile, so a compromised agent holds the session cookies and can
   send them to any public host; there is no AX-only observation and
   no fixed action set. This is the mode the spec set out to replace,
   made much safer by the jail and the proxy, but not the design.
   Acceptable for low-value sites only: nothing where a stolen
   session matters.
2. *The design.* Build `bdrive` on the host first, with the IPC
   decision above, then `obox`. The profile lives with `bdrive`, the
   agent sees AX snapshots, and cookies never reach the jail. Several
   days of work, after the grant channel, since first-use
   confirmations depend on it.

## Owner decisions (round 7): the order from here

Made by the reviewer at the owner's request and recorded as decisions.

1. **Round 7 is the grant channel plus the deploy path.** Findings 55
   to 66 with a test per behavior, `ssrf.deny` in the repo, and
   `proxy/deploy.sh` that the owner runs as himself: every file, unit,
   sudoers line, `daemon-reload`, restarts, and a hash check of the
   live files against the repo. Nothing else lands in this round. The
   owner deploys it and performs the first real approve and deny from
   his phone, which is the end-to-end test the page has never had.

2. **Jail IPC: bind-mounted sockets.** `bdrive`'s socket is bind-mounted
   into the jail. The daemon checks SO_PEERCRED and accepts exactly two
   uids: the jail's `muse` user as seen from the host (its mapped uid
   in the `2000000` range) and, later, `obox`. No new ports on the veth
   gateway.

3. **Round 8 is `bdrive` v1, driven by the agent from the jail.** The
   brain for v1 is the agent itself, over the socket. `obox` is
   deferred, not cancelled: it needs its own untrusted-content
   handling (26, 30) that the agent's own cell already provides, so
   building it first delays a safe browser for no gain. `bdrive` does
   not change when `obox` arrives. v1 scope: `open`, `goto`,
   `snapshot`, `click`, `fill`, `type`, `press`, `select`, `check`,
   `look`, `get_text`, `wait`, `back`, `reload`, `state`,
   `cookies_clear`; receipts and `ref_scope`; persistent profile as
   the `bdrive` user; proxy health gate; the nftables uid rule that
   confines `bdrive`'s egress to the proxy (10); the read restrictions
   on password fields (32); first-use confirmation through the page
   and the grant channel. Deferred to v1.1: `gesture`, `upload`,
   `download`, `pdf`, `hover`, `scroll`. Conformance tests against a
   local dummy site, dummy credentials only.

4. **No interim browser in the jail.** The time goes to `bdrive`. The
   agent's own lookups go through the proxy with curl.

5. **Round 9:** Web Push for the page, the card pathway helper, and
   then the `obox` question again with `bdrive` in hand.

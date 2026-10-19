#!/usr/bin/env python3
"""muse-gate-shim.py -- minimal `muse`-shaped vehicle for the golden-image build gate.

Gate-mode `harness-auth-probe` drives a CLI vehicle to prove the
inference-proxy swap path end to end (GitHub #1715): the golden-image
recipe deliberately does NOT bake the real muse CLI
(`deploy/golden-image/Dockerfile` "Deliberately NOT baked" — the install
is operator/account bound, bills the user's Meta pay-as-you-go), so the
build-time gate cannot depend on it. This shim is what the probe drives
instead. It speaks exactly the argv shape the probe invokes:

    muse exec --provider meta --base-url <url> --reasoning-effort minimal <prompt>

as a single HTTP POST to <base_url>/responses, through the proxy env,
carrying META_API_KEY's `hsurr:` placeholder as the Bearer <redacted> The gate
fixture installer (harness/install-gate-fixture.sh) points the probe at
this file via PROBE_MUSE_BIN. It is gate-scratch only — never a tenant
vehicle, never provision mode (provision mode still requires the real
CLI; the probe's missing-vehicle error says so).

Honest scope limits (read before extending):
  * This proves the AUTH/SWAP PATH (placeholder in, swapped credential
    out, proxy routing honored), not the real CLI's protocol. The echo
    log asserts the swapped wire shape; nothing here certifies a real
    model response.
  * The JSON body is a static shape with no key material: bodies are
    recorded only as sha256 by the echo fixture, and keeping the body
    free of env-derived values guarantees the placeholder cannot leak
    through it.

Fail-closed contract:
  * META_API_KEY missing or not starting with "hsurr:" (with a non-empty
    suffix) -> exit 2 (the vehicle must authenticate ONLY through the
    injected placeholder).
  * NO_PROXY/no_proxy present -> exit 2 (the vehicle must never route
    around the swapping proxy; the probe strips these anyway).
  * HTTPS_PROXY/HTTP_PROXY absent -> exit 2 (the vehicle must route
    through the probe-injected swapping proxy, never direct).
  * argv not exactly the probe's invocation shape -> exit 2.
  * HTTP 3xx (a redirect off the proxy path) -> exit 3; non-2xx ->
    exit 3. Exit 0 only on HTTP 200.
  * stdin is never read (contract: stdin closed).

Proxy pinning (GitHub #1715 Security review): routing is pinned to an
explicit proxies dict built from the probe-injected HTTPS_PROXY/
HTTP_PROXY env -- an empty urllib ProxyHandler() would defer to
urllib's ambient env/system proxy discovery, whose REQUEST_METHOD CGI
rule silently drops proxy env (and absent proxy env means a direct
connect), letting the shim exit 0 while routing around the swapping
proxy it claims to prove. Exit 0 means "through the proxy, swapped";
anything else means the path was not proven.
"""

import json
import os
import sys
import urllib.request

# Self-imposed bound: the probe caps the vehicle externally too
# (6s gate budget, 15s installer wrapper). A hang is a fail.
REQUEST_TIMEOUT_S = 5.0
# Exit codes mirror the probe's vocabulary: 2 = usage/env, 3 = check failed.
EXIT_USAGE = 2
EXIT_CHECK_FAILED = 3


def _die_usage(msg):
    # Never echo META_API_KEY (or anything env-derived) in diagnostics.
    sys.stderr.write("muse-gate-shim: usage/env error: %s\n" % msg)
    sys.exit(EXIT_USAGE)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect off the proxy path proves nothing: fail closed, exit 3."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _parse_argv(argv):
    """Parse the probe's exact invocation shape; die(2) on anything else."""
    if len(argv) < 2 or argv[1] != "exec":
        _die_usage("expected 'exec <flags> <prompt>', got %r" % (argv[1:],))
    rest = argv[2:]
    provider = None
    base_url = None
    effort = None
    prompt = None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--provider" and i + 1 < len(rest):
            provider = rest[i + 1]
            i += 2
        elif a == "--base-url" and i + 1 < len(rest):
            base_url = rest[i + 1]
            i += 2
        elif a == "--reasoning-effort" and i + 1 < len(rest):
            effort = rest[i + 1]
            i += 2
        elif a.startswith("-"):
            _die_usage("unexpected flag %r" % (a,))
        else:
            if prompt is not None:
                _die_usage("unexpected extra positional %r" % (a,))
            prompt = a
            i += 1
    if provider != "meta":
        _die_usage("expected --provider meta, got %r" % (provider,))
    if not base_url:
        _die_usage("expected --base-url <url>")
    if effort != "minimal":
        _die_usage("expected --reasoning-effort minimal, got %r" % (effort,))
    if prompt is None:
        _die_usage("expected exactly one prompt positional")
    return base_url, prompt


def main(argv):
    base_url, prompt = _parse_argv(argv)

    key = os.environ.get("META_API_KEY", "")
    if not key.startswith("hsurr:") or len(key) <= len("hsurr:"):
        _die_usage("META_API_KEY must be the injected hsurr: placeholder")
    if "NO_PROXY" in os.environ or "no_proxy" in os.environ:
        _die_usage("NO_PROXY/no_proxy present: the vehicle must not route "
                   "around the swapping proxy")

    # Pin routing to the probe-injected proxy: an explicit proxies dict
    # never consults ambient env/system proxy discovery (including
    # urllib's REQUEST_METHOD CGI rule), so no ambient env value can
    # route around the swapping proxy -- and absent proxy env is a
    # fail-closed usage error, not a silent direct connect.
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
             or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))
    if not proxy:
        _die_usage("no proxy env (HTTPS_PROXY/HTTP_PROXY): the vehicle must "
                   "route through the probe-injected swapping proxy")

    # Static body shape: no env-derived values, so the placeholder cannot
    # leak through it. The echo fixture records bodies as sha256 only.
    body = json.dumps({"input": prompt}).encode("utf-8")
    url = base_url.rstrip("/") + "/responses"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # The no-redirect handler keeps a redirect off the proxy path fail-closed.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
        _NoRedirect())
    try:
        with opener.open(req, timeout=REQUEST_TIMEOUT_S) as resp:
            status = resp.status
            resp.read(65536)
    except urllib.error.HTTPError as e:
        sys.stderr.write("muse-gate-shim: request failed: HTTP %s\n" % (e.code,))
        sys.exit(EXIT_CHECK_FAILED)
    except Exception as e:  # noqa: BLE001 — any failure means "path not proven"
        sys.stderr.write("muse-gate-shim: request failed: %r\n" % (e,))
        sys.exit(EXIT_CHECK_FAILED)
    if status != 200:
        sys.stderr.write("muse-gate-shim: unexpected status %s\n" % (status,))
        sys.exit(EXIT_CHECK_FAILED)
    sys.stderr.write("muse-gate-shim: ok (%s)\n" % (url,))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

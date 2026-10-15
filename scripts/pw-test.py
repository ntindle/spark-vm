import os

from playwright.sync_api import sync_playwright

# Contributors behind an egress proxy (corporate VPN, proxied dev VMs):
# Chromium does not read *_proxy environment variables on its own, so the
# smoke would fail with ERR_TUNNEL_CONNECTION_FAILED. Honor the standard
# env vars when set; no-op otherwise (CI runners have direct egress).
_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_launch_kwargs = {"headless": True}
if _proxy:
    _launch_kwargs["proxy"] = {"server": _proxy}

with sync_playwright() as p:
    b = p.chromium.launch(**_launch_kwargs)
    pg = b.new_page()
    pg.goto("https://example.com", timeout=30000)
    print("TITLE:", pg.title())
    pg.screenshot(path="/tmp/pw-test.png")
    b.close()
print("BROWSER_TEST_OK")

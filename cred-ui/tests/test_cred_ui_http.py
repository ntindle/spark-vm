"""Hermetic tests for cred-ui's HTTP layer and validation (arch deep-read).

Covers the CSRF Host gate, the POST custom-header gate, the host-name
validation contract with proxy/cred-registry-set, delete-failure
surfacing, and the /api/creds placement allowlist.

The real server is spun up on an ephemeral localhost port with the
sudo-backed `run()` monkeypatched, so no secrets, sudo, or swapd are
involved. ALLOWED_HOSTS is patched to the ephemeral port's own address.

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_http.py -q
"""

import http.client
import importlib.util
import json
import os
import threading

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UI_PATH = os.path.join(REPO, "cred-ui", "cred-ui.py")


def _load_cred_ui():
    spec = importlib.util.spec_from_loader("credui_http", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = UI_PATH  # the bootstrap walks up from __file__
    src = open(UI_PATH, encoding="utf-8").read()
    exec(compile(src, UI_PATH, "exec"), mod.__dict__)
    return mod


cred_ui = _load_cred_ui()


@pytest.fixture()
def server(monkeypatch):
    """cred-ui Handler on an ephemeral port with ALLOWED_HOSTS patched."""
    srv = cred_ui.ThreadingHTTPServer(("127.0.0.1", 0), cred_ui.Handler)
    port = srv.server_address[1]
    monkeypatch.setattr(
        cred_ui, "ALLOWED_HOSTS",
        {"127.0.0.1:%d" % port, "localhost:%d" % port},
    )
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()


def _req(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers=headers or {})
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, dict(resp.getheaders()), payload


def _post(port, path, body, csrf=True):
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-Cred-UI"] = "1"
    return _req(port, "POST", path, body=body, headers=headers)


# --- CSRF gates -----------------------------------------------------------


def test_index_requires_own_host_header(server):
    status, _, _ = _req(server, "GET", "/", headers={"Host": "evil.example"})
    assert status == 403
    status, _, _ = _req(server, "GET", "/")
    assert status == 200


def test_post_requires_custom_header(server):
    status, _, _ = _post(server, "/api/delete", {"name": "x"}, csrf=False)
    assert status == 403
    # Wrong Host fails even with the custom header present.
    status, _, _ = _req(
        server, "POST", "/api/delete",
        body={"name": "x"},
        headers={"Host": "evil.example", "Content-Type": "application/json",
                 "X-Cred-UI": "1"},
    )
    assert status == 403


def test_allowed_hosts_derived_from_bind_port():
    # The gate must track BIND/PORT, not a hand-maintained literal (a drifted
    # literal would 403 everything the day PORT changes).
    assert cred_ui.ALLOWED_HOSTS == {
        "%s:%d" % (cred_ui.BIND, cred_ui.PORT),
        "localhost:%d" % cred_ui.PORT,
    }


# --- host validation mirrors the narrow writer ----------------------------


@pytest.mark.parametrize("host", [
    "api.github.com",
    "a.b.c.example.com",
    ".example.com",          # writer's leading-dot subdomain entries
    "x" * 63 + ".example.com",
])
def test_host_ok_accepts_writer_shape(host):
    assert cred_ui.host_ok(host)


@pytest.mark.parametrize("host", [
    "api.github.com:8080",   # writer rejects ports; addon strips them anyway
    "under_score.example.com",
    "trailing.example.com.",
    "",
    "x" * 64 + ".example.com",  # label over DNS max
])
def test_host_ok_rejects_writer_rejections(host):
    assert not cred_ui.host_ok(host)


def test_api_set_rejects_port_before_any_store(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cred_ui, "run", lambda argv, inp=None: calls.append(argv) or (0, "", ""))
    with pytest.raises(ValueError, match="bad host"):
        cred_ui.api_set({
            "name": "gh", "value": "tok", "entry": "access_token",
            "placement": "bearer_header", "placement_arg": "",
            "hosts": ["api.github.com:8080"],
        })
    assert calls == []  # no sudo writer ran: the secret was never stored


@pytest.mark.parametrize("bad", [123, None, ["nested"], {"h": "x"}])
def test_api_set_rejects_non_string_hosts(monkeypatch, bad):
    """Non-string host values are a clean 400 (ValueError), not a TypeError
    that escapes the handler and drops the connection."""
    calls = []
    monkeypatch.setattr(
        cred_ui, "run", lambda argv, inp=None: calls.append(argv) or (0, "", ""))
    with pytest.raises(ValueError, match="bad host"):
        cred_ui.api_set({
            "name": "gh", "value": "tok", "entry": "access_token",
            "placement": "bearer_header", "placement_arg": "",
            "hosts": [bad],
        })
    assert calls == []


@pytest.mark.parametrize("bad", [123, None, ["nested"]])
def test_api_host_rejects_non_string_host(monkeypatch, bad):
    calls = []
    monkeypatch.setattr(
        cred_ui, "run", lambda argv, inp=None: calls.append(argv) or (0, "", ""))
    with pytest.raises(ValueError, match="bad host"):
        cred_ui.api_host({"name": "gh", "host": bad}, add=True)
    assert calls == []


# --- delete failure must surface ------------------------------------------


def test_api_delete_surfaces_store_failure(monkeypatch):
    calls = []

    def fake_run(argv, inp=None):
        calls.append(argv)
        if argv == cred_ui.SECRET_DELETE + ["gh"]:
            return 1, "", "rm: permission denied"
        return 0, "", ""

    monkeypatch.setattr(cred_ui, "run", fake_run)
    with pytest.raises(RuntimeError, match="store delete failed"):
        cred_ui.api_delete({"name": "gh"})
    # The registry writer must not run: value-on-disk + registry-gone would
    # have reported success while the secret survived.
    assert all("cred-registry-set" not in " ".join(c) or "remove" not in " ".join(c)
               for c in calls)
    assert len(calls) == 1


def test_api_delete_ok_path(monkeypatch):
    monkeypatch.setattr(cred_ui, "run", lambda argv, inp=None: (0, "", ""))
    assert cred_ui.api_delete({"name": "gh"}) == {"ok": True, "name": "gh"}


# --- /api/creds placement allowlist ---------------------------------------


def test_snapshot_renders_placement_only(monkeypatch):
    monkeypatch.setattr(
        cred_ui, "read_registry",
        lambda: {"gh": {
            "access_token": {"placement": "bearer_header",
                             "mystery": {"x": 1}},  # future dict key
            "allowed_hosts": ["api.github.com"],
        }},
    )
    monkeypatch.setattr(cred_ui, "list_secret_names", lambda: {"gh"})
    (cred,) = cred_ui.snapshot()["creds"]
    assert cred["entries"] == {"access_token": "bearer_header"}
    assert cred["allowed_hosts"] == ["api.github.com"]


# --- generic 500 on read failure ------------------------------------------


def test_creds_read_failure_is_generic(server, monkeypatch):
    monkeypatch.setattr(cred_ui, "read_registry",
                        lambda: (_ for _ in ()).throw(OSError("/home/swapd/x")))
    status, _, payload = _req(server, "GET", "/api/creds")
    assert status == 500
    body = json.loads(payload)
    assert body == {"error": "read failed"}
    assert "swapd" not in payload.decode()

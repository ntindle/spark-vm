"""Hermetic tests for cred-ui's per-install API token (issue #86).

The CSRF header (X-Cred-UI: 1) is not a secret — any local process can
set it. Every /api/* endpoint (except the public /api/version) now
additionally requires a per-install bearer token the human pastes once
per browser session.

The real server is spun up on an ephemeral localhost port with the
sudo-backed `run()` monkeypatched, so no secrets, sudo, or swapd are
involved. CRED_UI_TOKEN_FILE points the token at a tmp dir, so the real
~/.config/cred-ui/token is never touched.

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_api_token.py -q
"""

import http.client
import importlib.util
import json
import os
import stat
import threading

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UI_PATH = os.path.join(REPO, "cred-ui", "cred-ui.py")
INDEX_PATH = os.path.join(REPO, "cred-ui", "index.html")


def _load_cred_ui():
    spec = importlib.util.spec_from_loader("credui_token", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = UI_PATH  # the bootstrap walks up from __file__
    src = open(UI_PATH, encoding="utf-8").read()
    exec(compile(src, UI_PATH, "exec"), mod.__dict__)
    return mod


cred_ui = _load_cred_ui()


@pytest.fixture()
def token_env(tmp_path, monkeypatch):
    """Point the token file at a tmp path; return (path, expected_token)."""
    path = str(tmp_path / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    return path, cred_ui.api_token()


@pytest.fixture()
def server(token_env, monkeypatch):
    """cred-ui Handler on an ephemeral port with ALLOWED_HOSTS patched."""
    path, token = token_env
    srv = cred_ui.BoundedThreadingHTTPServer(("127.0.0.1", 0), cred_ui.Handler)
    port = srv.server_address[1]
    monkeypatch.setattr(
        cred_ui,
        "ALLOWED_HOSTS",
        {"127.0.0.1:%d" % port, "localhost:%d" % port},
    )
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port, token
    finally:
        srv.shutdown()
        srv.server_close()
        cred_ui._reset_token_cache()


def _req(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers=headers or {})
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, dict((k.lower(), v) for k, v in resp.getheaders()), payload


def _auth_headers(token, csrf=True):
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-Cred-UI"] = "1"
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    return headers


# --- token file behavior -------------------------------------------------


def test_token_auto_generated_owner_only(tmp_path, monkeypatch):
    path = str(tmp_path / "sub" / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    try:
        token = cred_ui.api_token()
        assert cred_ui._TOKEN_RE.match(token)
        st = os.stat(path)
        assert stat.S_IMODE(st.st_mode) == 0o600
        # Stable: a second load reads the same file, not a new token.
        cred_ui._reset_token_cache()
        assert cred_ui.api_token() == token
    finally:
        cred_ui._reset_token_cache()


def test_token_file_world_readable_refuses_start(tmp_path, monkeypatch):
    path = str(tmp_path / "token")
    with open(path, "w") as f:
        f.write("a" * 32 + "\n")
    os.chmod(path, 0o644)
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    try:
        with pytest.raises(RuntimeError, match="readable by group/other"):
            cred_ui.api_token()
    finally:
        cred_ui._reset_token_cache()


def test_token_file_malformed_refuses_start(tmp_path, monkeypatch):
    for bad in ("", "short", "has spaces in it", "x" * 200):
        path = str(tmp_path / "token")
        with open(path, "w") as f:
            f.write(bad + "\n")
        os.chmod(path, 0o600)
        monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
        cred_ui._reset_token_cache()
        try:
            with pytest.raises(RuntimeError, match="empty or malformed"):
                cred_ui.api_token()
        finally:
            cred_ui._reset_token_cache()
            os.unlink(path)


def test_rotate_token_replaces_atomically_owner_only(tmp_path, monkeypatch):
    path = str(tmp_path / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    try:
        old = cred_ui.api_token()
        new = cred_ui._rotate_token()
        assert new != old
        assert cred_ui._TOKEN_RE.match(new)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        cred_ui._reset_token_cache()
        assert cred_ui.api_token() == new
    finally:
        cred_ui._reset_token_cache()


def test_group_writable_parent_dir_refuses_start(tmp_path, monkeypatch):
    # A group-writable ancestor lets a non-owner uid replace the token
    # file (or plant a pre-first-start symlink) with a known value.
    sub = tmp_path / "sub"
    sub.mkdir()
    os.chmod(sub, 0o775)
    path = str(sub / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    try:
        with pytest.raises(RuntimeError, match="replaceable by group/other"):
            cred_ui.api_token()
    finally:
        cred_ui._reset_token_cache()
        os.chmod(sub, 0o755)


def test_missing_ancestors_created_owner_only(tmp_path, monkeypatch):
    # First start with no ~/.config/cred-ui at all must still work —
    # missing ancestors are created 0700, not refused.
    path = str(tmp_path / "nope" / "nada" / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    try:
        token = cred_ui.api_token()
        assert cred_ui._TOKEN_RE.match(token)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    finally:
        cred_ui._reset_token_cache()


# --- HTTP layer: what is and isn't gated ---------------------------------


def test_index_stays_public(server):
    port, _ = server
    status, _, _ = _req(port, "GET", "/")
    assert status == 200


def test_version_stays_public(server):
    port, _ = server
    status, _, payload = _req(port, "GET", "/api/version")
    assert status == 200
    assert json.loads(payload)["service"] == "cred-ui"


def test_creds_requires_token(server):
    port, token = server
    status, _, _ = _req(port, "GET", "/api/creds",
                        headers=_auth_headers(None))
    assert status == 401


def test_creds_rejects_wrong_token(server, monkeypatch):
    port, token = server
    monkeypatch.setattr(cred_ui, "run", lambda *a, **k: (1, "", "no store"))
    status, _, _ = _req(port, "GET", "/api/creds",
                        headers=_auth_headers("wrong-token"))
    assert status == 401


def test_creds_rejects_non_bearer_scheme(server, monkeypatch):
    port, token = server
    monkeypatch.setattr(cred_ui, "run", lambda *a, **k: (1, "", "no store"))
    headers = _auth_headers(None)
    headers["Authorization"] = "Basic " + token
    status, _, _ = _req(port, "GET", "/api/creds", headers=headers)
    assert status == 401


def test_creds_accepts_correct_token(server, monkeypatch):
    port, token = server
    monkeypatch.setattr(cred_ui, "run",
                        lambda argv, inp=None: (0, "{}", ""))
    status, _, payload = _req(port, "GET", "/api/creds",
                              headers=_auth_headers(token))
    assert status == 200
    assert "creds" in json.loads(payload)


def test_unauthorized_has_no_www_authenticate(server):
    # No WWW-Authenticate: a browser basic-auth popup would be the wrong
    # ceremony (the token is pasted, not typed into a dialog).
    port, _ = server
    status, headers, _ = _req(port, "GET", "/api/creds",
                              headers=_auth_headers(None))
    assert status == 401
    assert "www-authenticate" not in headers


@pytest.mark.parametrize("path", ["/api/set", "/api/delete",
                                  "/api/host/add", "/api/host/remove"])
def test_state_changing_endpoints_require_token(server, path):
    port, _ = server
    status, _, _ = _req(port, "POST", path, body={"name": "x"},
                        headers=_auth_headers(None))
    assert status == 401


def test_auth_checked_before_body_parsing(server):
    # An unauthenticated client must not make us read a body: garbage body
    # + no token is a 401, not the 400 the body would earn.
    port, _ = server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/set", body=b"{not json",
                 headers={"Content-Type": "application/json",
                          "X-Cred-UI": "1"})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 401


def test_post_with_token_reaches_handler(server, monkeypatch):
    port, token = server
    monkeypatch.setattr(cred_ui, "run",
                        lambda argv, inp=None: (0, "", ""))
    status, _, payload = _req(
        port, "POST", "/api/delete", body={"name": "gone"},
        headers=_auth_headers(token))
    assert status == 200
    assert json.loads(payload) == {"ok": True, "name": "gone"}


# --- index.html: the token ceremony --------------------------------------


def _index_src():
    return open(INDEX_PATH, encoding="utf-8").read()


def test_index_has_unlock_ceremony():
    src = _index_src()
    assert 'id="unlock-card"' in src
    assert 'id="f-token"' in src
    assert 'id="btn-unlock"' in src
    assert 'id="btn-lock"' in src


def test_index_stores_token_in_session_storage_only():
    src = _index_src()
    assert "sessionStorage" in src
    # The token must not survive the tab in localStorage (the word may
    # appear in comments documenting that choice — check real usage).
    assert "localStorage.setItem" not in src
    assert "localStorage.getItem" not in src


def test_index_routes_all_api_calls_through_api_fetch():
    src = _index_src()
    assert "async function apiFetch" in src
    # The one remaining raw fetch( is apiFetch's own implementation.
    assert src.count("await fetch(") == 1
    for endpoint in ("/api/creds", "/api/set", "/api/delete",
                     "/api/host/add", "/api/host/remove"):
        single = "apiFetch('%s'" % endpoint
        double = 'apiFetch("%s"' % endpoint
        assert single in src or double in src

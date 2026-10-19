"""Hermetic tests for cred-ui's failure paths (2026-10-19 arch deep-read).

Two structural findings from the deep-read of cred-ui.py:

1. A hung sudo writer raised subprocess.TimeoutExpired out of run(), which
   is neither ValueError nor RuntimeError — so it escaped do_POST's
   exception contract: the handler thread died and the connection was
   dropped with NO JSON response, contradicting the file's "fail closed,
   loudly" posture. run() now converts it to RuntimeError.

2. api_set was not atomic: a registry-set failure after a successful
   store left an orphaned secret on disk with no registry entry. api_set
   now compensates with cred-store-delete and reports loudly either way.

Style mirrors test_cred_ui_http.py: the real server on an ephemeral
localhost port, sudo-backed run() monkeypatched, CRED_UI_TOKEN_FILE at a
tmp path so no sudo/swapd is involved.

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_failure_paths.py -q
"""

import http.client
import importlib.util
import json
import os
import subprocess
import threading

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UI_PATH = os.path.join(REPO, "cred-ui", "cred-ui.py")


def _load_cred_ui():
    spec = importlib.util.spec_from_loader("credui_failpaths", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = UI_PATH  # the bootstrap walks up from __file__
    src = open(UI_PATH, encoding="utf-8").read()
    exec(compile(src, UI_PATH, "exec"), mod.__dict__)
    return mod


cred_ui = _load_cred_ui()


import pytest  # noqa: E402  (after the module exec, like the sibling file)


@pytest.fixture()
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", str(tmp_path / "token"))
    cred_ui._reset_token_cache()
    token = cred_ui.api_token()
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
    return resp.status, payload


def _post(port, path, body, token):
    headers = {
        "Content-Type": "application/json",
        "X-Cred-UI": "1",
        "Authorization": "Bearer " + token,
    }
    return _req(port, "POST", path, body=body, headers=headers)


def _set_body(name="deepread-test"):
    return {
        "name": name,
        "value": "s3cret-value",
        "entry": "access_token",
        "placement": "bearer_header",
        "placement_arg": "",
        "hosts": ["api.example.com"],
    }


# --- Finding 1: a hung writer must fail closed with a JSON 500 -----------


def test_run_converts_timeout_to_runtime_error(monkeypatch):
    def hung(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=15)

    monkeypatch.setattr(subprocess, "run", hung)
    try:
        cred_ui.run(["sudo", "-n", "-u", "swapd", "/usr/bin/true"])
    except RuntimeError as e:
        assert "timed out" in str(e)
    else:
        raise AssertionError("run() let TimeoutExpired escape")


def test_post_set_with_hung_writer_returns_json_500(server, monkeypatch):
    # Before the fix, this test's request never got a response: the
    # handler thread died on the escaping TimeoutExpired and the
    # connection was dropped (http.client would raise RemoteDisconnected).
    port, token = server

    def hung(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=15)

    # Patch subprocess.run (not cred_ui.run) so the real run() performs
    # its TimeoutExpired -> RuntimeError conversion on the wire.
    monkeypatch.setattr(subprocess, "run", hung)
    status, payload = _post(port, "/api/set", _set_body(), token)
    assert status == 500
    body = json.loads(payload)
    assert "error" in body


# --- Finding 2: api_set compensates a registry failure -------------------


def _fake_run(script, calls):
    """A run() fake driven by a script: {argv-prefix: (rc, out, err)}."""
    def fake(argv, inp=None):
        calls.append(list(argv))
        for prefix, result in script.items():
            if argv[: len(prefix)] == list(prefix):
                return result
        raise AssertionError("unexpected argv: %r" % (argv,))
    return fake


def test_set_registry_failure_rolls_back_stored_secret(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cred_ui, "run",
        _fake_run(
            {
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-store-set"): (0, "", ""),
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-registry-set"): (1, "", "writer exploded"),
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-store-delete"): (0, "", ""),
            },
            calls,
        ),
    )
    try:
        cred_ui.api_set(_set_body())
    except RuntimeError as e:
        assert "rolled back" in str(e)
        assert "writer exploded" in str(e)
    else:
        raise AssertionError("api_set did not raise on registry failure")
    # The compensating delete ran against the stored name.
    assert any(c[-2] == "/usr/local/bin/cred-store-delete" and c[-1] == "deepread-test"
               for c in calls), calls


def test_set_registry_failure_and_rollback_failure_names_orphan(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cred_ui, "run",
        _fake_run(
            {
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-store-set"): (0, "", ""),
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-registry-set"): (1, "", "writer exploded"),
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-store-delete"): (1, "", "delete exploded"),
            },
            calls,
        ),
    )
    try:
        cred_ui.api_set(_set_body())
    except RuntimeError as e:
        msg = str(e)
        assert "rollback failed" in msg
        assert "deepread-test" in msg  # the orphan is named, not hidden
        assert "writer exploded" in msg
        assert "delete exploded" in msg
    else:
        raise AssertionError("api_set did not raise on registry failure")


def test_set_success_path_unchanged(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cred_ui, "run",
        _fake_run(
            {
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-store-set"): (0, "", ""),
                ("sudo", "-n", "-u", "swapd",
                 "/usr/local/bin/cred-registry-set"): (0, "", ""),
            },
            calls,
        ),
    )
    assert cred_ui.api_set(_set_body()) == {"ok": True, "name": "deepread-test"}
    # No compensating delete on the happy path.
    assert not any("cred-store-delete" in c for c in calls), calls

"""Hermetic tests for cred-ui's #1751 token-rotation self-healing.

Before #1751 the running server cached its per-install bearer <redacted>
forever: `--rotate-token` wrote the new value to the store, but the old
token kept working until a manual `systemctl --user restart cred-ui` — a
forgotten restart left the rotation silently unapplied. The fix:
`--rotate-token` signals the running service (SIGHUP) and then VERIFIES
the server actually adopted the new token, warning loudly if it did not;
SIGHUP reloads through the same read-only refresh the watchdog uses; a
60-second watchdog re-reads the store as a fail-safe. The fail-safe is
bounded (Security round 2): a transient bad re-read keeps the cached
token, but after 5 consecutive failures the cache is invalidated and
auth fails closed (401) — a persistently unreadable store must not
honor a possibly-revoked token forever.

Hermetic like the other suites: the local-file backend via
CRED_UI_TOKEN_FILE, no sudo, no swapd, no systemd.

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_token_refresh.py -q
"""

import http.client
import importlib.util
import json
import os
import signal
import threading
import time

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UI_PATH = os.path.join(REPO, "cred-ui", "cred-ui.py")


def _load_cred_ui():
    spec = importlib.util.spec_from_loader("credui_refresh", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = UI_PATH
    src = open(UI_PATH, encoding="utf-8").read()
    exec(compile(src, UI_PATH, "exec"), mod.__dict__)
    return mod


cred_ui = _load_cred_ui()


@pytest.fixture()
def token_file(tmp_path, monkeypatch):
    """Point the token store at a tmp file; return its path."""
    path = str(tmp_path / "token")
    monkeypatch.setenv("CRED_UI_TOKEN_FILE", path)
    cred_ui._reset_token_cache()
    return path


@pytest.fixture()
def live_server(token_file, monkeypatch):
    """The real cred-ui Handler on an ephemeral port (mirrors
    test_cred_ui_api_token.py's server fixture)."""
    path = token_file
    with open(path, "w", encoding="utf-8") as f:
        f.write("s" * 32 + "\n")
    os.chmod(path, 0o600)
    cred_ui._reset_token_cache()
    token = cred_ui.api_token()
    srv = cred_ui.BoundedThreadingHTTPServer(("127.0.0.1", 0), cred_ui.Handler)
    port = srv.server_address[1]
    monkeypatch.setattr(
        cred_ui,
        "ALLOWED_HOSTS",
        {"127.0.0.1:%d" % port, "localhost:%d" % port},
    )
    monkeypatch.setattr(cred_ui, "PORT", port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port, token
    finally:
        srv.shutdown()
        srv.server_close()
        cred_ui._reset_token_cache()


def _write_token(path, value):
    # 0600 like the server writes it — the server refuses to read a
    # group/other-readable token file, and so must the tests.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value + "\n")


def _wait_for(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_refresh_adopts_changed_token(token_file):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    _write_token(token_file, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    assert cred_ui._refresh_cached_token() == "adopted"
    assert cred_ui.api_token() == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert cred_ui.api_token() != old


def test_refresh_unchanged_when_store_agrees(token_file):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    assert cred_ui.api_token()  # populate the cache
    assert cred_ui._refresh_cached_token() == "unchanged"


def test_refresh_keeps_cached_token_on_transient_failure(token_file, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    os.unlink(token_file)
    assert cred_ui._refresh_cached_token() == "kept"
    assert cred_ui.api_token() == old
    err = capsys.readouterr().err
    assert "keeping cached token" in err  # loud, not silent
    assert "failure 1/5" in err


def test_refresh_keeps_cached_token_when_store_malformed(token_file, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    _write_token(token_file, "short")  # fails _TOKEN_RE: not adopted
    assert cred_ui._refresh_cached_token() == "kept"
    assert cred_ui.api_token() == old
    err = capsys.readouterr().err
    assert "malformed" in err


def test_refresh_survives_non_utf8_store(token_file, capsys):
    # UnicodeDecodeError is a ValueError, not an OSError — it must not
    # escape _refresh_cached_token (Engineering round 1) and kill the
    # watchdog thread.
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    fd = os.open(token_file, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(fd, "wb") as f:
        f.write(b"\xff\xfe not utf-8 \x00\x01")
    assert cred_ui._refresh_cached_token() == "kept"
    assert cred_ui.api_token() == old


def test_refresh_fails_closed_after_five_consecutive_failures(
        token_file, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    _write_token(token_file, "short")  # persistently malformed store
    results = [cred_ui._refresh_cached_token() for _ in range(5)]
    assert results == ["kept", "kept", "kept", "kept", "failed-closed"]
    assert cred_ui._API_TOKEN is None  # auth now 401s via _auth_ok
    err = capsys.readouterr().err
    assert "invalidating cached token" in err
    # Recovery: the next good read adopts again and the streak resets.
    _write_token(token_file, "cccccccccccccccccccccccccccccccc")
    assert cred_ui._refresh_cached_token() == "adopted"
    _write_token(token_file, "short")
    assert cred_ui._refresh_cached_token() == "kept"  # streak was reset


def test_refresh_streak_resets_on_success(token_file):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    cred_ui.api_token()
    _write_token(token_file, "short")
    assert cred_ui._refresh_cached_token() == "kept"   # streak 1
    assert cred_ui._refresh_cached_token() == "kept"   # streak 2
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert cred_ui._refresh_cached_token() == "unchanged"  # streak reset
    _write_token(token_file, "short")
    # Two more failures must not fail closed: the streak restarted.
    assert cred_ui._refresh_cached_token() == "kept"
    assert cred_ui._refresh_cached_token() == "kept"
    assert cred_ui._API_TOKEN is not None


def test_watchdog_thread_adopts_rotation(token_file):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    assert cred_ui.api_token()
    stop = threading.Event()
    t = threading.Thread(
        target=cred_ui._token_watchdog, args=(stop, 0.05), daemon=True)
    t.start()
    try:
        _write_token(token_file, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert _wait_for(
            lambda: cred_ui.api_token() ==
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    finally:
        stop.set()
        t.join(timeout=5)


def test_hup_handler_actively_refreshes(token_file):
    # Round 2 (Architecture): SIGHUP goes through the read-only refresh —
    # never the create-on-absent startup path — so a transient store
    # hiccup can neither mint a surprise token nor blank auth.
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    assert cred_ui.api_token()
    _write_token(token_file, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    cred_ui._install_hup_reload()
    try:
        os.kill(os.getpid(), signal.SIGHUP)
        assert _wait_for(
            lambda: cred_ui.api_token() ==
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    finally:
        signal.signal(signal.SIGHUP, signal.SIG_DFL)


def test_hup_handler_keeps_cache_on_store_failure(token_file, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    cred_ui._reset_token_cache()
    old = cred_ui.api_token()
    os.unlink(token_file)  # store hiccup at HUP time
    cred_ui._install_hup_reload()
    try:
        os.kill(os.getpid(), signal.SIGHUP)
        time.sleep(0.2)  # the handler runs synchronously on this thread
        assert cred_ui._API_TOKEN == old  # kept, not blanked, not minted
    finally:
        signal.signal(signal.SIGHUP, signal.SIG_DFL)


def test_signal_running_service_true(monkeypatch):
    calls = []

    class _P:
        returncode = 0

    def _fake_run(argv, **kwargs):
        calls.append(argv)
        return _P()

    monkeypatch.setattr(cred_ui.subprocess, "run", _fake_run)
    assert cred_ui._signal_running_service() is True
    argv = calls[0]
    assert argv[:4] == ["systemctl", "--user", "kill", "-s"]
    assert argv[4] == "HUP"
    assert "cred-ui" in argv[5]


def test_signal_running_service_false_when_systemctl_missing(monkeypatch):
    def _boom(argv, **kwargs):
        raise OSError("no systemctl here")

    monkeypatch.setattr(cred_ui.subprocess, "run", _boom)
    assert cred_ui._signal_running_service() is False


def test_signal_running_service_false_on_nonzero_exit(monkeypatch):
    class _P:
        returncode = 1

    monkeypatch.setattr(
        cred_ui.subprocess, "run", lambda argv, **kw: _P())
    assert cred_ui._signal_running_service() is False


def test_verify_token_adopted_against_live_server(live_server):
    port, token = live_server
    assert cred_ui._verify_token_adopted(token, timeout_s=3) is True


def test_verify_token_adopted_false_for_stale_token(live_server):
    port, token = live_server
    # A wrong bearer gets 401s until the deadline — never adopted.
    assert cred_ui._verify_token_adopted(
        "z" * 32, timeout_s=1) is False


def test_verify_token_adopted_false_when_no_server(monkeypatch):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    dead_port = s.getsockname()[1]
    s.close()
    monkeypatch.setattr(cred_ui, "PORT", dead_port)
    assert cred_ui._verify_token_adopted("a" * 32, timeout_s=1) is False


def test_rotate_cli_verifies_adoption(token_file, monkeypatch, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setattr(cred_ui, "_signal_running_service", lambda: True)
    monkeypatch.setattr(cred_ui, "_verify_token_adopted",
                        lambda tok, timeout_s=8: tok == "new-token-marker")
    monkeypatch.setattr(cred_ui, "_rotate_token",
                        lambda path=None: "new-token-marker")
    monkeypatch.setattr(
        cred_ui.sys, "argv", ["cred-ui.py", "--rotate-token"])
    cred_ui.main()
    out = capsys.readouterr().out
    assert "adopted" in out

    monkeypatch.setattr(cred_ui, "_verify_token_adopted",
                        lambda tok, timeout_s=8: False)
    cred_ui.main()
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "old token" in out


def test_rotate_cli_no_service_message(token_file, monkeypatch, capsys):
    _write_token(token_file, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setattr(
        cred_ui, "_signal_running_service", lambda: False)
    monkeypatch.setattr(
        cred_ui.sys, "argv", ["cred-ui.py", "--rotate-token"])
    cred_ui.main()
    out = capsys.readouterr().out
    assert "no running cred-ui service found" in out
    assert "within a minute" in out  # the watchdog covers this case
    assert cred_ui._API_TOKEN is None  # CLI-side cache reset

"""Tests for cua/bin/cua-bridge-log (the #1597 operator reader).

The CLI runs in a subprocess against synthetic logs written with the
writer's own `_format_bridge_event` — so every "valid" line is contract
shaped by construction. Malformed/free-form lines are hand-written.
"""

import datetime as dt
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(REPO_ROOT, "cua", "bin")
CLI = os.path.join(BIN_DIR, "cua-bridge-log")


def _load_bridge():
    spec = importlib.util.spec_from_file_location(
        "cua_bridge", os.path.join(BIN_DIR, "cua-bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_reader():
    # the CLI carries no .py suffix, so spec_from_file_location finds no
    # loader — pin SourceFileLoader explicitly
    loader = importlib.machinery.SourceFileLoader("cua_bridge_log", CLI)
    spec = importlib.util.spec_from_loader("cua_bridge_log", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bridge():
    return _load_bridge()


def run_cli(log, *args):
    return subprocess.run(
        [sys.executable, CLI, "--log", log, *args],
        capture_output=True, text=True, timeout=60)


def write_log(tmp_path, lines, name="cua-bridge.log"):
    path = str(tmp_path / name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


def valid(bridge, kind="mutation", msg="type=click", level="WARNING"):
    return bridge._format_bridge_event(kind, msg, level=level)


MALFORMED = [
    "cua-bridge: startup banner (legacy free-form, no ts= prefix)\n",
    "ts=notanumber level=ERROR kind=bad msg=x\n",
    "ts=100 level=INFO kind=mutation msg=x\n",
    "ts=100 level=ERROR kind==bad msg=x\n",
    "ts=100 level=ERROR kind=mutation\n",          # missing msg= token
    "ts=100 level=ERROR kind=mutation note=1 msg=x\n",  # msg= not last
]


def test_valid_events_pass_filters_applied(tmp_path, bridge):
    log = write_log(tmp_path, [
        valid(bridge, "mutation", "type=click"),
        valid(bridge, "http-500", "type=ValueError", level="ERROR"),
        valid(bridge, "csrf-refusal", "reason=bad-host"),
    ])
    r = run_cli(log)
    assert r.returncode == 0
    assert "mutation type=click" in r.stdout
    assert "http-500 type=ValueError" in r.stdout

    r = run_cli(log, "--kind", "mutation")
    assert r.returncode == 0
    assert "mutation" in r.stdout
    assert "http-500" not in r.stdout

    r = run_cli(log, "--level", "ERROR")
    assert r.returncode == 0
    assert "http-500" in r.stdout
    assert "mutation" not in r.stdout


def test_skip_rule_silent(tmp_path, bridge):
    """The contract rule: lines the parser rejects are skipped, never
    parsed — legacy free-form banners and malformed audit lines alike."""
    log = write_log(tmp_path, [valid(bridge, "mutation", "type=click")]
                    + MALFORMED)
    r = run_cli(log)
    assert r.returncode == 0
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "mutation type=click" in lines[0]
    for bad in ("startup banner", "notanumber", "INFO", "==bad", "note=1"):
        assert bad not in r.stdout


def test_shared_parser_not_duplicated():
    """The reader must use the writer's parser, not a second assumption:
    the reader source defines no local parser, and at runtime its parser
    is the writer module's own function object."""
    src = open(CLI, "r", encoding="utf-8").read()
    assert "def _parse_bridge_event" not in src  # no local redefinition
    assert "_BRIDGE._parse_bridge_event" in src  # wired from the writer
    reader = _load_reader()
    assert reader._parse_bridge_event is reader._BRIDGE._parse_bridge_event
    # behavioral cross-check against a direct writer load
    bridge = _load_bridge()
    line = "ts=1700000000 level=ERROR kind=mutation msg=a\\nb"
    assert reader._parse_bridge_event(line) == bridge._parse_bridge_event(line)
    # the reader formats display only; the writer owns line formatting
    assert not hasattr(reader, "_format_bridge_event")


def test_multiline_unescape_display(tmp_path, bridge):
    """msg arrives unescaped; display keeps the real message with
    continuation lines indented."""
    raw_msg = "line1\nline2\\u2028 not-a-newline"
    log = write_log(tmp_path, [valid(bridge, "mutation", raw_msg)])
    r = run_cli(log)
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert lines[0].endswith("mutation line1")
    assert lines[1] == "    line2\\u2028 not-a-newline"


def test_since_relative(tmp_path, bridge):
    now = int(time.time())
    # ts comes from time.time() inside the writer; synthesize via the
    # writer's format, then rewrite ts= for determinism.
    new_line = valid(bridge, "mutation", "type=new").split(" ", 1)
    old_ts_line = f"ts={now - 7200} " + new_line[1].replace("type=new",
                                                            "type=old")
    new_ts_line = f"ts={now} " + new_line[1]
    log = write_log(tmp_path, [old_ts_line + "\n", new_ts_line + "\n"])
    r = run_cli(log, "--since", "1h")
    assert r.returncode == 0
    assert "type=new" in r.stdout
    assert "type=old" not in r.stdout


def test_since_iso(tmp_path, bridge):
    line = valid(bridge, "mutation", "type=x").split(" ", 1)
    log = write_log(tmp_path,
                    [f"ts=1000000000 " + line[1] + "\n"])  # 2001-09-09
    r = run_cli(log, "--since", "2026-01-01T00:00:00Z")
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    r = run_cli(log, "--since", "1999-01-01T00:00:00Z")
    assert r.returncode == 0
    assert "type=x" in r.stdout


def test_since_bad_is_usage_error(tmp_path, bridge):
    log = write_log(tmp_path, [valid(bridge, "mutation", "x")])
    r = run_cli(log, "--since", "yesterday-ish")
    assert r.returncode == 2
    assert "bad --since" in r.stderr


def test_tail(tmp_path, bridge):
    log = write_log(tmp_path,
                    [valid(bridge, "mutation", f"type={i}")
                     for i in range(5)])
    r = run_cli(log, "--tail", "2")
    assert r.returncode == 0
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "type=3" in lines[0] and "type=4" in lines[1]


def test_all_reads_rotations_oldest_first(tmp_path, bridge):
    base = write_log(tmp_path, [valid(bridge, "mutation", "gen=current")])
    write_log(tmp_path, [valid(bridge, "mutation", "gen=1")], "cua-bridge.log.1")
    write_log(tmp_path, [valid(bridge, "mutation", "gen=2")], "cua-bridge.log.2")
    # .3 does not exist — must be skipped, not an error
    r = run_cli(base)
    assert r.returncode == 0
    assert "gen=current" in r.stdout
    assert "gen=1" not in r.stdout
    r = run_cli(base, "--all")
    assert r.returncode == 0
    gens = [ln for ln in r.stdout.splitlines() if "gen=" in ln]
    assert [g.rsplit("gen=", 1)[1] for g in gens] == ["2", "1", "current"]


def test_missing_log_is_loud_failure(tmp_path):
    r = run_cli(str(tmp_path / "does-not-exist.log"))
    assert r.returncode == 1
    assert "does-not-exist.log" in r.stderr


def test_empty_match_is_clean_success(tmp_path, bridge):
    log = write_log(tmp_path, [valid(bridge, "mutation", "x")])
    r = run_cli(log, "--kind", "http-500")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_display_shape(tmp_path, bridge):
    log = write_log(tmp_path, [valid(bridge, "http-500", "type=ValueError",
                                           level="ERROR")])
    r = run_cli(log)
    assert r.returncode == 0
    import re
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ERROR http-500 "
        r"type=ValueError\n", r.stdout)

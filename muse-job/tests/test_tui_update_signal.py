"""Tests for the TUI-binary-swap detector (issue #212).

The Muse TUI auto-updates under running jobs: the pane's foreground
process is a versioned binary (`muse-bin-1.3.0-R3233.1`,
`-R3401.1`, ...) and an in-place update swaps it for a new one while
tmux stays alive. The update prompt's wording is not grounded anywhere,
so there is no text detector to test -- the observable is the process
name changing across watchdog passes. `_tui_swap_event` turns that
into a distinct `tui-updated` signal instead of lumping the aftermath
into `tui-dead`.

The baseline is manager-owned state in job.json (`tui_cmd`), the same
class as the watchdog's `last_bytes` counter: a same-user agent can
plant it, but planting only suppresses one informational event -- the
fail-loud liveness signals (tui-dead on a parked pane) never depend on
the baseline.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_tui_swap", CLI_PATH)


OLD = "muse-bin-1.3.0-R3233.1"
NEW = "muse-bin-1.3.0-R3401.1"


def test_first_observation_adopts_baseline_silently(cli):
    """A pre-#212 job has no baseline: adopt it, emit nothing."""
    job = {}
    assert cli._tui_swap_event(job, OLD) is None
    assert job["tui_cmd"] == OLD


def test_never_adopts_a_shell_as_baseline(cli):
    """Adopting 'bash' as baseline would fire a bogus swap when the TUI
    later relaunches; a dead pane leaves the baseline absent instead."""
    job = {}
    assert cli._tui_swap_event(job, "bash") is None
    assert "tui_cmd" not in job


def test_no_capture_is_not_a_swap(cli):
    """Capture failure ("") must not adopt or fire."""
    job = {"tui_cmd": OLD}
    assert cli._tui_swap_event(job, "") is None
    assert job["tui_cmd"] == OLD


def test_unchanged_name_is_quiet(cli):
    job = {"tui_cmd": OLD}
    assert cli._tui_swap_event(job, OLD) is None
    assert job["tui_cmd"] == OLD


def test_binary_swap_fires_tui_updated(cli):
    """old != new, both TUI processes: the swap. The event names the
    signal, the old and new binaries, and points at the per-pass
    liveness signals for the post-swap pane state."""
    job = {"tui_cmd": OLD}
    ev = cli._tui_swap_event(job, NEW)
    assert ev is not None
    assert ev["signal"] == "tui-updated"
    assert OLD in ev["detail"] and NEW in ev["detail"]
    assert "#212" in ev["detail"]
    # Baseline advances so the swap fires exactly once.
    assert job["tui_cmd"] == NEW
    assert cli._tui_swap_event(job, NEW) is None


def test_swap_into_shell_is_not_tui_updated(cli):
    """Pane dropped to a shell (TUI process gone) is the dead-TUI path's
    case, not a swap: no event, and the baseline is kept so a later
    relaunch with a new binary still fires."""
    job = {"tui_cmd": OLD}
    assert cli._tui_swap_event(job, "bash") is None
    assert job["tui_cmd"] == OLD
    ev = cli._tui_swap_event(job, NEW)
    assert ev is not None and ev["signal"] == "tui-updated"


def test_poisoned_baseline_is_repaired_silently(cli):
    """An agent-planted or absurd baseline (not a TUI process name) is
    treated as absent: adopt the real one, emit nothing."""
    job = {"tui_cmd": "bash"}
    assert cli._tui_swap_event(job, OLD) is None
    assert job["tui_cmd"] == OLD


def test_non_string_baseline_is_repaired_silently(cli):
    job = {"tui_cmd": 12345}
    assert cli._tui_swap_event(job, OLD) is None
    assert job["tui_cmd"] == OLD


def test_muse_to_node_flip_is_a_swap(cli):
    """The launcher presents as `muse`/`node` on some paths; a flip
    between them is still a binary identity change under the job."""
    job = {"tui_cmd": "muse"}
    ev = cli._tui_swap_event(job, "node")
    assert ev is not None and ev["signal"] == "tui-updated"


def test_event_names_are_sanitized(cli):
    """Process names reach operator-visible event detail; ANSI escapes
    must not survive (the #12 L3 class)."""
    job = {"tui_cmd": OLD}
    ev = cli._tui_swap_event(job, "muse-bin-\x1b[31m1.3.0")
    # "muse-bin-\x1b[31m1.3.0" still passes _is_tui_process (startswith),
    # so the swap fires and the escape must be stripped from the detail.
    assert ev is not None
    assert "\x1b" not in ev["detail"]


def test_watch_emission_contract(cli, tmp_path):
    """The watch-path contract, exercised at runtime (not grepped): the
    emission helper appends exactly one `tui-updated` event carrying the
    job key, persists the advanced baseline to job.json on disk, and a
    second identical pass appends nothing. Deleting the append or the job
    key in cmd_watch breaks this test."""
    slug = "swap-test"
    os.makedirs(os.path.join(cli.JOBS_DIR, slug))
    job = {"slug": slug, "tui_cmd": OLD}
    events = []
    cli._emit_tui_swap_event(job, slug, NEW, events)
    assert len(events) == 1
    assert events[0]["signal"] == "tui-updated"
    assert events[0]["job"] == slug
    assert OLD in events[0]["detail"] and NEW in events[0]["detail"]
    with open(os.path.join(cli.JOBS_DIR, slug, "job.json")) as f:
        on_disk = json.load(f)
    assert on_disk["tui_cmd"] == NEW
    # Second identical pass: baseline already advanced, nothing appended.
    events2 = []
    cli._emit_tui_swap_event(job, slug, NEW, events2)
    assert events2 == []


def test_emission_helper_quiet_when_no_swap(cli, tmp_path):
    """No swap: the helper persists the adopted baseline and appends
    nothing."""
    slug = "swap-quiet"
    os.makedirs(os.path.join(cli.JOBS_DIR, slug))
    job = {"slug": slug}
    events = []
    cli._emit_tui_swap_event(job, slug, OLD, events)
    assert events == []
    with open(os.path.join(cli.JOBS_DIR, slug, "job.json")) as f:
        assert json.load(f)["tui_cmd"] == OLD

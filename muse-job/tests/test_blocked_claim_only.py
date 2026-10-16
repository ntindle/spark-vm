"""Issue #21 item 2: `blocked` is claim-only -- `cmd_watch` never transitions
job state on the forgeable hook event.

Covers:
  1. A forged `blocked` tail-line event does NOT move job["state"] out of
     "active" (the old code set "blocked" on the forgeable tail line).
  2. Every visible blocked event pages on every pass (no tail-line
     reader, no one-shot latch): a buried genuine blocked is not hidden
     behind a newer line, and triage is oldest-first on the sanitized ts
     cursor.
  3. Burst coalescing mirrors done: >3 blocked claims in 24h -> the
     `blocked-repeated` label, still one signal per claim; the count comes
     from the event file, never from job.json.
  4. `question` keeps its tail-line behavior (out of scope for item 2).
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import time as _time

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
    return load_script("muse_job_cli_blocked", CLI_PATH)


def make_job(cli, slug="demo"):
    job = {
        "slug": slug,
        "session_uuid": "uuid-abc",
        "worktree": "/jobs/demo/work",
        "state": "active",
    }
    jd = cli.job_dir(slug)
    os.makedirs(jd, exist_ok=True)
    return job


def blocked_event(ts=1.0, detail="waiting on input", **kw):
    ev = {"event": "stop", "state": "blocked", "session_id": "uuid-abc",
          "detail": detail, "ts": ts}
    ev.update(kw)
    return ev


def write_events(cli, uuid, lines):
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    p = os.path.join(cli.EVENTS_DIR, uuid + ".jsonl")
    with open(p, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return p


def triage(cli, job, now, uuid="uuid-abc"):
    events = []
    cli.triage_blocked_events(job, uuid, now, events)
    return events


def test_forged_blocked_tail_line_never_transitions_job_state(cli):
    # The core of item 2: the same-user agent can append any line to its
    # event file. A forged `blocked` must page the operator but must not
    # move job["state"] -- state transitions are manager-side acts only.
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [blocked_event(ts=now - 10)])
    events = triage(cli, job, now)
    assert [e["signal"] for e in events] == ["blocked"]
    assert job["state"] == "active"


def test_buried_genuine_blocked_still_pages(cli):
    # The tail-line reader proved buryable for done (issue #23 B3); the old
    # blocked code used it too. A newer trailing line must not hide a
    # genuine blocked claim.
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        blocked_event(ts=now - 300, detail="genuine"),
        {"event": "stop", "state": "idle", "session_id": "uuid-abc",
         "detail": "forgery buries the tail", "ts": now - 5},
    ])
    sigs = [e["signal"] for e in triage(cli, job, now)]
    assert sigs == ["blocked"]
    assert "genuine" in triage(cli, job, now)[0]["detail"]


def test_every_visible_blocked_pages_oldest_first(cli):
    # No one-shot latch: two visible blocked events produce two signals,
    # ordered by the sanitized ts cursor (a newer line with an earlier ts
    # sorts first), every pass.
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        blocked_event(ts=now - 5, detail="newer-line-earlier-ts"),
        blocked_event(ts=now - 300, detail="older"),
    ])
    events = triage(cli, job, now)
    assert [e["signal"] for e in events] == ["blocked", "blocked"]
    assert [e["detail"] for e in events][0].endswith("older")


def test_forged_ts_never_breaks_the_cursor(cli):
    # The sanitized cursor (_claim_ts) must not raise on garbage ts;
    # non-numeric/NaN/bool ts sorts as 0 (oldest).
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        blocked_event(ts="not-a-number", detail="garbage-ts"),
        blocked_event(ts=now - 60, detail="real-ts"),
    ])
    events = triage(cli, job, now)  # must not raise
    assert [e["signal"] for e in events] == ["blocked", "blocked"]
    assert triage(cli, job, now)[0]["detail"].endswith("garbage-ts")


def test_blocked_claims_coalesce_after_three_in_24h(cli):
    # Mirrors done-repeated: >3 blocked claims visible from the last 24h
    # get the coalesced label; every claim still yields exactly one
    # signal; the count comes from the event file, never job.json.
    now = _time.time()
    job = make_job(cli)
    job["blocked_page_count"] = 999  # plant: must be inert
    sigs = []
    for i in range(5):
        sig = cli.handle_blocked_claim(job, blocked_event(ts=now - 300 + i),
                                       job["slug"], now,
                                       recent_count=i + 1)
        sigs.append(sig["signal"])
    assert sigs[:3] == ["blocked"] * 3
    assert sigs[3:] == ["blocked-repeated"] * 2
    assert "blocked_page_count" in job  # no migration: key never existed


def test_blocked_burst_window_ignores_old_claims(cli):
    now = _time.time()
    job = make_job(cli)
    old = [blocked_event(ts=now - 25 * 3600 + i) for i in range(5)]
    new = [blocked_event(ts=now - 10)]
    write_events(cli, "uuid-abc", old + new)
    events = triage(cli, job, now)
    # 6 blocked total but only 1 in the 24h window -> no repeated label.
    assert [e["signal"] for e in events] == ["blocked"] * 6


def test_blocked_signal_always_carries_job_and_sanitized_detail(cli):
    # handle_blocked_claim always returns a signal dict, never None, and
    # the detail is terminal-escape sanitized like every operator surface.
    now = _time.time()
    job = make_job(cli)
    sig = cli.handle_blocked_claim(job, blocked_event(detail="x\x1b[2Jred"),
                                   job["slug"], now)
    assert sig["signal"] == "blocked"
    assert "\x1b" not in sig["detail"]
    sig_none = cli.handle_blocked_claim(job, None, job["slug"], now)
    assert sig_none["signal"] == "blocked"

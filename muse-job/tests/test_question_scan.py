"""Issue #1561: `question` uses the whole-file scan -- the tail-line reader
the old question handling used is buryable (issue #23 B3 proved it for
`done`; PR #1560 fixed `blocked` the same way). `cmd_watch` now triages
every visible question event oldest-first on the sanitized ts cursor,
every pass, mirroring triage_blocked_events.

Covers:
  1. A buried genuine question still pages (a newer trailing line must not
     hide it).
  2. Every visible question pages on every pass, oldest-first by the
     sanitized _claim_ts cursor.
  3. A forged non-numeric ts never breaks the cursor (sorts as 0, no raise).
  4. Burst coalescing mirrors blocked: >3 question claims in 24h -> the
     `question-repeated` label, still one signal per claim; the count comes
     from the event file, never from job.json.
  5. Old claims outside the 24h window do not trigger the repeated label.
  6. handle_question_claim always returns a signal dict, never None, with
     the detail terminal-escape sanitized like every operator surface.
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
    return load_script("muse_job_cli_question", CLI_PATH)


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


def question_event(ts=1.0, detail="approve this?", **kw):
    ev = {"event": "stop", "state": "question", "session_id": "uuid-abc",
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
    cli.triage_question_events(job, uuid, now, events)
    return events


def test_buried_genuine_question_still_pages(cli):
    # The tail-line reader proved buryable for done (issue #23 B3); the old
    # question code used it too. A newer trailing line must not hide a
    # genuine question claim.
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        question_event(ts=now - 300, detail="genuine"),
        {"event": "stop", "state": "idle", "session_id": "uuid-abc",
         "detail": "forgery buries the tail", "ts": now - 5},
    ])
    sigs = [e["signal"] for e in triage(cli, job, now)]
    assert sigs == ["question"]
    assert "genuine" in triage(cli, job, now)[0]["detail"]


def test_every_visible_question_pages_oldest_first(cli):
    # No one-shot latch: two visible question events produce two signals,
    # ordered by the sanitized ts cursor (a newer line with an earlier ts
    # sorts first), every pass.
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        question_event(ts=now - 5, detail="newer-line-earlier-ts"),
        question_event(ts=now - 300, detail="older"),
    ])
    events = triage(cli, job, now)
    assert [e["signal"] for e in events] == ["question", "question"]
    assert [e["detail"] for e in events][0].endswith("older")


def test_forged_ts_never_breaks_the_cursor(cli):
    # The sanitized cursor (_claim_ts) must not raise on garbage ts;
    # non-numeric/NaN/bool ts sorts as 0 (oldest).
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [
        question_event(ts="not-a-number", detail="garbage-ts"),
        question_event(ts=now - 60, detail="real-ts"),
    ])
    events = triage(cli, job, now)  # must not raise
    assert [e["signal"] for e in events] == ["question", "question"]
    assert triage(cli, job, now)[0]["detail"].endswith("garbage-ts")


def test_question_claims_coalesce_after_three_in_24h(cli):
    # Mirrors blocked-repeated: >3 question claims visible from the last
    # 24h get the coalesced label; every claim still yields exactly one
    # signal; the count comes from the event file, never job.json.
    now = _time.time()
    job = make_job(cli)
    job["question_page_count"] = 999  # plant: must be inert
    sigs = []
    for i in range(5):
        sig = cli.handle_question_claim(job, question_event(ts=now - 300 + i),
                                        job["slug"], now,
                                        recent_count=i + 1)
        sigs.append(sig["signal"])
    assert sigs[:3] == ["question"] * 3
    assert sigs[3:] == ["question-repeated"] * 2
    assert "question_page_count" in job  # no migration: key never existed


def test_question_burst_window_ignores_old_claims(cli):
    now = _time.time()
    job = make_job(cli)
    old = [question_event(ts=now - 25 * 3600 + i) for i in range(5)]
    new = [question_event(ts=now - 10)]
    write_events(cli, "uuid-abc", old + new)
    events = triage(cli, job, now)
    # 6 questions total but only 1 in the 24h window -> no repeated label.
    assert [e["signal"] for e in events] == ["question"] * 6


def test_question_signal_always_carries_job_and_sanitized_detail(cli):
    # handle_question_claim always returns a signal dict, never None, and
    # the detail is terminal-escape sanitized like every operator surface.
    now = _time.time()
    job = make_job(cli)
    sig = cli.handle_question_claim(job, question_event(detail="x\x1b[2Jred"),
                                    job["slug"], now)
    assert sig["signal"] == "question"
    assert "\x1b" not in sig["detail"]
    sig_none = cli.handle_question_claim(job, None, job["slug"], now)
    assert sig_none["signal"] == "question"


def test_triage_fills_job_on_every_signal(cli):
    now = _time.time()
    job = make_job(cli)
    write_events(cli, "uuid-abc", [question_event(ts=now - 10)])
    events = triage(cli, job, now)
    assert [e["job"] for e in events] == ["demo"]

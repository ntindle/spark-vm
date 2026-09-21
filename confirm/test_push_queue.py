"""Tests for confirm/push.py's H14 push queue (enqueue/retry worker).

Run with:
    python3 -m pytest test_push_queue.py -q

No network is touched: the sender is a scripted fake. The real
PushSender._send_payload contract (returns (sent, pending), never raises)
is mirrored by FakeSender.
"""
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push


class FakeSender:
    """Scripted stand-in for push.PushSender.

    script: aid -> outcome of one _send_payload call:
      "ok"    -> (1, False)
      "retry" -> (0, True)   (transient)
      "prune" -> (1, False)  (subscription pruned; delivery succeeds)
      "crash" -> raises RuntimeError
    Unscripted aids default to "ok".
    """

    def __init__(self, notified_path, script=None):
        self.script = dict(script or {})
        self.enabled = True
        self.disabled_reason = None
        self.calls = []  # [(aid, payload)]
        self.pruned = []
        self.notified = push.NotifiedLog(notified_path)

    def _send_payload(self, aid, payload):
        self.calls.append((aid, payload))
        outcome = self.script.get(aid, "ok")
        if outcome == "ok":
            return (1, False)
        if outcome == "retry":
            return (0, True)
        if outcome == "prune":
            self.pruned.append(aid)
            return (1, False)
        if outcome == "crash":
            raise RuntimeError("boom")
        raise AssertionError("unknown scripted outcome %r" % outcome)


def make_queue(tmpdir, script=None):
    tmp = Path(str(tmpdir))
    q = push.PushQueue(str(tmp / "q.jsonl"), str(tmp / "dead.jsonl"),
                       str(tmp / "notified.json"))
    sender = FakeSender(str(tmp / "notified.json"), script)
    return q, sender


def read_entries(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


class TestEnqueue(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.q, self.sender = make_queue(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_queued_and_entry_fields(self):
        self.assertEqual(self.q.enqueue({"id": "a1", "summary": "hello"}),
                         "queued")
        entries = read_entries(self.q.queue_path)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["aid"], "a1")
        self.assertEqual(e["summary"], "hello")
        self.assertEqual(e["attempts"], 0)
        self.assertEqual(e["state"], "pending")
        self.assertLessEqual(e["next_at"], time.time())

    def test_invalid_aid(self):
        self.assertEqual(self.q.enqueue({"id": "bad id!"}), "invalid")
        self.assertEqual(read_entries(self.q.queue_path), [])

    def test_duplicate(self):
        self.assertEqual(self.q.enqueue({"id": "a1"}), "queued")
        self.assertEqual(self.q.enqueue({"id": "a1", "summary": "x"}),
                         "duplicate")
        self.assertEqual(len(read_entries(self.q.queue_path)), 1)

    def test_already_notified(self):
        self.q.notified.mark("a1")
        self.assertEqual(self.q.enqueue({"id": "a1"}), "notified")
        self.assertEqual(read_entries(self.q.queue_path), [])

    def test_enqueue_never_raises_on_io_failure(self):
        # queue_path under a path that can never exist (a file, not a dir)
        bad = push.PushQueue(
            os.path.join(self._td.name, "is-a-file", "q.jsonl"),
            os.path.join(self._td.name, "dead.jsonl"),
            os.path.join(self._td.name, "notified.json"))
        Path(os.path.join(self._td.name, "is-a-file")).write_text("x")
        self.assertEqual(bad.enqueue({"id": "a1"}), "error")

    def test_enqueue_truncates_summary(self):
        self.q.enqueue({"id": "a1", "summary": "y" * 5000})
        entry = read_entries(self.q.queue_path)[0]
        self.assertEqual(len(entry["summary"]), 200)
        self.assertTrue(entry["summary"].endswith("..."))

    def test_journal_lines_are_jsonl(self):
        self.q.enqueue({"id": "a1"})
        self.q.enqueue({"id": "a2"})
        with open(self.q.queue_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(l.startswith("{") for l in lines))


class TestRunOnce(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.q, self.sender = make_queue(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_empty(self):
        stats = self.q.run_once(sender=self.sender, now=1000.0)
        self.assertEqual(stats,
                         {"processed": 0, "sent": 0, "rescheduled": 0,
                          "dead": 0, "errors": 0})

    def test_all_ok_marks_notified_and_removes(self):
        now = time.time() + 5
        self.q.enqueue({"id": "a1", "summary": "hi"})
        stats = self.q.run_once(sender=self.sender, now=now)
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(read_entries(self.q.queue_path), [])
        self.assertTrue(self.sender.notified.seen("a1"))

    def test_retry_reschedules_with_backoff(self):
        now = time.time() + 5
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        q.enqueue({"id": "a1"})
        stats = q.run_once(sender=sender, now=now)
        self.assertEqual(stats["rescheduled"], 1)
        self.assertEqual(stats["sent"], 0)
        entries = read_entries(q.queue_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["attempts"], 1)
        self.assertEqual(entries[0]["next_at"], now + 60.0)
        self.assertEqual(entries[0]["state"], "pending")
        # Not marked notified on a transient failure.
        self.assertFalse(sender.notified.seen("a1"))

    def test_backoff_schedule_pinned(self):
        expected = [60.0, 120.0, 240.0, 480.0, 960.0, 1800.0, 1800.0]
        for attempts, delay in zip(range(1, 8), expected):
            self.assertEqual(push._queue_next_at(attempts, 1000.0),
                             1000.0 + delay)

    def test_max_attempts_dead_letters(self):
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        now = time.time() + 5
        q.enqueue({"id": "a1"})
        for i in range(push.QUEUE_MAX_ATTEMPTS - 1):
            stats = q.run_once(sender=sender, now=now)
            self.assertEqual(stats["rescheduled"], 1)
            now = push._queue_next_at(i + 1, now)
        with self.assertLogs("sparkvm.push", level="ERROR") as logs:
            stats = q.run_once(sender=sender, now=now)
        self.assertEqual(stats["dead"], 1)
        self.assertEqual(read_entries(q.queue_path), [])
        dead = read_entries(q.dead_path)
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]["aid"], "a1")
        self.assertEqual(dead[0]["dead_reason"], "max-attempts")
        self.assertEqual(dead[0]["attempts"], push.QUEUE_MAX_ATTEMPTS)
        self.assertTrue(any("DEAD-LETTERED" in m for m in logs.output))

    def test_prune_counts_as_success(self):
        now = time.time() + 5
        q, sender = make_queue(self._td.name, {"a1": "prune"})
        q.enqueue({"id": "a1"})
        stats = q.run_once(sender=sender, now=now)
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(read_entries(q.queue_path), [])
        self.assertTrue(sender.notified.seen("a1"))

    def test_send_exception_is_transient(self):
        now = time.time() + 5
        q, sender = make_queue(self._td.name, {"a1": "crash"})
        q.enqueue({"id": "a1"})
        stats = q.run_once(sender=sender, now=now)
        self.assertEqual(stats["rescheduled"], 1)
        self.assertEqual(len(read_entries(q.queue_path)), 1)

    def test_future_next_at_untouched(self):
        now = time.time() + 5
        self.q.enqueue({"id": "a1"})
        # A pass with a clock before the entry's next_at does nothing.
        stats = self.q.run_once(sender=self.sender, now=now - 3600)
        self.assertEqual(stats["processed"], 0)
        self.assertEqual(len(read_entries(self.q.queue_path)), 1)
        # ...and the entry is still due once the clock passes it.
        stats = self.q.run_once(sender=self.sender, now=now)
        self.assertEqual(stats["sent"], 1)

    def test_disabled_sender_skips_loudly(self):
        now = time.time() + 5
        self.q.enqueue({"id": "a1"})
        self.sender.enabled = False
        self.sender.disabled_reason = "no-keys: test"
        with self.assertLogs("sparkvm.push", level="WARNING"):
            stats = self.q.run_once(sender=self.sender, now=now)
        self.assertTrue(stats["disabled"])
        self.assertEqual(len(read_entries(self.q.queue_path)), 1)

    def test_corrupt_line_skipped_others_processed(self):
        self.q.enqueue({"id": "a1"})
        with open(self.q.queue_path, "a", encoding="utf-8") as f:
            f.write("this is not json\n")
            f.write('{"nope": true}\n')
        self.q.enqueue({"id": "a2"})
        with self.assertLogs("sparkvm.push", level="ERROR"):
            stats = self.q.run_once(sender=self.sender,
                                    now=time.time())
        self.assertEqual(stats["sent"], 2)
        self.assertEqual(read_entries(self.q.queue_path), [])

    def test_claim_lease_prevents_double_send(self):
        now = time.time() + 5
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        q.enqueue({"id": "a1"})
        # First pass claims (transient failure): next_at = now + 60.
        q.run_once(sender=sender, now=now)
        n_calls = len(sender.calls)
        # A second pass before the retry is due sends nothing.
        stats = q.run_once(sender=sender, now=now + 10)
        self.assertEqual(stats["processed"], 0)
        self.assertEqual(len(sender.calls), n_calls)
        # After the retry is due, the pass sends again.
        stats = q.run_once(sender=sender, now=now + 70)
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(len(sender.calls), n_calls + 1)

    def test_crashed_claim_self_heals_after_ttl(self):
        # Simulate a worker that claimed and died: entry is inflight with
        # a next_at in the past — the next pass must pick it up.
        self.q.enqueue({"id": "a1"})
        with push._locked(self.q.queue_path):
            entries = self.q._read_all()
            entries[0]["state"] = "inflight"
            entries[0]["next_at"] = 500.0
            self.q._rewrite(entries)
        stats = self.q.run_once(sender=self.sender, now=time.time())
        self.assertEqual(stats["sent"], 1)
        self.assertTrue(self.sender.notified.seen("a1"))

    def test_claimed_entry_already_notified_drops_without_resend(self):
        # Crash between notified.mark and _finalize: the entry is still
        # in the journal but the mark landed. The next pass must drop it
        # WITHOUT sending again (Eng B1).
        self.q.enqueue({"id": "a1"})
        self.q.notified.mark("a1")  # as the crashed pass did
        stats = self.q.run_once(sender=self.sender,
                                now=time.time() + 5)
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["sent"], 0)
        self.assertEqual(self.sender.calls, [])
        self.assertEqual(read_entries(self.q.queue_path), [])

    def test_touch_renews_claim_lease(self):
        self.q.enqueue({"id": "a1"})
        with push._locked(self.q.queue_path):
            entries = self.q._read_all()
            entries[0]["state"] = "inflight"
            entries[0]["next_at"] = 1000.0
            self.q._rewrite(entries)
        self.q._touch("a1", 2000.0)
        entry = read_entries(self.q.queue_path)[0]
        self.assertEqual(entry["next_at"], 2000.0 + push.QUEUE_CLAIM_TTL)

    def test_requeue_moves_dead_letter_back(self):
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        q.enqueue({"id": "a1", "summary": "hello"})
        now = time.time() + 5
        for _ in range(push.QUEUE_MAX_ATTEMPTS):
            q.run_once(sender=sender, now=now)
            now = push._queue_next_at(99, now) + 1
        self.assertEqual(read_entries(q.queue_path), [])
        self.assertEqual(q._requeue("a1"), "queued")
        entries = read_entries(q.queue_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["summary"], "hello")

    def test_requeue_unknown_aid(self):
        self.assertEqual(self.q._requeue("nope"), "not-found")

    def test_requeue_invalid_aid(self):
        self.assertEqual(self.q._requeue("bad id!"), "invalid")

    def test_enqueue_during_inflight_is_duplicate(self):
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        q.enqueue({"id": "a1"})
        with push._locked(q.queue_path):
            entries = q._read_all()
            entries[0]["state"] = "inflight"
            entries[0]["next_at"] = 5000.0
            q._rewrite(entries)
        self.assertEqual(q.enqueue({"id": "a1"}), "duplicate")

    def test_concurrent_enqueues_lose_nothing(self):
        errors = []

        def worker(i):
            try:
                res = self.q.enqueue({"id": "t-%d" % i})
                if res != "queued":
                    errors.append((i, res))
            except Exception as e:  # noqa: BLE001 — fail-open check
                errors.append((i, repr(e)))

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(read_entries(self.q.queue_path)), 20)

    def test_wire_payload_identical_to_inline_path(self):
        long_summary = "x" * 500
        now = time.time() + 5
        self.q.enqueue({"id": "a1", "summary": long_summary})
        self.q.run_once(sender=self.sender, now=now)
        aid, payload = self.sender.calls[0]
        want_aid, want = push._build_approval_payload(
            {"id": "a1", "summary": long_summary})
        self.assertEqual(aid, want_aid)
        self.assertEqual(payload, want)
        # 200-char truncation applied by the shared builder.
        body = json.loads(payload)["body"]
        self.assertTrue(body.endswith("...") and len(body) == 200)

    def test_huge_summary_stays_under_payload_cap(self):
        # The shared builder truncates summaries to 200 chars before the
        # 3800-byte wire cap, so the cap is unreachable defense-in-depth —
        # pin the invariant that a hostile summary can't inflate the wire
        # payload.
        huge = "y" * 5000
        now = time.time() + 5
        self.q.enqueue({"id": "a1", "summary": huge})
        self.q.run_once(sender=self.sender, now=now)
        _aid, payload = self.sender.calls[0]
        self.assertLessEqual(len(payload), 3800)
        body = json.loads(payload)["body"]
        self.assertEqual(len(body), 200)
        self.assertTrue(body.endswith("..."))

    def test_dead_lettered_aid_can_reenqueue(self):
        # Dead-lettering is not a notified mark: the operator may re-file.
        q, sender = make_queue(self._td.name, {"a1": "retry"})
        now = time.time() + 5
        q.enqueue({"id": "a1"})
        for i in range(push.QUEUE_MAX_ATTEMPTS):
            q.run_once(sender=sender, now=now)
            now = push._queue_next_at(i + 1, now)
        self.assertEqual(read_entries(q.queue_path), [])
        self.assertEqual(q.enqueue({"id": "a1"}), "queued")


class TestWorkerCLI(unittest.TestCase):
    def test_worker_once(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            qp = os.path.join(td, "q.jsonl")
            env = {"CONFIRM_PUSH_QUEUE": qp,
                   "CONFIRM_PUSH_DEAD": os.path.join(td, "dead.jsonl"),
                   "CONFIRM_PUSH_SUBS": os.path.join(td, "subs.json"),
                   "CONFIRM_VAPID_KEYS": os.path.join(td, "no-keys.json")}
            with mock.patch.dict(os.environ, env, clear=False):
                q = push.PushQueue.default()
                self.assertEqual(q.enqueue({"id": "cli1"}), "queued")
                # No keys configured -> sender disabled -> pass skips.
                self.assertEqual(push.main(["--worker-once"]), 0)
                self.assertEqual(len(read_entries(qp)), 1)

    def test_worker_interval_must_be_positive(self):
        self.assertEqual(push.main(["--worker", "--worker-interval", "0"]),
                         2)
        self.assertEqual(push.main(["--worker", "--worker-interval",
                                    "-5"]), 2)

    def test_worker_forever_loops(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env = {"CONFIRM_PUSH_QUEUE": os.path.join(td, "q.jsonl"),
                   "CONFIRM_PUSH_DEAD": os.path.join(td, "dead.jsonl"),
                   "CONFIRM_PUSH_SUBS": os.path.join(td, "subs.json"),
                   "CONFIRM_VAPID_KEYS": os.path.join(td, "no-keys.json")}
            with mock.patch.dict(os.environ, env, clear=False):
                q = push.PushQueue.default()
                with mock.patch.object(q, "run_once",
                                       side_effect=[{"processed": 0},
                                                    KeyboardInterrupt]):
                    with self.assertRaises(KeyboardInterrupt):
                        with mock.patch("push.PushQueue.default",
                                         return_value=q):
                            with mock.patch("time.sleep",
                                             side_effect=KeyboardInterrupt):
                                push.main(["--worker",
                                           "--worker-interval", "1"])


if __name__ == "__main__":
    unittest.main()

"""Tests for the G4 S1 box-side summons outbox journal (GitHub #428).

Run from the repo root:
    python3 -m unittest proxy/test_summons_outbox.py

Covers docs/FIRST_APPROVAL_SUMMONS.md slice S1: the inline journal append
in _file_approval (same-try durability, demote-to-no-signal on failure)
and the reconciliation sweep that diffs pending/ against the journal.

Nothing touches /home/swapd: APPROVALS_DIR is patched to a tmp dir and
CONFIRM_DIR (the push queue's journal) is pointed at the same tmp dir.
"""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swap_addon as sa  # noqa: E402

import logging  # noqa: E402
sa.log.propagate = False
sa.log.addHandler(logging.NullHandler())


def make_addon():
    a = sa.SwapAddon.__new__(sa.SwapAddon)
    a._audit = lambda host, matched: True  # noqa: E731
    return a


class SummonsOutboxTests(unittest.TestCase):
    """_file_approval writes one journal row per filing (G4 S1)."""

    def _ctx(self, tmp):
        return (mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)),
                mock.patch.object(sa, "APPROVALS_ENABLED", True),
                mock.patch.dict(os.environ,
                                {"SWAP_TENANT": "test-tenant",
                                 "CONFIRM_DIR": tmp,
                                 "SWAP_SUMMONS_OUTBOX": ""},
                                clear=False))

    def _file(self, a, name="github", host="github.com", method="POST",
              path="/repos/x", reason="no-grant"):
        return a._file_approval(name, host, method, path, reason)

    def _journal_rows(self, tmp):
        p = Path(tmp) / "summons-outbox.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text().splitlines()
                if line.strip()]

    def test_journal_row_shape(self):
        """The filed approval gets one journal row with the designed
        payload: aid, filed_at, expires, page-shown summary, the tuple
        machine-readable, and the tenant hint. The credential VALUE
        (never mind the request body) is nowhere in the journal."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, pen, env = self._ctx(tmp)
            with pdir, pen, env:
                a = make_addon()
                signals = self._file(a)
                self.assertEqual(len(signals), 1)
                aid, state = signals[0]
                self.assertEqual(state, "pending")
                rows = self._journal_rows(tmp)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row["aid"], aid)
                self.assertEqual(row["credential"], "github")
                self.assertEqual(row["host"], "github.com")
                self.assertEqual(row["method"], "POST")
                self.assertEqual(row["tenant_hint"], "test-tenant")
                pending = json.loads(
                    (Path(tmp) / "pending" / (aid + ".json")).read_text())
                self.assertEqual(row["filed_at"], pending["created"])
                self.assertEqual(row["expires"], pending["expires"])
                self.assertEqual(row["summary"], pending["summary"])
                # The summary is the page-shown text (finding-49
                # discipline): no model-authored free text, no secrets.
                raw = (Path(tmp) / "summons-outbox.jsonl").read_bytes()
                self.assertNotIn(b"ghp_TOKEN", raw)
                self.assertIn(b"no-grant", raw)  # the refusal reason is
                                                # page-shown, not secret

    def test_journal_file_mode_0600(self):
        """The journal is created 0600 like the push queue journal —
        it will eventually carry tenant hints worth keeping private."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, pen, env = self._ctx(tmp)
            with pdir, pen, env:
                self._file(make_addon())
                mode = stat.S_IMODE(os.stat(
                    Path(tmp) / "summons-outbox.jsonl").st_mode)
                self.assertEqual(mode, 0o600)

    def test_append_failure_demotes_signal(self):
        """OSError in the journal append falls through to the filing's
        existing except OSError: the approval stays filed (pending file
        on disk) but the client gets no pending signal — no signal beats
        a signal for a summons that never reached the observer's
        channel. The sweep recovers the filing on its next pass."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, pen, env = self._ctx(tmp)
            with pdir, pen, env:
                a = make_addon()
                with mock.patch.object(sa, "_summons_append",
                                       side_effect=OSError("disk gone")):
                    signals = self._file(a)
                self.assertEqual(signals, [])
                filed = list((Path(tmp) / "pending").glob("*.json"))
                self.assertEqual(len(filed), 1)
                self.assertFalse(
                    (Path(tmp) / "summons-outbox.jsonl").exists())

    def test_tenant_hint_hostname_fallback(self):
        """Without SWAP_TENANT the hint is the box hostname — still an
        unverified hint, just a weaker one."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SWAP_TENANT", None)
            self.assertEqual(sa._summons_tenant_hint(),
                             socket.gethostname())


class SummonsSweepTests(unittest.TestCase):
    """_summons_sweep diffs pending/ against the journal (G4 §7)."""

    def _write_pending(self, pending_d, aid, **kw):
        item = {"id": aid, "created": kw.get("created", "2026-09-26T00:00:00+00:00"),
                "expires": kw.get("expires", "2026-09-26T01:00:00+00:00"),
                "summary": kw.get("summary", "POST api.example /x for cred"),
                "credential": kw.get("credential", "cred"),
                "host": kw.get("host", "api.example"),
                "method": kw.get("method", "POST")}
        item.update(kw)
        p = os.path.join(pending_d, aid + ".json")
        with open(p, "w") as f:
            json.dump(item, f)
        return p

    def _ctx(self, tmp):
        return (mock.patch.object(sa, "APPROVALS_DIR", Path(tmp)),
                mock.patch.dict(os.environ, {"SWAP_TENANT": "test-tenant"},
                                clear=False))

    @staticmethod
    def _read_rows(outbox):
        with open(outbox, encoding="utf-8") as f:
            return [line for line in f.read().splitlines() if line.strip()]

    def test_sweep_recovers_missed_filing(self):
        """A pending approval with no journal row (crash between the
        two writes) gets its row re-appended, with filed_at taken from
        the pending record's own created timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                pending_d = os.path.join(tmp, "pending")
                os.makedirs(pending_d)
                self._write_pending(pending_d, "aaaabbbbccccdddd")
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 1)
                rows = [json.loads(line) for line in self._read_rows(outbox)]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["aid"], "aaaabbbbccccdddd")
                self.assertEqual(rows[0]["filed_at"],
                                 "2026-09-26T00:00:00+00:00")
                self.assertEqual(rows[0]["tenant_hint"], "test-tenant")

    def test_sweep_skips_already_journaled(self):
        """A pending approval whose aid is already in the journal is
        not duplicated — the journal is at-least-once, not
        append-per-sweep."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                pending_d = os.path.join(tmp, "pending")
                os.makedirs(pending_d)
                self._write_pending(pending_d, "aaaabbbbccccdddd")
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                with open(outbox, "w") as f:
                    f.write(json.dumps({"aid": "aaaabbbbccccdddd"}) + "\n")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 0)
                self.assertEqual(len(self._read_rows(outbox)), 1)

    def test_sweep_ignores_nonpending_journal_rows(self):
        """Journal rows with no pending file are answered or
        expiry-reaped records — moot, never re-shipped."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                pending_d = os.path.join(tmp, "pending")
                os.makedirs(pending_d)
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                with open(outbox, "w") as f:
                    f.write(json.dumps({"aid": "answered1234abcd"}) + "\n")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 0)
                self.assertEqual(len(self._read_rows(outbox)), 1)

    def test_sweep_skips_corrupt_journal_line(self):
        """A corrupt journal line is logged and skipped, never fatal —
        and it must not mask a real miss in the same pass."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                pending_d = os.path.join(tmp, "pending")
                os.makedirs(pending_d)
                self._write_pending(pending_d, "aaaabbbbccccdddd")
                self._write_pending(pending_d, "eeeefeeeffff1111")
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                with open(outbox, "w") as f:
                    f.write("this is not json\n")
                    f.write(json.dumps({"aid": "aaaabbbbccccdddd"}) + "\n")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 1)
                aids = [json.loads(line)["aid"] for line in
                        self._read_rows(outbox)
                        if line.startswith("{") and "aid" in line]
                self.assertIn("eeeefeeeffff1111", aids)

    def test_sweep_rejects_bad_aid(self):
        """A planted pending id that fails _AID_RE is never journaled —
        the journal is the observer's input and must not carry
        path-shaped junk."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                pending_d = os.path.join(tmp, "pending")
                os.makedirs(pending_d)
                self._write_pending(pending_d, "evil",
                                    id="../../x")  # noqa: S106 - test data
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 0)
                self.assertFalse(os.path.exists(outbox))

    def test_sweep_missing_dirs_never_raises(self):
        """Fail-open: a box with no approvals tree yet sweeps to zero,
        silently."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, env = self._ctx(tmp)
            with pdir, env:
                n = sa._summons_sweep(
                    outbox=os.path.join(tmp, "nope", "summons-outbox.jsonl"),
                    pending_d=os.path.join(tmp, "nope", "pending"))
                self.assertEqual(n, 0)

    def test_sweep_recovers_demoted_filing(self):
        """End-to-end of the demotion contract: a filing whose journal
        append failed (no-signal to the client) is re-appended by the
        next sweep pass."""
        with tempfile.TemporaryDirectory() as tmp:
            pdir, pen, env = (mock.patch.object(sa, "APPROVALS_DIR",
                                                Path(tmp)),
                              mock.patch.object(sa, "APPROVALS_ENABLED",
                                                True),
                              mock.patch.dict(
                                  os.environ,
                                  {"SWAP_TENANT": "test-tenant",
                                   "CONFIRM_DIR": tmp}, clear=False))
            with pdir, pen, env:
                a = make_addon()
                with mock.patch.object(sa, "_summons_append",
                                       side_effect=OSError("disk gone")):
                    self.assertEqual(
                        a._file_approval("github", "github.com", "POST",
                                         "/repos/x", "no-grant"), [])
                outbox = os.path.join(tmp, "summons-outbox.jsonl")
                pending_d = os.path.join(tmp, "pending")
                n = sa._summons_sweep(outbox=outbox, pending_d=pending_d)
                self.assertEqual(n, 1)
                rows = [json.loads(line) for line in self._read_rows(outbox)]
                self.assertEqual(len(rows), 1)
                filed = json.loads(
                    list(Path(pending_d).glob("*.json"))[0].read_text())
                self.assertEqual(rows[0]["aid"], filed["id"])


class SummonsSweepCliTests(unittest.TestCase):
    """`python3 swap_addon.py --summons-sweep` drives the timer unit."""

    def test_cli_recovers_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            pending_d = os.path.join(tmp, "pending")
            os.makedirs(pending_d)
            item = {"id": "aaaabbbbccccdddd",
                    "created": "2026-09-26T00:00:00+00:00",
                    "expires": "2026-09-26T01:00:00+00:00",
                    "summary": "POST api.example /x for cred",
                    "credential": "cred", "host": "api.example",
                    "method": "POST"}
            with open(os.path.join(pending_d, "aaaabbbbccccdddd.json"),
                      "w") as f:
                json.dump(item, f)
            addon = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "swap_addon.py")
            env = dict(os.environ, SWAP_APPROVALS_DIR=tmp,
                       SWAP_TENANT="test-tenant")
            env.pop("SWAP_SUMMONS_OUTBOX", None)
            proc = subprocess.run(
                [sys.executable, addon, "--summons-sweep"],
                capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("recovered 1", proc.stdout)
            rows = [json.loads(line) for line in
                    open(os.path.join(tmp, "summons-outbox.jsonl"))
                    .read().splitlines() if line.strip()]
            self.assertEqual(rows[0]["aid"], "aaaabbbbccccdddd")


if __name__ == "__main__":
    unittest.main()

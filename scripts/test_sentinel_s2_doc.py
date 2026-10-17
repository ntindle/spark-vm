#!/usr/bin/env python3
"""Pin: docs/SENTINEL_TELEMETRY_SURFACES.md S2 row enumerates the swap.log writer shapes.

The S2 row is the sentinel consumer's contract for `swap.log`: a shipper
parses each line by which fields are present, and joins a flow's lines by
`flow=`. When a writer emits a shape the row does not name, the consumer
misreads it — the `refused=egress` SSRF shape shipped without a row entry
until this change, even though the row's own joinability story ("join a
flow's `swapped=` lines to its later refusal lines") is exactly the egress
case.

What these tests pin, at writer-method level: (a) the set of SwapAddon
methods that open the audit log is exactly the six known writers, so a
seventh writer fails; (b) every `refused=<literal>` the row names appears
among the values the six writers emit, so a row claim no writer emits
fails; (c) each writer emits exactly its documented field set.
`_audit_note` token values stay exemplified, not enumerated: a new
verbatim token alone does not fail the pin — the row's generic
`refused=<token|...>` family covers it.

Stdlib-only. Run from the repo root: `python3 -m pytest scripts/test_sentinel_s2_doc.py`.
"""

import inspect
import logging
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "SENTINEL_TELEMETRY_SURFACES.md"

sys.path.insert(0, str(ROOT / "proxy"))
import swap_addon as sa  # noqa: E402

sa.log.propagate = False  # keep addon warnings out of test output
sa.log.addHandler(logging.NullHandler())


def _s2_row():
    with open(DOC_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith("| S2 |"):
                return line
    raise AssertionError("no S2 row in %s" % DOC_PATH)


def _parse(line):
    # Strict per-token split is sound here (not a general logfmt
    # parser): every value passes through _sanitize_audit_field, whose
    # _AUDIT_FIELD_ALLOW_RE strips everything outside [!-~], so values
    # can never contain spaces; None renders as "-".
    fields = {}
    for token in line.strip().split():
        key, _, value = token.partition("=")
        assert key and value, "unparseable audit token %r in %r" % (token, line)
        fields[key] = value
    return fields


def _emit(call):
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "swap.log"
        with mock.patch.object(sa, "LOG_FILE", log_file):
            call()
        return log_file.read_text(encoding="utf-8").strip().splitlines()


def _addon():
    addon = sa.SwapAddon.__new__(sa.SwapAddon)
    addon._current_egress_ip = None
    return addon


def _emit_all_lines():
    """Drive all six writers once against one temp log; return parsed lines."""
    addon = _addon()
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "swap.log"
        with mock.patch.object(sa, "LOG_FILE", log_file):
            addon._audit("example.com", "hsurr:github", flow_id="f1")
            # Issue #199: the batch writer emits the same `swapped=`
            # shape as _audit, in a single open.
            addon._audit_batch([("example.com", "hsurr:github", "f1")])
            addon._audit_refused(
                "example.com", "github", "unknown-credential", flow_id="f1")
            addon._audit_note(
                "example.com", "json-swap", "invalid-json-after-swap",
                flow_id="f1")
            addon._audit_authority_mismatch(
                "example.com", "evil.example", "203.0.113.9", flow_id="f1")
            addon._audit_ssrf_refused(
                "example.com", "203.0.113.9", "private-range", flow_id="f1")
        return [_parse(line)
                for line in log_file.read_text(encoding="utf-8")
                .strip().splitlines()]


class TestSentinelS2Doc(unittest.TestCase):
    def test_s2_row_names_all_five_writer_shapes(self):
        row = _s2_row()
        for needle in (
            "swapped=",
            "tenant=",
            "refused=<token",
            "hsurr:name",
            "refused=authority-mismatch",
            "refused=egress",
            "flow=<f>",
            "never left the box",
        ):
            self.assertIn(needle, row, "S2 row omits %r" % needle)

    def test_audit_writer_set_is_exactly_the_six_known(self):
        writers = set()
        for name, fn in inspect.getmembers(
                sa.SwapAddon, predicate=inspect.isfunction):
            # Call-pattern scan, not a bare-name scan: a bare
            # "_open_audit_log" would also match comment mentions —
            # e.g. the line-399 comment inside module-level
            # _stamp_expired_consumed, which illustrates the mention
            # class but sits outside the scanned SwapAddon methods, so
            # it could never be a hit of this scan.
            if "with _open_audit_log()" in inspect.getsource(fn):
                writers.add(name)
        self.assertEqual(
            writers,
            {"_audit", "_audit_batch", "_audit_refused", "_audit_note",
             "_audit_authority_mismatch", "_audit_ssrf_refused"})

    def test_s2_row_refused_literals_match_emitted_values(self):
        row = _s2_row()
        # `refused=<token|...>` is a template, not a literal: the `<`
        # keeps it out of this match, as intended.
        literals = set(
            re.findall(r"refused=([A-Za-z0-9][A-Za-z0-9_-]*)", row))
        emitted = {f["refused"] for f in _emit_all_lines()
                   if "refused" in f}
        self.assertTrue(literals, "no refused= literals found in S2 row")
        self.assertTrue(
            literals <= emitted,
            "S2 row names refused= values no writer emits: %s"
            % sorted(literals - emitted))

    def test_audit_swapped_shape(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit(
                "example.com", "hsurr:github", flow_id="f1"))
        self.assertEqual(len(lines), 1)
        fields = _parse(lines[0])
        self.assertEqual(
            set(fields), {"ts", "host", "swapped", "ip", "tenant", "flow"})
        self.assertEqual(fields["swapped"], "hsurr:github")
        self.assertEqual(fields["flow"], "f1")
        # Issue #1653: tenant is the unverified hint, never an
        # identity claim — the pin is presence + sanitization, not value.
        self.assertIn("tenant", fields)

    def test_audit_batch_shape(self):
        """Issue #199: the batch writer emits the same `swapped=` line
        shape as _audit — one open, not one per line, must not change
        what the sentinel consumer parses."""
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_batch(
                [("example.com", "hsurr:github", "f1"),
                 ("example.com", "hsurr:github", "f2")]))
        self.assertEqual(len(lines), 2)
        for line, flow in zip(lines, ("f1", "f2")):
            fields = _parse(line)
            self.assertEqual(
                set(fields), {"ts", "host", "swapped", "ip", "tenant",
                              "flow"})
            self.assertEqual(fields["swapped"], "hsurr:github")
            self.assertEqual(fields["flow"], flow)

    def test_audit_refused_shape(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_refused(
                "example.com", "github", "unknown-credential", flow_id="f1"))
        self.assertEqual(len(lines), 1)
        fields = _parse(lines[0])
        self.assertEqual(
            set(fields), {"ts", "host", "refused", "reason", "ip", "flow"})
        self.assertEqual(fields["refused"], "hsurr:github")
        self.assertEqual(fields["reason"], "unknown-credential")

    def test_audit_note_shape(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_note(
                "example.com", "json-swap", "invalid-json-after-swap",
                flow_id="f1"))
        self.assertEqual(len(lines), 1)
        fields = _parse(lines[0])
        self.assertEqual(
            set(fields), {"ts", "host", "refused", "reason", "ip", "flow"})
        # _audit_note writes the token verbatim: no hsurr: prefix.
        self.assertEqual(fields["refused"], "json-swap")

    def test_audit_authority_mismatch_shape(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_authority_mismatch(
                "example.com", "evil.example", "203.0.113.9", flow_id="f1"))
        self.assertEqual(len(lines), 1)
        fields = _parse(lines[0])
        self.assertEqual(
            set(fields),
            {"ts", "host", "refused", "authority", "ip", "flow"})
        self.assertEqual(fields["refused"], "authority-mismatch")
        self.assertEqual(fields["authority"], "evil.example")
        self.assertNotIn("reason", fields)

    def test_audit_ssrf_refused_shape(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_ssrf_refused(
                "example.com", "203.0.113.9", "private-range", flow_id="f1"))
        self.assertEqual(len(lines), 1)
        fields = _parse(lines[0])
        self.assertEqual(
            set(fields), {"ts", "host", "refused", "reason", "ip", "flow"})
        self.assertEqual(fields["refused"], "egress")
        self.assertEqual(fields["reason"], "private-range")
        self.assertEqual(fields["flow"], "f1")

    def test_flow_none_renders_dash(self):
        addon = _addon()
        lines = _emit(
            lambda: addon._audit_ssrf_refused(
                "example.com", "203.0.113.9", "private-range"))
        self.assertEqual(len(lines), 1)
        self.assertEqual(_parse(lines[0])["flow"], "-")


if __name__ == "__main__":
    unittest.main()

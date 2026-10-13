"""Tests for credlib name validation (security sweep 2026-09-19).

Credential and entry names reach filesystem paths in fill_secret.py
(/home/swapd/secrets/<name>), so dynamic_credential_entry validates
them at the choke point. An unvalidated name ("../../etc/passwd",
"../.mitmproxy/mitmproxy-ca-key.pem") was a path-traversal read as
swapd. Run with:
    python3 -m unittest credlib.test_credlib -v   (from the repo root)
"""
import ctypes
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dynamic_credentials import (
    DynamicCredentialError,
    dynamic_credential_entry,
)
import fill_secret


class NameValidationTests(unittest.TestCase):

    def test_traversal_names_rejected(self):
        """Path-traversal names must never reach the filesystem."""
        for bad in ("../etc/passwd",
                    "../../etc/shadow",
                    "../.mitmproxy/mitmproxy-ca-key.pem",
                    "a/b",
                    "..",
                    ".",
                    "name;rm",
                    "name\ninjected",
                    ""):
            with self.assertRaises(DynamicCredentialError, msg=bad):
                dynamic_credential_entry(bad)
            with self.assertRaises(DynamicCredentialError, msg=bad):
                dynamic_credential_entry("ok-name", entry_name=bad)

    def test_legacy_long_names_accepted(self):
        """Read path is legacy-tolerant: the swapd writers enforce
        charset-only (no 64-char cap), and swap_addon still serves
        pre-#150 long names — so surrogate building must accept them.
        (2026-09-23 arch deep-read finding.)"""
        long_name = "x" * 100
        e = dynamic_credential_entry(long_name, entry_name="y" * 100)
        self.assertEqual(e["surrogate"],
                         "hsurr:%s:%s" % (long_name, "y" * 100))
        # fill_secret's filesystem read validates through the same choke
        # point: a legacy name must reach the (stubbed) store read, not
        # raise at validation. The read goes through the narrow
        # cred-store-get reader (issue #669) — the name is its final
        # argv element.
        class Proc:
            returncode = 0
            stdout = b"tok"
            stderr = b""
        real_run = fill_secret.subprocess.run
        seen = []
        def fake_run(argv, **kwargs):
            seen.append(argv)
            return Proc()
        fill_secret.subprocess.run = fake_run
        try:
            self.assertEqual(fill_secret._read_value(long_name, "access_token"),
                             "tok")
        finally:
            fill_secret.subprocess.run = real_run
        self.assertTrue(any("/usr/local/bin/cred-store-get" in a
                            and a[-1] == long_name for a in seen))

    def test_valid_names_still_resolve(self):
        """Legitimate names are unaffected; surrogate format unchanged."""
        e = dynamic_credential_entry("github", entry_name="access_token")
        self.assertEqual(e["surrogate"], "hsurr:github:access_token")
        e = dynamic_credential_entry("openai-api_key-2")
        self.assertEqual(e["surrogate"], "hsurr:openai-api_key-2:access_token")
        e = dynamic_credential_entry("a")
        self.assertEqual(e["surrogate"], "hsurr:a:access_token")

    def test_non_string_names_rejected(self):
        for bad in (None, 123, ["x"], {"n": "x"}):
            with self.assertRaises(DynamicCredentialError, msg=repr(bad)):
                dynamic_credential_entry(bad)


class ReadValueVerbatimTests(unittest.TestCase):
    """#88: _read_value must return the stored bytes exactly — no strip().

    Every supported store path chomps one trailing newline at write time,
    so the file contents ARE the intended value. Stubs subprocess.run (the
    sudo cat); no real secrets, no sudo needed."""

    def _read(self, stored: bytes) -> str:
        class Proc:
            returncode = 0
            stdout = stored
        real_run = fill_secret.subprocess.run
        fill_secret.subprocess.run = lambda *a, **k: Proc()
        try:
            return fill_secret._read_value("gh", "access_token")
        finally:
            fill_secret.subprocess.run = real_run

    def test_trailing_newlines_preserved(self):
        self.assertEqual(self._read(b"tok\n\n"), "tok\n\n")

    def test_whitespace_only_value_preserved(self):
        self.assertEqual(self._read(b"  \n"), "  \n")

    def test_leading_and_trailing_spaces_preserved(self):
        self.assertEqual(self._read(b" tok "), " tok ")

    def test_plain_value_unchanged(self):
        self.assertEqual(self._read(b"tok"), "tok")

    def test_missing_credential_raises(self):
        class Proc:
            returncode = 1
            stdout = b""
            stderr = b""
        real_run = fill_secret.subprocess.run
        fill_secret.subprocess.run = lambda *a, **k: Proc()
        try:
            with self.assertRaises(DynamicCredentialError):
                fill_secret._read_value("gh", "access_token")
        finally:
            fill_secret.subprocess.run = real_run

    def test_reader_failure_surfaces_reader_stderr(self):
        """#147 class: a denied/broken read must not mask as plain
        \"not set\" — the narrow reader's stderr (which never carries
        secret values) is surfaced in the error."""
        class Proc:
            returncode = 1
            stdout = b""
            stderr = b"sudo: a password is required\n"
        real_run = fill_secret.subprocess.run
        fill_secret.subprocess.run = lambda *a, **k: Proc()
        try:
            with self.assertRaises(DynamicCredentialError) as ctx:
                fill_secret._read_value("gh", "access_token")
        finally:
            fill_secret.subprocess.run = real_run
        self.assertIn("reader: sudo: a password is required", str(ctx.exception))
        self.assertIn("cred set gh", str(ctx.exception))


class HumanContextGuardTests(unittest.TestCase):
    """#671: fill_secret's human-context boundary must be code, not a
    docstring. The guard refuses when the process is neither on a real
    terminal nor explicitly opted in."""

    class _NonTty:
        def isatty(self):
            return False

    class _Tty:
        def isatty(self):
            return True

    def _guard_without_tty_or_optin(self):
        real_stdin, real_env = sys.stdin, os.environ.pop(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
        sys.stdin = self._NonTty()
        try:
            with self.assertRaises(DynamicCredentialError) as ctx:
                fill_secret._require_human_context()
        finally:
            sys.stdin = real_stdin
            if real_env is not None:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env
        return str(ctx.exception)

    def test_refuses_agent_context(self):
        """No terminal + no opt-in: refuse, and point at the swap-proxy
        path and the opt-in so a human operator knows both exits."""
        msg = self._guard_without_tty_or_optin()
        self.assertIn("SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1", msg)
        self.assertIn("hsurr:<name>", msg)
        self.assertIn("#671", msg)

    def test_refuses_when_stdin_is_none(self):
        real_stdin, real_env = sys.stdin, os.environ.pop(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
        sys.stdin = None
        try:
            with self.assertRaises(DynamicCredentialError):
                fill_secret._require_human_context()
        finally:
            sys.stdin = real_stdin
            if real_env is not None:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env

    def test_tty_stdin_is_human_context(self):
        """A real terminal on stdin is the human-driven case."""
        real_stdin, real_env = sys.stdin, os.environ.pop(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
        sys.stdin = self._Tty()
        try:
            fill_secret._require_human_context()  # must not raise
        finally:
            sys.stdin = real_stdin
            if real_env is not None:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env

    def test_env_optin_allows_isolated_automation(self):
        """SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1 is the explicit opt-in for
        isolated (non-interactive) automation that owns the HONEST LIMIT."""
        real_stdin, real_env = sys.stdin, os.environ.get(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE)
        sys.stdin = self._NonTty()
        os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = "1"
        try:
            fill_secret._require_human_context()  # must not raise
        finally:
            sys.stdin = real_stdin
            if real_env is None:
                os.environ.pop(fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
            else:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env

    class _RaisingTty:
        """isatty() itself blows up (embedded interpreters, stdin-replacing
        harnesses) — the guard must still refuse with ITS error, not leak
        the unexpected exception type."""
        def isatty(self):
            raise AttributeError("no isatty here")

    def test_isatty_exception_still_refuses(self):
        """An isatty() that raises (e.g. AttributeError from an
        isatty-less stdin) must produce the guard's DynamicCredentialError
        refusal, not the raw exception — the gate refuses uniformly."""
        real_stdin, real_env = sys.stdin, os.environ.pop(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
        sys.stdin = self._RaisingTty()
        try:
            with self.assertRaises(DynamicCredentialError) as ctx:
                fill_secret._require_human_context()
        finally:
            sys.stdin = real_stdin
            if real_env is not None:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env
        self.assertIn("fill_secret refused", str(ctx.exception))

    def test_fill_secret_entry_point_enforces_the_guard(self):
        """The guard sits at the top of fill_secret, not in the
        docstring — an agent-context call never reaches the read. The
        message marker proves the GUARD refused: without it, the same
        call would raise DynamicCredentialError with "credential 'gh'
        not set" from the read path instead."""
        real_stdin, real_env = sys.stdin, os.environ.pop(
            fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
        sys.stdin = self._NonTty()
        try:
            with self.assertRaises(DynamicCredentialError) as ctx:
                fill_secret.fill_secret(None, "#x", "gh")
        finally:
            sys.stdin = real_stdin
            if real_env is not None:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env
        self.assertIn("fill_secret refused", str(ctx.exception))


class MemoryHygieneTests(unittest.TestCase):
    """#730: overwrite-on-delete for fill_secret's secret buffers.

    `del` alone never zeroizes a CPython buffer — these tests prove the
    buffers are actually overwritten, by reading the raw memory back
    through the verified span. Stubs subprocess.run (the sudo cat); no
    real secrets, no sudo needed."""

    def _assert_zeroed(self, s, pristine):
        """Assert s's character buffer is all zeros. The span is derived
        from `pristine` — an equal-content str captured before scrubbing —
        because deriving it from the zeroed object itself would
        mis-detect kind (zeroed content reads as ascii). Span layout
        depends only on length+kind, so the pristine copy's span applies
        to s."""
        span = fill_secret._str_buffer_span(pristine)
        self.assertIsNotNone(span, "span must verify for test-built str")
        off, ln = span
        self.assertEqual(ctypes.string_at(id(s) + off, ln), b"\x00" * ln)

    def _read_with_stub(self, stored: bytes):
        # fill_secret.subprocess IS the global subprocess module, so the
        # stub must also serve dynamic_credential_entry's registry read
        # (sudo cat of the registry path) — an empty registry means
        # every name takes defaults.
        class StoreProc:
            returncode = 0
            stdout = stored
            stderr = b""
        class RegProc:
            returncode = 0
            stdout = b"{}"
            stderr = b""
        real_run = fill_secret.subprocess.run
        def fake_run(argv, **kwargs):
            if "/usr/bin/cat" in argv:
                return RegProc()
            return StoreProc()
        fill_secret.subprocess.run = fake_run
        return real_run

    def _fill_with_optin(self, page, stored: bytes, entry="access_token"):
        real_run = self._read_with_stub(stored)
        real_env = os.environ.get(fill_secret._FILL_SECRET_HUMAN_OVERRIDE)
        os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = "1"
        try:
            fill_secret.fill_secret(page, "#pw", "gh", entry)
        finally:
            fill_secret.subprocess.run = real_run
            if real_env is None:
                os.environ.pop(fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
            else:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env

    class _FakePage:
        def __init__(self):
            self.fills = []
            self.snapshots = []
        def fill(self, selector, value):
            # Snapshot the bytes the page actually received (pre-scrub),
            # and keep a handle to the exact str object for the
            # post-scrub buffer assertion.
            self.snapshots.append(value.encode("utf-8"))
            self.fills.append((selector, value))

    def test_zero_str_zeroes_ascii_buffer(self):
        s = "".join(["s3cr3t-", "x" * 40])  # fresh, never interned
        pristine = "".join(["s3cr3t-", "x" * 40])
        fill_secret._zero_str(s)
        self._assert_zeroed(s, pristine)

    def test_zero_str_zeroes_non_ascii_buffer(self):
        s = "".join(["pâsswörd-🔑-fin"])
        pristine = "".join(["pâsswörd-🔑-fin"])
        fill_secret._zero_str(s)
        self._assert_zeroed(s, pristine)

    def test_zero_str_refuses_unverifiable_layout(self):
        """A str subclass has extra header bytes — the span probe must
        fail and the value must be left untouched, never corrupted."""
        class S(str):
            pass
        s = S("hello-subclass")
        fill_secret._zero_str(s)
        self.assertEqual(s, "hello-subclass")

    def test_zero_str_empty_noop(self):
        # Must not raise and must not touch the interned empty string.
        fill_secret._zero_str("")
        self.assertEqual("", "")

    def test_zero_str_never_raises(self):
        fill_secret._zero_str(None)
        fill_secret._zero_str(123)

    def test_scrub_bytearray_zeroes(self):
        buf = bytearray(b"s3cr3t-bytes")
        fill_secret._scrub_bytearray(buf)
        self.assertEqual(bytes(buf), b"\x00" * 12)

    def test_fill_secret_scrubs_value_after_fill(self):
        """End to end: the page receives the verbatim secret (#88), and
        afterwards the exact str object's buffer is all zeros."""
        page = self._FakePage()
        self._fill_with_optin(page, b"  s3cr3t-whitespace  \n")
        self.assertEqual(page.fills[0][0], "#pw")
        # What the page got, byte-exact including whitespace (#88).
        self.assertEqual(page.snapshots[0], b"  s3cr3t-whitespace  \n")
        # What remains in this process afterwards: zeros.
        self._assert_zeroed(page.fills[0][1],
                            page.snapshots[0].decode("utf-8"))

    def test_fill_secret_scrubs_on_fill_exception(self):
        """A raising page.fill must not skip the scrub (finally)."""
        class BoomPage:
            def fill(self, selector, value):
                self.value = value
                raise RuntimeError("boom")
        page = BoomPage()
        real_run = self._read_with_stub(b"s3cr3t")
        real_env = os.environ.get(fill_secret._FILL_SECRET_HUMAN_OVERRIDE)
        os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = "1"
        try:
            with self.assertRaises(RuntimeError):
                fill_secret.fill_secret(page, "#pw", "gh")
        finally:
            fill_secret.subprocess.run = real_run
            if real_env is None:
                os.environ.pop(fill_secret._FILL_SECRET_HUMAN_OVERRIDE, None)
            else:
                os.environ[fill_secret._FILL_SECRET_HUMAN_OVERRIDE] = real_env
        self._assert_zeroed(page.value, "s3cr3t")

    def test_multi_entry_losers_scrubbed(self):
        """Non-requested entries are scrubbed during the read — only the
        kept value survives until after the fill."""
        real_zero = fill_secret._zero_str
        seen = []
        def spy(s):
            span = fill_secret._str_buffer_span(s)
            snap = (ctypes.string_at(id(s) + span[0], span[1])
                    if span is not None else None)
            seen.append((s, snap))  # keep the exact object, pre-zero bytes
            real_zero(s)
        fill_secret._zero_str = spy
        page = self._FakePage()
        try:
            self._fill_with_optin(
                page, b"#hsurr:multi\naccess_token=tok-AAA\nbackup=tok-BBB\n")
        finally:
            fill_secret._zero_str = real_zero
        self.assertEqual(page.snapshots[0], b"tok-AAA")
        # The loser's buffer is actually zeros now (not just "visited").
        losers = [o for o, snap in seen if snap == b"tok-BBB"]
        self.assertEqual(len(losers), 1)
        self._assert_zeroed(losers[0], "tok-BBB")
        # And the kept value's buffer is zeros after the fill.
        self._assert_zeroed(page.fills[0][1], "tok-AAA")

    def test_multi_entry_missing_entry_scrubs_before_raise(self):
        """A 'no entry' raise must not leave the parsed values behind."""
        real_zero = fill_secret._zero_str
        seen = []
        def spy(s):
            span = fill_secret._str_buffer_span(s)
            snap = (ctypes.string_at(id(s) + span[0], span[1])
                    if span is not None else None)
            seen.append((s, snap))
            real_zero(s)
        fill_secret._zero_str = spy
        real_run = self._read_with_stub(
            b"#hsurr:multi\naccess_token=tok-AAA\n")
        try:
            with self.assertRaises(DynamicCredentialError):
                fill_secret._read_value("gh", "nope")
        finally:
            fill_secret._zero_str = real_zero
            fill_secret.subprocess.run = real_run
        losers = [o for o, snap in seen if snap == b"tok-AAA"]
        self.assertEqual(len(losers), 1)
        self._assert_zeroed(losers[0], "tok-AAA")


if __name__ == "__main__":
    unittest.main()

"""Tests for proxy/build_ca_bundle.py (issue #144).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. The privileged
paths (/etc/ssl/..., /home/swapd/...) are overridden via --sys/--ca/--dest,
and ownership is the running user (same trick as test_safe_install.py).
"""
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent / "build_ca_bundle.py")


def _me():
    return pwd.getpwuid(os.getuid()).pw_name


class TestBuildCaBundle(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, "--owner", _me(), "--group", _me()]
            + list(args),
            capture_output=True, text=True)

    def _files(self, d):
        sys_bundle = Path(d) / "ca-certificates.crt"
        sys_bundle.write_bytes(b"SYSTEM-BUNDLE\n")
        ca = Path(d) / "mitmproxy-ca-cert.pem"
        ca.write_bytes(b"-----BEGIN CERTIFICATE-----\nCA\n")
        return sys_bundle, ca

    def test_bundle_concats_system_and_ca(self):
        with tempfile.TemporaryDirectory() as d:
            sys_bundle, ca = self._files(d)
            dest = Path(d) / "ca-bundle.crt"
            r = self._run("--sys", str(sys_bundle), "--ca", str(ca),
                          "--dest", str(dest))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(dest.read_bytes(),
                             b"SYSTEM-BUNDLE\n"
                             b"-----BEGIN CERTIFICATE-----\nCA\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o644)
            self.assertFalse(dest.is_symlink())

    def test_ca_only_writes_just_the_ca(self):
        with tempfile.TemporaryDirectory() as d:
            _, ca = self._files(d)
            dest = Path(d) / "swapd-mitmproxy.crt"
            r = self._run("--ca-only", "--ca", str(ca), "--dest", str(dest))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(dest.read_bytes(),
                             b"-----BEGIN CERTIFICATE-----\nCA\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o644)

    def test_symlink_ca_is_refused_and_secret_not_leaked(self):
        # The #144 attack: swapd plants ca -> a root-readable secret; the
        # old `cat` would follow it into the world-readable bundle.
        with tempfile.TemporaryDirectory() as d:
            sys_bundle, ca = self._files(d)
            secret = Path(d) / "shadow"
            secret.write_bytes(b"root:$6$SECRET-HASH\n")
            ca.unlink()
            ca.symlink_to(secret)
            dest = Path(d) / "ca-bundle.crt"
            r = self._run("--sys", str(sys_bundle), "--ca", str(ca),
                          "--dest", str(dest))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("symlink", r.stderr)
            self.assertFalse(dest.exists(), "no bundle on refusal")
            self.assertNotIn("SECRET-HASH", r.stderr + r.stdout)

    def test_symlink_ca_refused_in_ca_only_mode(self):
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "shadow"
            secret.write_bytes(b"root:$6$SECRET-HASH\n")
            ca = Path(d) / "mitmproxy-ca-cert.pem"
            ca.symlink_to(secret)
            dest = Path(d) / "swapd-mitmproxy.crt"
            r = self._run("--ca-only", "--ca", str(ca), "--dest", str(dest))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse(dest.exists())

    def test_dangling_symlink_ca_is_refused_not_skipped(self):
        # A dangling symlink is not a first deploy -- fail closed.
        with tempfile.TemporaryDirectory() as d:
            sys_bundle, _ = self._files(d)
            ca = Path(d) / "mitmproxy-ca-cert.pem"
            ca.unlink()
            ca.symlink_to(Path(d) / "nonexistent")
            dest = Path(d) / "ca-bundle.crt"
            r = self._run("--sys", str(sys_bundle), "--ca", str(ca),
                          "--dest", str(dest))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse(dest.exists())

    def test_missing_ca_bundle_mode_skips_loudly(self):
        # First deploy: no CA yet -- keep the old skip behavior, loudly.
        with tempfile.TemporaryDirectory() as d:
            sys_bundle, _ = self._files(d)
            dest = Path(d) / "ca-bundle.crt"
            r = self._run("--sys", str(sys_bundle),
                          "--ca", str(Path(d) / "nope.pem"),
                          "--dest", str(dest))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("WARNING", r.stderr)
            self.assertFalse(dest.exists(), "no bundle built on first deploy")

    def test_missing_ca_ca_only_mode_fails(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "swapd-mitmproxy.crt"
            r = self._run("--ca-only", "--ca", str(Path(d) / "nope.pem"),
                          "--dest", str(dest))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse(dest.exists())

    def test_symlink_dest_is_refused(self):
        # Destination write goes through safe_install's refusal.
        with tempfile.TemporaryDirectory() as d:
            sys_bundle, ca = self._files(d)
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            dest = Path(d) / "ca-bundle.crt"
            dest.symlink_to(target)
            r = self._run("--sys", str(sys_bundle), "--ca", str(ca),
                          "--dest", str(dest))
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertEqual(target.read_text(), "precious\n")


if __name__ == "__main__":
    unittest.main()

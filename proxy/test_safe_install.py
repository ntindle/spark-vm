"""Tests for proxy/safe_install.py (deploy.sh symlink-following writes).

All hermetic: scratch tmpdirs only, no root, no /home/swapd. fchown to the
*current* uid/gid is unprivileged-legal, so the owner is monkeypatched to
the running user via pwd.getpwnam (same trick as test_enforce_secrets_dir.py).
"""
import io
import errno
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safe_install as si

SCRIPT = str(Path(__file__).resolve().parent / "safe_install.py")


def _self_user():
    me = pwd.getpwuid(os.getuid())
    fake = mock.Mock()
    fake.pw_uid = me.pw_uid
    fake.pw_gid = me.pw_gid
    return me.pw_name, fake


class TestSafeInstall(unittest.TestCase):
    def _run(self, *args, **kwargs):
        name, fake = _self_user()
        kwargs.setdefault("owner", name)
        with mock.patch.object(pwd, "getpwnam", return_value=fake):
            return si.safe_install(*args, **kwargs)

    def test_write_creates_with_content_mode(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "new.txt"
            self._run(str(dest), content=b"hello\n", mode=0o640)
            self.assertEqual(dest.read_bytes(), b"hello\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o640)

    def test_write_truncates_existing(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "f.txt"
            dest.write_text("old content that is longer")
            self._run(str(dest), content=b"new\n", mode=0o600)
            self.assertEqual(dest.read_bytes(), b"new\n")
            self.assertTrue(dest.is_file() and not dest.is_symlink())

    def test_symlink_is_refused_and_target_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            os.chmod(target, 0o644)
            link = Path(d) / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(SystemExit) as cm:
                self._run(str(link), content=b"evil\n", mode=0o600)
            self.assertEqual(cm.exception.code, 2)
            # The write must not have gone through to the target.
            self.assertEqual(target.read_bytes(), b"precious\n")
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o644)
            self.assertTrue(link.is_symlink())

    def test_dangling_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "dangling"
            link.symlink_to(Path(d) / "no-such-target")
            with self.assertRaises(SystemExit):
                self._run(str(link), content=b"x\n", mode=0o600)

    def test_rewrite_replaces_inode_atomically(self):
        # Issue #301: the rewrite must be an atomic rename, not in-place
        # O_TRUNC -- the inode changes (a new file was installed) and no
        # temp file is left behind.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "ca-bundle.crt"
            dest.write_bytes(b"old bundle\n")
            old_ino = os.stat(dest).st_ino
            self._run(str(dest), content=b"new bundle\n", mode=0o644)
            self.assertEqual(dest.read_bytes(), b"new bundle\n")
            self.assertNotEqual(os.stat(dest).st_ino, old_ino)
            self.assertEqual(
                [p.name for p in Path(d).iterdir()
                 if p.name.startswith(".safe_install.")],
                [])

    def test_reader_never_sees_partial_content(self):
        # Issue #301's contract: a racing reader must observe only whole
        # old or whole new content -- never an O_TRUNC-ed empty or partial
        # file. The reader must actually observe BOTH values, so the test
        # cannot pass vacuously on a race that never happened.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "bundle.crt"
            old = b"A" * 65536
            new = b"B" * 65536
            dest.write_bytes(old)
            violations = []
            seen = set()
            stop = threading.Event()

            def reader():
                while not stop.is_set():
                    try:
                        data = dest.read_bytes()
                    except OSError:
                        continue
                    seen.add(data)
                    if data not in (old, new):
                        violations.append(len(data))

            t = threading.Thread(target=reader)
            t.start()
            try:
                it = 0
                while (len(seen) < 2 or it < 20) and it < 200:
                    self._run(str(dest), content=new, mode=0o644)
                    self._run(str(dest), content=old, mode=0o644)
                    it += 2
            finally:
                stop.set()
                t.join()
            self.assertEqual(violations, [],
                             "reader saw partial content: %r" % violations[:5])
            self.assertEqual(seen, {old, new},
                             "reader never observed a race -- test vacuous")
            self.assertEqual(
                [p.name for p in Path(d).iterdir()
                 if p.name.startswith(".safe_install.")],
                [])

    def test_create_only_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "grants.json"
            dest.write_text('{"grants": ["real"]}\n')
            os.chmod(dest, 0o644)
            result = self._run(str(dest), content=b'{"grants": []}\n',
                               create_only=True, mode=0o600)
            self.assertEqual(result, "enforced")
            # Content preserved, mode still enforced.
            self.assertEqual(dest.read_bytes(), b'{"grants": ["real"]}\n')
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_create_only_race_lost_enforces_and_cleans_temp(self):
        # The atomic create-only (os.link, EEXIST = already there) keeps the
        # old enforce-on-existing behavior and leaves no temp behind.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "grants.json"
            dest.write_text('{"grants": ["real"]}\n')
            os.chmod(dest, 0o644)
            result = self._run(str(dest), content=b'{"grants": []}\n',
                               create_only=True, mode=0o600)
            self.assertEqual(result, "enforced")
            self.assertEqual(dest.read_bytes(), b'{"grants": ["real"]}\n')
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)
            self.assertEqual(
                [p.name for p in Path(d).iterdir()
                 if p.name.startswith(".safe_install.")],
                [])

    def test_create_only_creates_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "grants.json"
            result = self._run(str(dest), content=b'{"grants": []}\n',
                               create_only=True, mode=0o600)
            self.assertEqual(result, "created")
            self.assertEqual(dest.read_bytes(), b'{"grants": []}\n')
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_enforce_only_mode(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "swap.log"
            dest.write_text("log line\n")
            os.chmod(dest, 0o644)
            result = self._run(str(dest), mode=0o600)
            self.assertEqual(result, "enforced")
            self.assertEqual(dest.read_bytes(), b"log line\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

    def test_enforce_only_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.log"
            target.write_text("log\n")
            os.chmod(target, 0o644)
            link = Path(d) / "link.log"
            link.symlink_to(target)
            with self.assertRaises(SystemExit):
                self._run(str(link), mode=0o600)
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o644)

    def test_cli_stdin_and_src(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "out.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--mode", "0600",
                 str(dest)],
                input=b"via stdin\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest.read_bytes(), b"via stdin\n")

            src = Path(d) / "src.txt"
            src.write_text("via src\n")
            dest2 = Path(d) / "out2.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--src", str(src), "--mode", "0644",
                 str(dest2)], capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest2.read_bytes(), b"via src\n")
            self.assertEqual(stat.S_IMODE(os.stat(dest2).st_mode), 0o644)

    def test_cli_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "target.txt"
            target.write_text("precious\n")
            link = Path(d) / "link.txt"
            link.symlink_to(target)
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", str(link)],
                input=b"evil\n", capture_output=True, timeout=30)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(target.read_bytes(), b"precious\n")

    def test_cli_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "n.txt"
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--create-only",
                 "--mode", "0600", str(dest)],
                input=b"first\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            r = subprocess.run(
                [sys.executable, SCRIPT, "--stdin", "--create-only",
                 "--mode", "0600", str(dest)],
                input=b"second\n", capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertEqual(dest.read_bytes(), b"first\n")

    def test_install_to_directory_fails_clean(self):
        # Installing onto a directory must fail loudly and leave no
        # staging debris behind.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "adir"
            dest.mkdir()
            with self.assertRaises(OSError):
                self._run(str(dest), content=b"x\n", mode=0o600)
            self.assertTrue(dest.is_dir())
            self.assertEqual(
                [p.name for p in Path(d).iterdir()
                 if p.name.startswith(".safe_install.")],
                [])

    def test_install_addresses_temp_by_dirfd_not_path(self):
        # Contract test for the #301 substitution fix: the install must
        # address the staged temp as (dirfd, name), never by re-resolving a
        # parent-dir path -- so a parent-dir attacker cannot substitute it.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "f.txt"
            calls = []
            real_rename = si.os.rename

            def spy(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                calls.append((src, dst, src_dir_fd, dst_dir_fd))
                return real_rename(src, dst, src_dir_fd=src_dir_fd,
                                   dst_dir_fd=dst_dir_fd)

            with mock.patch.object(si.os, "rename", spy):
                self._run(str(dest), content=b"x\n", mode=0o600)
            self.assertEqual(dest.read_bytes(), b"x\n")
            self.assertTrue(calls, "rename was never called")
            for src, _dst, sfd, dfd in calls:
                self.assertEqual(src, si._TMP_NAME)
                self.assertIsNotNone(sfd, "temp must be addressed by dirfd")
                self.assertIsNotNone(dfd, "dest must be addressed by dirfd")

    def test_staged_temp_unreachable_by_parent_dir_attacker(self):
        # Regression test for the round-1 TOCTOU (Engineering review, PR
        # #332): the old design staged the temp directly in the parent
        # dir, so a parent-dir attacker could rename their file over it
        # between stage and install and root would install attacker bytes.
        # The new design stages inside a 0700 staging dir addressed only by
        # dirfd. This test emulates real privilege separation (root-owned
        # staging dir, attacker = uid nobody via seteuid) and lets the
        # attacker try the substitution on the REAL stage path between
        # _stage and _install_staged: every attempt must fail, and the
        # install must land OUR bytes.
        if os.geteuid() != 0:
            self.skipTest("needs root for seteuid privilege separation")
        try:
            nobody = pwd.getpwnam("nobody").pw_uid
        except KeyError:
            self.skipTest("no 'nobody' user for privilege separation")
        with tempfile.TemporaryDirectory() as d:
            # The deploy parent mirrors /home/swapd: attacker-owned and
            # attacker-writable (this is the threat model — the round-2
            # review caught that a 0755 root-owned parent makes the test
            # vacuous, since the attacker's rename fails EACCES regardless
            # of the install design).
            home = Path(d) / "swapd"
            home.mkdir()
            os.chown(home, nobody, nobody)
            os.chmod(d, 0o755)  # attacker can traverse the grandparent
            dest = home / "ssrf.deny"
            # Attacker-controlled dir + file.
            ad = Path(d) / "attacker"
            ad.mkdir()
            os.chown(ad, nobody, nobody)
            evil = ad / "evil"
            evil.write_bytes(b"ATTACKER\n")
            os.chown(evil, nobody, nobody)
            real_install = si._install_staged
            attack_errnos = []

            def hostile(stage_fd, parent_fd, name, create_only):
                stage_path = os.readlink("/proc/self/fd/%d" % stage_fd)
                os.seteuid(nobody)  # become the parent-dir attacker
                try:
                    for label, target in (
                            ("tmp", os.path.join(stage_path, ".tmp")),
                            ("stage", stage_path)):
                        try:
                            os.rename(str(evil), target)
                        except OSError as e:
                            attack_errnos.append((label, e.errno))
                        else:
                            self.fail("attacker substituted " + label)
                finally:
                    os.seteuid(0)  # back to root for the install
                return real_install(stage_fd, parent_fd, name, create_only)

            with mock.patch.object(si, "_install_staged", hostile):
                result = self._run(str(dest), content=b"deny all\n",
                                   mode=0o600)
            self.assertEqual(result, "written")
            self.assertEqual(dest.read_bytes(), b"deny all\n")
            self.assertIn(("tmp", errno.EACCES), attack_errnos,
                          "attacker never reached the staged temp: %r"
                          % (attack_errnos,))
            self.assertEqual(
                [p.name for p in home.iterdir()
                 if p.name.startswith(".safe_install.")],
                [])

    def test_staging_dir_swap_fails_closed(self):
        # Regression test for Security round-2 Blocker 1 (PR #332):
        # mkdir(stage) -> open(stage) resolves the staging dir BY NAME
        # through the attacker-writable parent. Force the attacker's race
        # win here (rename the real dir away, mkdir an attacker-owned
        # 0777 dir at the name, as the attacker) and assert the install
        # fails closed (SystemExit 2) with dest untouched. Without the
        # fstat identity check this test fails (the install proceeds).
        if os.geteuid() != 0:
            self.skipTest("needs root for seteuid privilege separation")
        try:
            nobody = pwd.getpwnam("nobody").pw_uid
        except KeyError:
            self.skipTest("no 'nobody' user for privilege separation")
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "swapd"
            home.mkdir()
            os.chown(home, nobody, nobody)
            os.chmod(d, 0o755)
            dest = home / "ssrf.deny"
            real_open = si.os.open
            swapped = []

            def swapping_open(path, flags, *args, **kwargs):
                if ((flags & os.O_DIRECTORY)
                        and kwargs.get("dir_fd") is not None):
                    # The staging-dir open: let the attacker win the
                    # mkdir->open race first.
                    parent_path = os.readlink(
                        "/proc/self/fd/%d" % kwargs["dir_fd"])
                    stage_path = os.path.join(parent_path, path)
                    os.seteuid(nobody)
                    try:
                        os.rename(stage_path, stage_path + ".orig")
                        os.mkdir(stage_path, 0o777)
                        swapped.append(True)
                    finally:
                        os.seteuid(0)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(si.os, "open", swapping_open):
                with self.assertRaises(SystemExit) as cm:
                    self._run(str(dest), content=b"deny all\n", mode=0o600)
            self.assertEqual(cm.exception.code, 2)
            self.assertTrue(swapped, "the swap never happened")
            self.assertFalse(dest.exists(), "dest must not be installed")


if __name__ == "__main__":
    unittest.main()

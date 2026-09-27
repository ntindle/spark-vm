#!/usr/bin/env python3
"""Tests for the #90 narrow-writer path-override guard and the #96 set-merge fix.

Issue #90: the narrow writers (cred-registry-set, cred-registry-set-inference,
grant-writer, cred-grant-revoke, cred-store-set-inference) honor caller-controlled
env vars to redirect security-critical file paths. Production safety rested on
sudo's env_reset stripping them — an assumption in comments. The guard asserts it
in code, keyed off the EFFECTIVE UID: when the process actually runs as swapd,
any caller-set override fails closed (exit 2, "refusing" on stderr) before any
path is used. A caller-settable bless marker was tried and rejected — a
direct-as-swapd caller can set any marker, so it is no boundary at all.

Outside the swapd identity (tests, dev) the overrides are honored as a test
seam; root already has arbitrary write authority, so nothing new is granted.

Because the refusal only triggers in the swapd identity, subprocess tests
simulate it two ways:
- python writers: the decision function _running_as_swapd() takes an injectable
  euid/getpwnam, so it is unit-tested directly (importlib load, no .py suffix).
- bash writers: run under a real `swapd` uid via setpriv. The class provisions
  a temporary `swapd` user when running as root (removed afterwards); without
  root and without a pre-existing swapd user those tests skip. Scripts are
  copied to a world-accessible temp dir because the worktree is not
  traversable by other uids.

A hostile-`id`-on-PATH regression test proves the bash identity check is
PATH-independent (/usr/bin/id + $EUID): even an `id` that claims the swapd
identity must not arm or disarm the guard.

Issue #96: cred-registry-set `set` replaced the whole entry dict, silently
dropping a per-entry `scrub:false` opt-out. It now merges (placement only).
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROXY = Path(__file__).resolve().parent

REGISTRY_SET = str(PROXY / "cred-registry-set")
REGISTRY_SET_INFERENCE = str(PROXY / "cred-registry-set-inference")
GRANT_WRITER = str(PROXY / "grant-writer")
GRANT_REVOKE = str(PROXY / "cred-grant-revoke")
STORE_SET_INFERENCE = str(PROXY / "cred-store-set-inference")

FAKE_UID = 424242  # the uid the fake `id` reports in as-swapd simulations


def _load_module(name, path):
    # Extensionless scripts: SourceFileLoader explicitly.
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run(script, args, env, input_text=None):
    return subprocess.run([script] + list(args), env=env,
                          input=input_text,
                          capture_output=True, text=True, timeout=30)


def plain_env(extra=None):
    """Ordinary caller env (no marker — the marker design is gone)."""
    env = dict(os.environ)
    if extra:
        env.update(extra)
    return env


class SwapdIdentityUnitTests(unittest.TestCase):
    """The python writers' _running_as_swapd() decision function."""

    @classmethod
    def setUpClass(cls):
        cls.grant_writer = _load_module("gw90", GRANT_WRITER)
        cls.grant_revoke = _load_module("gr90", GRANT_REVOKE)

    class _Pw:
        def __init__(self, uid):
            self.pw_uid = uid

    def test_match_is_swapd(self):
        for mod in (self.grant_writer, self.grant_revoke):
            self.assertTrue(
                mod._running_as_swapd(
                    euid=1001, getpwnam=lambda n: self._Pw(1001)))

    def test_mismatch_is_not_swapd(self):
        for mod in (self.grant_writer, self.grant_revoke):
            self.assertFalse(
                mod._running_as_swapd(
                    euid=1002, getpwnam=lambda n: self._Pw(1001)))

    def test_no_swapd_user_is_not_swapd(self):
        def _nok(name):
            raise KeyError(name)
        for mod in (self.grant_writer, self.grant_revoke):
            self.assertFalse(
                mod._running_as_swapd(euid=1001, getpwnam=_nok))

    def test_refusal_fires_only_as_swapd(self):
        cases = (
            (self.grant_writer,
             {"SWAP_GRANTS_FILE": "/tmp/evil.json",
              "SWAP_GRANTS_LOCK": "/tmp/evil.lock",
              "SWAP_LOG_FILE": "/tmp/evil.log"}),
            (self.grant_revoke, {"GRANT_WRITER": "/tmp/evil-writer"}),
        )
        for mod, overrides in cases:
            with self.subTest(mod=mod.__name__):
                # Not swapd: no refusal.
                with mock.patch.dict(os.environ, overrides, clear=False):
                    mod._check_path_overrides()  # must not raise
                # Swapd: refusal, exit 2, "refusing" on stderr.
                with mock.patch.object(mod, "_running_as_swapd",
                                       lambda euid=None, getpwnam=None: True):
                    with mock.patch.dict(os.environ, overrides, clear=False):
                        err = io.StringIO()
                        with contextlib.redirect_stderr(err):
                            with self.assertRaises(SystemExit) as cm:
                                mod._check_path_overrides()
                        self.assertEqual(cm.exception.code, 2)
                        self.assertIn("refusing", err.getvalue())


def hostile_id_env(extra=None):
    """Env with a hostile `id` on PATH claiming the swapd identity.

    Regression test for the PATH-independence of the bash guards: the
    fake reports FAKE_UID for every `id` invocation. The guards must
    ignore it — identity comes from /usr/bin/id and $EUID, never PATH.
    """
    d = tempfile.mkdtemp(prefix="hostileid-")
    fake = Path(d) / "id"
    fake.write_text("#!/bin/bash\necho %d\nexit 0\n" % FAKE_UID,
                    encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = d + os.pathsep + env.get("PATH", "")
    if extra:
        env.update(extra)
    return env


class BashGuardAsSwapdTests(unittest.TestCase):
    """Bash writers' guards under a real swapd uid (setpriv).

    The temporary `swapd` user is provisioned only when running as root
    and no swapd user exists; a pre-existing swapd user is used as-is and
    never removed. Refusal tests write nothing — the guard fires before
    any path is used — so they are safe against a real swapd account too.
    """

    swapd_created = False
    script_dir = None

    @classmethod
    def setUpClass(cls):
        try:
            pwd.getpwnam("swapd")
            cls.have_swapd = True
        except KeyError:
            cls.have_swapd = False
            if os.geteuid() == 0:
                subprocess.run(
                    ["useradd", "-M", "-s", "/bin/false", "swapd"],
                    check=True, capture_output=True, timeout=30)
                cls.have_swapd = True
                cls.swapd_created = True
        # World-accessible copies: the worktree is not traversable by
        # other uids.
        cls._tmp = tempfile.mkdtemp(prefix="swapdscripts-")
        os.chmod(cls._tmp, 0o755)
        for name in ("cred-registry-set", "cred-registry-set-inference",
                     "cred-store-set-inference", "grant-writer",
                     "cred-grant-revoke"):
            dst = Path(cls._tmp) / name
            dst.write_bytes((PROXY / name).read_bytes())
            dst.chmod(0o755)
        cls.script_dir = cls._tmp

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmp, ignore_errors=True)
        if cls.swapd_created:
            subprocess.run(["userdel", "swapd"], capture_output=True,
                           timeout=30)

    def _as_swapd(self, script, args, extra_env=None, input_text=None):
        if not self.have_swapd:
            self.skipTest("no swapd user and not root — cannot provision one")
        env = {"PATH": "/usr/bin:/bin"}
        if extra_env:
            env.update(extra_env)
        cmd = ["setpriv", "--reuid", "swapd", "--regid", "swapd",
               "--clear-groups", str(Path(self.script_dir) / script)]
        cmd += list(args)
        return subprocess.run(cmd, env=env, input=input_text,
                              capture_output=True, text=True, timeout=30)

    def test_registry_set_refuses_override_as_swapd(self):
        with tempfile.TemporaryDirectory() as d:
            reg = str(Path(d) / "evil.json")
            lock = str(Path(d) / "evil.lock")
            p = self._as_swapd("cred-registry-set",
                               ["set", "x", "y", '"bearer_header"'],
                               {"CRED_REGISTRY_FILE": reg,
                                "CRED_REGISTRY_LOCK": lock})
            self.assertEqual(p.returncode, 2)
            self.assertIn("refusing", p.stderr)
            self.assertIn("CRED_REGISTRY_FILE", p.stderr)
            self.assertFalse(Path(reg).exists())
            self.assertFalse(Path(lock).exists())

    def test_registry_set_marker_does_not_bypass_as_swapd(self):
        # The old SWAPD_WRITER_PATH_OVERRIDE marker is dead: even set, a
        # direct-as-swapd caller is still refused.
        with tempfile.TemporaryDirectory() as d:
            reg = str(Path(d) / "evil.json")
            p = self._as_swapd("cred-registry-set",
                               ["set", "x", "y", '"bearer_header"'],
                               {"CRED_REGISTRY_FILE": reg,
                                "SWAPD_WRITER_PATH_OVERRIDE": "1"})
            self.assertEqual(p.returncode, 2)
            self.assertIn("refusing", p.stderr)
            self.assertFalse(Path(reg).exists())

    def test_grant_writer_refuses_override_as_swapd(self):
        p = self._as_swapd("grant-writer", ["list"],
                           {"SWAP_GRANTS_FILE": "/tmp/evil.json",
                            "SWAP_LOG_FILE": "/tmp/evil.log"})
        self.assertEqual(p.returncode, 2)
        self.assertIn("refusing", p.stderr)
        self.assertIn("SWAP_GRANTS_FILE", p.stderr)

    def test_grant_revoke_refuses_writer_override_as_swapd(self):
        p = self._as_swapd("cred-grant-revoke", ["--job", "j1"],
                           {"GRANT_WRITER": "/tmp/evil-writer"})
        self.assertEqual(p.returncode, 2)
        self.assertIn("refusing", p.stderr)
        self.assertIn("GRANT_WRITER", p.stderr)

    def test_store_set_inference_refuses_override_as_swapd(self):
        with tempfile.TemporaryDirectory() as d:
            target = str(Path(d) / "secrets")
            p = self._as_swapd("cred-store-set-inference", [],
                               {"INFERENCE_SECRETS_DIR": target},
                               input_text="sekret\n")
            self.assertEqual(p.returncode, 2)
            self.assertIn("refusing", p.stderr)
            self.assertIn("INFERENCE_SECRETS_DIR", p.stderr)
            self.assertFalse(Path(target).exists())

    def test_wrapper_refuses_caller_paths_as_swapd(self):
        for var in ("CRED_REGISTRY_FILE", "CRED_REGISTRY_SET"):
            with self.subTest(var=var):
                p = self._as_swapd("cred-registry-set-inference",
                                   ["set", "x", "y", '"bearer_header"'],
                                   {var: "/tmp/evil"})
                self.assertEqual(p.returncode, 2)
                self.assertIn("refusing", p.stderr)
                self.assertIn(var, p.stderr)

    def test_hostile_path_id_is_ignored(self):
        # A hostile `id` on PATH claiming the swapd identity must not arm
        # the guard: on this box the real /usr/bin/id reports no swapd
        # user, so the override seam stays open and the writes succeed.
        # (The attack this prevents: a hostile `id` making `id -u swapd`
        # fail while really running as swapd, neutering the guard so
        # caller overrides are honored.)
        with tempfile.TemporaryDirectory() as d:
            # cred-registry-set: override honored, write succeeds.
            reg = str(Path(d) / "reg.json")
            p = run(REGISTRY_SET, ["set", "c", "e", '"bearer_header"'],
                    hostile_id_env({"CRED_REGISTRY_FILE": reg,
                                    "CRED_REGISTRY_LOCK": str(Path(d) / "r.lock")}))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("refusing", p.stderr)
            self.assertTrue(Path(reg).exists())
            # cred-registry-set-inference: wrapper does not refuse the
            # caller var; it execs the CRED_REGISTRY_SET double.
            double = Path(d) / "double"
            double.write_text("#!/bin/bash\necho double-ok\n",
                              encoding="utf-8")
            double.chmod(0o755)
            p = run(REGISTRY_SET_INFERENCE, [],
                    hostile_id_env({"CRED_REGISTRY_FILE": "/tmp/evil",
                                    "CRED_REGISTRY_SET": str(double)}))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("refusing", p.stderr)
            self.assertIn("double-ok", p.stdout)
            # cred-store-set-inference: override honored, write succeeds.
            target = str(Path(d) / "secrets")
            os.mkdir(target, 0o700)
            p = run(STORE_SET_INFERENCE, [],
                    hostile_id_env({"INFERENCE_SECRETS_DIR": target}),
                    input_text="sekret\n")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("refusing", p.stderr)
            self.assertTrue(Path(target, "llm-api").exists())


class NonSwapdOverrideTests(unittest.TestCase):
    """Outside the swapd identity the override seam works (plain env)."""

    def test_registry_set_honors_override(self):
        with tempfile.TemporaryDirectory() as d:
            reg = str(Path(d) / "reg.json")
            p = run(REGISTRY_SET,
                    ["set", "mycred", "access_token", '"bearer_header"'],
                    plain_env({"CRED_REGISTRY_FILE": reg,
                               "CRED_REGISTRY_LOCK": str(Path(d) / "r.lock")}))
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(Path(reg).read_text(encoding="utf-8"))
            self.assertEqual(data["mycred"]["access_token"]["placement"],
                             "bearer_header")

    def test_grant_writer_honors_override(self):
        with tempfile.TemporaryDirectory() as d:
            grants = str(Path(d) / "grants.json")
            env = plain_env({"SWAP_GRANTS_FILE": grants,
                             "SWAP_GRANTS_LOCK": str(Path(d) / "g.lock"),
                             "SWAP_LOG_FILE": str(Path(d) / "audit.log")})
            p = run(GRANT_WRITER,
                    ["add", "--credential", "c", "--host", "h.example",
                     "--method", "GET", "--approval-id", "aid1"], env)
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(Path(grants).read_text(encoding="utf-8"))
            self.assertEqual(data["grants"][0]["approval_id"], "aid1")

    def test_grant_revoke_honors_writer_override(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "fake-grant-writer"
            fake.write_text("#!/bin/bash\necho revoked-ok\n", encoding="utf-8")
            fake.chmod(0o755)
            p = run(GRANT_REVOKE, ["--job", "j1"],
                    plain_env({"GRANT_WRITER": str(fake)}))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("revoked-ok", p.stdout)

    def test_store_set_inference_honors_override(self):
        with tempfile.TemporaryDirectory() as d:
            target = str(Path(d) / "secrets")
            os.mkdir(target, 0o700)
            p = run(STORE_SET_INFERENCE, [],
                    plain_env({"INFERENCE_SECRETS_DIR": target}),
                    input_text="sekret\n")
            self.assertEqual(p.returncode, 0, p.stderr)
            stored = Path(target, "llm-api").read_bytes()
            self.assertEqual(stored, b"sekret")
            st = os.stat(Path(target, "llm-api"))
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)

    def test_wrapper_pins_inference_flag_for_child(self):
        # The wrapper execs the CRED_REGISTRY_SET double with
        # CRED_REGISTRY_INFERENCE=1 (a flag, not a path) and no
        # CRED_REGISTRY_FILE — the child maps the flag to the fixed
        # inference registry path.
        with tempfile.TemporaryDirectory() as d:
            double = Path(d) / "double"
            double.write_text(
                "#!/bin/bash\n"
                "echo \"FLAG=${CRED_REGISTRY_INFERENCE:-unset}\"\n"
                "echo \"REGFILE=${CRED_REGISTRY_FILE:-unset}\"\n",
                encoding="utf-8")
            double.chmod(0o755)
            p = run(REGISTRY_SET_INFERENCE, [],
                    plain_env({"CRED_REGISTRY_SET": str(double)}))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("FLAG=1", p.stdout)
            self.assertIn("REGFILE=unset", p.stdout)

    def test_wrapper_default_tool_path_without_override(self):
        # No CRED_REGISTRY_SET: the wrapper execs the fixed install path.
        # It will fail (no /usr/local/bin/cred-registry-set here) but must
        # fail trying the FIXED path, not an env-controlled one.
        p = run(REGISTRY_SET_INFERENCE, ["set", "x", "y", '"bearer_header"'],
                plain_env())
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("/usr/local/bin/cred-registry-set", p.stderr)


class SetMergeTests(unittest.TestCase):
    """Issue #96: `set` merges placement instead of replacing the entry."""

    def _env(self, d):
        return plain_env({"CRED_REGISTRY_FILE": str(Path(d) / "reg.json"),
                          "CRED_REGISTRY_LOCK": str(Path(d) / "reg.lock")})

    def test_set_preserves_scrub_opt_out(self):
        with tempfile.TemporaryDirectory() as d:
            env = self._env(d)
            reg = Path(d) / "reg.json"
            self.assertEqual(
                run(REGISTRY_SET,
                    ["set", "mycred", "access_token", '"bearer_header"'],
                    env).returncode, 0)
            self.assertEqual(
                run(REGISTRY_SET,
                    ["set-scrub", "mycred", "access_token", "false"],
                    env).returncode, 0)
            # Re-`set` with a new placement: placement updates, the
            # scrub:false opt-out survives (the old code dropped it).
            p = run(REGISTRY_SET,
                    ["set", "mycred", "access_token", '"url_path_segment"'],
                    env)
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(reg.read_text(encoding="utf-8"))
            entry = data["mycred"]["access_token"]
            self.assertEqual(entry["placement"], "url_path_segment")
            self.assertIs(entry["scrub"], False)

    def test_set_still_rejects_bad_placement(self):
        with tempfile.TemporaryDirectory() as d:
            env = self._env(d)
            p = run(REGISTRY_SET,
                    ["set", "mycred", "access_token", '"nope"'], env)
            self.assertNotEqual(p.returncode, 0)

    def test_set_on_non_object_entry_fails_closed(self):
        # The old replace path would silently clobber a non-dict entry;
        # the merge path refuses loudly instead.
        with tempfile.TemporaryDirectory() as d:
            env = self._env(d)
            reg = Path(d) / "reg.json"
            reg.write_text(json.dumps({"mycred": {"access_token": "weird"}}),
                           encoding="utf-8")
            p = run(REGISTRY_SET,
                    ["set", "mycred", "access_token", '"bearer_header"'],
                    env)
            self.assertNotEqual(p.returncode, 0)
            data = json.loads(reg.read_text(encoding="utf-8"))
            self.assertEqual(data["mycred"]["access_token"], "weird")


if __name__ == "__main__":
    unittest.main()

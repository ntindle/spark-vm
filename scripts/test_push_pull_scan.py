#!/usr/bin/env python3
"""Pin scripts/push.sh's secret scan and scripts/pull.sh's CLI contract.

push.sh refuses to push staged content containing secret-shaped values — the
last automated line of defense before a secret lands on the public remote.
It is also the script every contributor runs to sync the box-side checkout,
yet it had zero test coverage. This module pins:

1. The scan pattern (extracted verbatim from push.sh, never duplicated)
   detects every secret family it claims to and ignores benign lookalikes.
2. The real push.sh --dry-run refuses a staged synthetic secret, refuses
   BEFORE any network attempt, and never echoes the secret in its report.
3. pull.sh's minimal CLI contract (--help works, unknown flags die loudly).

All secret-shaped fixtures are SYNTHETIC (built by concatenation at runtime)
and clearly fake; the test file itself carries no contiguous secret-shaped
string, so the scan under test would not flag this module if it were staged.
"""

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUSH_SH = os.path.join(_REPO_ROOT, "scripts", "push.sh")
PULL_SH = os.path.join(_REPO_ROOT, "scripts", "pull.sh")


def _extract_secret_re():
    with open(PUSH_SH, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^SECRET_RE='(.*)'$", text, re.M)
    assert m, "SECRET_RE= line not found in push.sh"
    # push.sh scans with `git grep -nEi` (case-insensitive); the pin must test
    # the same pattern the production scan uses, not a narrower one.
    return re.compile(m.group(1), re.IGNORECASE)


# Synthetic positives: one per alternative in push.sh's SECRET_RE. Built by
# concatenation so no contiguous secret-shaped string lives in this file.
POSITIVES = [
    "sk-" + "SYNTH" * 4,                      # OpenAI-style key
    "ghp_" + "t" * 20,                        # classic GitHub PAT
    "github_pat_" + "t" * 20,                 # fine-grained GitHub PAT
    "gho_" + "t" * 36,                        # GitHub OAuth token
    "ghu_" + "t" * 36,                        # GitHub user-to-server token
    "ghs_" + "t" * 36,                        # GitHub installation token
    "ghr_" + "t" * 36,                        # GitHub refresh token
    "glpat-" + "t" * 20,                      # GitLab PAT
    "hf_" + "t" * 20,                         # Hugging Face token
    "AIza" + "t" * 35,                        # Google API key
    "AKIA" + "T" * 16,                        # AWS access key id
    "LLM_" + "123" + "_" + "t" * 16,          # provider-agnostic LLM key
    "-----BEGIN " + "RSA " + "PRIVATE KEY-----",
    "-----BEGIN " + "EC " + "PRIVATE KEY-----",
    "-----BEGIN " + "PRIVATE KEY-----",
    "-----BEGIN " + "OPENSSH " + "PRIVATE KEY-----",
    "xox" + "b-" + "1234",                     # Slack bot token
    "xox" + "p-" + "1234",                     # Slack user token
    "xox" + "a-" + "1234",                     # Slack app token
]

# Benign lookalikes that must NOT trip the scan (guard against false
# positives that would block legitimate pushes).
NEGATIVES = [
    "hsurr:github",                            # the credential-swap placeholder
    "x-access-token:hsurr:github",             # the placeholder as used
    "ghp_",                                    # prefix without a token
    "sk-",                                     # prefix without a key
    "AKIA" + "T" * 15,                         # one char short of the shape
    "LLM_" + "12" + "_" + "t" * 16,            # digit run too short
    "-----BEGIN PUBLIC KEY-----",              # public keys are fine
    "-----BEGIN CERTIFICATE-----",
    "paste your github_pat_ token at the prompt",  # prose, no token
    "export GITHUB_TOKEN=   # set me in your own session",
    "xox",                                     # prefix without a token
]


class SecretPatternTest(unittest.TestCase):
    def test_pattern_extracts_and_compiles(self):
        pat = _extract_secret_re()
        self.assertTrue(pat.pattern)

    def test_detects_every_family(self):
        pat = _extract_secret_re()
        for value in POSITIVES:
            with self.subTest(value=value[:12] + "..."):
                self.assertIsNotNone(
                    pat.search(value),
                    "scan pattern failed to detect a synthetic %r-shaped value"
                    % value[:12],
                )

    def test_ignores_benign_lookalikes(self):
        pat = _extract_secret_re()
        for text in NEGATIVES:
            with self.subTest(text=text[:30]):
                self.assertIsNone(
                    pat.search(text),
                    "scan pattern false-positived on benign %r" % text[:30],
                )


def _stub_with_proxy(bin_dir, log_path):
    """A with-proxy that never touches the network: logs invocations, fails."""
    path = os.path.join(bin_dir, "with-proxy")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/bash\n"
            'echo "$@" >> "$WITH_PROXY_LOG"\n'
            "exit 1\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    # Pre-create the log so the refusal test can assert it stayed EMPTY
    # (i.e. the stub was never invoked) without a FileNotFoundError.
    open(log_path, "a", encoding="utf-8").close()
    return path


def _scratch_repo_with_script(tmp, script_name):
    """A scratch git repo containing a real copy of the script under test."""
    repo = os.path.join(tmp, "scratch")
    scripts = os.path.join(repo, "scripts")
    os.makedirs(scripts)
    subprocess.run(["git", "init", "-b", "main", "-q", repo], check=True)
    subprocess.run(
        ["git", "-C", repo, "remote", "add", "origin",
         "https://example.invalid/ntindle/spark-vm.git"],
        check=True,
    )
    # push.sh's scan diffs the staged index against HEAD, so the scratch repo
    # needs at least one commit — mirroring the real box checkout, which
    # always has history.
    subprocess.run(["git", "-C", repo, "config", "user.email",
                    "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name",
                    "push-scan-test"], check=True)
    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as f:
        f.write("# scratch\n")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "init"], check=True)
    shutil.copy(os.path.join(_REPO_ROOT, "scripts", script_name),
                 os.path.join(scripts, script_name))
    return repo


def _run(script_path, args, bin_dir, log_path, cwd):
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["WITH_PROXY_LOG"] = log_path
    return subprocess.run(
        ["bash", script_path] + args,
        cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=60,
    )


class PushDryRunTest(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.mkdtemp(prefix="pushscan-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bin_dir = os.path.join(tmp, "bin")
        os.makedirs(bin_dir)
        log_path = os.path.join(tmp, "with-proxy.log")
        _stub_with_proxy(bin_dir, log_path)
        repo = _scratch_repo_with_script(tmp, "push.sh")
        script = os.path.join(repo, "scripts", "push.sh")
        return tmp, bin_dir, log_path, repo, script

    def test_dryrun_refuses_staged_secret(self):
        tmp, bin_dir, log_path, repo, script = self._setup()
        secret = "sk-" + "SYNTH" * 4
        with open(os.path.join(repo, "leak.txt"), "w", encoding="utf-8") as f:
            f.write('api_key = "%s"\n' % secret)
        p = _run(script, ["--dry-run", "test message"], bin_dir, log_path, tmp)
        out = p.stdout + p.stderr
        self.assertEqual(p.returncode, 1, "dry-run must refuse: %s" % out)
        self.assertIn("REFUSED", p.stderr)
        self.assertIn("leak.txt", p.stderr, "report must name the file")
        self.assertNotIn(secret, out,
                         "the refusal report must never echo the secret itself")
        with open(log_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "",
                             "refusal must happen BEFORE any network attempt")

    def test_dryrun_clean_tree_passes_and_probes_remote(self):
        tmp, bin_dir, log_path, repo, script = self._setup()
        with open(os.path.join(repo, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("nothing secret here: hsurr:github is a placeholder\n")
        p = _run(script, ["--dry-run", "test message"], bin_dir, log_path, tmp)
        out = p.stdout + p.stderr
        self.assertEqual(p.returncode, 0, "clean dry-run must pass: %s" % out)
        self.assertIn("secret scan clean", p.stdout)
        with open(log_path, encoding="utf-8") as f:
            self.assertIn("ls-remote", f.read(),
                          "clean path must still probe the remote")


class PullCliTest(unittest.TestCase):
    def test_help_exits_zero(self):
        p = subprocess.run(["bash", PULL_SH, "--help"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertIn("Usage: pull.sh", p.stdout)

    def test_unknown_flag_dies(self):
        p = subprocess.run(["bash", PULL_SH, "--bogus"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=30)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unknown flag", p.stderr)

    def test_push_help_exits_zero(self):
        p = subprocess.run(["bash", PUSH_SH, "--help"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertIn("Usage: push.sh", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

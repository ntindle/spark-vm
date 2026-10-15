#!/usr/bin/env python3
"""Pin scripts/png-smoke.sh and CI's png-check job to the playwright pin.

Three drift classes, all cheap to introduce by accident:

1. **CI pin drift** — .github/workflows/ci.yml's `png-check` job installs
   playwright. An unpinned (or differently-pinned) install floats on
   upstream releases while the toolset converges boxes onto
   scripts/self_update_pins.conf's pin, so the smoke CI runs can diverge
   from the browser the fleet was validated against. The job's
   `playwright==X` must equal the conf's pin exactly.
2. **Script pin-source drift** — png-smoke.sh resolves its pin from the
   conf. If the script ever hardcodes a version or reads a different file,
   `--plan` (which prints the resolved pin and its source file) exposes it.
3. **Runner contract** — `--plan` must stay hermetic (exit 0, no side
   effects, no venv required) and the script must fail closed on a
   missing pin and on a missing venv, so contributors get a clear error
   instead of a half-installed smoke.

Non-vacuity (all verified by neutering, then reverted): changing the CI
pin to a different version fails the pin test; deleting the playwright
line from a scratch pins conf fails the fail-closed test; unsetting
VIRTUAL_ENV in full-run mode fails the venv test.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "png-smoke.sh"
PINS_CONF = SCRIPTS / "self_update_pins.conf"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def conf_pin():
    pins = []
    for line in PINS_CONF.read_text().splitlines():
        m = re.match(r"\s*playwright\s*=\s*([0-9][0-9.]*)", line)
        if m:
            pins.append(m.group(1).strip())
    # Duplicate pin lines are a config error: fail loudly rather than
    # silently letting the script (last match wins) and this test
    # (first match) disagree on the pinned invariant.
    assert len(pins) == 1, f"expected exactly one playwright pin, found {pins!r}"
    return pins[0]


def ci_png_job_text():
    text = CI_YML.read_text()
    start = text.find("png-check:")
    assert start != -1, "png-check job missing from ci.yml"
    # The job runs to the next top-level job key or end of file. The
    # boundary must not require a trailing newline: a future appended job
    # whose key line carries a trailing comment must still terminate
    # the slice.
    rest = text[start:]
    m = re.search(r"\n(?=  [a-z0-9_-]+:)", rest)
    return rest[: m.start()] if m else rest


def ci_png_job_code_lines():
    # Comment lines excluded: a commented-out install must not satisfy
    # the pin (a comment installs nothing).
    return [
        line
        for line in ci_png_job_text().splitlines()
        if not line.strip().startswith("#")
    ]


def run_script(*args, env_extra=None, check_venv=True):
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    if check_venv:
        env["VIRTUAL_ENV"] = "/tmp/png-smoke-test-venv"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=60,
    )


class TestPngSmoke(unittest.TestCase):
    def test_ci_png_job_playwright_pin_matches_conf(self):
        pin = conf_pin()
        code = "\n".join(ci_png_job_code_lines())
        installs = re.findall(r'pip3?\s+install\s+"?playwright==([0-9][0-9.]*)"?', code)
        self.assertEqual(
            len(installs),
            1,
            "png-check job must pin playwright exactly once "
            f"(found {installs!r}) — an unpinned `pip install playwright` "
            "floats on upstream releases",
        )
        self.assertEqual(
            installs[0],
            pin,
            "CI's png-check playwright pin must equal "
            "scripts/self_update_pins.conf's pin",
        )
        # And no OTHER playwright install may sneak in beside the pinned
        # one: an added unpinned `pip install playwright` would otherwise
        # pass the assertions above while breaking the invariant.
        for m in re.finditer(r"pip3?\s+install\s+([^\n#]+)", code):
            for tok in re.findall(r'"?playwright[^"\s]*"?', m.group(1)):
                self.assertEqual(
                    tok.strip('"'),
                    f"playwright=={pin}",
                    f"unpinned/mismatched playwright install in png-check job: {tok!r}",
                )

    def test_plan_is_hermetic_and_names_steps(self):
        # --plan needs no venv and must not touch the tree: run it with
        # VIRTUAL_ENV scrubbed and assert exit 0 + the step inventory.
        r = run_script("--plan", check_venv=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        for step in (
            "playwright pin",
            "venv check",
            "pip install",
            "browser install",
            "screenshot",
            "PNG check",
        ):
            self.assertIn(step, r.stdout, f"--plan missing step {step!r}")
        self.assertIn(conf_pin(), r.stdout)
        self.assertIn("self_update_pins.conf", r.stdout)

    def test_plan_with_deps_flag_surfaces_in_browser_step(self):
        r = run_script("--plan", "--with-deps", check_venv=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("install --with-deps chromium", r.stdout)

    def test_help_exits_zero(self):
        r = run_script("--help", check_venv=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("png-smoke.sh", r.stdout)
        # The header's usage constraints must survive in --help: a past
        # revision truncated the header mid-paragraph and hid the venv
        # requirement (the script's most important constraint).
        self.assertIn("VIRTUAL_ENV", r.stdout)
        self.assertIn("Env overrides", r.stdout)

    def test_unknown_flag_exits_two(self):
        r = run_script("--bogus", check_venv=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown flag", r.stderr)

    def test_missing_pin_fails_closed(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".conf", delete=False
        ) as f:
            f.write("# no playwright line here\n")
            path = f.name
        try:
            r = run_script(
                "--plan", check_venv=False, env_extra={"PNG_SMOKE_PINS_CONF": path}
            )
        finally:
            os.unlink(path)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fail-closed", r.stderr)

    def test_missing_venv_fails_closed_in_run_mode(self):
        # Full run with no VIRTUAL_ENV must refuse before any install —
        # playwright goes into the contributor venv, never system Python.
        # Assert the intentional fail-closed path, not merely a crash: with
        # the check removed, `set -u` aborts with exit 1 "VIRTUAL_ENV:
        # unbound variable", which looser assertions cannot distinguish.
        r = run_script(check_venv=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no active venv", r.stderr)

    def test_install_vs_skip_decision_hermetic(self):
        # The script's core branch — pip-install only on version mismatch —
        # exercised hermetically with stub python3/pip binaries: no network,
        # no real venv, no browser. The stubs emulate the exact argv shapes
        # the script uses ("$VIRTUAL_ENV/bin/python3" / "$VIRTUAL_ENV/bin/pip").
        import stat

        with tempfile.TemporaryDirectory() as stubdir:
            # Real venv layout: the script resolves "$VIRTUAL_ENV/bin/python3"
            # and "$VIRTUAL_ENV/bin/pip" (never PATH), so the stubs must
            # live under bin/.
            bindir = os.path.join(stubdir, "bin")
            os.mkdir(bindir)
            log = os.path.join(stubdir, "calls.log")
            stub_py = os.path.join(bindir, "python3")
            with open(stub_py, "w") as f:
                f.write(
                    "#!/bin/sh\n"
                    'if [ "$1" = "-c" ]; then echo "$STUB_PW_VERSION"; exit 0; fi\n'
                    'if [ "$1" = "-m" ]; then echo "py -m $3 $4" >> "$STUB_LOG"; exit 0; fi\n'
                    'case "$1" in\n'
                    "  *pw-test.py) touch /tmp/pw-test.png; echo BROWSER_TEST_OK; exit 0;;\n"
                    "  *png-check.py) echo STUB_PNGCHECK_OK; exit 0;;\n"
                    "esac\n"
                    'echo "stub python3: unexpected args: $*" >&2; exit 99\n'
                )
            stub_pip = os.path.join(bindir, "pip")
            with open(stub_pip, "w") as f:
                f.write('#!/bin/sh\necho "pip $*" >> "$STUB_LOG"\nexit 0\n')
            os.chmod(stub_py, os.stat(stub_py).st_mode | stat.S_IEXEC)
            os.chmod(stub_pip, os.stat(stub_pip).st_mode | stat.S_IEXEC)

            def run_case(version):
                env = dict(os.environ)
                env.pop("VIRTUAL_ENV", None)
                env["VIRTUAL_ENV"] = stubdir
                env["STUB_PW_VERSION"] = version
                env["STUB_LOG"] = log
                if os.path.exists(log):
                    os.unlink(log)
                return subprocess.run(
                    ["bash", str(SCRIPT)],
                    capture_output=True,
                    text=True,
                    cwd=str(ROOT),
                    env=env,
                    timeout=60,
                )

            # Version matches the pin: pip must never be invoked. (The stub
            # python3's `-m` branch also logs to the same file, so assert
            # on the absence of pip lines, not the absence of the file.)
            r = run_case(conf_pin())
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("skipping pip install", r.stdout)
            pip_lines = []
            if os.path.exists(log):
                pip_lines = [
                    line
                    for line in Path(log).read_text().splitlines()
                    if line.startswith("pip ")
                ]
            self.assertEqual(
                pip_lines,
                [],
                "pip must not be invoked when the installed version matches",
            )
            self.assertIn("png-smoke: PASS", r.stdout)

            # Version differs: exactly one pinned pip install.
            r = run_case("0.0.0")
            self.assertEqual(r.returncode, 0, r.stderr)
            pip_lines = [
                line
                for line in Path(log).read_text().splitlines()
                if line.startswith("pip ")
            ]
            self.assertEqual(len(pip_lines), 1, pip_lines)
            self.assertIn(f"playwright=={conf_pin()}", pip_lines[0])
            self.assertIn("png-smoke: PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""spark-vm self-update, slice S1: read-only toolset inventory (issue #532).

`self_update.py status` reports the installed version of every tool in the
self-update scope (unattended-upgrades, the CUA stack's cua-driver, docker,
node, gh, playwright + browsers, snap packages, cred, swapd, muse-job, and
spark-vm's own version) against the known-good pins in
``scripts/self_update_pins.conf``.

Scope is the spark-vm-provisioned defaults only (the #532 corrected scope —
user-installed tools like Tailscale, KiCad/KiKit, Muse CLI, and Blender are
explicitly out of scope).

Read-only by construction: probes only run ``--version``-style commands and
read config files. Nothing is installed, changed, restarted, downloaded, or
elevated — no network, no writes, no sudo. Later slices (roadmap in
``docs/SELF_UPDATE.md``) add update execution, the systemd timer, and the
backfill installer.

Probes never raise: a tool that cannot be probed reports ``installed: false``
with a note, so ``status`` always exits 0. Stdlib only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Per-probe subprocess timeout: a stuck version command must not stall the
# whole inventory. Tools report in milliseconds; 10 s is generous.
_PROBE_TIMEOUT_S = 10

_PINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "self_update_pins.conf")


def default_runner(argv, timeout=_PROBE_TIMEOUT_S):
    """Run argv, return (returncode, stdout_text, stderr_text). Never raises."""
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.SubprocessError):
        return 127, "", ""


def _first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


def _version_output(stdout, stderr):
    """First non-empty line of stdout, falling back to stderr.

    Some tools print versions to stderr (java-style). stdout is preferred so
    stderr noise (deprecation warnings, PYTHONWARNINGS, sitecustomize
    banners) can never masquerade as the version — see B1.
    """
    line = _first_line(stdout)
    return line if line else _first_line(stderr)


def _probe_binary_version(binary, argv, pattern=None, which=shutil.which,
                          runner=default_runner):
    """Probe `binary` on PATH, run argv, return (installed, version, note).

    pattern: optional regex with one group; the group becomes the version.
    Without a pattern the whole first stdout line is the version.
    """
    path = which(binary)
    if not path:
        return False, None, "not found on PATH"
    try:
        rc, stdout, stderr = runner([binary] + argv)
    except Exception:
        # A runner that raises (rather than returning rc != 0) still must not
        # break the inventory — the binary exists, its version is unknown.
        return True, None, "found at %s but version query raised" % path
    line = _version_output(stdout, stderr)
    if rc != 0 or not line:
        return True, None, "found at %s but version query failed" % path
    version = line
    if pattern is not None:
        m = re.search(pattern, line)
        version = m.group(1) if m else line
    return True, version, "via %s %s" % (binary, " ".join(argv))


def _probe_python_package(package, python=sys.executable,
                           runner=default_runner):
    """Probe an installed Python package via importlib.metadata."""
    rc, stdout, stderr = runner([
        python, "-c",
        "import importlib.metadata as m; print(m.version(%r))" % package,
    ])
    line = _version_output(stdout, stderr)
    if rc != 0 or not line:
        return False, None, "python package %r not installed" % package
    return True, line, "python package"


_DEFAULT_UU_CONF_PATHS = ("/etc/apt/apt.conf.d/20auto-upgrades",
                          "/etc/apt/apt.conf.d/10periodic")


def probe_unattended_upgrades(which=shutil.which, runner=default_runner,
                              conf_paths=_DEFAULT_UU_CONF_PATHS):
    """OS security auto-installs: the unattended-upgrades package + config.

    `conf_paths` is injectable so the enabled/disabled detection is testable
    against fixture files (B2).
    """
    path = which("unattended-upgrade")
    if not path:
        return False, None, "unattended-upgrade not on PATH"
    version = None
    rc, stdout, _ = runner(["dpkg-query", "-W", "-f=${Version}",
                            "unattended-upgrades"])
    if rc == 0 and _first_line(stdout):
        version = _first_line(stdout)
    enabled = False
    read_any = False
    for conf in conf_paths:
        try:
            with open(conf, encoding="utf-8", errors="replace") as f:
                read_any = True
                for line in f:
                    # Commented-out directives must not count as enabled.
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("#"):
                        continue
                    if re.search(r'Unattended-Upgrade\s+"1"', line):
                        enabled = True
                        break
        except OSError:
            continue
        if enabled:
            break
    if not read_any:
        note = "config unreadable"
    else:
        note = "auto-installs %s" % ("ENABLED" if enabled else "DISABLED")
    return True, version, note


def probe_docker(which=shutil.which, runner=default_runner):
    return _probe_binary_version(
        "docker", ["--version"], r"Docker version ([0-9][^,\s]*)",
        which=which, runner=runner)


def probe_node(which=shutil.which, runner=default_runner):
    return _probe_binary_version("node", ["--version"], r"v?([0-9][\w.\-]*)",
                                 which=which, runner=runner)


def probe_gh(which=shutil.which, runner=default_runner):
    return _probe_binary_version("gh", ["--version"], r"gh version ([0-9][\w.\-]*)",
                                 which=which, runner=runner)


def probe_playwright(runner=default_runner, which=shutil.which):
    """Probe the playwright package in the box's canonical python3.

    Uses the PATH-resolved `python3` (the interpreter SETUP provisioned
    Playwright into), not necessarily the interpreter running this script —
    invoking via a venv or uv-managed python must not false-report a miss
    (B4).
    """
    python = which("python3") or sys.executable
    return _probe_python_package("playwright", python=python, runner=runner)


def probe_playwright_browsers(home=None):
    """Installed Playwright browser builds under ~/.cache/ms-playwright.

    Reports for the INVOKING user (on the box that's whoever runs the
    command) — S3's timer runs it as the box owner so the report covers
    the browsers the agent actually uses.
    """
    base = os.path.join(home or os.path.expanduser("~"),
                        ".cache", "ms-playwright")
    try:
        entries = sorted(os.listdir(base))
    except OSError:
        return False, None, "no browser cache at %s" % base
    browsers = [e for e in entries
                if not e.startswith(".")  # skip Playwright's .links dir
                and os.path.isdir(os.path.join(base, e))]
    if not browsers:
        return False, None, "browser cache dir exists but is empty"
    return True, "%d build(s)" % len(browsers), ", ".join(browsers)


def probe_snap(which=shutil.which, runner=default_runner):
    path = which("snap")
    if not path:
        return False, None, "not found on PATH"
    rc, stdout, _ = runner(["snap", "list"])
    if rc != 0:
        return True, None, "snap present but `snap list` failed"
    names = []
    for line in stdout.splitlines()[1:]:  # skip the header row
        parts = line.split()
        if parts:
            names.append(parts[0])
    if not names:
        return True, "0 snaps", "snap present, nothing installed"
    return True, "%d snap(s)" % len(names), ", ".join(names)


def probe_cua_driver(which=shutil.which, runner=default_runner):
    # cua-driver is held on a known-good pin (see self_update_pins.conf);
    # S1 reports drift only.
    return _probe_binary_version("cua-driver", ["--version"],
                                 r"([0-9][\w.\-]*)",
                                 which=which, runner=runner)


def probe_cred(which=shutil.which):
    # `cred` (the swapping-proxy secret front-end) has no --version flag,
    # so S1 reports presence only. Liveness (cred round-trips) is S2's
    # post-update health-check work.
    path = which("cred")
    if not path:
        return False, None, "not found on PATH"
    return True, None, "installed at %s (no version flag)" % path


def probe_swapd(which=shutil.which, runner=default_runner):
    # The swapping proxy runs as the dedicated `swapd` system user; its
    # presence is the S1 installed signal. Proxy health (port answers,
    # swap audit) is S2's post-update health-check work.
    if not which("id"):
        return False, None, "cannot check: `id` not on PATH"
    rc, stdout, _ = runner(["id", "-u", "swapd"])
    if rc != 0 or not _first_line(stdout):
        return False, None, "swapd system user absent"
    return True, None, "swapd system user present"


def probe_muse_job(which=shutil.which, runner=default_runner):
    # muse-job stamps the spark-vm release version at startup, so its
    # --version is the component's version.
    return _probe_binary_version("muse-job", ["--version"],
                                 r"([0-9][\w.\-]*)",
                                 which=which, runner=runner)


def probe_sparkvm():
    """spark-vm's own release version (repo VERSION file)."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        from sparkvm_version import sparkvm_version
        version = sparkvm_version()
    except Exception:
        return False, None, "could not read VERSION"
    if version == "0.0.0-unknown":
        return False, None, "VERSION missing or unparsable"
    return True, version, "repo VERSION"


# Registry: (tool name, scope sentence, probe callable). Order is the display
# order — OS first, then the third-party toolset, then the spark-vm agent
# components, then spark-vm itself. Matches the #532 corrected scope:
# spark-vm-provisioned defaults only (Tailscale, KiCad/KiKit, Muse CLI,
# Blender are explicitly out of scope).
PROBES = (
    ("unattended-upgrades", "OS security auto-installs", probe_unattended_upgrades),
    ("cua-driver", "CUA driver (held pin)", probe_cua_driver),
    ("docker", "docker engine + compose", probe_docker),
    ("node", "node/npm (nodesource)", probe_node),
    ("gh", "GitHub CLI (apt)", probe_gh),
    ("playwright", "playwright (pip)", probe_playwright),
    ("playwright-browsers", "playwright browser builds", probe_playwright_browsers),
    ("snap", "snap packages", probe_snap),
    ("cred", "cred secret front-end", probe_cred),
    ("swapd", "swapping proxy (system user)", probe_swapd),
    ("muse-job", "muse-job agent runner", probe_muse_job),
    ("spark-vm", "spark-vm release", probe_sparkvm),
)


def load_pins(path=_PINS_FILE):
    """Read the known-good pin file. Returns {tool: pinned_version}."""
    pins = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if name and value:
                    pins[name] = value
    except OSError:
        pass
    return pins


def run_probe(name, probe, pins):
    """Run one probe, never raise. Returns the inventory record dict."""
    try:
        installed, version, note = probe()
    except Exception as exc:  # noqa: BLE001 - probes must never break status
        installed, version, note = False, None, "probe error: %s" % exc
    pinned = pins.get(name)
    # Presence-only probes (version None) can still drift against a pin:
    # a pin naming them means someone cares, and an unverifiable version
    # must be loud, not silently ignored (B3).
    drift = bool(pinned and installed and version != pinned)
    if drift and version is None:
        note = "%s; pinned %s but version unverifiable" % (note, pinned)
    return {
        "tool": name,
        "scope": next((s for n, s, _ in PROBES if n == name), ""),
        "installed": installed,
        "version": version,
        "pinned": pinned,
        "drift": drift,
        "note": note,
    }


def status(pins_path=_PINS_FILE):
    """Full inventory. Never raises; every probe is isolated."""
    pins = load_pins(pins_path)
    return [run_probe(name, probe, pins) for name, _, probe in PROBES]


def format_table(records):
    rows = [("TOOL", "INSTALLED", "VERSION", "PINNED", "DRIFT", "NOTE")]
    for r in records:
        rows.append((
            r["tool"],
            "yes" if r["installed"] else "no",
            r["version"] or "-",
            r["pinned"] or "-",
            "DRIFT" if r["drift"] else "-",
            (r["note"] or "")[:60],
        ))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for i, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[j])
                               for j, cell in enumerate(row)).rstrip())
        if i == 0:
            lines.append("  ".join("-" * widths[j]
                                   for j in range(len(row))).rstrip())
    missing = [r["tool"] for r in records if not r["installed"]]
    drifted = [r["tool"] for r in records if r["drift"]]
    if missing:
        lines.append("")
        lines.append("not installed: %s" % ", ".join(missing))
    if drifted:
        lines.append("drift from pin: %s" % ", ".join(drifted))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="spark-vm self-update (issue #532) — S1: read-only "
                    "toolset inventory")
    sub = parser.add_subparsers(dest="command", required=True)
    p_status = sub.add_parser("status", help="report installed tool versions")
    p_status.add_argument("--json", action="store_true",
                          help="emit machine-readable JSON")
    p_status.add_argument("--pins", default=_PINS_FILE,
                          help="pin file path (default: bundled pins)")
    args = parser.parse_args(argv)

    if args.command == "status":
        records = status(pins_path=args.pins)
        if args.json:
            print(json.dumps({
                "generated_at": int(time.time()),
                "slice": "S1-status",
                "tools": records,
            }, indent=2))
        else:
            print(format_table(records))
        return 0
    return 2  # unreachable: argparse enforces the subcommand


if __name__ == "__main__":
    sys.exit(main())

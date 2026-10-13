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

Traceability: F-A1 (issue #1308) — the playwright/cua-driver probes target
the managed artifacts the update plane converges; F-A2 (issue #1309) —
pins are first-wins (matching ``_read_pin``) and duplicates are loud;
issue #1313 — the status plane compares its checkout pins against the
sha256(installed pins) record the privileged install publishes
(``PINS_HASH_FILE``), warning when they differ so a pin bump without an
install is loud instead of un-actionable drift.

Probes never raise: a tool that cannot be probed reports ``installed: false``
with a note, so ``status`` always exits 0. Stdlib only.
"""

import argparse
import hashlib
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

# Issue #1313: the update plane reads the INSTALLED pins
# ($TOOLSET_STATE_DIR/self_update_pins.conf, root-owned mode 700) while the
# status plane reads the CHECKOUT pins (_PINS_FILE). A pin bump without a
# privileged `toolset-update.sh install` leaves S1 reporting drift the
# updater can never clear — silently. The privileged install publishes
# sha256(installed pins) to this world-readable record (only a privileged
# install may write it; the pins themselves are public in the repo), and S1
# compares it against its checkout pins: match / mismatch / unknown (no
# record yet — pre-#1313 installs, or an unreadable record; silent by
# design, not an error).
_PINS_HASH_FILE = os.environ.get(
    "PINS_HASH_FILE", "/var/lib/sparkvm-toolset/self_update_pins.hash")

# "installed pins differ from checkout — run `toolset-update.sh install`"
# is the prescribed wording (issue #1313): the mismatch is actionable only
# by re-running the privileged install.
_PINS_MISMATCH_WARNING = ("installed pins differ from checkout — "
                          "run `toolset-update.sh install`")

# Issue #1310: the update plane resolves the managed targets
# (CUA_DRIVER_BIN, PLAYWRIGHT_VENV) from ITS environment (the systemd
# unit's, under the timer) while the status plane resolves them from the
# invoker's shell — the two planes silently target different artifacts when
# the operator relocates the managed locations in one environment but not
# the other. The privileged install publishes the resolved targets, and
# every update tick refreshes the record, to this world-readable file (the
# #1313 pins-hash carrier dir; only the privileged update plane may write
# it). The status plane prefers the record — falling back to its env
# override, then the default — so S1 always probes the artifacts the
# updater actually converges. A missing or unreadable record is silent by
# design (pre-#1310 installs never wrote one), and only the two known keys
# with absolute-path values are accepted: a malformed record is ignored
# wholesale, fail-closed to env/default.
_MANAGED_TARGETS_FILE = os.environ.get(
    "MANAGED_TARGETS_FILE",
    os.path.join(os.environ.get("MANAGED_TARGETS_DIR",
                                "/var/lib/sparkvm-toolset"),
                 "managed_targets"))
_MANAGED_TARGET_KEYS = ("CUA_DRIVER_BIN", "PLAYWRIGHT_VENV")


def _read_managed_targets_record(path=_MANAGED_TARGETS_FILE):
    """Read the update plane's published managed targets (issue #1310).

    Returns a dict of the known keys, or {} on any problem (missing file,
    unreadable, malformed). Fail-closed: values must be absolute paths,
    and unknown keys are ignored — the caller falls back to env/default.
    """
    record = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            # Bounded read: the record is two short lines; an unbounded
            # read of a huge file (e.g. MANAGED_TARGETS_FILE pointed at
            # /dev/zero) must not hang the import.
            lines = f.read(65536).splitlines()
    except (OSError, ValueError):
        # ValueError covers UnicodeDecodeError (non-UTF8 bytes) and the
        # NUL-byte path rejection — both fail closed like any other
        # unreadable record, instead of killing the status tool at import.
        return {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in _MANAGED_TARGET_KEYS and value.startswith("/"):
            record[key] = value
    # The publisher always writes both keys together: a record missing one
    # is corrupt (e.g. torn by a concurrent read landing mid-publish) —
    # ignore it wholesale, fail-closed to env/default, rather than
    # trusting the surviving half (which may itself be truncated).
    if set(record) != set(_MANAGED_TARGET_KEYS):
        return {}
    return record

# The update plane (deploy/toolset-update.sh) converges MANAGED targets, never
# PATH — the status plane must report the same artifacts the updater holds,
# or "drift" in S1 is not the drift S2's layers clear (F-A1). These are the
# update plane's resolved targets, read from the record the privileged
# install publishes and every update tick refreshes (issue #1310); when no
# record exists the invoker's environment overrides still apply, then the
# defaults — so the two planes keep agreeing when the operator relocates
# the managed locations (and S1 stays useful on boxes the updater never
# managed).
_managed_targets_record = _read_managed_targets_record()
_MANAGED_CUA_DRIVER = (_managed_targets_record.get("CUA_DRIVER_BIN")
                       or os.environ.get("CUA_DRIVER_BIN",
                                         "/home/ntindle/cua/bin/cua-driver"))
_MANAGED_PLAYWRIGHT_VENV = (_managed_targets_record.get("PLAYWRIGHT_VENV")
                            or os.environ.get("PLAYWRIGHT_VENV",
                                              "/home/ntindle/.venvs/pw"))


def _managed_target_source_note(key, resolved_value):
    """Status-note fragment naming the winning managed-target source.

    Issue #1412: the record wins over the invoker's env override silently —
    an operator who set CUA_DRIVER_BIN in their shell sees S1 probe a
    different artifact with no explanation (the probes name the probed path,
    not why it won). Returns "" unless the record names a value for `key`,
    the environment names a DIFFERENT value, and `resolved_value` is the
    record's value (i.e. the record's artifact is what was actually probed).
    """
    record_value = _managed_targets_record.get(key)
    env_value = os.environ.get(key)
    if (record_value and env_value and env_value != record_value
            and resolved_value == record_value):
        return ("env %s=%s overridden by managed-targets record"
                % (key, env_value))
    return ""


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


def _probe_binary_version_at(path, argv, pattern=None, runner=default_runner):
    """Probe an explicit binary path, run argv, return (installed, version, note).

    Same contract as _probe_binary_version but for a caller-resolved path
    (the managed target), so the version query runs against the exact
    artifact the update plane converges, not a PATH lookup.
    """
    try:
        rc, stdout, stderr = runner([path] + argv)
    except Exception:
        # A runner that raises (rather than returning rc != 0) still must not
        # break the inventory — the binary exists, its version is unknown.
        return True, None, "found at %s but version query raised" % path
    line = _version_output(stdout, stderr)
    if rc != 0 or not line:
        return True, None, "found at %s but version query failed" % path
    version = line
    if pattern is not None:
        # Some tools print banners above their version line; scan all
        # non-empty lines for the first pattern match before falling back
        # to the raw first line (a banner must never become the version).
        # stdout is searched before stderr, matching _version_output's
        # preference (B1).
        m = None
        for stream in (stdout, stderr):
            for candidate in (stream or "").strip().splitlines():
                candidate = candidate.strip()
                if not candidate:
                    continue
                m = re.search(pattern, candidate)
                if m:
                    break
            if m:
                break
        version = m.group(1) if m else line
    return True, version, "via %s %s" % (path, " ".join(argv))


def _managed_executable(path):
    """True when the managed target is a real executable file.

    Existence + executability on the real filesystem, so the probes'
    managed-first preference order is testable with real tmp files
    (no mocking needed) rather than a stubbed filesystem.
    """
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


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
        # Some tools print banners above their version line; scan all
        # non-empty lines for the first pattern match before falling back
        # to the raw first line (a banner must never become the version).
        # stdout is searched before stderr, matching _version_output's
        # preference (B1).
        m = None
        for stream in (stdout, stderr):
            for candidate in (stream or "").strip().splitlines():
                candidate = candidate.strip()
                if not candidate:
                    continue
                m = re.search(pattern, candidate)
                if m:
                    break
            if m:
                break
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
    return True, line, "python package via %s" % python


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


def probe_playwright(runner=default_runner, which=shutil.which, managed=None):
    """Probe the playwright package in the managed venv's python when present.

    The update plane converges the MANAGED venv ($PLAYWRIGHT_VENV), never
    PATH — the status plane must report the same interpreter the updater
    holds (F-A1): a PATH python3 carrying a different playwright would
    report drift the updater can never clear, or report clean while the
    managed venv rots. PATH python3 is the fallback for boxes the updater
    never managed; the note names the interpreter either way. The managed
    target resolves from the update plane's published record when present
    (issue #1310), else the invoker's env override, else the default. When
    the record wins over an explicitly-set, disagreeing env var, the note
    names the override (issue #1412).
    `managed` is injectable (the venv dir) so the preference order is
    testable.
    """
    venv = _MANAGED_PLAYWRIGHT_VENV if managed is None else managed
    managed_py = os.path.join(venv, "bin", "python") if venv else None
    override = ""
    if _managed_executable(managed_py):
        python = managed_py
        override = _managed_target_source_note("PLAYWRIGHT_VENV", venv)
    else:
        python = which("python3") or sys.executable
    installed, version, note = _probe_python_package(
        "playwright", python=python, runner=runner)
    if override:
        note = "%s; %s" % (note, override)
    return installed, version, note


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


def probe_cua_driver(which=shutil.which, runner=default_runner, managed=None):
    """Probe cua-driver at the managed binary when present, else on PATH.

    The update plane converges the MANAGED binary ($CUA_DRIVER_BIN) as its
    owner, never PATH (PATH-hijacking: the timer runs as root) — the status
    plane must report the same artifact the updater holds on the pin
    (F-A1). PATH is the fallback for boxes the updater never managed; the
    note names the probed path either way. The managed target resolves from
    the update plane's published record when present (issue #1310), else
    the invoker's env override, else the default. When the record wins over
    an explicitly-set, disagreeing env var, the note names the override
    (issue #1412). `managed` is injectable
    (the binary path) so the preference order is testable.
    """
    target = _MANAGED_CUA_DRIVER if managed is None else managed
    if _managed_executable(target):
        installed, version, note = _probe_binary_version_at(
            target, ["--version"], r"([0-9][\w.\-]*)", runner=runner)
        override = _managed_target_source_note("CUA_DRIVER_BIN", target)
        if override:
            note = "%s; %s" % (note, override)
        return installed, version, note
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
    """Read the known-good pin file. Returns {tool: pinned_version}.

    Never raises: a malformed file (non-UTF-8 bytes, garbage lines) must not
    crash the status inventory (B2). Non-decodable bytes are replaced — the
    same defensive pattern as probe_unattended_upgrades — and lines without
    "name=value" shape are skipped.

    First occurrence of a duplicated tool name wins, matching _read_pin in
    deploy/toolset-update.sh (F-A2): the two planes read the same pins file
    and must agree on which line is the pin. Duplicates are surfaced by
    pin_duplicates — a losing line is silently ignored forever otherwise.
    """
    pins = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if name and value and name not in pins:
                    pins[name] = value
    except OSError:
        pass
    return pins


def pin_duplicates(path=_PINS_FILE):
    """Pin tool names appearing more than once — dead config must be loud.

    The two planes read the same pins file with first-wins semantics
    (load_pins here, _read_pin in deploy/toolset-update.sh); a duplicated
    tool name means every later line is silently ignored forever, so
    duplicates are surfaced in the table footer and the --json document.
    """
    counts = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if name and value:
                    counts[name] = counts.get(name, 0) + 1
    except OSError:
        return []
    return sorted(name for name, n in counts.items() if n > 1)


def installed_pins_state(pins_path=_PINS_FILE, hash_path=None):
    """Compare checkout pins vs the installed pins' published hash.

    Returns "match", "mismatch", or "unknown". "unknown" is the honest
    no-signal state: the hash record is missing, unreadable, or malformed
    (pre-#1313 installs publish none; the record is an informational signal,
    not an enforcement point — a corrupt record is indistinguishable from
    absent to the unprivileged reader, and the privileged install fails
    closed on write). Never raises.

    hash_path defaults to _PINS_HASH_FILE resolved at call time (not import
    time), so tests can override the record location by monkeypatching the
    module constant (the PINS_HASH_FILE env var itself is read once at
    import).
    """
    if hash_path is None:
        hash_path = _PINS_HASH_FILE
    try:
        with open(hash_path, encoding="utf-8", errors="replace") as f:
            recorded = f.read().strip()
    except OSError:
        return "unknown"
    if (len(recorded) != 64
            or any(c not in "0123456789abcdef" for c in recorded)):
        return "unknown"
    try:
        with open(pins_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return "unknown"
    return "match" if digest == recorded else "mismatch"


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


def pin_warnings(pins):
    """Pin names matching no registered probe — dead config must be loud.

    A misspelled pin (`doker = ...`) would otherwise silently report no
    drift forever, so unknown pin names are surfaced as warnings in both
    the table footer and the --json document.
    """
    known = {name for name, _, _ in PROBES}
    return sorted(name for name in pins if name not in known)


def format_table(records, pin_warnings=(), duplicate_pins=()):
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
    if pin_warnings:
        lines.append("unmatched pins (no such probe): %s"
                     % ", ".join(pin_warnings))
    if duplicate_pins:
        lines.append("duplicate pins (later lines ignored): %s"
                     % ", ".join(duplicate_pins))
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
        warnings = pin_warnings(load_pins(args.pins))
        duplicates = pin_duplicates(args.pins)
        pins_state = installed_pins_state(pins_path=args.pins)
        mismatch_lines = ([_PINS_MISMATCH_WARNING]
                          if pins_state == "mismatch" else [])
        if args.json:
            print(json.dumps({
                "generated_at": int(time.time()),
                "slice": "S1-status",
                "tools": records,
                "pin_warnings": warnings,
                "duplicate_pins": duplicates,
                "installed_pins_state": pins_state,
            }, indent=2))
        else:
            table = format_table(records, pin_warnings=warnings,
                                 duplicate_pins=duplicates)
            if mismatch_lines:
                table += "\n\n" + "\n".join(mismatch_lines)
            print(table)
        return 0
    return 2  # unreachable: argparse enforces the subcommand


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Pin every install target of proxy/deploy.sh against the README inventory.

proxy/README.md's Deploy section carries a machine-readable inventory
(the <!-- deploy-inventory:start --> ... <!-- deploy-inventory:end -->
block): every `sudo install` target in deploy.sh, its repo source, its
deployed owner:group:mode, and any conditional. A new /usr/local/bin
install (or a renamed one, or a changed owner/mode) currently drifts
silently: no test fails, no doc must change. Issue #1235 closes that gap.

This test pins both directions:

1. every `sudo install` target in deploy.sh resolves to an inventory row
   with the same src, owner, group, and mode;
2. every inventory row resolves to a `sudo install` target in deploy.sh.

Three shapes need explicit handling, and each is pinned rather than
special-cased away:

- `/etc/sudoers.d/swapd` is installed to a mktemp path (`$tmp_sudoers`)
  and then moved: the parser maps `$tmp_sudoers` through the
  `sudo mv -f "$tmp_sudoers" /etc/sudoers.d/swapd` line, which must exist
  exactly once.
- The two plane-push drop-in directories are created by
  `install -d "$_dropdir"` with a shell variable: the parser expands
  `_dropdir="/etc/systemd/system/$_svc.service.d"` over the
  `for _svc in swap-proxy push-worker; do` word list.
- `/home/swapd/inference-ssrf.allow` installs `/dev/null`, but only when
  absent: still a static install target, and the inventory row says so.

Deliberately out of the src/owner/mode pin, matching the inventory
block's own note: the plane-push drop-in file contents (written inline
via `sudo tee`, not `install`) and the CA bundle (built by
`proxy/build_ca_bundle.py --dest`, operator-overridable via
WITH_PROXY_CA_BUNDLE). They are NOT unguarded, though: the
`test_no_undocumented_non_install_writes` tripwire allowlists every
literal-absolute-path non-`install` file write by path — `sudo tee`
dests, `cp`/`rsync`/`mv`/`ln` dests, `safe_install.py` dests, the
CA-bundle `--dest`, absolute-path redirects (spaced and no-space),
`dd of=` — and fails loud on any write primitive the scanners cannot
see (bare `install` without sudo, `/usr/bin/install`, env-prefixed
installs, `sudo sh -c` subshells, `python3 -c` bodies that open files
for writing), so a `sudo tee /usr/local/bin/sneaky-tool` cannot drift
silently either. Scanners see literal absolute paths only: writes to
dynamic paths (`exec 9>"$UPDATER_STATE_DIR/…"`), the sudo-invoked
helper scripts (`ensure-approval-filer.sh` → /etc/group + /etc/gshadow,
`enforce_pending_dir.py` / `enforce_secrets_dir.py` → dir
create/chown/chmod), and py_compile's repo-local .pyc writes are
deliberately outside the tripwire's vocabulary and are named in the
README's out-of-scope list instead.

Non-vacuity (all verified by neutering, then reverted): renaming an
install dest fails direction 1; adding a bogus inventory row fails
direction 2; changing an owner or mode flag on an install line fails the
ownership pin; a trailing comment on an install line fails the
unparsed-line guard instead of slipping through; a commented-out install
line does not resurrect via a cross-line slurp.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "proxy" / "README.md"
DEPLOY = REPO_ROOT / "proxy" / "deploy.sh"

INV_START = "<!-- deploy-inventory:start -->"
INV_END = "<!-- deploy-inventory:end -->"

# Destinations deploy.sh writes through primitives OTHER than `sudo
# install` — generated content, conditional seeds, mode enforcement, the
# tee-written drop-ins, the CA bundle, and the sudoers fragment's
# mv-into-place destination (the move half of the mktemp+mv install whose
# src/owner/mode are pinned by the install inventory above — listed here
# so the mv scan below does not flag it). The non-install tripwire below
# fails loud on any literal-absolute-path file write NOT on this list: a
# `sudo tee /usr/local/bin/sneaky-tool` (a pattern already present in
# this file) must not drift silently.
_KNOWN_NON_INSTALL_WRITES = {
    # safe_install.py targets
    "/home/swapd/ssrf.deny",
    "/home/swapd/grants.json",
    "/home/swapd/swap.log",
    "/etc/logrotate.d/swap-proxy",
    # sudo tee drop-in contents (conditional: plane-enrolled)
    "/etc/systemd/system/swap-proxy.service.d/10-plane-push.conf",
    "/etc/systemd/system/push-worker.service.d/10-plane-push.conf",
    # CA bundle default dest (operator-overridable via WITH_PROXY_CA_BUNDLE)
    "/usr/local/share/with-proxy-ca/ca-bundle.crt",
    # sudoers mv-into-place (see the $tmp_sudoers mapping in the pin above)
    "/etc/sudoers.d/swapd",
}

# Marker src for rows whose target is created rather than copied
# (install -d directories).
DIR_SRC = "(none)"

# Absolute sources that are not repo files but are still static
# install sources.
STATIC_NON_REPO_SOURCES = {"/dev/null"}

# Line-local: a \s token matches \n, which let a non-matching install
# line slurp forward across newlines and resurrect a commented-out
# install — a silent bypass (the same failure the writer pin's QA round
# caught). Every pattern below stays line-local ([^\S\n]).
_SUDO_INSTALL = re.compile(r"^[^\S\n]*sudo[^\S\n]+install\b")


def _join_continuations(src):
    return re.sub(r"\\\n", " ", src)


def _tokenize_args(argstr):
    """Split an install argument string into tokens.

    No deploy.sh install line quotes spaces, but several quote shell
    variables ("$_dropdir", "$tmp_sudoers"); strip the quotes so the
    positional is the bare variable token.
    """
    tokens = []
    for tok in argstr.split():
        if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            tok = tok[1:-1]
        tokens.append(tok)
    return tokens


def _parse_install_line(line):
    """Parse one logical `sudo install` line.

    Returns (owner, group, mode, is_dir, src, dest) or None if the line
    is not a sudo-install line. Raises AssertionError on any flag or
    shape the parser does not understand — a silently skipped line
    would pass the pins vacuously.
    """
    if not _SUDO_INSTALL.match(line):
        return None
    argstr = _SUDO_INSTALL.sub("", line, count=1)
    tokens = _tokenize_args(argstr)
    owner = group = mode = None
    is_dir = False
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-o", "-g", "-m"):
            assert i + 1 < len(tokens), (
                "deploy.sh install line ends after flag %r: %r — extend "
                "the parser" % (tok, line.strip())
            )
            val = tokens[i + 1]
            if tok == "-o":
                owner = val
            elif tok == "-g":
                group = val
            else:
                mode = val
            i += 2
        elif tok == "-d":
            is_dir = True
            i += 1
        elif tok.startswith("-"):
            raise AssertionError(
                "deploy.sh install line uses flag %r the pin does not "
                "understand: %r — extend the parser, do not skip the line"
                % (tok, line.strip())
            )
        else:
            positionals.append(tok)
            i += 1
    assert owner is not None and group is not None and mode is not None, (
        "deploy.sh install line is missing an -o/-g/-m flag: %r — the "
        "pin requires the ownership contract on every install"
        % line.strip()
    )
    if is_dir:
        assert len(positionals) == 1, (
            "deploy.sh `install -d` line has %d positionals, expected 1 "
            "(the directory): %r" % (len(positionals), line.strip())
        )
        return (owner, group, mode, True, DIR_SRC, positionals[0])
    assert len(positionals) == 2, (
        "deploy.sh install line has %d positionals, expected src + dest: "
        "%r" % (len(positionals), line.strip())
    )
    return (owner, group, mode, False, positionals[0], positionals[1])


def _expand_dropdir(src):
    """Expand `install -d "$_dropdir"` to concrete directory paths.

    The deploy writes the drop-in dir per service in
    `for _svc in swap-proxy push-worker; do` with
    `_dropdir="/etc/systemd/system/$_svc.service.d"`. Expand that
    construction here so the inventory rows name the concrete dirs and
    the loop's service list stays the single source of truth.
    """
    loop = re.search(
        r"^[^\S\n]*for[^\S\n]+_svc[^\S\n]+in[^\S\n]+(.*?);[^\S\n]*do[^\S\n]*$",
        src,
        re.MULTILINE,
    )
    assert loop, (
        "deploy.sh's plane-push dropdir loop changed shape — update the "
        "expansion in test_deploy_inventory.py"
    )
    services = loop.group(1).split()
    assert services, "dropdir loop names no services"
    assign = re.search(
        r'^[^\S\n]*_dropdir="(/etc/systemd/system/\$_svc\.service\.d)"'
        r"[^\S\n]*$",
        src,
        re.MULTILINE,
    )
    assert assign, (
        "deploy.sh's _dropdir assignment changed shape — update the "
        "expansion in test_deploy_inventory.py"
    )
    template = assign.group(1)
    return [template.replace("$_svc", svc) for svc in services]


def _deploy_installs():
    """Every install target in deploy.sh.

    Returns a dict dest -> (src, owner, group, mode, notes) with all
    dynamic dests resolved to their concrete paths.
    """
    src = _join_continuations(DEPLOY.read_text())
    installs = {}
    unparsed = []
    # Tripwire: an env-prefixed form (`sudo VAR=x install ...`) matches
    # neither the strict pattern nor the unparsed-line guard, so it would
    # slip through both directions silently if undocumented. Fail loud.
    env_prefixed = [
        line.strip()
        for line in src.splitlines()
        if re.match(r"^[^\S\n]*sudo[^\S\n]+\S+[^\S\n]+install\b", line)
        and not _SUDO_INSTALL.match(line)
    ]
    assert not env_prefixed, (
        "proxy/deploy.sh has env-prefixed install lines the pin cannot "
        "parse: %s — extend the parser, do not let them slip through"
        % "; ".join(env_prefixed)
    )
    # Tripwire: a bare `install` (no sudo) matches neither the strict
    # parser nor the env-prefixed guard, so it would slip through both
    # directions silently (deploy.sh runs as the operator; installing
    # into /home/swapd needs no privilege). Fail loud.
    bare_install = [
        line.strip()
        for line in src.splitlines()
        if re.match(r"^[^\S\n]*install\b", line)
    ]
    assert not bare_install, (
        "proxy/deploy.sh has `install` lines without sudo the pin cannot "
        "parse: %s — use `sudo install` or extend the parser"
        % "; ".join(bare_install)
    )
    for line in src.splitlines():
        if not _SUDO_INSTALL.match(line):
            continue
        try:
            parsed = _parse_install_line(line)
        except AssertionError:
            unparsed.append(line.strip())
            continue
        owner, group, mode, is_dir, psrc, pdest = parsed
        if pdest == "$tmp_sudoers":
            # The sudoers fragment installs to a mktemp path and is then
            # moved into place. The mv line is the real destination and
            # must exist exactly once.
            mv = re.findall(
                r'^[^\S\n]*sudo[^\S\n]+mv[^\S\n]+-f[^\S\n]+'
                r'"\$tmp_sudoers"[^\S\n]+(\S+)[^\S\n]*$',
                src,
                re.MULTILINE,
            )
            assert mv, (
                "deploy.sh installs proxy/sudoers-swapd to $tmp_sudoers "
                "but no `sudo mv -f \"$tmp_sudoers\" <dest>` line exists "
                "— the fragment never goes live"
            )
            assert len(mv) == 1, (
                "deploy.sh moves $tmp_sudoers to %d destinations: %s — "
                "the pin expects exactly one" % (len(mv), ", ".join(mv))
            )
            dests = [mv[0]]
            notes = "via-mktemp+mv"
        elif pdest == "$_dropdir":
            dests = _expand_dropdir(src)
            notes = "install -d; conditional: plane-enrolled"
        else:
            assert not pdest.startswith("$"), (
                "deploy.sh install line has an unresolvable dynamic "
                "destination %r — teach the pin to expand it: %r"
                % (pdest, line.strip())
            )
            dests = [pdest]
            notes = ""
        for dest in dests:
            assert dest not in installs, (
                "deploy.sh installs %r twice — the inventory pin needs "
                "one row per dest" % dest
            )
            installs[dest] = (psrc, owner, group, mode, notes)
    # Fail loudly on any sudo-install line the strict parser rejected
    # (trailing comment, reformat): a silently skipped line would pass
    # the pins below vacuously.
    assert not unparsed, (
        "proxy/deploy.sh has sudo-install lines the pin cannot parse "
        "(trailing comment? unknown flag?): %s — extend the parser, do "
        "not let them slip through" % "; ".join(unparsed)
    )
    return installs


def _non_install_writes():
    """Absolute destinations deploy.sh writes outside `sudo install`.

    Scans for `sudo tee <dest>` (sudo flags and tee flags skipped, so
    `sudo -n tee -a /dest` reports the real dest), `cp`/`rsync`/`mv`/`ln`
    to absolute dests (`mv`/`ln` create files at absolute paths just like
    `cp` does — a `sudo mv /tmp/x /usr/local/bin/sneaky-tool` is an
    install in everything but name), `safe_install.py` dests, the
    CA-bundle `--dest`, output redirects to absolute paths (spaced and
    no-space forms — `echo x>/abs/path` is valid shell), and `dd of=`
    writes. A bare `install` (no sudo) or `/usr/bin/install` fails loud
    outright — both bypass the install parser, so they must use plain
    `install` or the parser must learn them. A `sudo sh -c '...'` /
    `sudo bash -c '...'` subshell body is opaque to every scanner and
    fails loud; likewise a `python3 -c` body that opens a file for
    writing (the read-only `python3 -c` JSON check stays green).

    The scanners only see literal absolute paths. Deliberately out of
    this tripwire's vocabulary (named, not an oversight): writes to
    dynamic paths (`exec 9>"$UPDATER_STATE_DIR/…"`, `mkdir -p
    "$approvals_dir"`), the sudo-invoked helper scripts
    (`proxy/ensure-approval-filer.sh` — writes /etc/group and
    /etc/gshadow; `proxy/enforce_pending_dir.py`,
    `proxy/enforce_secrets_dir.py` — dir create/chown/chmod), and
    `python3 -m py_compile`'s repo-local .pyc writes. Deletions
    (`sudo rm`) are out of the pin's stated scope.
    """
    src = _join_continuations(DEPLOY.read_text())
    found = set()
    # sudo tee <dest> — resolve the two dynamic forms deploy.sh uses.
    # Sudo flags and tee flags are skipped so `sudo -n tee -a /dest`
    # reports the real dest, not `-a`.
    for dest in re.findall(
        r"^[^\S\n]*.*?\bsudo(?:[^\S\n]+-\S+)*[^\S\n]+tee"
        r"(?:[^\S\n]+-\S+)*[^\S\n]+(\"[^\"]+\"|\S+)",
        src,
        re.MULTILINE,
    ):
        dest = dest.strip('"')
        if dest == "$tmp_deny":
            continue  # temp staging file, removed after safe_install
        if dest == "$_dropdir/10-plane-push.conf":
            found.update(
                d + "/10-plane-push.conf" for d in _expand_dropdir(src)
            )
            continue
        found.add(dest)
    # safe_install.py dests: the last positional before any redirect.
    # Anchored on `python3 proxy/safe_install.py` so the preflight file
    # list and the py_compile line (which merely NAME the helper) are
    # not mistaken for invocations.
    for m in re.finditer(
        r"\bpython3[^\S\n]+proxy/safe_install\.py\b(.*)$",
        src,
        re.MULTILINE,
    ):
        toks = _tokenize_args(m.group(1))
        pos = []
        i = 0
        valued = {"--src", "--owner", "--group", "--mode"}
        while i < len(toks):
            t = toks[i]
            if t in ("<", ">", ">>"):
                break
            if t in valued:
                i += 2
                continue
            if t.startswith("--"):
                i += 1
                continue
            pos.append(t)
            i += 1
        assert pos, (
            "deploy.sh safe_install.py invocation with no destination: "
            "%r" % m.group(0).strip()
        )
        found.add(pos[-1])
    # CA bundle: build_ca_bundle.py --dest "$ca_bundle_dest"; resolve the
    # operator-overridable default.
    if re.search(
        r"\bbuild_ca_bundle\.py\b.*?[^\S\n]--dest[^\S\n]+\"\$ca_bundle_dest\"",
        src,
    ):
        default = re.search(
            r'^[^\S\n]*ca_bundle_dest="\$\{WITH_PROXY_CA_BUNDLE:-([^}]+)\}"',
            src,
            re.MULTILINE,
        )
        assert default, (
            "deploy.sh's ca_bundle_dest assignment changed shape — update "
            "the tripwire in test_deploy_inventory.py"
        )
        found.add(default.group(1))
    # Output redirects to absolute paths (other than /dev/null), with
    # or without whitespace before the operator — `echo x>/abs/path` is
    # valid shell. The no-space lookbehind excludes `-` so `->` in
    # comments is not mistaken for a redirect. Both captures exclude a
    # trailing `)` so `2>/dev/null)` does not read as a distinct path.
    for pat in (
        r"[^\S\n][12]?>>?[^\S\n]*(\"(?:/[^\"]*)\"|/[^\s;|&\"')]+)",
        r"(?<=[\w\"')\]])[12]?>>?[^\S\n]*(\"(?:/[^\"]*)\"|/[^\s;|&\"')]+)",
    ):
        for dest in re.findall(pat, src):
            dest = dest.strip('"')
            if dest != "/dev/null":
                found.add(dest)
    # dd of= is a file write none of the scanners above see.
    for dest in re.findall(
        r"(?<![\w-])dd[^\S\n][^|;\n]*?\bof=(\"[^\"]+\"|/\S+)", src
    ):
        found.add(dest.strip('"'))
    # cp / rsync / mv / ln to absolute dests (the last absolute path
    # wins). `mv` and `ln` create files at absolute paths just like `cp`
    # does — a `sudo mv /tmp/x /usr/local/bin/sneaky-tool` is an install
    # in everything but name, so it must not slip past this tripwire.
    for dest in re.findall(
        r"^[^\S\n]*(?:sudo[^\S\n]+)?(?:cp|rsync|mv|ln)\b"
        r".*[^\S\n](/\S+)[^\S\n]*$",
        src,
        re.MULTILINE,
    ):
        found.add(dest)
    # /usr/bin/install bypasses the sudo-install parser entirely.
    full = re.findall(
        r"^[^\S\n]*(?:sudo[^\S\n]+)?/usr/bin/install\b", src, re.MULTILINE
    )
    assert not full, (
        "proxy/deploy.sh uses /usr/bin/install, which the pin does not "
        "parse — use plain `install` or extend the parser"
    )
    # A `sudo sh -c '...'` / `sudo bash -c '...'` body is opaque to every
    # scanner above (it can hide install/cp/tee/redirect writes). Fail
    # loud instead of passing it silently.
    subshell = [
        line.strip()
        for line in src.splitlines()
        if re.match(
            r"^[^\S\n]*sudo[^\S\n]+\S*(?:sh|bash|dash|fish)[^\S\n]+-c\b",
            line,
        )
    ]
    assert not subshell, (
        "proxy/deploy.sh runs commands through a sudo subshell whose "
        "inner writes the pin cannot see: %s — inline them or extend "
        "the pin" % "; ".join(subshell)
    )
    # A `python3 -c '...'` body is opaque to the scanners above. The
    # read-only `python3 -c` JSON check stays green; any -c body that
    # opens a file for writing fails loud.
    for m in re.finditer(
        r"\bpython3[^\S\n]+-c[^\S\n]+(\".*?\"|'.*?')", src, re.DOTALL
    ):
        body = m.group(1)[1:-1]
        assert not (
            re.search(r"open\([^)]*['\"][^'\"]*[wa+]", body)
            or "write_text(" in body
            or "os.write(" in body
        ), (
            "proxy/deploy.sh has a `python3 -c` body that writes files, "
            "which the pin cannot see: %r — extend the pin" % body[:80]
        )
    return found


def _inventory_rows():
    """Parse the README's deploy-inventory block into rows.

    Returns a dict dest -> (src, owner, group, mode).
    """
    text = README.read_text()
    assert INV_START in text, (
        "proxy/README.md lost the %r marker — update the pin's bounds"
        % INV_START
    )
    assert INV_END in text, (
        "proxy/README.md lost the %r marker — update the pin's bounds"
        % INV_END
    )
    block = text.split(INV_START, 1)[1].split(INV_END, 1)[0]
    rows = {}
    for lineno, raw in enumerate(block.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [f.strip() for f in line.split("|", 3)]
        assert len(fields) == 4, (
            "deploy-inventory block line %d is not `dest | src | "
            "owner:group:mode | notes`: %r" % (lineno, raw)
        )
        dest, psrc, ogm, _notes = fields
        assert dest.startswith("/"), (
            "deploy-inventory block line %d: dest %r is not absolute"
            % (lineno, dest)
        )
        m = re.fullmatch(r"([^:]+):([^:]+):(\d{4})", ogm)
        assert m, (
            "deploy-inventory block line %d: %r is not "
            "owner:group:mode" % (lineno, ogm)
        )
        owner, group, mode = m.groups()
        if psrc == DIR_SRC or psrc in STATIC_NON_REPO_SOURCES:
            pass
        else:
            assert not psrc.startswith("/"), (
                "deploy-inventory block line %d: src %r is absolute but "
                "not a known static source" % (lineno, psrc)
            )
            assert (REPO_ROOT / psrc).exists(), (
                "deploy-inventory block line %d: src %r does not exist "
                "in the repo" % (lineno, psrc)
            )
        assert dest not in rows, (
            "deploy-inventory block lists %r twice" % dest
        )
        rows[dest] = (psrc, owner, group, mode)
    assert rows, "the deploy-inventory block has no rows"
    return rows


def test_deploy_installs_are_all_inventoried():
    """Every deploy.sh install target has a matching inventory row."""
    installs = _deploy_installs()
    rows = _inventory_rows()
    missing = sorted(d for d in installs if d not in rows)
    assert not missing, (
        "deploy.sh install targets with no proxy/README.md "
        "deploy-inventory row: %s" % ", ".join(missing)
    )
    mismatched = []
    for dest, (psrc, owner, group, mode, _notes) in installs.items():
        rsrc, rowner, rgroup, rmode = rows[dest]
        if (psrc, owner, group, mode) != (rsrc, rowner, rgroup, rmode):
            mismatched.append(
                "%s: deploy.sh has %s %s:%s:%s, inventory has %s %s:%s:%s"
                % (dest, psrc, owner, group, mode,
                   rsrc, rowner, rgroup, rmode)
            )
    assert not mismatched, (
        "deploy.sh install targets whose src/owner/group/mode differ "
        "from the inventory: %s" % "; ".join(mismatched)
    )


def test_inventory_rows_are_all_deployed():
    """Every inventory row matches a deploy.sh install target."""
    installs = _deploy_installs()
    rows = _inventory_rows()
    extra = sorted(d for d in rows if d not in installs)
    assert not extra, (
        "proxy/README.md deploy-inventory rows with no matching "
        "deploy.sh install target: %s" % ", ".join(extra)
    )


def test_no_undocumented_non_install_writes():
    """Every non-`install` file write in deploy.sh is allowlisted.

    A `sudo tee /usr/local/bin/sneaky-tool` (a pattern already present in
    this file) is not a `sudo install` target, so the two pin tests above
    would pass on it silently. This tripwire scans the other write
    primitives (`sudo tee` with flag skipping, `cp`/`rsync`/`mv`/`ln`,
    `safe_install.py` dests, the CA-bundle `--dest`, absolute-path
    redirects in spaced and no-space forms, `dd of=`) and fails loud on
    any write primitive it cannot see (bare `install`, `/usr/bin/install`,
    env-prefixed installs, `sudo sh -c` subshells, `python3 -c` bodies
    that open files for writing) — and on any literal-absolute-path
    destination not in _KNOWN_NON_INSTALL_WRITES, in both directions.
    """
    found = _non_install_writes()
    unknown = sorted(found - _KNOWN_NON_INSTALL_WRITES)
    assert not unknown, (
        "proxy/deploy.sh writes files outside `sudo install` that are "
        "not in _KNOWN_NON_INSTALL_WRITES: %s — allowlist them with a "
        "reason or extend the pin" % ", ".join(unknown)
    )
    stale = sorted(_KNOWN_NON_INSTALL_WRITES - found)
    assert not stale, (
        "_KNOWN_NON_INSTALL_WRITES names paths deploy.sh no longer "
        "writes: %s — remove them" % ", ".join(stale)
    )

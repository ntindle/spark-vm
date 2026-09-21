"""Hermetic smoke test for jail/build.sh.

build.sh mutates the host (debootstrap, nftables, machinectl) and can never
run in CI, so this pins what a smoke check CAN verify without executing it:
  - syntax (bash -n, shellcheck at error severity)
  - strict mode + flag contract
  - --help / -h renders the header doc and exits 0 before any side effect
    (plus a structural tripwire that no side-effecting statement sits
    above the help branch)
  - the tailnet->jail DNAT port is single-sourced from $JAIL_SSH_PORT
    (quoted heredoc + sed placeholder substitution, render-verified)
  - idempotency guards (re-runs must not re-bootstrap a good rootfs)
  - the jail's documented isolation properties (no bind mounts, no DNS,
    proxy-only nftables egress, explicit UID range, sshd hardening)
  - secret hygiene (the swapd CA is installed via the symlink-safe
    build_ca_bundle.py helper, never plain cp; no embedded key material)

A future edit that silently drops one of these properties fails the suite.
"""
import os
import re
import subprocess

import pytest

JAIL_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_SH = os.path.join(JAIL_DIR, "build.sh")


@pytest.fixture()
def src():
    with open(BUILD_SH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def active(src):
    # Full-line comments stripped: a security property must be an ACTIVE
    # line, not a commented-out remnant — otherwise `# ResolvConf=off`
    # would pass. Negative scans use `src` (a commented-out "--bind"
    # mention is still worth a human look).
    return "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#"))


class TestSyntax:
    def test_bash_syntax(self):
        p = subprocess.run(["bash", "-n", BUILD_SH],
                           capture_output=True, text=True)
        assert p.returncode == 0, p.stderr

    def test_shellcheck_error_severity(self, src):
        try:
            p = subprocess.run(
                ["shellcheck", "-S", "error", BUILD_SH],
                capture_output=True, text=True)
        except FileNotFoundError:
            pytest.skip("shellcheck not installed")
        assert p.returncode == 0, p.stdout


class TestContract:
    def test_strict_mode(self, active):
        assert "set -euo pipefail" in active

    def test_rebuild_flag_contract(self, active):
        assert "REBUILD_ROOTFS=0" in active
        assert '[ "$a" = "--rebuild-rootfs" ]' in active

    def test_idempotent_rootfs(self, active):
        # Re-running must skip debootstrap over a good tree.
        assert 'test -x "$ROOTFS/bin/bash"' in active
        assert "rootfs present, skipping debootstrap" in active
        # The unprivileged -x check is deliberately run under sudo (the
        # rootfs is root-owned); pin that the guard is not weakened.
        assert '$SUDO test -x "$ROOTFS/bin/bash"' in active


class TestHelp:
    """`build.sh --help` / `-h` must render the header doc and exit 0
    BEFORE any side effect — the only safe entry point on a dev box.
    The structural test below pins that contract: a future edit that
    inserts a side-effecting statement above the help branch fails the
    suite even though --help still exits 0."""

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_help_exits_zero_with_usage(self, flag):
        p = subprocess.run(["bash", BUILD_SH, flag],
                           capture_output=True, text=True)
        assert p.returncode == 0, f"build.sh {flag} failed:\n{p.stderr}"
        # The help path renders the script's header doc: the jail's
        # properties a contributor needs before ever running it as root.
        assert "systemd-nspawn" in p.stdout
        assert "usage: build.sh [--rebuild-rootfs] [--help]" in p.stdout

    def test_help_runs_from_another_cwd(self):
        # $0 resolution must not depend on being run from the repo root.
        p = subprocess.run(["bash", BUILD_SH, "--help"],
                           capture_output=True, text=True, cwd="/tmp")
        assert p.returncode == 0, p.stderr

    def test_help_branch_precedes_all_side_effects(self, src):
        lines = src.splitlines()
        idx = next(
            i for i, ln in enumerate(lines)
            if re.search(r'\[\s*"\$\{1:-\}"\s*=\s*"--help"', ln))
        for n, ln in enumerate(lines[1:idx], start=2):  # [1:] drops the shebang
            code = ln.split("#", 1)[0].rstrip()
            if not code.strip():
                continue  # blank or comment-only
            _assert_side_effect_free(code, n)


# Statement shapes that are provably side-effect-free: anything else above
# the --help branch is treated as a potential side effect. Every pattern
# is full-line anchored ($): a prefix match would let `set -euo pipefail;
# touch /tmp/pwned` sail through on the allowed prefix.
_SIDE_EFFECT_FREE = (
    re.compile(r"^set(?:\s+-?[A-Za-z][A-Za-z0-9-]*)+\s*$"),
    re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*="
               r"(?:\"[^\"]*\"|'[^']*'|[^\s;|&(){}<>]*?)"
               r"(?:\s+|$))+$"),
    re.compile(r"^for\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+\"\$\@\"\s*;\s*do\s+"
               r"\[.*\]\s*(?:&&|\|\|)\s*"
               r"[A-Za-z_][A-Za-z0-9_]*="
               r"(?:\"[^\"]*\"|'[^']*'|[^\s;|&(){}<>]*?)"
               r"\s*;\s*done\s*$"),
)


def _assert_side_effect_free(ln, lineno):
    # Command or process substitution can run arbitrary commands — never
    # allowed above the --help branch, even inside an assignment.
    for sub in ("$(", "`", "<(", ">("):
        assert sub not in ln, (
            f"line {lineno}: substitution above the --help branch: {ln!r}")
    assert any(p.search(ln) for p in _SIDE_EFFECT_FREE), (
        f"line {lineno}: statement above the --help branch may have "
        f"side effects: {ln!r}")


@pytest.mark.parametrize("mutant", [
    # Each of these runs a real command in bash and must be rejected by
    # the tripwire — they prove the gate is not vacuous.
    "for a in <(touch /tmp/pw4); do X=1; done",   # process substitution
    "X=$(touch /tmp/pw5)",                        # command substitution
    "touch /tmp/pw6",                             # bare command
    "set -euo pipefail; touch /tmp/pw7",          # chained after an allowed prefix
    "X=1 Y=$(touch /tmp/pw8)",                    # substitution in a later assignment
])
def test_help_tripwire_rejects_side_effects(mutant):
    with pytest.raises(AssertionError):
        _assert_side_effect_free(mutant, 0)


class TestSshPortSingleSourced:
    """$JAIL_SSH_PORT is the single source for the tailnet->jail DNAT
    port. The nftables heredoc stays QUOTED (no accidental expansion);
    the port is substituted by sed on the way into `tee`, so the conf
    the firewall applies always carries the variable's value."""

    def _port(self, src):
        m = re.search(r"^JAIL_SSH_PORT=(\d+)\s*(?:#.*)?$", src, re.M)
        assert m, "JAIL_SSH_PORT assignment not found"
        return m.group(1)

    def _heredoc_body(self, src):
        m = re.search(r"<<'NFT_EOF'[^\n]*\n(.*?)\nNFT_EOF$", src, re.M | re.S)
        assert m, "quoted NFT_EOF heredoc not found"
        return m.group(1)

    def test_dnat_rule_uses_placeholder(self, src, active):
        port = self._port(src)
        body = self._heredoc_body(src)
        assert body.count("@@JAIL_SSH_PORT@@") == 1
        assert ('iifname "tailscale0" tcp dport @@JAIL_SSH_PORT@@ '
                'dnat ip to 10.99.0.2:22') in active
        # No literal port anywhere: a second hardcoded copy would drift.
        assert f"dport {port} dnat" not in active
        # The jail-side accept stays the jail's own port 22 (unrelated).
        assert "tcp dport 22 ct state new,established accept" in active

    def test_substitution_mechanism_pinned(self, src):
        # Quoted heredoc (no expansion) piped through the placeholder
        # substitution into tee: change the shape and this fails loudly.
        assert ('sed "s/@@JAIL_SSH_PORT@@/${JAIL_SSH_PORT}/g" '
                "<<'NFT_EOF' | $SUDO tee /etc/nftables-jail.conf >/dev/null") in src

    def test_rendered_conf_carries_port(self, src):
        # Prove the mechanism end to end: render the heredoc exactly the
        # way build.sh does and check the applied line.
        port = self._port(src)
        rendered = self._heredoc_body(src).replace("@@JAIL_SSH_PORT@@", port)
        assert "@@" not in rendered
        assert (f'iifname "tailscale0" tcp dport {port} '
                'dnat ip to 10.99.0.2:22') in rendered

    def test_verify_line_uses_variable(self, active):
        assert 'ssh -p $JAIL_SSH_PORT $JAIL_USER@<tailnet-ip>' in active


class TestIsolation:
    def test_no_host_bind_mounts(self, src, active):
        for pat in ("--bind", "Bind=", "--bind-ro", "bindfs"):
            assert pat not in active, pat
        assert "Deliberately no bind mounts" in src

    def test_explicit_uid_range_not_yes(self, active):
        assert "PrivateUsers=2000000:65536" in active
        assert not re.search(r"^PrivateUsers=yes\s*$", active, re.M)

    def test_no_dns_in_jail(self, active):
        assert "ResolvConf=off" in active

    def test_nftables_drops_jail_egress(self, active):
        assert 'iifname "ve-jail" log prefix "jail-fwd-drop: " drop' in active

    def test_nftables_drops_jail_to_host_services(self, active):
        assert 'iifname "ve-jail" log prefix "jail-input-drop: " drop' in active

    def test_nftables_drops_traffic_into_jail(self, active):
        assert 'oifname "ve-jail" log prefix "jail-fwd-indrop: " drop' in active

    def test_nftables_accept_head_is_proxy_and_ssh_only(self, active):
        # Pin the allow head, not just the drop tail: these are the ONLY
        # things the jail can reach. Exact lines so a widened rule fails
        # loudly instead of hiding behind the passing drop pins.
        assert 'iifname "ve-jail" tcp dport { 18080, 18081 } accept' in active
        assert 'iifname "ve-jail" ct state established,related accept' in active
        assert ('iifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 '
                'tcp dport 22 ct state new,established accept') in active
        assert 'oifname "ve-jail" ct state established,related accept' in active
        assert ('iifname "ve-jail" ip daddr 10.99.0.1 '
                'tcp dport { 18080, 18081 } dnat to 127.0.0.1') in active
        assert ('iifname "tailscale0" tcp dport @@JAIL_SSH_PORT@@ '
                'dnat ip to 10.99.0.2:22') in active
        # No broader jail-side accept: every `iifname "ve-jail" … accept`
        # line must be one of the pinned narrow rules above.
        for line in active.splitlines():
            line = line.strip()
            if line.startswith('iifname "ve-jail"') and line.endswith("accept"):
                assert line in (
                    'iifname "ve-jail" tcp dport { 18080, 18081 } accept',
                    'iifname "ve-jail" ct state established,related accept',
                ), line

    def test_route_localnet_scoped_to_veth(self, active):
        assert "net.ipv4.conf.ve-$MACHINE.route_localnet=1" in active
        assert "net.ipv4.conf.all.route_localnet" not in active

    def test_sshd_hardening(self, active):
        assert "PermitRootLogin no" in active
        assert "PasswordAuthentication no" in active
        assert "KbdInteractiveAuthentication no" in active
        assert "X11Forwarding no" in active
        assert 'AllowUsers \'"$JAIL_USER"\'' in active
        # Deliberate hardening tradeoff: ~/.ssh/environment carries the
        # proxy vars for non-interactive ssh (documented in build.sh). Pin
        # it so a change fails loudly instead of silently widening or
        # narrowing session env.
        assert "PermitUserEnvironment yes" in active

    def test_guest_network_shadows_systemd_default(self, active):
        # Same-name file wins over /usr/lib's default; a differently-named
        # file would lose lexicographically. Pin the filename.
        assert "80-container-host0.network" in active


class TestSecretHygiene:
    def test_swapd_ca_copied_from_host_path(self, active):
        assert "/home/swapd/.mitmproxy/mitmproxy-ca-cert.pem" in active

    def test_swapd_ca_installed_via_symlink_safe_helper(self, active):
        # Issue #144 class: the CA source is swapd-writable, so the install
        # must go through build_ca_bundle.py's O_NOFOLLOW refusal, not cp.
        assert "build_ca_bundle.py" in active
        assert "--ca-only" in active

    def test_no_symlink_following_ca_copy(self, src):
        # A bare `cp` of the swapd CA follows a planted symlink (#144).
        for line in src.splitlines():
            if "mitmproxy-ca-cert.pem" in line and not line.lstrip().startswith("#"):
                assert not re.match(r"\s*\$SUDO cp ", line), \
                    "plain cp of the swapd CA follows symlinks: %r" % line

    def test_no_embedded_pem(self, src):
        assert "-----BEGIN" not in src

    def test_no_embedded_ssh_key(self, src):
        assert "ssh-ed25519 AAAA" not in src
        assert "ssh-rsa AAAA" not in src

    def test_pubkey_comes_from_file_not_literal(self, active):
        assert 'PUBKEY="$(cat "$PUBKEY_FILE")"' in active

    def test_no_curl_pipe_bash(self, active):
        assert not re.search(r"curl[^\n]*\|\s*(ba)?sh", active)
        assert not re.search(r"wget[^\n]*\|\s*(ba)?sh", active)

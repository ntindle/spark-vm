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
  - the fail-closed enforcement-downgrade contract (TestFailClosedOrdering:
    firewall applied before the machine starts; the jail Requires= the
    firewall at boot; no runtime re-apply — the stated residual)
  - secret hygiene (the swapd CA is installed via the symlink-safe
    build_ca_bundle.py helper, never plain cp; no embedded key material)

A future edit that silently drops one of these properties fails the suite.
"""
import os
import re
import subprocess
from pathlib import Path

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

    def test_help_honored_in_any_position(self):
        # Usage documents `build.sh [--rebuild-rootfs] [--help]`; --help
        # after the rebuild flag must still exit before the privileged
        # build instead of starting it (B1). Safe: help exits pre-side-effect.
        p = subprocess.run(["bash", BUILD_SH, "--rebuild-rootfs", "--help"],
                           capture_output=True, text=True, cwd="/tmp")
        assert p.returncode == 0, f"build.sh --rebuild-rootfs --help failed:\n{p.stderr}"
        assert "usage: build.sh [--rebuild-rootfs] [--help]" in p.stdout

    def test_help_branch_precedes_all_side_effects(self, src):
        lines = src.splitlines()
        # Strip comments before searching: a comment above the branch
        # containing the help-check text would otherwise shrink the
        # scanned region (QA review).
        idx = next(
            i for i, ln in enumerate(lines)
            if re.search(r'\[\s*"\$SHOW_HELP"\s*=\s*1\s*\]', ln.split("#", 1)[0]))
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
    "X=`touch /tmp/pw9`",                        # backtick substitution
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
        assert "tcp dport 22 ct state established,new accept" in active

    def test_substitution_mechanism_pinned(self, src):
        # Quoted heredoc (no expansion) piped through the placeholder
        # substitution into tee: change the shape and this fails loudly.
        assert ('sed "s/@@JAIL_SSH_PORT@@/${JAIL_SSH_PORT}/g" '
                "<<'NFT_EOF' | $SUDO tee /etc/nftables-jail.conf >/dev/null") in src

    def test_rendered_conf_carries_port(self, src):
        # Prove the mechanism end to end: render the heredoc exactly the
        # way build.sh does — through the real sed pipeline, not a
        # reimplementation — and check the applied line.
        port = self._port(src)
        p = subprocess.run(
            ["sed", f"s/@@JAIL_SSH_PORT@@/{port}/g"],
            input=self._heredoc_body(src), capture_output=True, text=True)
        assert p.returncode == 0, f"sed render failed:\n{p.stderr}"
        rendered = p.stdout
        assert "@@" not in rendered
        assert (f'iifname "tailscale0" tcp dport {port} '
                'dnat ip to 10.99.0.2:22') in rendered

    def test_verify_line_uses_variable(self, active):
        assert 'ssh -p $JAIL_SSH_PORT $JAIL_USER@<tailnet-ip>' in active


class TestFailClosedOrdering:
    """C22: the enforcement-downgrade contract. The jail must never run
    where its firewall cannot be enforced. These tests pin the mechanism
    the README's contract section states: firewall-before-machine at
    build time, firewall-required-by-nspawn at boot time.

    All assertions run against the `active` fixture (full-line comments
    stripped): a commented-out ordering/dependency line must fail, not
    pass on a substring match."""

    def _firewall_unit(self, active):
        m = re.search(
            r"tee /etc/systemd/system/jail-firewall\.service.*?\nEOF",
            active, re.S)
        assert m, "jail-firewall.service unit block not found"
        return m.group(0)

    def _requires_dropin(self, active):
        m = re.search(
            r"systemd-nspawn@\$MACHINE\.service\.d/firewall-requires\.conf"
            r".*?\nEOF",
            active, re.S)
        assert m, ("consumer-side firewall-requires.conf drop-in not "
                   "found")
        return m.group(0)

    def test_firewall_unit_applies_table(self, active):
        unit = self._firewall_unit(active)
        assert "Type=oneshot" in unit
        assert "nft -f /etc/nftables-jail.conf" in unit

    def test_jail_requires_firewall(self, active):
        # Before= is ordering-only: a failed firewall apply would NOT
        # stop the jail. The fail-closed edge is Requires= on the
        # consumer side (the nspawn unit), so a failed apply blocks the
        # container from starting.
        dropin = self._requires_dropin(active)
        assert "Requires=jail-firewall.service" in dropin
        assert "After=jail-firewall.service" in dropin
        # The producer unit keeps its ordering declaration too.
        assert "Before=systemd-nspawn@jail.service" in self._firewall_unit(active)

    def test_firewall_applied_before_machine_start(self, active):
        # set -e aborts the build if the firewall apply fails, so no jail
        # ever starts without its table. Pin the structural ordering:
        # the enable --now must precede any machinectl start.
        fw = active.index("systemctl enable --now jail-firewall.service")
        start = active.index("machinectl start $MACHINE")
        assert fw < start, (
            "firewall apply must precede the machine start")

    def test_firewall_watchdog_mechanism_documented(self, active):
        # C25 closed the "no runtime re-apply" residual fail-closed: the
        # verify timer exists, the README documents it, and the residual
        # is bounded downtime. (This replaced
        # test_no_firewall_reapply_mechanism — the C22 residual no longer
        # exists, so asserting its absence would be a falsehood that
        # passed vacuously on the new unit names.)
        assert "jail-firewall-verify.timer" in active
        readme = open(os.path.join(JAIL_DIR, "README.md"),
                      encoding="utf-8").read()
        assert "jail-firewall-verify" in readme
        assert "bounded downtime" in readme


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
                'tcp dport 22 ct state established,new accept') in active
        assert 'oifname "ve-jail" ct state established,related accept' in active
        assert ('iifname "ve-jail" ip daddr 10.99.0.1 '
                'tcp dport { 18080, 18081 } dnat ip to 127.0.0.1') in active
        assert ('iifname "tailscale0" tcp dport @@JAIL_SSH_PORT@@ '
                'dnat ip to 10.99.0.2:22') in active
        # No broader jail-side accept: every `iifname "ve-jail" … accept`
        # line must be one of the pinned narrow rules above.
        pinned = {
            'iifname "ve-jail" tcp dport { 18080, 18081 } accept',
            'iifname "ve-jail" ct state established,related accept',
            ('iifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 '
             'tcp dport 22 ct state established,new accept'),
            'oifname "ve-jail" ct state established,related accept',
            ('iifname "ve-jail" ip daddr 10.99.0.1 '
             'tcp dport { 18080, 18081 } dnat ip to 127.0.0.1'),
            ('iifname "tailscale0" tcp dport @@JAIL_SSH_PORT@@ '
             'dnat ip to 10.99.0.2:22'),
        }
        # (A5 hardening) No extra verdicts anywhere: every accept or dnat
        # line in the generated table must be one of the pinned rules — a
        # widened ssh-forward or oifname accept added to build.sh fails
        # here, not just in the runtime watchdog.
        for line in active.splitlines():
            line = line.strip()
            if line.endswith("accept") or "dnat" in line:
                assert line in pinned, line

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


VERIFY_SCRIPT = os.path.join(JAIL_DIR, "jail-firewall-verify.sh")


@pytest.fixture()
def verify_src():
    with open(VERIFY_SCRIPT, encoding="utf-8") as f:
        return f.read()


class TestFirewallWatchdogStatic:
    """C25 / issue #254: runtime watchdog for `table inet jail`.

    Fail-closed design (round-2 review, Security + Architecture): the
    watchdog pins the enforcement RULES, not the chain shells (all chains
    are policy accept, so an emptied chain is open egress); on confirmed
    damage it stops the jail before repairing (a re-apply does not flush
    conntrack); every fail-closed event exits nonzero so the unit goes
    red. Static pins live here; the detection semantics are exercised
    functionally in TestFirewallWatchdogFunctional with a stubbed nft.
    """

    def test_script_installed_from_repo_file(self, active):
        # The script is a first-class repo file, not a build.sh heredoc:
        # directly testable, shellcheckable, reviewable.
        assert 'VERIFY_SCRIPT="$(dirname "$0")/jail-firewall-verify.sh"' \
            in active
        assert 'install -m 755 "$VERIFY_SCRIPT" ' \
            '/usr/local/sbin/jail-firewall-verify.sh' in active

    def test_script_install_guarded(self, active):
        assert '[[ -f "$VERIFY_SCRIPT" ]]' in active

    def test_pins_enforcement_markers_not_chain_shells(self, verify_src):
        # Security blocker (round 1): `nft flush chain` empties rules but
        # leaves chain definitions; grepping 'chain forward' would report
        # healthy on an open-egress chain. The markers are the drop-rule
        # log prefixes and the proxy DNAT.
        for marker in ("jail-fwd-drop", "jail-fwd-indrop",
                       "jail-input-drop", "dnat ip to 127.0.0.1"):
            assert marker in verify_src, "marker missing: %s" % marker
        # ...and the check must not be satisfiable by chain shells alone.
        assert "grep -q 'chain forward'" not in verify_src

    def test_single_nft_list_call(self, verify_src):
        # One listing parsed repeatedly: no triple invocation, no TOCTOU
        # between checks.
        assert verify_src.count("list table") == 1

    def test_validates_before_destroy(self, verify_src):
        # A corrupt conf must not widen the hole: `nft -c -f` precedes any
        # destroy. Order pinned by position.
        check = verify_src.index("-c -f")
        destroy = verify_src.index("destroy table")
        assert check < destroy, "validation must precede destroy"

    def test_fail_closed_stop_before_repair(self, verify_src):
        # Architecture blocker (round 1): conntrack survives a re-apply, so
        # hole-era flows would pass established,related after repair. The
        # jail stops FIRST; restart is the operator's explicit decision.
        stop = verify_src.index("systemctl stop systemd-nspawn@jail")
        destroy = verify_src.index("destroy table")
        assert stop < destroy, "jail stop must precede table repair"

    def test_red_unit_on_every_fail_closed_event(self, verify_src):
        # Structural, not string-presence (Engineering round-1 blocker 3:
        # asserting '"exit 1" in script' is theater — a flipped failure
        # branch would still pass). Both CRITICAL failure paths must be
        # immediately followed by exit 1, and the repaired-and-stopped
        # path must end exit 1 — the operator has to see that the jail
        # was stopped, even when the repair succeeded.
        crit_exits = re.findall(r'CRITICAL[^\n]*\n\s*exit 1', verify_src)
        assert len(crit_exits) == 2, \
            "each CRITICAL failure path must exit nonzero: %r" % crit_exits
        non_empty = [l for l in verify_src.splitlines()
                     if l.strip() and not l.lstrip().startswith("#")]
        assert non_empty[-1].strip() == "exit 1", \
            "script must end exit 1 (red unit on repair)"

    def test_repair_scoped_to_jail_table(self, verify_src):
        assert 'destroy table "$TABLE"' in verify_src
        assert 'TABLE="inet jail"' in verify_src

    def test_no_unscoped_nft_destruction(self, verify_src):
        for line in verify_src.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert "flush ruleset" not in line, \
                "watchdog must not flush the whole ruleset: %r" % line
            assert "flush chain" not in line, \
                "watchdog must not flush chains either: %r" % line

    def test_transient_recheck(self, verify_src):
        # The oneshot service's own destroy-then-apply is a
        # millisecond-scale hole; one re-check before treating it as
        # damage avoids fail-closed false positives.
        assert "sleep 10" in verify_src

    def test_allow_head_pin(self, verify_src):
        # Arch finding (2026-09-23): the marker presence checks cannot see
        # a WIDENED ruleset — with policy-accept chains, an added broad
        # accept above the drops voids the isolation exactly like a
        # deleted drop. healthy() must also pin the allow head: every rule
        # line in the live table must be one of the installed conf's rule
        # lines, matched on the FULL rule text (match expression plus
        # verdict) — a broadened match (dropped qualifier) is not the
        # expected line and fails closed.
        assert "allow_head_intact" in verify_src
        assert '&& allow_head_intact "$rules"' in verify_src
        # The pin derives its expected lines from the installed conf —
        # nothing about the allow head is hardcoded in the script, so it
        # cannot drift from the table it guards (Architecture blocker 2).
        assert "conf_rule_lines" in verify_src
        assert "norm_rule_line" in verify_src
        assert 'CONF="${CONF:-/etc/nftables-jail.conf}"' in verify_src
        # Full-line exact matching with quotes INTACT (grep -qxF): a DNAT
        # port suffix cannot hide, and quoted interface names keep their
        # identity — stripping quotes made iifname "ve-jail" and
        # iifname "tailscale0" indistinguishable (Security round 2).
        assert "grep -qxF" in verify_src
        assert 's/"[^"]*"//g' not in verify_src
        # An unreadable conf must fail closed, not bless the table.
        assert '[ -n "$expected" ] || return 1' in verify_src

    def test_conf_fixture_matches_build_sh(self):
        # Drift test (Architecture blocker 2): the HEALTHY_CONF fixture
        # the functional tests stub must be exactly what build.sh renders
        # (@@JAIL_SSH_PORT@@ substituted). Extract the heredoc from
        # build.sh, apply the same sed, and compare normalized rule lines.
        build_sh = (Path(JAIL_DIR) / "build.sh").read_text()
        m = re.search(r"<<'NFT_EOF'.*?\n(.*?)\nNFT_EOF\n", build_sh, re.S)
        assert m, "nftables heredoc not found in build.sh"
        port = re.search(r"^JAIL_SSH_PORT=(\d+)", build_sh, re.M).group(1)
        rendered = m.group(1).replace("@@JAIL_SSH_PORT@@", port)

        def norm_lines(text):
            # Mirrors the production norm_rule_line (quotes INTACT —
            # Architecture final review: stripping quotes here would let a
            # quote-confined conf change pass while the fixture goes stale).
            out = []
            for line in text.splitlines():
                t = line.lstrip()
                if not t or t.startswith("#") or \
                        t.startswith(("chain", "type", "table", "}")):
                    continue
                out.append(t)
            return out

        assert norm_lines(rendered) == norm_lines(HEALTHY_CONF), \
            "HEALTHY_CONF drifted from build.sh's nftables heredoc"
        # Guard (Architecture round 2): an inline `#` comment on a conf
        # rule line would fail closed as a false positive (only full-line
        # comments are skipped by the pin). Keep comments on their own
        # lines so a future editor doesn't trip the watchdog.
        for line in rendered.splitlines():
            t = line.strip()
            if t and not t.startswith(("#", "table", "chain", "type", "}")):
                assert " #" not in t, "inline comment on conf rule: %r" % t

    def test_service_runs_the_script(self, active):
        m = re.search(
            r"tee /etc/systemd/system/jail-firewall-verify\.service"
            r".*?\nEOF",
            active, re.S)
        assert m, "jail-firewall-verify.service unit block not found"
        unit = m.group(0)
        assert "Type=oneshot" in unit
        assert "ExecStart=/usr/local/sbin/jail-firewall-verify.sh" in unit
        # Boot-ordering edge (Architecture round 2): the Persistent timer
        # can fire at timers.target, before the oneshot applies the table
        # at multi-user.target. Without an ordering edge the watchdog
        # would observe a legitimately-absent table and raise a spurious
        # fail-closed red unit at boot, training the operator to ignore
        # the signal.
        assert "Wants=jail-firewall.service" in unit
        assert "After=jail-firewall.service" in unit
        # Wants, never Requires: if the oneshot failed at boot, the
        # watchdog must still run and fail-close on the missing table.
        assert "Requires=jail-firewall.service" not in unit
        # Security round 2: pin the comparison source in the unit so the
        # pin compares against the conf it repairs from, not whatever
        # $CONF the environment happens to carry.
        assert "Environment=CONF=/etc/nftables-jail.conf" in unit

    def test_timer_cadence_and_wiring(self, active):
        m = re.search(
            r"tee /etc/systemd/system/jail-firewall-verify\.timer"
            r".*?\nEOF",
            active, re.S)
        assert m, "jail-firewall-verify.timer unit block not found"
        timer = m.group(0)
        assert "OnCalendar=*:0/5" in timer
        assert "WantedBy=timers.target" in timer
        assert "systemctl enable --now jail-firewall-verify.timer" in active


# ---------------------------------------------------------------- functional
# The detection semantics the round-1 review proved were missing: stub nft /
# systemctl / logger / sleep via PATH (+ the NFT env override) and run the
# real script against canned rulesets.

# The conf build.sh installs (JAIL_SSH_PORT=2222 substituted) — the
# watchdog's single source of truth for the allow-head pin. The drift
# test below pins this fixture to build.sh's actual heredoc.
HEALTHY_CONF = """\
# Proxy-only egress for the jail's veth (ve-jail).
table inet jail {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        iifname "ve-jail" ip daddr 10.99.0.1 tcp dport { 18080, 18081 } dnat ip to 127.0.0.1
        iifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.2:22
    }
    chain input {
        type filter hook input priority -10; policy accept;
        iifname "ve-jail" tcp dport { 18080, 18081 } accept
        iifname "ve-jail" ct state established,related accept
        iifname "ve-jail" log prefix "jail-input-drop: " drop
    }
    chain forward {
        type filter hook forward priority -10; policy accept;
        iifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 tcp dport 22 ct state established,new accept
        iifname "ve-jail" ct state established,related accept
        oifname "ve-jail" ct state established,related accept
        iifname "ve-jail" log prefix "jail-fwd-drop: " drop
        oifname "ve-jail" log prefix "jail-fwd-indrop: " drop
    }
}
"""

HEALTHY_RULESET = """\
table inet jail {
\tchain prerouting {
\t\ttype nat hook prerouting priority dstnat; policy accept;
\t\tiifname "ve-jail" ip daddr 10.99.0.1 tcp dport { 18080, 18081 } dnat ip to 127.0.0.1
\t\tiifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.2:22
\t}
\tchain input {
\t\ttype filter hook input priority -10; policy accept;
\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept
\t\tiifname "ve-jail" ct state established,related accept
\t\tiifname "ve-jail" log prefix "jail-input-drop: " drop
\t}
\tchain forward {
\t\ttype filter hook forward priority -10; policy accept;
\t\tiifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 tcp dport 22 ct state established,new accept
\t\tiifname "ve-jail" ct state established,related accept
\t\toifname "ve-jail" ct state established,related accept
\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop
\t\toifname "ve-jail" log prefix "jail-fwd-indrop: " drop
\t}
}
"""

# The Security round-1 case: `nft flush chain inet jail forward` — chains
# intact, rules gone, policy accept. Old code reported healthy; the new
# code must not.
FLUSHED_CHAIN_RULESET = """\
table inet jail {
\tchain prerouting {
\t\ttype nat hook prerouting priority dstnat; policy accept;
\t}
\tchain input {
\t\ttype filter hook input priority -10; policy accept;
\t}
\tchain forward {
\t\ttype filter hook forward priority -10; policy accept;
\t}
}
"""

# The 2026-09-23 arch case: a WIDENED ruleset — every drop marker and the
# proxy DNAT are present, but an injected broad accept sits above the
# drops. Marker presence alone reported healthy on this; the allow-head
# pin must not.
WIDENED_ACCEPT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
    '\t\tiifname "ve-jail" accept\n'
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
)

# The 2026-09-23 arch case: a rogue DNAT variant — the proxy DNAT's target
# gains a port. The old substring grep 'dnat to 127.0.0.1' still matched
# this; the end-anchored pin must not.
ROGUE_DNAT_RULESET = HEALTHY_RULESET.replace(
    'dnat ip to 127.0.0.1\n',
    'dnat ip to 127.0.0.1:9999\n',
)

# The 2026-09-23 review case (Security): a re-addressed DNAT variant —
# the target is a different host that still contains the 'dnat to
# 127.0.0.1' substring. The end-anchored pin must reject it.
ROGUE_DNAT_READDR_RULESET = HEALTHY_RULESET.replace(
    'dnat ip to 127.0.0.1\n',
    'dnat ip to 127.0.0.10\n',
)

# The 2026-09-23 review case (Security): a quoted-string smuggle — the
# broad accept carries a full accept fingerprint inside its log prefix.
# Unanchored fingerprint matching alone passes this; the pin must strip
# quoted strings before matching and fail closed.
SMUGGLER_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
    '\t\tiifname "ve-jail" log prefix "ct state established,related accept" accept\n'
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
)

# The 2026-09-23 review case (Security): a DNAT-family verdict spelled
# differently — 'redirect' moves packets without the 'dnat' or 'accept'
# substrings. The pin must deny all packet-moving verdicts it does not
# know, not just dnat/accept spellings.
REDIRECT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
    '\t\tiifname "ve-jail" tcp dport 9999 redirect to :9999\n'
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
)

# The 2026-09-23 review case (Engineering A1): a rogue sshd-DNAT
# variant — the target address is changed while the match stays narrow.
ROGUE_SSH_DNAT_RULESET = HEALTHY_RULESET.replace(
    'iifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.2:22',
    'iifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.99:22',
)

# The 2026-09-23 review case (Architecture, blocker 1): broadened-match
# variants — the realistic way a ruleset gets widened (an admin copying a
# rule and loosening it). Each keeps the verdict but drops narrowing
# qualifiers, so verdict-substring pins are blind to them; the full-rule
# pin must fail closed on all three.
# 1. Forward chain: jail sshd accept reachable from anywhere, not just the
#    tailnet (dropped iifname/oifname/daddr qualifiers).
BROADENED_SSH_ACCEPT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
    '\t\tiifname "ve-jail" tcp dport 22 ct state established,new accept\n'
    '\t\tiifname "ve-jail" log prefix "jail-fwd-drop: " drop',
)
# 2. Prerouting: the jail's sshd DNATed from any interface (dropped the
#    tailscale0 iifname).
BROADENED_DNAT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.2:22',
    '\t\ttcp dport 9999 dnat ip to 10.99.0.2:22',
)
# 3. Input chain: proxy ports accepted off every interface (dropped the
#    ve-jail iifname).
BROADENED_PROXY_ACCEPT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept',
    '\t\ttcp dport { 18080, 18081 } accept',
)

# The 2026-09-23 review case (Security round 2): an interface-name
# swap — the proxy accept with "ve-jail" replaced by "tailscale0".
# Quote-stripping made these indistinguishable; with quotes intact the
# line is not the conf's line and must fail closed.
IFACE_SWAP_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept',
    '\t\tiifname "tailscale0" tcp dport { 18080, 18081 } accept',
)

# A benign duplicate of a legit narrow rule: the pin must not false-positive
# on rule duplication (e.g. a re-applied table that kept a stale copy).
DUPLICATE_ACCEPT_RULESET = HEALTHY_RULESET.replace(
    '\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept\n',
    '\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept\n'
    '\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept\n',
)


@pytest.fixture()
def watchdog_stubs(tmp_path, monkeypatch):
    """PATH stub dir: nft (canned ruleset via $NFT_FIXTURE_FILE, rc via
    $NFT_LIST_RC / $NFT_CHECK_RC, invocation log at $NFT_LOG), systemctl,
    logger, sleep (no-op). Returns (stubdir, logpath)."""
    bindir = tmp_path / "stubs"
    bindir.mkdir()
    log = tmp_path / "calls.log"
    (bindir / "nft").write_text("""\
#!/bin/bash
echo "nft $*" >> "$CALLS_LOG"
if [ "$1 $2" = "list table" ]; then
    cat "$NFT_FIXTURE_FILE"; exit "${NFT_LIST_RC:-0}"
fi
if [ "$1 $2" = "-c -f" ]; then exit "${NFT_CHECK_RC:-0}"; fi
exit 0
""")
    (bindir / "systemctl").write_text("""\
#!/bin/bash
echo "systemctl $*" >> "$CALLS_LOG"
exit 0
""")
    (bindir / "logger").write_text("""\
#!/bin/bash
echo "logger $*" >> "$CALLS_LOG"
exit 0
""")
    (bindir / "sleep").write_text("#!/bin/bash\nexit 0\n")
    for f in ("nft", "systemctl", "logger", "sleep"):
        (bindir / f).chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + ":/usr/bin:/bin")
    monkeypatch.setenv("NFT", str(bindir / "nft"))
    monkeypatch.setenv("CALLS_LOG", str(log))
    monkeypatch.delenv("NFT_FIXTURE_FILE", raising=False)
    return log


def _run_watchdog(fixture_text=None, list_rc="0", check_rc="0",
                  tmp_path=None, monkeypatch=None, conf_text=HEALTHY_CONF):
    fix = tmp_path / "ruleset.txt"
    fix.write_text(fixture_text or "")
    conf = tmp_path / "nftables-jail.conf"
    conf.write_text(conf_text)
    monkeypatch.setenv("NFT_FIXTURE_FILE", str(fix))
    monkeypatch.setenv("CONF", str(conf))
    monkeypatch.setenv("NFT_LIST_RC", list_rc)
    monkeypatch.setenv("NFT_CHECK_RC", check_rc)
    return subprocess.run(
        ["bash", VERIFY_SCRIPT], capture_output=True, text=True)


class TestFirewallWatchdogFunctional:
    def test_healthy_table_exits_quiet(self, watchdog_stubs, tmp_path,
                                       monkeypatch):
        r = _run_watchdog(HEALTHY_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 0
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls

    def test_flushed_chain_triggers_fail_closed(self, watchdog_stubs,
                                                tmp_path, monkeypatch):
        # The round-1 Security hole: chain shells intact, rules gone.
        r = _run_watchdog(FLUSHED_CHAIN_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        # Fail-closed: jail stopped BEFORE the table is repaired.
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "nft -f %s" % (tmp_path / "nftables-jail.conf") in calls
        assert "ALERT" in calls

    def test_missing_table_triggers_fail_closed(self, watchdog_stubs,
                                                tmp_path, monkeypatch):
        r = _run_watchdog("", list_rc="1", tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_transient_gap_heals_without_drama(self, watchdog_stubs,
                                               tmp_path, monkeypatch):
        # First listing damaged (the oneshot's own destroy-then-apply
        # window), second listing healthy: no stop, no repair, exit 0.
        fix = tmp_path / "ruleset.txt"
        fix.write_text(FLUSHED_CHAIN_RULESET)
        monkeypatch.setenv("NFT_FIXTURE_FILE", str(fix))
        counter = tmp_path / "n"
        counter.write_text("0")
        stub = tmp_path / "stubs" / "nft"
        stub.write_text("""\
#!/bin/bash
echo "nft $*" >> "$CALLS_LOG"
if [ "$1 $2" = "list table" ]; then
    c=$(cat "$NFT_COUNT"); echo $((c+1)) > "$NFT_COUNT"
    if [ "$c" = "0" ]; then cat "$NFT_FIXTURE_FILE"; else cat "$NFT_HEALTHY"; fi
    exit 0
fi
exit 0
""")
        stub.chmod(0o755)
        healthy = tmp_path / "healthy.txt"
        healthy.write_text(HEALTHY_RULESET)
        conf = tmp_path / "nftables-jail.conf"
        conf.write_text(HEALTHY_CONF)
        monkeypatch.setenv("CONF", str(conf))
        monkeypatch.setenv("NFT_COUNT", str(counter))
        monkeypatch.setenv("NFT_HEALTHY", str(healthy))
        r = subprocess.run(["bash", VERIFY_SCRIPT],
                           capture_output=True, text=True)
        assert r.returncode == 0
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls

    def test_corrupt_conf_never_destroys(self, watchdog_stubs, tmp_path,
                                         monkeypatch):
        r = _run_watchdog(FLUSHED_CHAIN_RULESET, check_rc="1",
                          tmp_path=tmp_path, monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        # Fail-closed stop still happens, but the table is never widened.
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "destroy table" not in calls
        assert "CRITICAL" in calls

    def test_widened_accept_triggers_fail_closed(self, watchdog_stubs,
                                                 tmp_path, monkeypatch):
        # The 2026-09-23 arch case: every marker is present but an
        # injected broad accept sits above the drops — policy-accept
        # chains make this open egress. The old presence-only check
        # reported healthy; the allow-head pin must fail closed.
        r = _run_watchdog(WIDENED_ACCEPT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_rogue_dnat_variant_triggers_fail_closed(self, watchdog_stubs,
                                                     tmp_path, monkeypatch):
        # The old substring grep 'dnat to 127.0.0.1' matched the rogue
        # 'dnat to 127.0.0.1:9999' variant; the end-anchored pin must not.
        r = _run_watchdog(ROGUE_DNAT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_rogue_dnat_readdressed_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case: 'dnat ip to 127.0.0.10' is not the conf's
        # 'dnat ip to 127.0.0.1' line; the full-line pin must reject it.
        r = _run_watchdog(ROGUE_DNAT_READDR_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_smuggled_fingerprint_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Security): a broad accept smuggling a full accept
        # fingerprint inside its log prefix. Unanchored matching alone
        # passes this; the pin strips quoted strings first, so this must
        # fail closed — with stop-before-destroy ordering.
        r = _run_watchdog(SMUGGLER_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_redirect_verdict_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Security): 'redirect' moves packets without the
        # 'dnat' or 'accept' substrings. The pin denies packet-moving
        # verdicts it does not know; this must fail closed.
        r = _run_watchdog(REDIRECT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_iface_swap_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Security round 2): "ve-jail" swapped for
        # "tailscale0" on the proxy accept. Quoted identifiers are part
        # of the rule's identity; this must fail closed.
        r = _run_watchdog(IFACE_SWAP_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_rogue_ssh_dnat_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Engineering A1): the sshd DNAT's target is
        # re-addressed while the match stays narrow — not the conf's line.
        r = _run_watchdog(ROGUE_SSH_DNAT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_broadened_ssh_accept_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Architecture blocker 1): the SSH accept with its
        # narrowing qualifiers dropped — direct outbound SSH for the jail.
        # A verdict-substring pin is blind to this; the full-rule pin
        # must fail closed.
        r = _run_watchdog(BROADENED_SSH_ACCEPT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_broadened_dnat_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Architecture blocker 1): the sshd DNAT without the
        # tailscale0 iifname — reachable from any interface.
        r = _run_watchdog(BROADENED_DNAT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_broadened_proxy_accept_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # Review case (Architecture blocker 1): the proxy-port accept
        # without the ve-jail iifname — accepted off every interface.
        r = _run_watchdog(BROADENED_PROXY_ACCEPT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_benign_duplicate_accept_stays_healthy(self, watchdog_stubs,
                                                   tmp_path, monkeypatch):
        # A duplicated legit narrow rule is not damage: no false positive.
        r = _run_watchdog(DUPLICATE_ACCEPT_RULESET, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 0
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls


def _with_proxy_heredoc_body(src):
    """Extract the with-proxy heredoc body lines from build.sh source.

    The body is the text the guest shell sees inside the run_guest
    ``bash -c`` single-quoted string, i.e. raw file lines between the
    ``cat > /usr/local/bin/with-proxy <<EOF`` opener and the bare ``EOF``.
    """
    lines = src.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if "cat > /usr/local/bin/with-proxy <<EOF" in line)
    body = []
    for line in lines[start + 1:]:
        if line.strip() == "EOF":
            break
        body.append(line)
    else:
        raise AssertionError("with-proxy heredoc terminator not found")
    return body


def _render_with_proxy(body):
    """Emulate the two expansion layers that produce the jail artifact.

    1. Host shell (build.sh): the ``'"$HOST_VETH_IP"'`` splice is
       double-quoted between single-quoted segments, so the host expands it
       and consumes the quotes as syntax (true artifact has no quotes).
    2. Guest shell: the heredoc is UNQUOTED (``<<EOF``), so the guest
       collapses a backslash only before ``\``, ``$``, backtick, or
       newline — ``\"`` and ``\!`` are preserved as two bytes. The
       class below mirrors exactly that set.
    """
    rendered = []
    for line in body:
        line = line.replace("'\"$HOST_VETH_IP\"'", "10.99.0.1")
        line = re.sub(r"\\([\\$`])", r"\1", line)
        rendered.append(line)
    return "\n".join(rendered) + "\n"


class TestWithProxyHeredoc:
    """#285: the with-proxy jail edition is generated by a doubly-nested
    unquoted heredoc and was never syntax-checked."""

    def test_artifact_syntax_checked_at_build(self, active):
        # A quoting slip must fail the build loudly, at build time, in the
        # same guest shell that wrote the file.
        assert "/bin/bash -n /usr/local/bin/with-proxy" in active

    def test_no_unescaped_dollar_in_heredoc_body(self, src):
        # Core invariant: every $ in the body is either the host-side
        # "$HOST_VETH_IP" splice or a backslash-escaped guest-side literal.
        # An unescaped $VAR would be expanded by the guest shell at build
        # time (silently to empty) — fail the suite instead.
        for line in _with_proxy_heredoc_body(src):
            scrubbed = line.replace("'\"$HOST_VETH_IP\"'", "")
            scrubbed = re.sub(r"\\.", "", scrubbed)
            assert "$" not in scrubbed, \
                "unescaped $ in with-proxy heredoc body: %r" % line

    def test_rendered_artifact_parses(self, src, tmp_path):
        rendered = _render_with_proxy(_with_proxy_heredoc_body(src))
        p = tmp_path / "with-proxy"
        p.write_text(rendered, encoding="utf-8")
        r = subprocess.run(["bash", "-n", str(p)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + "\n--- rendered ---\n" + rendered

    def test_rendered_artifact_executes(self, src, tmp_path):
        # The shape pin is only useful if the pinned shape actually runs:
        # execute the rendered artifact the way the jail does
        # (`with-proxy echo hello`) and require the command to dispatch.
        # A quoting slip like `exec \"$@\"` would fail here with 127.
        rendered = _render_with_proxy(_with_proxy_heredoc_body(src))
        p = tmp_path / "with-proxy"
        p.write_text(rendered, encoding="utf-8")
        p.chmod(0o755)
        r = subprocess.run([str(p), "echo", "hello"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + "\n--- rendered ---\n" + rendered
        assert r.stdout.strip() == "hello"

    def test_rendered_expansion_shape(self, src):
        # Pin the two layers' net effect: the host splice lands as a
        # literal address; guest-side $VARs survive as runtime references
        # (not expanded to empty at build time).
        rendered = _render_with_proxy(_with_proxy_heredoc_body(src))
        assert 'export http_proxy=http://10.99.0.1:18080' in rendered
        assert 'export REQUESTS_CA="$CA_BUNDLE"' in rendered
        assert 'exec "$@"' in rendered
        assert "$HOST_VETH_IP" not in rendered

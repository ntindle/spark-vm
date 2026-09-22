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
        assert "tcp dport 22 ct state new,established accept" in active

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
                       "jail-input-drop", "dnat to 127.0.0.1"):
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

HEALTHY_RULESET = """\
table inet jail {
\tchain prerouting {
\t\ttype nat hook prerouting priority dstnat; policy accept;
\t\tiifname "ve-jail" ip daddr 10.99.0.1 tcp dport { 18080, 18081 } dnat to 127.0.0.1
\t}
\tchain input {
\t\ttype filter hook input priority -10; policy accept;
\t\tiifname "ve-jail" tcp dport { 18080, 18081 } accept
\t\tiifname "ve-jail" ct state established,related accept
\t\tiifname "ve-jail" log prefix "jail-input-drop: " drop
\t}
\tchain forward {
\t\ttype filter hook forward priority -10; policy accept;
\t\tiifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 tcp dport 22 ct state new,established accept
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
                  tmp_path=None, monkeypatch=None):
    fix = tmp_path / "ruleset.txt"
    fix.write_text(fixture_text or "")
    monkeypatch.setenv("NFT_FIXTURE_FILE", str(fix))
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
        assert "nft -f /etc/nftables-jail.conf" in calls
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

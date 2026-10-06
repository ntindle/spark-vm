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
import json
import os
import re
import shutil
import subprocess
import sys
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
        # #441: the limit is a MATCH, not a log modifier — it must gate
        # the log only, with the drop in a separate unconditional rule.
        # With default (until) semantics the limit matches while the rate
        # is under the limit, so a single rule of the form `limit rate
        # ... log prefix ... drop` would log+drop the first 5/min but skip
        # BOTH log and drop for over-limit packets (fail-open on the flood
        # itself: the chains are policy accept).
        assert ('iifname "ve-jail" limit rate 5/minute burst 10 packets '
                'log prefix "jail-fwd-drop: "') in active
        assert 'iifname "ve-jail" drop' in active

    def test_nftables_drops_jail_to_host_services(self, active):
        assert ('iifname "ve-jail" limit rate 5/minute burst 10 packets '
                'log prefix "jail-input-drop: "') in active
        assert 'iifname "ve-jail" drop' in active

    def test_nftables_drops_traffic_into_jail(self, active):
        assert ('oifname "ve-jail" limit rate 5/minute burst 10 packets '
                'log prefix "jail-fwd-indrop: "') in active
        assert 'oifname "ve-jail" drop' in active

    def test_nftables_drop_log_rate_limit_shape(self, active):
        # #441: pin the SAFE two-rule shape, not just the presence of a
        # limit token. The gated log line must be immediately followed by
        # the unconditional drop on the same match — a limit AFTER `log`
        # in one rule would invert the semantics (Security round-1
        # finding), and a missing/paired-elsewhere drop would fail open.
        cases = [
            ('iifname "ve-jail"', "jail-input-drop: "),
            ('iifname "ve-jail"', "jail-fwd-drop: "),
            ('oifname "ve-jail"', "jail-fwd-indrop: "),
        ]
        lines = active.splitlines()
        for match, prefix in cases:
            gated = (match + " limit rate 5/minute burst 10 packets "
                     'log prefix "' + prefix + '"')
            idx = next(i for i, l in enumerate(lines) if gated in l)
            nxt = lines[idx + 1].strip()
            assert nxt == match + " drop", (gated, nxt)

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
        # Issue #439: the file read now goes through the validator — the
        # key must still come from $PUBKEY_FILE, never an inline literal.
        assert 'validate_pubkey_file "$PUBKEY_FILE"' in active
        assert not re.search(r'PUBKEY="ssh-', active)

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

    def test_semantic_pin_subsumes_text_markers(self, verify_src):
        # Issue #444: the whole-table semantic pin replaces the marker
        # presence checks (drop-rule log prefixes, proxy DNAT grep) and
        # the text allow-head pin — a widened or narrowed ruleset differs
        # structurally from the pin and fails closed, so the old
        # grep/norm_canon/conf_rule_lines machinery is gone.
        for token in ("grep -q 'jail-fwd-drop'", "norm_canon",
                      "norm_rule_line", "conf_rule_lines",
                      "allow_head_intact"):
            assert token not in verify_src, \
                "text-pin machinery must be gone: %s" % token
        # The single comparison: live == pin, both canonicalized.
        assert 'live="$(capture_table)" || return 1' in verify_src
        assert 'pin="$(read_pin)" || return 1' in verify_src
        assert '[ "$live" = "$pin" ]' in verify_src
        # ...and the check must not be satisfiable by chain shells alone:
        # an emptied chain is a structural diff against the pin.
        assert "grep -q 'chain forward'" not in verify_src

    def test_single_json_list_call(self, verify_src):
        # One listing parsed repeatedly: no triple invocation, no TOCTOU
        # between checks. The listing is the JSON rendering, not text.
        assert verify_src.count('"$NFT" --json list table "$TABLE"') == 1
        assert '"$NFT" list table "$TABLE"' not in verify_src

    def test_unverifiable_table_fails_closed(self, verify_src):
        # An unreadable pin, a failed capture, or an empty capture must
        # never bless the table: every read path carries || return 1 and
        # the comparison requires both sides non-empty.
        assert 'live="$(capture_table)" || return 1' in verify_src
        assert 'pin="$(read_pin)" || return 1' in verify_src
        assert '[ -n "$live" ] && [ -n "$pin" ]' in verify_src
        # capture_table and read_pin both run through the canonicalizer —
        # an invalid JSON capture or an unreadable pin exits nonzero.
        assert '"$NFT" --json list table "$TABLE" 2>/dev/null | python3 "$CANON" 2>/dev/null' in verify_src
        assert 'python3 "$CANON" < "$PIN" 2>/dev/null' in verify_src

    def test_pin_and_canon_overridable(self, verify_src):
        # Same test-seam discipline as NFT/CONF: the functional tests
        # point PIN at a fixture and CANON at the repo script.
        assert 'PIN="${PIN:-/etc/nftables-jail.pin.json}"' in verify_src
        assert 'CANON="${CANON:-/usr/local/sbin/jail-nft-pin-canon.py}"' in verify_src

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

    def test_canon_script_installed_from_repo_file(self, active):
        # The canonicalizer is a first-class repo file, not an inline
        # python -c: directly testable, reviewable, and installed to the
        # path the watchdog expects -- one implementation, two consumers
        # (build-time capture and tick-time comparison).
        assert 'CANON_SCRIPT="$(dirname "$0")/nft-pin-canon.py"' in active
        assert '[[ -f "$CANON_SCRIPT" ]]' in active
        assert 'install -m 755 "$CANON_SCRIPT" ' \
            '/usr/local/sbin/jail-nft-pin-canon.py' in active

    def test_pin_regenerated_after_firewall_apply(self, active):
        # Issue #444: build.sh compiles the applied conf to the canonical
        # JSON pin (apply -> capture), regenerated on every build, so the
        # pin can never drift from the installed table. Position pinned:
        # the capture must follow the firewall apply.
        apply = active.index("systemctl enable --now jail-firewall.service")
        tail = active[apply:]
        assert "nft --json list table inet jail" in tail, \
            "pin capture never runs after the firewall apply"
        assert "tee /etc/nftables-jail.pin.json" in tail, \
            "pin capture never writes /etc/nftables-jail.pin.json"
        # Atomic pin write (Engineering review): the pipeline lands in a
        # .tmp sibling and is renamed into place, so a failed capture
        # never leaves a truncated pin for the running timer to trip on.
        assert "tee /etc/nftables-jail.pin.json.tmp" in tail
        assert "mv /etc/nftables-jail.pin.json.tmp " \
            "/etc/nftables-jail.pin.json" in tail
        # set -e means an uncapturable pin aborts the build -- a jail must
        # never be built without its pin (fail-closed at build time).
        capture = tail.index("nft --json list table inet jail")
        pin_write = tail.index("tee /etc/nftables-jail.pin.json")
        assert capture < pin_write


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
        # Security round 2: pin the comparison sources in the unit so the
        # watchdog compares against the pin it repairs toward, the conf
        # it repairs from, and the canonicalizer it compares through —
        # not whatever the environment happens to carry.
        assert "Environment=CONF=/etc/nftables-jail.conf" in unit
        assert "Environment=PIN=/etc/nftables-jail.pin.json" in unit
        assert "Environment=CANON=/usr/local/sbin/jail-nft-pin-canon.py" in unit

    def test_timer_cadence_and_wiring(self, active):
        m = re.search(
            r"tee /etc/systemd/system/jail-firewall-verify\.timer"
            r".*?\nEOF",
            active, re.S)
        assert m, "jail-firewall-verify.timer unit block not found"
        timer = m.group(0)
        assert "OnCalendar=*:0/1" in timer
        assert "Run the jail firewall watchdog every minute" in timer
        # Issue #440: the "~1 minute" detection bound needs the tick to
        # actually land every minute — the default AccuracySec=1min can
        # defer a firing by up to a minute and silently double it.
        assert "AccuracySec=10s" in timer
        assert "WantedBy=timers.target" in timer
        assert "systemctl enable --now jail-firewall-verify.timer" in active

    def test_build_self_tests_watchdog_pin(self, active):
        # Issue #437: build.sh must run the verify service once after
        # enabling the timer — the build-time self-test proves the pin
        # matches this box's live `nft --json` rendering at build time.
        # With #444's semantic pin this exercises the canonicalizer
        # against this box's rendering (a canonicalizer crash fails the
        # build); it is NOT a tripwire for future JSON schema drift —
        # drift fails closed on the first post-upgrade tick, by design,
        # and re-running build.sh regenerates the pin. The oneshot exits
        # 0 on healthy / nonzero on damage, and build.sh runs under
        # `set -e`, so a pin mismatch fails the build loudly instead of
        # surfacing as a fail-closed storm on the first tick.
        enable = active.index(
            "systemctl enable --now jail-firewall-verify.timer")
        tail = active[enable:]
        assert "systemctl start jail-firewall-verify.service" in tail, \
            "watchdog verify service is never started at build time"


# ---------------------------------------------------------------- functional
# Detection semantics, issue #444: stub nft / systemctl / logger / sleep
# via PATH (+ the NFT/PIN/CANON env overrides) and run the real script
# against canned `nft --json list table` captures.
#
# The fixtures are canonicalizer-shaped (nft-pin-canon.py is
# schema-opaque): each capture is a JSON doc with metainfo + table +
# chain + rule objects whose exprs are compact match/verdict pairs. What
# matters is the property under test: two captures of the SAME table
# under different renderings (nft version, key order, kernel handles)
# canonicalize equal; any structural change canonicalizes different.

CANON_SCRIPT = os.path.join(JAIL_DIR, "nft-pin-canon.py")

# The healthy table: (chain, match, verdict) for every rule build.sh's
# conf installs.
HEALTHY_RULES = [
    ("prerouting",
     'iifname "ve-jail" ip daddr 10.99.0.1 tcp dport {18080,18081}',
     "dnat ip to 127.0.0.1"),
    ("prerouting", 'iifname "tailscale0" tcp dport 2222',
     "dnat ip to 10.99.0.2:22"),
    ("input", 'iifname "ve-jail" tcp dport {18080,18081}', "accept"),
    ("input", 'iifname "ve-jail" ct state established,related', "accept"),
    ("input",
     'iifname "ve-jail" limit rate 5/minute burst 10 packets',
     'log prefix "jail-input-drop: "'),
    ("input", 'iifname "ve-jail"', "drop"),
    ("forward",
     'iifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 '
     "tcp dport 22 ct state established,new", "accept"),
    ("forward", 'iifname "ve-jail" ct state established,related', "accept"),
    ("forward", 'oifname "ve-jail" ct state established,related', "accept"),
    ("forward",
     'iifname "ve-jail" limit rate 5/minute burst 10 packets',
     'log prefix "jail-fwd-drop: "'),
    ("forward", 'iifname "ve-jail"', "drop"),
    ("forward",
     'oifname "ve-jail" limit rate 5/minute burst 10 packets',
     'log prefix "jail-fwd-indrop: "'),
    ("forward", 'oifname "ve-jail"', "drop"),
]


def _reverse_keys(node):
    # Simulate a renderer that emits dict keys in the opposite order.
    if isinstance(node, dict):
        return {k: _reverse_keys(v) for k, v in reversed(list(node.items()))}
    if isinstance(node, list):
        return [_reverse_keys(x) for x in node]
    return node


def _render_capture(rules, *, version, handle_base, reverse_keys=False):
    """One `nft --json list table inet jail` capture of `rules`."""
    objs = [
        {"metainfo": {"version": version, "release_name": "Laotzu",
                      "json_schema_version": 1}},
        {"table": {"family": "inet", "name": "jail"}},
    ]
    for chain in ("prerouting", "input", "forward"):
        objs.append({"chain": {"family": "inet", "table": "jail",
                               "name": chain, "policy": "accept"}})
    for i, (chain, match, verdict) in enumerate(rules):
        objs.append({"rule": {"family": "inet", "table": "jail",
                              "chain": chain, "handle": handle_base + i,
                              "expr": [{"match": match,
                                        "verdict": verdict}]}})
    doc = {"nftables": objs}
    return json.dumps(_reverse_keys(doc) if reverse_keys else doc)


# Build-time capture (the pin's source) vs tick-time capture of the SAME
# table under a re-rendered schema: new nft version, new kernel handles,
# reversed key order. The raw captures differ byte-wise; the
# canonicalizer must absorb all of it (the #444 headline case).
PIN_CAPTURE = _render_capture(HEALTHY_RULES, version="1.0.9",
                              handle_base=5)
LIVE_SAME_TABLE = _render_capture(HEALTHY_RULES, version="1.1.0",
                                  handle_base=900, reverse_keys=True)

# Structural damage variants (each must fail closed).
_dropped = [r for i, r in enumerate(HEALTHY_RULES) if i != 5]
LIVE_RULE_DELETED = _render_capture(_dropped, version="1.1.0",
                                    handle_base=900, reverse_keys=True)
_widened = list(HEALTHY_RULES)
_widened.insert(10, ("forward", 'iifname "ve-jail"', "accept"))
LIVE_BROAD_ACCEPT = _render_capture(_widened, version="1.1.0",
                                    handle_base=900, reverse_keys=True)
_readdr = list(HEALTHY_RULES)
_readdr[0] = ("prerouting", _readdr[0][1], "dnat ip to 10.99.0.10")
LIVE_DNAT_READDRESSED = _render_capture(_readdr, version="1.1.0",
                                        handle_base=900, reverse_keys=True)
# The old round-1 Security case: `nft flush chain` — chains intact, rules
# gone, policy accept. A structural diff against the pin.
LIVE_FLUSHED = _render_capture([], version="1.1.0", handle_base=900,
                               reverse_keys=True)


@pytest.fixture()
def watchdog_stubs(tmp_path, monkeypatch):
    """PATH stub dir: nft (canned JSON capture via $NFT_JSON_FIXTURE,
    rc via $NFT_LIST_RC / $NFT_CHECK_RC, invocation log at $CALLS_LOG),
    systemctl, logger, sleep (no-op). Returns the log path."""
    bindir = tmp_path / "stubs"
    bindir.mkdir()
    log = tmp_path / "calls.log"
    (bindir / "nft").write_text("""\
#!/bin/bash
echo "nft $*" >> "$CALLS_LOG"
if [ "$1 $2 $3" = "--json list table" ]; then
    cat "$NFT_JSON_FIXTURE"; exit "${NFT_LIST_RC:-0}"
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
    monkeypatch.delenv("NFT_JSON_FIXTURE", raising=False)
    return log


def _canonicalize(raw):
    p = subprocess.run([sys.executable, CANON_SCRIPT], input=raw,
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _run_watchdog(live_capture=None, *, list_rc="0", check_rc="0",
                  pin_capture=PIN_CAPTURE, unreadable_pin=False,
                  raw_pin=False, canon_path=CANON_SCRIPT,
                  tmp_path=None, monkeypatch=None):
    live = tmp_path / "live.json"
    live.write_text(live_capture if live_capture is not None else "")
    conf = tmp_path / "nftables-jail.conf"
    conf.write_text("# repair source; content is irrelevant to the pin")
    monkeypatch.setenv("NFT_JSON_FIXTURE", str(live))
    if unreadable_pin:
        monkeypatch.setenv("PIN", str(tmp_path / "does-not-exist.pin.json"))
    else:
        pin = tmp_path / "pin.json"
        # raw_pin: store the capture un-canonicalized — read_pin
        # re-canonicalizes on read (idempotent), so this must stay healthy.
        pin.write_text(pin_capture if raw_pin else _canonicalize(pin_capture))
        monkeypatch.setenv("PIN", str(pin))
    monkeypatch.setenv("CONF", str(conf))
    monkeypatch.setenv("CANON", str(canon_path))
    monkeypatch.setenv("NFT_LIST_RC", list_rc)
    monkeypatch.setenv("NFT_CHECK_RC", check_rc)
    return subprocess.run(
        ["bash", VERIFY_SCRIPT], capture_output=True, text=True)


class TestFirewallWatchdogFunctional:
    def test_healthy_table_exits_quiet(self, watchdog_stubs, tmp_path,
                                       monkeypatch):
        # The #444 headline: build-time capture vs tick-time capture of
        # the SAME table under a re-rendered schema (new nft version,
        # new handles, reversed key order). The raw captures differ
        # byte-wise; the semantic pin must report healthy, not fail
        # closed.
        assert PIN_CAPTURE != LIVE_SAME_TABLE
        r = _run_watchdog(LIVE_SAME_TABLE, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 0, r.stderr
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls

    def test_deleted_drop_triggers_fail_closed(self, watchdog_stubs,
                                               tmp_path, monkeypatch):
        r = _run_watchdog(LIVE_RULE_DELETED, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_added_broad_accept_triggers_fail_closed(self, watchdog_stubs,
                                                     tmp_path, monkeypatch):
        # The arch case: every drop and the DNAT are present, but an
        # injected broad accept sits above the drops — policy-accept
        # chains make this open egress. The whole-table pin fails closed.
        r = _run_watchdog(LIVE_BROAD_ACCEPT, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_readdressed_dnat_triggers_fail_closed(self, watchdog_stubs,
                                                   tmp_path, monkeypatch):
        # 'dnat ip to 10.99.0.10' is not the pin's 'dnat ip to
        # 127.0.0.1' verdict; the structural comparison must reject it.
        r = _run_watchdog(LIVE_DNAT_READDRESSED, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_flushed_chain_triggers_fail_closed(self, watchdog_stubs,
                                                tmp_path, monkeypatch):
        # The round-1 Security case: chain shells intact, rules gone.
        r = _run_watchdog(LIVE_FLUSHED, tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert calls.index("systemctl stop systemd-nspawn@jail") < \
            calls.index("nft destroy table")
        assert "ALERT" in calls

    def test_missing_table_triggers_fail_closed(self, watchdog_stubs,
                                                tmp_path, monkeypatch):
        r = _run_watchdog("", list_rc="1", tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "nft destroy table" in calls

    def test_invalid_live_json_triggers_fail_closed(self, watchdog_stubs,
                                                    tmp_path, monkeypatch):
        # A corrupt `nft --json` capture is unverifiable — never blessed.
        r = _run_watchdog("not json at all", tmp_path=tmp_path,
                          monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls

    def test_unreadable_pin_triggers_fail_closed(self, watchdog_stubs,
                                                 tmp_path, monkeypatch):
        # An unreadable pin must fail closed, not bless the table.
        r = _run_watchdog(LIVE_SAME_TABLE, unreadable_pin=True,
                          tmp_path=tmp_path, monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls

    def test_missing_canon_helper_triggers_fail_closed(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # QA blocker 1: capture_table()'s comment names the missing
        # canon helper as a fail-closed case — prove it. python3 cannot
        # open the helper, the pipeline fails under pipefail, and the
        # unverifiable table is never blessed.
        r = _run_watchdog(LIVE_SAME_TABLE,
                          canon_path=str(tmp_path / "no-such-canon.py"),
                          tmp_path=tmp_path, monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        assert "systemctl stop systemd-nspawn@jail" in calls

    def test_raw_uncanonicalized_pin_still_healthy(
            self, watchdog_stubs, tmp_path, monkeypatch):
        # QA blocker 2: read_pin re-canonicalizes on read (idempotent),
        # so a pin file stored as the raw capture — never canonicalized
        # at write time — must still compare healthy.
        assert _canonicalize(PIN_CAPTURE) != PIN_CAPTURE
        r = _run_watchdog(LIVE_SAME_TABLE, raw_pin=True,
                          tmp_path=tmp_path, monkeypatch=monkeypatch)
        assert r.returncode == 0, r.stderr
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls

    def test_corrupt_conf_never_destroys(self, watchdog_stubs, tmp_path,
                                         monkeypatch):
        r = _run_watchdog(LIVE_RULE_DELETED, check_rc="1",
                          tmp_path=tmp_path, monkeypatch=monkeypatch)
        assert r.returncode == 1
        calls = watchdog_stubs.read_text()
        # Fail-closed stop still happens, but the table is never widened.
        assert "systemctl stop systemd-nspawn@jail" in calls
        assert "destroy table" not in calls
        assert "CRITICAL" in calls

    def test_transient_gap_heals_without_drama(self, watchdog_stubs,
                                               tmp_path, monkeypatch):
        # First capture damaged (the oneshot's own destroy-then-apply
        # window), second capture healthy: no stop, no repair, exit 0.
        damaged = tmp_path / "damaged.json"
        damaged.write_text(LIVE_RULE_DELETED)
        healthy = tmp_path / "healthy.json"
        healthy.write_text(LIVE_SAME_TABLE)
        counter = tmp_path / "n"
        counter.write_text("0")
        stub = tmp_path / "stubs" / "nft"
        stub.write_text("""\
#!/bin/bash
echo "nft $*" >> "$CALLS_LOG"
if [ "$1 $2 $3" = "--json list table" ]; then
    c=$(cat "$NFT_COUNT"); echo $((c+1)) > "$NFT_COUNT"
    if [ "$c" = "0" ]; then cat "$NFT_JSON_FIXTURE"; else cat "$NFT_HEALTHY"; fi
    exit 0
fi
exit 0
""")
        stub.chmod(0o755)
        pin = tmp_path / "pin.json"
        pin.write_text(_canonicalize(PIN_CAPTURE))
        conf = tmp_path / "nftables-jail.conf"
        conf.write_text("# repair source")
        monkeypatch.setenv("NFT_JSON_FIXTURE", str(damaged))
        monkeypatch.setenv("NFT_HEALTHY", str(healthy))
        monkeypatch.setenv("NFT_COUNT", str(counter))
        monkeypatch.setenv("PIN", str(pin))
        monkeypatch.setenv("CONF", str(conf))
        monkeypatch.setenv("CANON", CANON_SCRIPT)
        r = subprocess.run(["bash", VERIFY_SCRIPT],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        calls = watchdog_stubs.read_text()
        assert "systemctl stop" not in calls
        assert "destroy table" not in calls
        # QA blocker 3: prove the transient path actually ran — the
        # damaged first capture plus the healing re-check are exactly
        # two live captures. Without this the test would pass even if
        # the "damaged" fixture were accidentally healthy.
        assert (tmp_path / "n").read_text().strip() == "2"
        assert calls.count("nft --json list table") == 2


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

# ---------------------------------------------------------------- pubkey validation
# Issue #439: the pubkey is written verbatim into the guest's
# authorized_keys, so a malformed file fails the agent's SSH login
# silently. validate-pubkey.sh normalizes (CRLF/blank-line strip) and
# validates up front; build.sh aborts loudly on failure. These tests run
# the real helper as a subprocess — the same entry point build.sh
# sources — and pin build.sh's wiring of it.

# An ephemeral ed25519 keypair's public half, generated 2026-09-26 for
# this test and never attached to anything. PUBLIC key material only —
# safe to embed (this is exactly what a pubkey file contains).
_VALID_ED25519 = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILx9f7U12S8F8f8rFUGv6+x5x60G5ULYfKOIeaYTXvRf "
    "test-jail-pubkey"
)


class TestPubkeyValidation:
    VALIDATOR = os.path.join(JAIL_DIR, "validate-pubkey.sh")

    def _run(self, content: bytes):
        # Real tempfiles: the validator requires a regular file
        # (`[[ -f ]]`) — /dev/stdin pipes are rejected by design.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pub", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            return subprocess.run(["bash", self.VALIDATOR, path],
                                  capture_output=True)
        finally:
            os.unlink(path)

    def test_valid_key_accepted(self):
        r = self._run((_VALID_ED25519 + "\n").encode())
        assert r.returncode == 0, r.stderr.decode()
        assert r.stdout.decode().strip() == _VALID_ED25519

    def test_crlf_and_trailing_blank_lines_normalized(self):
        # Issue #439's exact failure mode: CRLF line endings and trailing
        # blank lines must be stripped, not rejected — the normalized key
        # is what lands in authorized_keys.
        r = self._run((_VALID_ED25519 + "\r\n\r\n\n").encode())
        assert r.returncode == 0, r.stderr.decode()
        assert "\r" not in r.stdout.decode()
        assert r.stdout.decode().strip() == _VALID_ED25519

    def test_missing_file_fails(self, tmp_path):
        r = subprocess.run(["bash", self.VALIDATOR,
                            str(tmp_path / "no-such-file.pub")],
                           capture_output=True)
        assert r.returncode != 0
        assert b"not found" in r.stderr

    def test_empty_file_fails(self):
        r = self._run(b"")
        assert r.returncode != 0
        assert b"empty" in r.stderr

    def test_garbage_fails(self):
        r = self._run(b"definitely-not-a-key\n")
        assert r.returncode != 0
        assert b"not a valid SSH public key line" in r.stderr

    def test_unknown_key_type_fails(self):
        r = self._run(b"ssh-magic AAAAC3NzaC1lZDI1NTE5AAAAILx9f7U12S8F8f8rFUGv6+x5x60G5ULYfKOIeaYTXvRf x\n")
        assert r.returncode != 0

    def test_two_keys_fails(self):
        r = self._run((_VALID_ED25519 + "\n" + _VALID_ED25519 + "\n").encode())
        assert r.returncode != 0
        assert b"more than one key" in r.stderr

    @pytest.mark.skipif(
        shutil.which("ssh-keygen") is None,
        reason="structural layer needs ssh-keygen on PATH")
    def test_well_shaped_but_corrupt_blob_fails(self):
        # Passes the regex (valid base64 alphabet) but does not decode
        # to a key — only the ssh-keygen layer catches this.
        corrupt = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICORRUPTEDBLOBxxx "
                   "comment\n")
        r = self._run(corrupt.encode())
        assert r.returncode != 0
        assert b"ssh-keygen rejects" in r.stderr

    def test_comment_with_spaces_accepted(self):
        key = _VALID_ED25519.replace("test-jail-pubkey", "test jail pubkey")
        r = self._run((key + "\n").encode())
        assert r.returncode == 0, r.stderr.decode()
        assert r.stdout.decode().strip() == key

    def test_build_sh_validates_before_guest_setup(self, src, active):
        # Static wiring pin: build.sh must source the helper and abort on
        # an invalid pubkey BEFORE the key is handed to run_guest for
        # authorized_keys. The "active" fixture strips full-line comments,
        # so this proves a live wiring, not a commented-out remnant.
        source_idx = active.index('. "$(dirname "$0")/validate-pubkey.sh"')
        validate_call = active.index("validate_pubkey_file", source_idx)
        guest_idx = active.index('run_guest /bin/bash -s "$JAIL_USER" "$PUBKEY"')
        assert validate_call < guest_idx, \
            "pubkey validation must precede the guest authorized_keys write"
        tail = active[validate_call:]
        assert "refusing to build the jail with an invalid agent pubkey" in tail
        # The raw `cat` read is gone — nothing bypasses the validator.
        assert 'PUBKEY="$(cat "$PUBKEY_FILE")"' not in active


# ---------------------------------------------------------------------------
# Issue #438: guest ~/.ssh/environment hardcoded 10.99.0.1 instead of
# $HOST_VETH_IP. Every other guest artifact takes the proxy address from the
# host variable; this block now receives it as a guest-side argument ($3)
# because the outer heredoc is quoted (host vars do not expand there) and
# the inner environment heredoc is unquoted (the guest var expands there).
# ---------------------------------------------------------------------------

def _guest_setup_block(src):
    """Lines of the quoted GUEST_EOF heredoc that builds the guest user."""
    lines = src.splitlines()
    start = next(i for i, l in enumerate(lines)
                 if 'run_guest /bin/bash -s' in l and "<<'GUEST_EOF'" in l)
    end = next(i for i in range(start + 1, len(lines))
               if lines[i] == "GUEST_EOF")
    return lines[start:end + 1]


def _ssh_environment_body(src):
    """Lines of the inner (unquoted) heredoc writing ~/.ssh/environment."""
    block = _guest_setup_block(src)
    start = next(i for i, l in enumerate(block)
                 if ".ssh/environment" in l and "<<EOF" in l)
    end = next(i for i in range(start + 1, len(block)) if block[i] == "EOF")
    return block[start:end + 1]


class TestSshEnvironmentVethIP:
    def test_guest_setup_receives_veth_ip(self, src):
        # The host splices its $HOST_VETH_IP into the guest as an argument
        # (the outer heredoc is quoted, so it cannot expand there).
        line = next(l for l in src.splitlines()
                    if 'run_guest /bin/bash -s' in l and "<<'GUEST_EOF'" in l)
        assert '"$HOST_VETH_IP"' in line

    def test_veth_ip_bound_to_named_var_with_fail_closed_guard(self, active):
        block = "\n".join(_guest_setup_block(active))
        assert 'VETH_IP="$3"' in block
        # An empty $3 must fail the build loudly, never write a proxy URL
        # with an empty host.
        assert '[ -n "$VETH_IP" ]' in block

    def test_environment_heredoc_uses_guest_var_not_literal(self, src):
        body = "\n".join(_ssh_environment_body(src))
        assert "$VETH_IP" in body
        assert "10.99.0.1" not in body

    def test_environment_renders_with_non_default_veth(self, src):
        # Render the inner (unquoted) heredoc exactly the way the guest
        # shell does, with a non-default address: the drift is caught only
        # if no literal address survives.
        inner = "\n".join(_ssh_environment_body(src)[1:-1])
        script = "VETH_IP=203.0.113.7\ncat <<EOF\n%s\nEOF\n" % inner
        r = subprocess.run(["bash", "-c", script],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "http://203.0.113.7:18080" in r.stdout
        assert "10.99.0.1" not in r.stdout

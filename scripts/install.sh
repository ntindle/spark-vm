#!/usr/bin/env bash
# scripts/install.sh — idempotent spark-vm box installer.
#
# Machine form of the README "Try it" runbook (issue #1526): creates the
# agent user, drops the passwordless-sudo rule, copies the installer's SSH
# key, joins the tailnet, clones the repo, deploys the proxy/confirmd stack,
# installs the muse-job CLI + plugin, enables the cred-ui user service, and
# starts the CUA desktop.
#
# Usage:
#   git clone https://github.com/ntindle/spark-vm.git
#   sudo ./spark-vm/scripts/install.sh [--agent-user NAME] [--dry-run] [--force]
#
# Every step checks whether its end state already holds and skips when it
# does, so re-running converges to the same state (the desktop start and the
# repo sync always run, but both are no-ops when current). Anything the
# script cannot complete fails loudly with a diagnostic instead of
# half-applying. Tailscale installs from its signed apt repository, never
# from a piped shell script.
#
# The agent phase always works in the AGENT user's own checkout
# (~$AGENT_USER/spark-vm) — the invoker's checkout is only the delivery
# vehicle for this script (the agent user cannot read /root or another
# user's home). The bootstrap re-execs the agent phase through a login
# shell (sudo -iu) so systemctl --user has a user bus.
#
# Out of scope: choosing a published artifact format (#1529), version pinning
# (#1527), provenance stamping (#1528).

set -euo pipefail

# ${VAR:-default} (not plain assignment): the bootstrap phase re-execs the
# agent phase with these as environment, and plain assignments would clobber
# them (notably --agent-user and --force). CLI parsing below still overrides.
# AGENT_PHASE is deliberately NOT env-preserved (plain assignment): the
# re-exec passes --agent-phase-internal explicitly, so a stray exported
# AGENT_PHASE=1 can never silently skip bootstrap.
AGENT_USER="${AGENT_USER:-ntindle}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
AGENT_PHASE=0

SCRIPT_ABS="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SUDOERS_DIR="${SUDOERS_DIR:-/etc/sudoers.d}"
REPO_URL="https://github.com/ntindle/spark-vm.git"
# AGENT_REPO is derived in run_agent from the agent user's passwd entry.

usage() {
    cat <<'EOF'
Usage: install.sh [--agent-user NAME] [--dry-run] [--force] [--help]

  --agent-user NAME  agent account the stack runs as (default: ntindle; not root)
  --dry-run          print what would change without changing anything
  --force            re-run steps that already hold (e.g. redeploy the stack)
  --help             this text

Run as root (or with sudo) for the bootstrap phase — creating the agent
user, the sudoers drop, and the SSH key copy — then the script drops to the
agent user itself (login shell) for the tailnet + stack phase. Run directly
as the agent user only once the bootstrap phase already holds.
EOF
}

note() { echo "install.sh: $*"; }
die() { echo "install.sh: ERROR: $*" >&2; exit 1; }

# exec_if_live <description> <command...> — describe the mutation, then run
# it, unless --dry-run, in which case only describe it. Read-only probes
# always run for real so a dry run reports the true plan.
exec_if_live() {
    local desc="$1"; shift
    if [ "$DRY_RUN" = 1 ]; then
        note "would $desc"
        return 0
    fi
    "$@"
}

# Argument parsing lives in main(), not at top level, so sourcing this
# file (as the test suite does) never shifts a sourcer's positional params.
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --agent-user) AGENT_USER="${2:?--agent-user needs a name}"; shift 2 ;;
            --agent-user=*) AGENT_USER="${1#*=}"; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            --force) FORCE=1; shift ;;
            # Internal re-exec flag (bootstrap -> agent phase). Safe to pass
            # directly once the bootstrap phase already holds.
            --agent-phase-internal) AGENT_PHASE=1; shift ;;
            --help|-h) usage; exit 0 ;;
            *) die "unknown argument: $1 (try --help)" ;;
        esac
    done

    [[ "$AGENT_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "bad --agent-user name: $AGENT_USER"
    [ "$AGENT_USER" != root ] || die "--agent-user root defeats the user-isolation design — pick a non-root agent account"
}

# ---------------------------------------------------------------------------
# Bootstrap phase (root): agent user, sudoers drop, SSH key copy, prereqs.
# ---------------------------------------------------------------------------

apt_get_update() {
    apt-get update
}

step_prereqs() {
    local missing=()
    command -v git >/dev/null 2>&1 || missing+=(git)
    command -v curl >/dev/null 2>&1 || missing+=(curl)
    if [ "${#missing[@]}" -eq 0 ]; then
        note "skip: prereqs present (git, curl)"
        return 0
    fi
    # This script owns prereq installation (the runbook assumed git/curl
    # present), so it owns the package-list refresh too.
    exec_if_live "refresh the apt package lists" apt_get_update
    exec_if_live "install missing prereqs: ${missing[*]}" \
        apt-get install -y "${missing[@]}"
}

step_agent_user() {
    if id -u "$AGENT_USER" >/dev/null 2>&1; then
        note "skip: user $AGENT_USER exists"
    else
        exec_if_live "create user $AGENT_USER (no password)" \
            adduser --disabled-password --gecos '' "$AGENT_USER"
    fi
    if getent group sudo >/dev/null 2>&1; then
        if id -nG "$AGENT_USER" 2>/dev/null | tr ' ' '\n' | grep -qx sudo; then
            note "skip: $AGENT_USER already in sudo group"
        else
            exec_if_live "add $AGENT_USER to sudo group" \
                usermod -aG sudo "$AGENT_USER"
        fi
    fi
}

step_sudoers() {
    local file="$SUDOERS_DIR/$AGENT_USER"
    local want="$AGENT_USER ALL=(ALL) NOPASSWD: ALL"
    if [ -f "$file" ] && [ "$(cat "$file")" = "$want" ]; then
        note "skip: $file already drops passwordless sudo for $AGENT_USER"
        return 0
    fi
    if [ "$DRY_RUN" = 1 ]; then
        note "would write $file (passwordless sudo for $AGENT_USER)"
        return 0
    fi
    # Atomic: validate a temp copy, then install it with the final mode —
    # a broken drop can never be left behind, not even briefly.
    local tmp
    tmp="$(mktemp)"
    printf '%s\n' "$want" > "$tmp"
    if command -v visudo >/dev/null 2>&1; then
        # The content is a single line built from the regex-constrained
        # $AGENT_USER (no whitespace/newline possible), so a failure here
        # would be a visudo/environment problem, not our content.
        visudo -cf "$tmp" >/dev/null || {
            rm -f "$tmp"
            die "$file failed the visudo syntax check — nothing written"
        }
    fi
    install -m 440 "$tmp" "$file"
    rm -f "$tmp"
    note "wrote $file"
}

step_ssh_key() {
    # Copy the invoking user's key so the agent (and the human) can SSH in
    # as the agent user over Tailscale. Skip silently when the invoker
    # logged in with a password instead of a key (README documents the
    # manual fallback).
    local invoker="${SUDO_USER:-root}"
    local src_home
    src_home="$(getent passwd "$invoker" | cut -d: -f6)"
    local src="$src_home/.ssh/authorized_keys"
    if [ ! -s "$src" ]; then
        note "skip: no SSH key for $invoker ($src missing/empty) — add one to ~$AGENT_USER/.ssh/authorized_keys by hand if agent SSH is wanted"
        return 0
    fi
    local dest_home
    dest_home="$(getent passwd "$AGENT_USER" | cut -d: -f6)"
    local sshdir="$dest_home/.ssh"
    local dest="$sshdir/authorized_keys"
    if [ -L "$sshdir" ] || [ -L "$dest" ]; then
        die "refusing: $sshdir or $dest is a symlink — fix it by hand, then re-run"
    fi
    # Append-only with exact-line dedup (ssh-copy-id semantics). Note: a
    # rotated/revoked invoker key persists here — key rotation needs manual
    # cleanup of the agent user's authorized_keys.
    local keys_missing=0
    if [ -f "$dest" ]; then
        while IFS= read -r key || [ -n "$key" ]; do
            [ -z "$key" ] && continue
            grep -qFx "$key" "$dest" || keys_missing=1
        done < "$src"
    else
        keys_missing=1
    fi
    if [ "$keys_missing" -eq 0 ]; then
        note "skip: $invoker's SSH key already in $dest"
        return 0
    fi
    exec_if_live "install $sshdir for $AGENT_USER" \
        install -d -o "$AGENT_USER" -g "$AGENT_USER" -m 700 "$sshdir"
    if [ "$DRY_RUN" = 1 ]; then
        note "would append $invoker's SSH key(s) to $dest"
        return 0
    fi
    touch "$dest"
    chown "$AGENT_USER:$AGENT_USER" "$dest"
    chmod 600 "$dest"
    while IFS= read -r key || [ -n "$key" ]; do
        [ -z "$key" ] && continue
        grep -qFx "$key" "$dest" || printf '%s\n' "$key" >> "$dest"
    done < "$src"
    note "copied $invoker's SSH key(s) to $dest"
}

# ---------------------------------------------------------------------------
# The agent phase always works in the AGENT user's own checkout
# (~$AGENT_USER/spark-vm) — never the invoker's. Bootstrap stages an
# agent-owned copy of the repo first (the invoker's checkout is frequently
# unreadable to the agent user: /root is mode 700, human homes are 750),
# then re-execs the staged copy through a login shell (sudo -iu) so
# systemctl --user has a user bus.
derive_agent_repo() {
    local agent_home
    agent_home="$(getent passwd "$AGENT_USER" | cut -d: -f6)"
    if [ -z "$agent_home" ]; then
        if [ "$DRY_RUN" = 1 ]; then
            agent_home="/home/$AGENT_USER"
            note "dry-run: no passwd entry for $AGENT_USER yet — planning against $agent_home"
        else
            die "no passwd entry for $AGENT_USER — run the bootstrap phase first (with sudo)"
        fi
    fi
    AGENT_REPO="$agent_home/spark-vm"
}

stage_repo_copy() {
    mkdir -p "$AGENT_REPO"
    cp -a "$REPO_DIR/." "$AGENT_REPO/"
    chown -R "$AGENT_USER:$AGENT_USER" "$AGENT_REPO"
}

staged_copy_current() {
    # Freshness predicate for the staged agent checkout: the staged tree
    # must be at-or-ahead of the invoker checkout (its own ff-pulls may
    # advance it) with the invoker tree clean — otherwise a re-run would
    # silently deploy stale content.
    [ -d "$AGENT_REPO/.git" ] || return 1
    [ -f "$AGENT_REPO/scripts/install.sh" ] || return 1
    [ "$(stat -c %U "$AGENT_REPO")" = "$AGENT_USER" ] || return 1
    local invoker_head staged_head
    invoker_head="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null)" || return 1
    staged_head="$(git -C "$AGENT_REPO" rev-parse HEAD 2>/dev/null)" || return 1
    git -C "$AGENT_REPO" merge-base --is-ancestor "$invoker_head" "$staged_head" 2>/dev/null || return 1
    [ -z "$(git -C "$REPO_DIR" status --porcelain 2>/dev/null)" ] || return 1
    return 0
}

step_stage_repo() {
    # The re-exec opens this script as the agent user, and the agent phase
    # reads the whole repo as the agent user — but the invoker's checkout
    # is frequently unreadable to them (/root is mode 700, human homes are
    # 750). Stage an agent-owned copy first; the re-exec then targets the
    # staged copy, never the invoker's checkout.
    if [ "$AGENT_REPO" = "$REPO_DIR" ]; then
        note "skip: installer already runs from the agent-owned checkout"
        return 0
    fi
    if [ "$FORCE" = 0 ] && staged_copy_current; then
        note "skip: agent-readable repo copy already staged at $AGENT_REPO"
        return 0
    fi
    exec_if_live "stage an agent-readable repo copy at $AGENT_REPO" \
        stage_repo_copy
}
# ---------------------------------------------------------------------------

tailscale_apt_install() {
    sudo apt-get update
    sudo apt-get install -y tailscale
}

write_tailscale_list() { # $1 = path, $2 = content (runs as the caller)
    local tmp
    tmp="$(mktemp)"
    printf '%s\n' "$2" > "$tmp"
    sudo install -m 644 "$tmp" "$1"
    rm -f "$tmp"
}

fetch_tailscale_keyring() { # $1 = keyring path (runs as the caller)
    sudo curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o "$1"
}

step_tailscale_install() {
    if command -v tailscale >/dev/null 2>&1; then
        note "skip: tailscale already installed"
        return 0
    fi
    # Signed apt repository — apt verifies package signatures; no
    # piped-to-shell remote code. Pinned to Ubuntu 24.04 (noble), the
    # installer's target OS.
    # shellcheck disable=SC1091
    . /etc/os-release
    [ "${VERSION_CODENAME:-}" = noble ] || \
        die "tailscale installs from the noble apt repo; this box is '${VERSION_CODENAME:-unknown}' — install tailscale by hand, then re-run $SCRIPT_ABS"
    local keyring=/usr/share/keyrings/tailscale-archive-keyring.gpg
    local list=/etc/apt/sources.list.d/tailscale.list
    local entry="deb [signed-by=$keyring] https://pkgs.tailscale.com/stable/ubuntu noble main"
    if [ -f "$keyring" ]; then
        note "skip: tailscale apt keyring present"
    else
        exec_if_live "fetch the tailscale apt keyring" \
            fetch_tailscale_keyring "$keyring"
    fi
    if [ -f "$list" ] && [ "$(cat "$list")" = "$entry" ]; then
        note "skip: tailscale apt source already configured"
    else
        exec_if_live "configure the tailscale apt source" \
            write_tailscale_list "$list" "$entry"
    fi
    exec_if_live "install tailscale from apt" \
        tailscale_apt_install
}

step_tailscale_up() {
    if tailscale status >/dev/null 2>&1; then
        note "skip: tailscale already up"
        return 0
    fi
    if [ "$DRY_RUN" = 1 ]; then
        note "would join the tailnet (sudo tailscale up) — approve the device in the Tailscale admin console, then re-run"
        return 0
    fi
    # stdin closed: never hang waiting on interactive auth — fail loud instead.
    sudo tailscale up < /dev/null || true
    if tailscale status >/dev/null 2>&1; then
        note "tailscale is up"
    else
        die "tailscale is not up — approve this device in your Tailscale admin console, then re-run $SCRIPT_ABS"
    fi
}

step_linger() {
    if loginctl show-user "$AGENT_USER" 2>/dev/null | grep -q '^Linger=yes$'; then
        note "skip: linger already enabled for $AGENT_USER"
        return 0
    fi
    exec_if_live "enable linger for $AGENT_USER" \
        sudo loginctl enable-linger "$AGENT_USER"
}

step_repo() {
    if [ ! -d "$AGENT_REPO/.git" ]; then
        if [ -n "$(ls -A "$AGENT_REPO" 2>/dev/null)" ]; then
            die "$AGENT_REPO exists but is not a git checkout — move it aside, then re-run $SCRIPT_ABS"
        fi
        exec_if_live "clone $REPO_URL to $AGENT_REPO" \
            git clone "$REPO_URL" "$AGENT_REPO"
        return 0
    fi
    if ! git -C "$AGENT_REPO" remote get-url origin >/dev/null 2>&1; then
        die "$AGENT_REPO has no origin remote — fix the checkout, then re-run $SCRIPT_ABS"
    fi
    local branch
    branch="$(git -C "$AGENT_REPO" symbolic-ref --short HEAD 2>/dev/null || echo detached)"
    if [ "$branch" != main ]; then
        # Never pull origin/main into another branch — the operator checked
        # that branch out deliberately.
        note "$AGENT_REPO is on '$branch', not main — skipping pull (re-run from a main checkout to update it)"
        return 0
    fi
    note "repo at $AGENT_REPO is on main — fast-forwarding to origin/main"
    exec_if_live "git pull --ff-only origin main in $AGENT_REPO" \
        git -C "$AGENT_REPO" pull --ff-only origin main || \
        die "$AGENT_REPO has diverged from origin/main — resolve it, then re-run $SCRIPT_ABS"
}

step_deploy() {
    local units=(swap-proxy.service swap-inference.service confirmd.service push-worker.service)
    local all_active=1
    for u in "${units[@]}"; do
        systemctl is-active --quiet "$u" || all_active=0
    done
    if [ "$all_active" = 1 ] && [ "$FORCE" = 0 ]; then
        note "skip: proxy/confirmd units already active (use --force to redeploy)"
        return 0
    fi
    exec_if_live "deploy the swap proxy + confirmd stack (proxy/deploy.sh)" \
        env -C "$AGENT_REPO" ./proxy/deploy.sh
}

step_muse_job() {
    if [ "$DRY_RUN" = 0 ]; then
        mkdir -p "$HOME/bin"
    fi
    if [ -f "$HOME/bin/muse-job" ] && cmp -s "$AGENT_REPO/muse-job/bin/muse-job" "$HOME/bin/muse-job"; then
        note "skip: ~/bin/muse-job already matches the repo copy"
        return 0
    fi
    exec_if_live "install ~/bin/muse-job from the repo" \
        cp "$AGENT_REPO/muse-job/bin/muse-job" "$HOME/bin/muse-job"
}

step_plugin() {
    if ! command -v muse >/dev/null 2>&1; then
        if [ "$DRY_RUN" = 1 ]; then
            note "would install the muse-job plugin (muse CLI not present yet — install it and log in first)"
            return 0
        fi
        die "muse CLI not found — install it and log in, then re-run $SCRIPT_ABS"
    fi
    # Substring match on the plugin name: `muse plugins list` output format
    # is the CLI's contract, and a forked plugin containing "muse-job" would
    # false-positive this skip. Accepted: re-running the install is harmless.
    if muse plugins list 2>/dev/null | grep -q "muse-job"; then
        note "skip: muse-job plugin already installed in the muse CLI"
        return 0
    fi
    exec_if_live "install the muse-job plugin (muse plugins install)" \
        env -C "$AGENT_REPO" muse plugins install ./muse-job/plugin || \
        die "muse plugins install failed — is the muse CLI logged in? Log in, then re-run $SCRIPT_ABS"
    note "plugin installed — run 'muse plugins approve' and approve it when prompted"
}

step_cred_ui() {
    if [ "$DRY_RUN" = 0 ]; then
        mkdir -p "$HOME/.config/systemd/user"
    fi
    local unit="$HOME/.config/systemd/user/cred-ui.service"
    if [ -f "$unit" ] && cmp -s "$AGENT_REPO/cred-ui/cred-ui.service" "$unit"; then
        note "skip: cred-ui.service unit already matches the repo copy"
    else
        exec_if_live "install the cred-ui user unit" \
            cp "$AGENT_REPO/cred-ui/cred-ui.service" "$unit"
        exec_if_live "reload the user systemd daemon" \
            systemctl --user daemon-reload
    fi
    if systemctl --user is-enabled --quiet cred-ui 2>/dev/null && \
       systemctl --user is-active --quiet cred-ui 2>/dev/null; then
        note "skip: cred-ui user service already enabled and active"
    else
        exec_if_live "enable and start the cred-ui user service" \
            systemctl --user enable --now cred-ui
    fi
}

step_cua() {
    # cua-desktop.sh start is itself idempotent (skips running components).
    exec_if_live "start the CUA desktop (cua/bin/cua-desktop.sh start)" \
        env -C "$AGENT_REPO" ./cua/bin/cua-desktop.sh start
}

run_bootstrap() {
    [ "$(id -u)" = 0 ] || die "bootstrap phase needs root — run with sudo"
    step_prereqs
    step_agent_user
    derive_agent_repo
    step_sudoers
    step_ssh_key
    step_stage_repo
    note "bootstrap complete — handing the agent phase to $AGENT_USER (login shell, so the user bus exists)"
    if [ "$DRY_RUN" = 1 ]; then
        if id -u "$AGENT_USER" >/dev/null 2>&1 && staged_copy_current 2>/dev/null; then
            note "dry-run: re-executing the agent phase as $AGENT_USER so probes see the true plan"
            sudo -iu "$AGENT_USER" env "DRY_RUN=1" "FORCE=$FORCE" "AGENT_USER=$AGENT_USER" \
                "$AGENT_REPO/scripts/install.sh" --agent-phase-internal
        else
            note "dry-run: agent checkout not staged/current — simulating the agent phase in-process"
            AGENT_PHASE=1
            run_agent
        fi
        return 0
    fi
    # Login shell (-i): pam_systemd sets XDG_RUNTIME_DIR so systemctl --user
    # has a bus. The staged path is absolute, so the cwd change is safe.
    # shellcheck disable=SC2093
    exec sudo -iu "$AGENT_USER" env \
        "DRY_RUN=$DRY_RUN" "FORCE=$FORCE" "AGENT_USER=$AGENT_USER" \
        "$AGENT_REPO/scripts/install.sh" --agent-phase-internal
}

run_agent() {
    if [ "$DRY_RUN" = 1 ]; then
        note "dry-run: simulating the agent phase (identity/sudoers gates skipped, nothing mutates)"
    else
        [ "$(id -un)" = "$AGENT_USER" ] || die "agent phase must run as $AGENT_USER (ran as $(id -un))"
        [ -f "$SUDOERS_DIR/$AGENT_USER" ] || \
            die "no sudoers drop for $AGENT_USER — run the bootstrap phase first (with sudo)"
    fi
    derive_agent_repo
    step_tailscale_install
    step_tailscale_up
    step_linger
    step_repo
    step_deploy
    step_muse_job
    step_plugin
    step_cred_ui
    step_cua
    note "install complete — approve the muse-job plugin ('muse plugins approve'), then point your Muse at the box (ONBOARDING.md)"
}

main() {
    parse_args "$@"
    # The agent phase works only in the agent-owned checkout (AGENT_REPO),
    # so the delivery checkout's readability is irrelevant to it — notably
    # Option B, where the invoker's checkout lives under /root (mode 700).
    if [ "$AGENT_PHASE" != 1 ] && [ ! -d "$REPO_DIR/.git" ]; then
        die "cannot find the repo checkout at $REPO_DIR — clone it first, then run $SCRIPT_ABS from the checkout"
    fi
    if [ "$AGENT_PHASE" = 1 ]; then
        run_agent
    elif [ "$(id -u)" = 0 ]; then
        run_bootstrap
    elif [ "$(id -un)" = "$AGENT_USER" ]; then
        note "running directly as $AGENT_USER — bootstrap phase must already hold"
        run_agent
    else
        die "run as root (sudo) for the full install, or as $AGENT_USER once bootstrap holds"
    fi
}

# Sourcing guard: the test suite sources this file to exercise the step
# functions without executing the install.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi

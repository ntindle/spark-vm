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
# does, so re-running is safe (a second run is a no-op). Anything the script
# cannot complete fails loudly with a diagnostic instead of half-applying.
#
# Out of scope: choosing a published artifact format (#1529), version pinning
# (#1527), provenance stamping (#1528).

set -euo pipefail

AGENT_USER="ntindle"
DRY_RUN=0
FORCE=0
AGENT_PHASE=0

SCRIPT_ABS="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SUDOERS_DIR="${SUDOERS_DIR:-/etc/sudoers.d}"
REPO_URL="https://github.com/ntindle/spark-vm.git"

usage() {
    cat <<'EOF'
Usage: install.sh [--agent-user NAME] [--dry-run] [--force] [--help]

  --agent-user NAME  agent account the stack runs as (default: ntindle)
  --dry-run          print what would change without changing anything
  --force            re-run steps that already hold (e.g. redeploy the stack)
  --help             this text

Run as root (or with sudo) for the bootstrap phase — creating the agent
user, the sudoers drop, and the SSH key copy — then the script drops to the
agent user itself for the tailnet + stack phase. Run directly as the agent
user only once the bootstrap phase already holds.
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

while [ $# -gt 0 ]; do
    case "$1" in
        --agent-user) AGENT_USER="${2:?--agent-user needs a name}"; shift 2 ;;
        --agent-user=*) AGENT_USER="${1#*=}"; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --force) FORCE=1; shift ;;
        --agent-phase-internal) AGENT_PHASE=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) die "unknown argument: $1 (try --help)" ;;
    esac
done

[[ "$AGENT_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "bad --agent-user name: $AGENT_USER"

# ---------------------------------------------------------------------------
# Bootstrap phase (root): agent user, sudoers drop, SSH key copy, prereqs.
# ---------------------------------------------------------------------------

step_prereqs() {
    local missing=()
    command -v git >/dev/null 2>&1 || missing+=(git)
    command -v curl >/dev/null 2>&1 || missing+=(curl)
    if [ "${#missing[@]}" -eq 0 ]; then
        note "skip: prereqs present (git, curl)"
        return 0
    fi
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
    printf '%s\n' "$want" > "$file"
    chmod 440 "$file"
    if command -v visudo >/dev/null 2>&1; then
        visudo -cf "$file" >/dev/null || {
            rm -f "$file"
            die "$file failed visudo syntax check — removed; not leaving a broken sudoers drop"
        }
    fi
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
    local dest="$dest_home/.ssh/authorized_keys"
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
    exec_if_live "install $dest_home/.ssh for $AGENT_USER" \
        install -d -o "$AGENT_USER" -g "$AGENT_USER" -m 700 "$dest_home/.ssh"
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
# Agent phase ($AGENT_USER): tailnet, repo, stack.
# ---------------------------------------------------------------------------

tailscale_install_cmd() {
    # Matches the README runbook: the upstream script escalates itself.
    curl -fsSL https://tailscale.com/install.sh | sh
}

step_tailscale_install() {
    if command -v tailscale >/dev/null 2>&1; then
        note "skip: tailscale already installed"
        return 0
    fi
    exec_if_live "install tailscale via https://tailscale.com/install.sh (needs sudo)" \
        tailscale_install_cmd
}

step_tailscale_up() {
    if tailscale status >/dev/null 2>&1; then
        note "skip: tailscale already up"
        return 0
    fi
    # stdin closed: never hang waiting on interactive auth — fail loud instead.
    exec_if_live "join the tailnet (sudo tailscale up)" \
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
    if [ ! -d "$REPO_DIR/.git" ]; then
        local default_home
        default_home="$(getent passwd "$AGENT_USER" | cut -d: -f6)"
        local target="${REPO_DIR:-$default_home/spark-vm}"
        exec_if_live "clone $REPO_URL to $target" \
            git clone "$REPO_URL" "$target"
        return 0
    fi
    note "repo exists at $REPO_DIR — fast-forwarding to origin/main"
    exec_if_live "git pull --ff-only origin main in $REPO_DIR" \
        git -C "$REPO_DIR" pull --ff-only origin main || \
        die "$REPO_DIR has local commits/divergence — resolve them, then re-run $SCRIPT_ABS"
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
        env -C "$REPO_DIR" ./proxy/deploy.sh
}

step_muse_job() {
    mkdir -p "$HOME/bin"
    if [ -f "$HOME/bin/muse-job" ] && cmp -s "$REPO_DIR/muse-job/bin/muse-job" "$HOME/bin/muse-job"; then
        note "skip: ~/bin/muse-job already matches the repo copy"
        return 0
    fi
    exec_if_live "install ~/bin/muse-job from the repo" \
        cp "$REPO_DIR/muse-job/bin/muse-job" "$HOME/bin/muse-job"
}

step_plugin() {
    command -v muse >/dev/null 2>&1 || \
        die "muse CLI not found — install it and log in, then re-run $SCRIPT_ABS"
    if muse plugins list 2>/dev/null | grep -q "muse-job"; then
        note "skip: muse-job plugin already installed in the muse CLI"
        return 0
    fi
    exec_if_live "install the muse-job plugin (muse plugins install)" \
        env -C "$REPO_DIR" muse plugins install ./muse-job/plugin || \
        die "muse plugins install failed — is the muse CLI logged in? Log in, then re-run $SCRIPT_ABS"
    note "plugin installed — run 'muse plugins approve' and approve it when prompted"
}

step_cred_ui() {
    mkdir -p "$HOME/.config/systemd/user"
    local unit="$HOME/.config/systemd/user/cred-ui.service"
    if [ -f "$unit" ] && cmp -s "$REPO_DIR/cred-ui/cred-ui.service" "$unit"; then
        note "skip: cred-ui.service unit already matches the repo copy"
    else
        exec_if_live "install the cred-ui user unit" \
            cp "$REPO_DIR/cred-ui/cred-ui.service" "$unit"
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
        env -C "$REPO_DIR" ./cua/bin/cua-desktop.sh start
}

run_bootstrap() {
    [ "$(id -u)" = 0 ] || die "bootstrap phase needs root — run with sudo"
    step_prereqs
    step_agent_user
    step_sudoers
    step_ssh_key
    note "bootstrap complete — dropping to $AGENT_USER for the agent phase"
    if [ "$DRY_RUN" = 1 ]; then
        AGENT_PHASE=1
        run_agent
        return 0
    fi
    exec sudo -u "$AGENT_USER" env \
        "REPO_DIR=$REPO_DIR" "DRY_RUN=$DRY_RUN" "FORCE=$FORCE" \
        "AGENT_USER=$AGENT_USER" "SUDOERS_DIR=$SUDOERS_DIR" \
        "$SCRIPT_ABS" --agent-phase-internal
}

run_agent() {
    [ "$(id -un)" = "$AGENT_USER" ] || die "agent phase must run as $AGENT_USER (ran as $(id -un))"
    [ -f "$SUDOERS_DIR/$AGENT_USER" ] || \
        die "no sudoers drop for $AGENT_USER — run the bootstrap phase first (with sudo)"
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
    if [ ! -d "$REPO_DIR/.git" ]; then
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

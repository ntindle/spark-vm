#!/bin/bash
# cred-ui/install.sh — install cred-ui's runtime OUTSIDE the working checkout.
#
# Issue #85: cred-ui used to execute from the working checkout, and the page
# it serves (index.html) needed no restart to take effect — so any writer
# with checkout access could change the page the human pastes real secrets
# into, and a dirty checkout failed the auto-deploy closed (blocking the
# updater from overwriting the injected file). This script copies the
# runtime set (cred-ui.py + index.html + the shared validation contract +
# the shared bounded server + the version reader + VERSION) into a fixed install directory that only the
# gated deploy path writes, and installs the systemd user unit whose
# ExecStart points at the installed copy.
#
# Run from the repo root:  bash cred-ui/install.sh
# (deploy/auto-deploy.sh runs it from the updater mirror at the new commit.)
#
# Env (all overridable; production never sets them, the defaults are live):
#   CRED_UI_INSTALL_DIR  default $HOME/.local/share/spark-vm/cred-ui
#   SYSTEMD_USER_DIR     default $HOME/.config/systemd/user
#
# Fail-closed: every required repo file is checked BEFORE any directory is
# created or any file copied — a partial repo (or a mid-merge tree) aborts
# with no mutation.

set -euo pipefail

# Deterministic modes regardless of the caller's umask (the auto-deploy
# runs at 077, a manual run at 022): these are public code files, 644/755
# is correct for all of them.
umask 022

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"

: "${CRED_UI_INSTALL_DIR:=${HOME}/.local/share/spark-vm/cred-ui}"
: "${SYSTEMD_USER_DIR:=${HOME}/.config/systemd/user}"

# Normalize a trailing slash: the staging dir below is a SIBLING
# ("${CRED_UI_INSTALL_DIR}.staging.XXXXXX"), and a trailing slash would
# silently turn it into a CHILD of the install dir instead.
CRED_UI_INSTALL_DIR="${CRED_UI_INSTALL_DIR%/}"

# Repo-relative sources, in install order. The .py files must compile;
# VERSION must parse as semver (the reader reports 0.0.0-unknown otherwise,
# which would silently age the deployed UI's version stamp).
SOURCES=(
    "cred-ui/cred-ui.py"
    "cred-ui/index.html"
    "credlib/credvalidate.py"
    "scripts/bounded_http.py"
    "scripts/sparkvm_version.py"
    "VERSION"
)

for f in "${SOURCES[@]}"; do
    [ -f "$REPO/$f" ] || {
        echo "ERROR: required repo file missing: $f — aborting before any mutation" >&2
        exit 1
    }
done
[ -f "$REPO/cred-ui/cred-ui.service" ] || {
    echo "ERROR: required repo file missing: cred-ui/cred-ui.service — aborting before any mutation" >&2
    exit 1
}

# Syntax check without touching the source tree: compile() validates
# in-memory, so no __pycache__ litter lands in the updater mirror or the
# operator's checkout (PYTHONDONTWRITEBYTECODE does not suppress
# py_compile's explicit writes — verified).
for f in "$REPO/cred-ui/cred-ui.py" \
         "$REPO/credlib/credvalidate.py" \
         "$REPO/scripts/bounded_http.py" \
         "$REPO/scripts/sparkvm_version.py"; do
    python3 -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' "$f" || {
        echo "ERROR: python syntax check failed for $f — aborting before any mutation" >&2
        exit 1
    }
done

# VERSION is the deployed UI's version stamp (docs/VERSIONING.md): the
# reader walks up from the installed cred-ui.py, so it must find a
# parseable VERSION in the install dir, not "0.0.0-unknown".
if ! python3 - "$REPO/VERSION" <<'PYEOF'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read().strip()
if not re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(-([0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?"
                r"(\+([0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?$", text):
    sys.exit("unparseable VERSION: %r" % text)
PYEOF
then
    echo "ERROR: VERSION check failed — aborting before any mutation" >&2
    exit 1
fi

# Issue #964: pre-restart guard for the swapd-backed token. The installed
# UI fetches its token through the pinned
# `sudo -n -u swapd /usr/bin/cat /home/swapd/ui-token` sudoers entry; if
# that entry is absent the service fails at startup. Fail the install
# here instead — before any mutation and before the deploy's restart —
# so a deploy never swaps a working UI for one that can't start. A
# missing /home/swapd/ui-token FILE is fine (first start generates it
# through the narrow writer); a sudo denial means the sudoers entry
# isn't installed (proxy/deploy.sh hasn't run, or a proxy-only rollback
# reverted it — see the cross-component note in deploy/components.conf).
# Skipped when CRED_UI_TOKEN_FILE names a local file (dev/CI/manual
# installs without swapd — the README documents this contract).
if [ -z "${CRED_UI_TOKEN_FILE:-}" ]; then
    # stdout is discarded (it would be the token on success); only
    # stderr is captured — on failure cat prints nothing to stdout, so
    # the captured text can never contain the token.
    set +e
    _ui_token_err="$(sudo -n -u swapd /usr/bin/cat /home/swapd/ui-token 2>&1 >/dev/null)"
    _ui_token_rc=$?
    set -e
    case "$_ui_token_rc:$_ui_token_err" in
        0:*) ;; # entry present, token readable
        *"No such file or directory"*) ;; # entry present, file not yet generated
        *)
            echo "ERROR: the pinned ui-token sudoers entry is not installed:" >&2
            echo "  sudo -n -u swapd /usr/bin/cat /home/swapd/ui-token -> ${_ui_token_err}" >&2
            echo "The UI would fail at startup. Install it with proxy/deploy.sh" >&2
            echo "(or set CRED_UI_TOKEN_FILE for a local-file install) — aborting before any mutation" >&2
            exit 1
            ;;
    esac
    unset _ui_token_err _ui_token_rc
fi

mkdir -p "$CRED_UI_INSTALL_DIR" "$SYSTEMD_USER_DIR" || {
    echo "ERROR: cannot create install directories" >&2
    exit 1
}

# Atomic publication: the whole runtime set + unit is assembled in a
# staging directory first, then renamed over the live files. The staging
# dir is a SIBLING of the install dir (same parent directory, so the
# publication renames below stay renames, never copy+unlink) and is NOT
# one of the deploy's snapshot/rollback paths, so it never lands in a
# snapshot. Consequence of the ordering: a crash or copy failure any time
# before publication leaves the live install byte-identical to before —
# no partially-written live file, ever. (The per-file publication below
# can still leave a transient mixed old/new FILE SET mid-deploy; the
# writer is the trusted deploy path, which is the stated residual — the
# per-file guarantee is the new part.)
STAGING="$(mktemp -d "${CRED_UI_INSTALL_DIR}.staging.XXXXXX")" || {
    echo "ERROR: cannot create staging dir next to $CRED_UI_INSTALL_DIR" >&2
    exit 1
}
# The EXIT trap cleans the staging dir on every exit path — except SIGKILL,
# which leaves a stale 0700 sibling holding only public runtime copies. It
# is never read by the service and never snapshotted; harmless clutter.
cleanup_staging() { rm -rf "$STAGING"; }
trap cleanup_staging EXIT

# --remove-destination: replace a symlinked destination instead of writing
# through it. Only matters against a same-uid attacker (the stated
# residual), but it is one flag and removes the ambiguity.
cp --remove-destination \
   "$REPO/cred-ui/cred-ui.py" \
   "$REPO/cred-ui/index.html" \
   "$REPO/credlib/credvalidate.py" \
   "$REPO/scripts/bounded_http.py" \
   "$REPO/scripts/sparkvm_version.py" \
   "$REPO/VERSION" \
   "$REPO/cred-ui/cred-ui.service" \
   "$STAGING/" || {
    echo "ERROR: runtime staging failed — live install untouched" >&2
    exit 1
}

# Durability before publication: a crash after a rename must not surface a
# zero-length file.
if ! python3 - "$STAGING" <<'PYEOF'
import os, sys
d = sys.argv[1]
fds = []
dfd = None
try:
    for name in sorted(os.listdir(d)):
        fds.append(os.open(os.path.join(d, name), os.O_RDONLY))
    dfd = os.open(d, os.O_RDONLY)
    for fd in fds:
        os.fsync(fd)
    os.fsync(dfd)
finally:
    for fd in fds:
        os.close(fd)
    if dfd is not None:
        os.close(dfd)
PYEOF
then
    echo "ERROR: staging fsync failed — live install untouched" >&2
    exit 1
fi

# Publish: each mv is an atomic rename on the same filesystem — the live
# file is never observed partially written. Runtime set first, then the
# unit (the unit is re-read only on daemon-reload, after publication).
for f in cred-ui.py index.html credvalidate.py bounded_http.py sparkvm_version.py VERSION; do
    mv -f "$STAGING/$f" "$CRED_UI_INSTALL_DIR/$f" || {
        echo "ERROR: publishing $f failed — live set may be mixed old/new; re-run install.sh to complete" >&2
        exit 1
    }
done

mv -f "$STAGING/cred-ui.service" "$SYSTEMD_USER_DIR/cred-ui.service" || {
    echo "ERROR: unit publish failed — re-run install.sh to complete" >&2
    exit 1
}

echo "cred-ui installed: $CRED_UI_INSTALL_DIR (unit: $SYSTEMD_USER_DIR/cred-ui.service)"

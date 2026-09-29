#!/bin/bash
# cred-ui/install.sh — install cred-ui's runtime OUTSIDE the working checkout.
#
# Issue #85: cred-ui used to execute from the working checkout, and the page
# it serves (index.html) needed no restart to take effect — so any writer
# with checkout access could change the page the human pastes real secrets
# into, and a dirty checkout failed the auto-deploy closed (blocking the
# updater from overwriting the injected file). This script copies the
# runtime set (cred-ui.py + index.html + the shared bounded server + the
# version reader + VERSION) into a fixed install directory that only the
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

# Repo-relative sources, in install order. The .py files must compile;
# VERSION must parse as semver (the reader reports 0.0.0-unknown otherwise,
# which would silently age the deployed UI's version stamp).
SOURCES=(
    "cred-ui/cred-ui.py"
    "cred-ui/index.html"
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

mkdir -p "$CRED_UI_INSTALL_DIR" "$SYSTEMD_USER_DIR" || {
    echo "ERROR: cannot create install directories" >&2
    exit 1
}

# --remove-destination: replace a symlinked destination instead of writing
# through it. Only matters against a same-uid attacker (the stated
# residual), but it is one flag and removes the ambiguity.
cp --remove-destination \
   "$REPO/cred-ui/cred-ui.py" \
   "$REPO/cred-ui/index.html" \
   "$REPO/scripts/bounded_http.py" \
   "$REPO/scripts/sparkvm_version.py" \
   "$REPO/VERSION" \
   "$CRED_UI_INSTALL_DIR/" || {
    echo "ERROR: runtime copy failed" >&2
    exit 1
}

cp --remove-destination \
   "$REPO/cred-ui/cred-ui.service" \
   "$SYSTEMD_USER_DIR/cred-ui.service" || {
    echo "ERROR: unit install failed" >&2
    exit 1
}

echo "cred-ui installed: $CRED_UI_INSTALL_DIR (unit: $SYSTEMD_USER_DIR/cred-ui.service)"

#!/bin/bash
# cua-trust.sh — shared trust predicate for the CUA desktop stack (#493).
# Sourced by cua-desktop.sh, start-xfce.sh, cua-keepalive.sh. Not executed
# directly.
#
# The desktop env file lives in world-writable /tmp and its contents are
# sourced (executed) or parsed into the environment of every desktop
# subprocess, so every consumer must apply the same check: the file must
# be a regular file (never a symlink — the swap/plant vector), owned by
# the current user, and not writable by group/other.
trust_env_file() { # trust_env_file <path> — 0 when trusted
  local f=$1
  [ -f "$f" ] && [ ! -L "$f" ] || return 1
  [ "$(stat -c %U "$f")" = "$(id -un)" ] || return 1
  [ $(( 0$(stat -c %a "$f") & 022 )) -eq 0 ] || return 1
}

#!/bin/bash
# jail/validate-pubkey.sh — issue #439: validate the agent's SSH public key file.
#
# build.sh writes the agent's pubkey verbatim into the guest's
# authorized_keys; a CRLF line ending, trailing blank lines, or a
# malformed key then fails the agent's SSH login silently (the failure
# looks like a jail/network problem, not a key-format problem). This
# helper normalizes (strips CR bytes and blank lines) and validates the
# file BEFORE the build, and the build aborts loudly on any error.
## Usage from build.sh:
#   . "$(dirname "$0")/validate-pubkey.sh"
#   if ! PUBKEY="$(validate_pubkey_file "$PUBKEY_FILE")"; then
#       echo "ERROR: invalid agent pubkey ($PUBKEY_FILE)" >&2
#       exit 1
#   fi
# Usage standalone (smoke tests / operator pre-check):
#   ./validate-pubkey.sh <pubkey-file>   # prints the normalized key line
set -euo pipefail

# validate_pubkey_file <path> — print the single normalized key line on
# stdout; exit nonzero with an ERROR on stderr when the file is missing,
# empty, holds more than one key, or fails validation.
validate_pubkey_file() {
    local file="$1" raw line key="" nlines=0
    [[ -f "$file" ]] || {
        echo "ERROR: pubkey file not found: $file" >&2
        return 1
    }
    # Strip CR bytes: CRLF line endings otherwise land verbatim in
    # authorized_keys and break the agent's login.
    raw="$(tr -d '\r' <"$file")"
    # Exactly one non-blank line is allowed — blank lines anywhere are
    # tolerated (normalized away); any second key line is an error.
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "${line//[[:space:]]/}" ]] && continue
        nlines=$((nlines + 1))
        if ((nlines > 1)); then
            echo "ERROR: pubkey file holds more than one key line ($file)" >&2
            return 1
        fi
        key="$line"
    done <<<"$raw"
    ((nlines == 1)) || {
        echo "ERROR: pubkey file is empty: $file" >&2
        return 1
    }
    # Shape check (cheap, no fork): <known key type> <base64 blob>
    # [optional comment]. Fields are space- or tab-separated.
    # Deliberately excludes cert key types (ssh-ed25519-cert-v01@...
    # etc.): the ssh-keygen layer below is the backstop for anything
    # the shape check cannot see, and certs are not agent login keys.
    if ! [[ "$key" =~ ^(ssh-(ed25519|rsa|dss)|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh\.com|sk-ecdsa-sha2-nistp256@openssh\.com)[[:space:]][A-Za-z0-9+/]+={0,3}([[:space:]].*)?$ ]]; then
        echo "ERROR: pubkey file is not a valid SSH public key line ($file)" >&2
        return 1
    fi
    # Structural check when available: ssh-keygen verifies the blob
    # actually decodes to a key of the claimed type. This catches
    # well-shaped-but-corrupt base64 the regex cannot see (verified:
    # a syntactically valid base64 blob of the right length still fails
    # -l when it does not decode to a key).
    if command -v ssh-keygen >/dev/null 2>&1; then
        if ! printf '%s\n' "$key" | ssh-keygen -l -f /dev/stdin >/dev/null 2>&1; then
            echo "ERROR: ssh-keygen rejects the pubkey in $file" >&2
            return 1
        fi
    fi
    printf '%s\n' "$key"
}

# Standalone mode: validate the argv path (build.sh sources this file
# instead, in which case BASH_SOURCE[0] != $0 and nothing executes).
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    validate_pubkey_file "${1:?usage: validate-pubkey.sh <pubkey-file>}"
fi

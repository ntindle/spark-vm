#!/usr/bin/env bash
# scan-baked-secrets.sh — gate-time negative scan enforcing the
# never-bake-values rule (GitHub #154; R2 docs/PRE_SEEDED_HARNESS_RESEARCH.md
# §4: "bake placeholders hsurr:<name>, never values").
#
# The golden-image manifest CLAIMS "empty credential stores with fixed
# registry paths" and "CA generated per tenant at first boot; private key
# never baked" (harness/generate-image-manifest.sh baked[]), but
# check-image-manifest.sh only validates the claim's SHAPE — nothing checks
# the truth. This scan is the truth check, run by the image-build gate
# (docs/GOLDEN_IMAGE_GATE_PROCEDURE.md Step 0b) before the image is
# published. A single baked-in real credential defeats the whole
# transparent-swapping model: the tenant agent could read it directly,
# bypassing every proxy control. Today the only defense is operator care
# at build time; this scan makes it mechanical.
#
# What it checks (pattern list in baked-secrets-patterns.txt, reviewed
# like code):
#   1. content patterns — real secret shapes (PEM private-key blocks, AWS
#      key IDs, GitHub/OpenAI/Anthropic tokens) must not appear in any
#      baked file. This is the "never values, only hsurr:<name>
#      placeholders" rule for baked configs, approximated by the concrete
#      shapes the pattern list names.
#   2. filename globs — credential-shaped filenames (id_rsa, .env,
#      auth.json, ...) must not exist in baked locations.
#   3. secrets-dir rule — the credential value dirs
#      (<target>/home/swapd/secrets, <target>/home/swapd/inference-secrets;
#      the narrow writers store one raw value file per credential name)
#      must hold no non-empty value except the allowlisted public gate
#      fixture dummy. This is the backstop the pattern list cannot be:
#      a novel token shape no pattern names still fails here.
#
# Honest residual: a secret in a format no content pattern names, stored
# OUTSIDE the secrets dirs, is not caught — the pattern list is the
# reviewed, extensible control for that half; extend it when new shapes
# matter. Unknown-format material inside the secrets dirs IS caught.
#
# Usage: harness/scan-baked-secrets.sh <target-root> [--patterns <file>]
#   <target-root> is the filesystem to scan (the image root at gate time,
#   e.g. /; a scratch tree in tests). Pseudo-filesystems (proc, sys, dev)
#   are excluded. The scan never modifies the target.
# Exit 0: clean — no baked secrets found.
# Exit 1: GATE REFUSAL — hits listed on stdout as
#         "baked-secrets-scan: HIT <rule-id> <path>".
# Exit 2: invocation or environment error (bad args, unreadable patterns,
#         target not a directory).
set -euo pipefail

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "usage: $0 <target-root> [--patterns <file>]" >&2; exit 2
fi
TARGET="$1"; shift
PATTERNS=""
if [[ "${1:-}" == "--patterns" ]]; then PATTERNS="${2:?--patterns needs a file}"; shift 2; fi
if [[ $# -gt 0 ]]; then echo "usage: $0 <target-root> [--patterns <file>]" >&2; exit 2; fi

HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -z "$PATTERNS" ]]; then PATTERNS="$HERE/baked-secrets-patterns.txt"; fi

if [[ ! -d "$TARGET" ]]; then
  echo "baked-secrets-scan: target is not a directory: $TARGET" >&2; exit 2
fi
if [[ ! -r "$PATTERNS" ]]; then
  echo "baked-secrets-scan: patterns file unreadable: $PATTERNS" >&2; exit 2
fi

# Canonicalize for the self-exclusion check below: the scan must not flag
# its own pattern definitions when the target tree contains them (e.g. a
# future bare-word pattern would match this file's own comment lines).
TARGET_C="$(realpath -m "$TARGET")"
PATTERNS_C="$(realpath -m "$PATTERNS")"
SELF=""
case "$PATTERNS_C" in
  "$TARGET_C"/*) SELF="$PATTERNS_C" ;;
esac

CONTENT_RULES=()  # "id:regex"
NAME_RULES=()     # "id:glob"
ALLOW_VALUES=()   # exact strings
lineno=0
while IFS= read -r line || [[ -n "$line" ]]; do
  lineno=$((lineno + 1))
  case "$line" in ''|\#*) continue ;; esac
  kind="${line%%:*}"
  rest="${line#*:}"
  if [[ "$rest" == "$line" ]]; then
    echo "baked-secrets-scan: $PATTERNS:$lineno: bad rule (want KIND: ID: RULE)" >&2; exit 2
  fi
  rest="${rest# }"
  id="${rest%%:*}"
  rule="${rest#*:}"
  if [[ "$rule" == "$rest" ]]; then
    echo "baked-secrets-scan: $PATTERNS:$lineno: bad rule (want KIND: ID: RULE)" >&2; exit 2
  fi
  rule="${rule# }"
  case "$kind" in
    content) CONTENT_RULES+=("$id:$rule") ;;
    name)    NAME_RULES+=("$id:$rule") ;;
    allow)   ALLOW_VALUES+=("$rule") ;;
    *)
      echo "baked-secrets-scan: $PATTERNS:$lineno: unknown kind '$kind'" >&2; exit 2 ;;
  esac
done < "$PATTERNS"

hits=0
hit() {  # hit <rule-id> <path>
  echo "baked-secrets-scan: HIT $1 $2"
  hits=$((hits + 1))
}

# --- 1. content patterns ---------------------------------------------------
for entry in ${CONTENT_RULES[@]+"${CONTENT_RULES[@]}"}; do
  id="${entry%%:*}"
  re="${entry#*:}"
  while IFS= read -r f; do
    [[ -n "$SELF" && "$f" == "$SELF" ]] && continue
    hit "$id" "$f"
  done < <(grep -rlE --exclude-dir=proc --exclude-dir=sys --exclude-dir=dev \
                 -e "$re" -- "$TARGET_C" 2>/dev/null || true)
done

# --- 2. filename globs -----------------------------------------------------
if ((${#NAME_RULES[@]})); then
  find_expr=()
  for entry in "${NAME_RULES[@]}"; do
    glob="${entry#*:}"
    find_expr+=(-o -name "$glob")
  done
  while IFS= read -r f; do
    [[ -n "$SELF" && "$f" == "$SELF" ]] && continue
    # recover the rule id for the report: re-match the basename
    base="$(basename "$f")"
    rid="filename"
    for entry in "${NAME_RULES[@]}"; do
      id="${entry%%:*}"; glob="${entry#*:}"
      # shellcheck disable=SC2254
      case "$base" in $glob) rid="$id"; break ;; esac
    done
    hit "$rid" "$f"
  done < <(find "$TARGET_C" \( -path "$TARGET_C/proc" -o -path "$TARGET_C/sys" -o -path "$TARGET_C/dev" \) -prune \
           -o -type f \( -false "${find_expr[@]}" \) -print 2>/dev/null || true)
fi

# --- 3. secrets-dir rule ----------------------------------------------------
# The narrow writers store one raw value file per credential name; the
# gate-time contract is empty dirs (plus the public fixture dummy while
# the gate fixture is installed). Byte-exact compare via cmp so binary
# values cannot slip past a text comparison.
allow_tmp="$(mktemp)"
trap 'rm -f "$allow_tmp"' EXIT
value_allowed() {  # value_allowed <file> -> 0 iff content exactly equals an allow entry
  local a
  for a in ${ALLOW_VALUES[@]+"${ALLOW_VALUES[@]}"}; do
    printf '%s' "$a" > "$allow_tmp"
    if cmp -s "$1" "$allow_tmp"; then return 0; fi
  done
  return 1
}
for sdir in "$TARGET_C/home/swapd/secrets" "$TARGET_C/home/swapd/inference-secrets"; do
  [[ -d "$sdir" ]] || continue
  while IFS= read -r -d '' e; do
    if [[ -L "$e" ]]; then
      hit "secret-store-symlink" "$e"      # writers create regular files only
    elif [[ -f "$e" ]]; then
      if [[ -s "$e" ]] && ! value_allowed "$e"; then
        hit "secret-store-value" "$e"
      fi
    else
      hit "secret-store-unexpected" "$e"   # writers never create dirs/fifos/sockets here
    fi
  done < <(find "$sdir" -mindepth 1 -maxdepth 1 -print0 2>/dev/null || true)
done

if ((hits > 0)); then
  echo "baked-secrets-scan: REFUSED — $hits hit(s) under $TARGET_C" >&2
  exit 1
fi
echo "baked-secrets-scan: clean — $TARGET_C"
exit 0

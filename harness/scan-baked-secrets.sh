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
# (docs/GOLDEN_IMAGE_GATE_PROCEDURE.md Steps 0b and 5b) before the image is
# published. A single baked-in real credential defeats the whole
# transparent-swapping model: the tenant agent could read it directly,
# bypassing every proxy control.
#
# What it checks (pattern list in baked-secrets-patterns.txt, reviewed
# like code):
#   1. content patterns — real secret shapes (PEM private-key blocks, AWS
#      key IDs, GitHub/OpenAI/Anthropic token shapes) must not appear in any
#      baked file. This is the "never values, only hsurr:<name>
#      placeholders" rule for baked configs, approximated by the concrete
#      shapes the pattern list names.
#   2. filename globs — credential-shaped filenames (id_rsa, .env,
#      auth.json, *.p12, ...) must not exist in baked locations. This rule
#      is deliberately stricter than the values rule: even a placeholder-
#      only .env is refused, because the filename itself advertises "secrets
#      live here" to anyone reading the image.
#   3. secrets-dir rule — the credential value dirs
#      (<target>/home/swapd/secrets, <target>/home/swapd/inference-secrets;
#      the narrow writers store one raw value file per credential name)
#      must hold no non-empty value except the allowlisted public gate
#      fixture dummy. This is the backstop the pattern list cannot be:
#      a novel token shape no pattern names still fails here.
#
# The scan itself is mechanical; the wiring is operator procedure (the gate
# doc names the steps and the gate record captures the scan's exit code and
# target — an operator can still skip a step, and the record is what makes
# a skipped scan visible at audit time).
#
# Honest residuals:
# - A secret in a format no content pattern names, stored OUTSIDE the
#   secrets dirs, is not caught — the pattern list is the reviewed,
#   extensible control for that half; extend it when new shapes matter.
#   There is deliberately no content-allowlist: a legitimate baked string
#   matching a heuristic pattern is handled by editing the patterns file
#   (reviewed like code), not by a local exception.
# - Between the Step 0b scan and the Step 5b re-run the gate itself writes
#   only public-by-design material (the fixture dummy, echo logs); the 5b
#   re-run is the verdict on the artifact that actually ships and catches
#   operator-introduced material (a key pasted during debugging, stray
#   files). Material introduced between 5b and the snapshot is unscanned —
#   snapshot promptly and touch nothing after 5b.
# - Unreadable files/dirs are skipped with a loud stderr warning, not a
#   silent pass (fail-open, but visible; the gate runs as root, which moots
#   it on a healthy image).
# - Filenames containing newlines are still refused (exit 1) but the hit
#   report may render the path across lines; the verdict is correct, the
#   rendering is line-oriented.
# - `__pycache__` / `.pytest_cache` dirs are pruned: .pyc files are
#   byte-compilations of the .py sources the scan already covers (CPython
#   constant-folds even dynamically-constructed test fixtures into .pyc
#   literals), and pytest's node-id cache embeds parametrized runtime
#   values — both are regenerable test-runner artifacts derived from
#   scanned sources, and scanning them would false-refuse on the repo's
#   own test vectors.
# - No `-xdev`: the scan descends into every mount under the target, so run
#   it with only image filesystems mounted.
#
# Usage: harness/scan-baked-secrets.sh <target-root> [--patterns <file>]
#   <target-root> is the filesystem to scan (the image root at gate time,
#   e.g. /; a scratch tree in tests). The scan never modifies the target.
# Exit 0: clean — no baked secrets found.
# Exit 1: GATE REFUSAL — hits listed on stdout as
#         "baked-secrets-scan: HIT <rule-id> <path>".
# Exit 2: invocation or environment error (bad args, unreadable patterns,
#         target not a directory, patterns file with zero checkable rules).
set -euo pipefail

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "usage: $0 <target-root> [--patterns <file>]" >&2; exit 2
fi
TARGET="$1"; shift
PATTERNS=""
if [[ "${1:-}" == "--patterns" ]]; then
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    echo "usage: $0 <target-root> [--patterns <file>]" >&2; exit 2
  fi
  PATTERNS="$2"; shift 2
fi
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
# TARGET_UNDER is computed in a separate step on purpose: "${TARGET_C%/}"/*
# written inline in the case pattern silently NEVER matches when the %-
# removal consumes the whole value (TARGET_C="/" -> the pattern is dead and
# the gate's documented `scan-baked-secrets.sh /` invocation loses its
# self-exclusion). The intermediate variable keeps the pattern well-formed.
TARGET_C="$(realpath -m "$TARGET")"
PATTERNS_C="$(realpath -m "$PATTERNS")"
TARGET_UNDER="${TARGET_C%/}"  # "" when TARGET_C is "/"; "$TARGET_UNDER"/* still matches
SELF=""
case "$PATTERNS_C" in
  "$TARGET_UNDER"/*) SELF="$PATTERNS_C" ;;
esac

CONTENT_RULES=()  # "id:regex"
NAME_RULES=()     # "id:glob"
ALLOW_VALUES=()   # exact strings
lineno=0
while IFS= read -r line || [[ -n "$line" ]]; do
  lineno=$((lineno + 1))
  line="${line%$'\r'}"                       # CRLF must not silently weaken rules
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
  rule="${rule%"${rule##*[![:space:]]}"}"    # trailing whitespace is never significant
  case "$kind" in
    content) CONTENT_RULES+=("$id:$rule") ;;
    name)    NAME_RULES+=("$id:$rule") ;;
    allow)   ALLOW_VALUES+=("$rule") ;;
    *)
      echo "baked-secrets-scan: $PATTERNS:$lineno: unknown kind '$kind'" >&2; exit 2 ;;
  esac
done < "$PATTERNS"

if ((${#CONTENT_RULES[@]} == 0 && ${#NAME_RULES[@]} == 0)); then
  echo "baked-secrets-scan: $PATTERNS defines zero checkable rules — refusing to scan clean" >&2
  exit 2
fi

hits=0
hit() {  # hit <rule-id> <path>
  echo "baked-secrets-scan: HIT $1 $2"
  hits=$((hits + 1))
}

# Unreadable entries are skipped loudly, not silently: find's stderr is
# collected and reported as a warning after the walks.
ERR_TMP="$(mktemp)"
allow_tmp="$(mktemp)"
trap 'rm -f "$allow_tmp" "$ERR_TMP"' EXIT

# One find expression shared by the content and name walks: anchored prunes
# for the top-level pseudo-filesystems (a real subdir named e.g. "dev"
# deeper in the tree is still scanned) plus any-depth __pycache__ prune.
# ${TARGET_C%/} keeps the prunes correct when TARGET is / ("/proc", not
# "//proc" — find -path does string matching, so "//proc" never matches).
PSEUDO_PRUNES=( -path "${TARGET_C%/}/proc" -o -path "${TARGET_C%/}/sys" -o -path "${TARGET_C%/}/dev" )
walk_files() {  # prints NUL-delimited regular-file/symlink paths
  find "$TARGET_C" \
    \( "${PSEUDO_PRUNES[@]}" \) -prune -o \
    \( -type d \( -name __pycache__ -o -name .pytest_cache \) \) -prune -o \
    \( -type f -o -type l \) -print0 2>>"$ERR_TMP"
}

# --- 1. content patterns ---------------------------------------------------
for entry in ${CONTENT_RULES[@]+"${CONTENT_RULES[@]}"}; do
  id="${entry%%:*}"
  re="${entry#*:}"
  # xargs -r (GNU): grep never runs on an empty file list, so a tree with
  # no files is not a hang. A batch with no match exits 1 -> || true.
  while IFS= read -r f; do
    [[ -n "$SELF" && "$f" == "$SELF" ]] && continue
    hit "$id" "$f"
  done < <(walk_files | xargs -0 -r grep -lE -e "$re" 2>/dev/null || true)
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
    base="$(basename "$f")"
    rid="filename"
    for entry in "${NAME_RULES[@]}"; do
      nid="${entry%%:*}"; nglob="${entry#*:}"
      # shellcheck disable=SC2254
      case "$base" in $nglob) rid="$nid"; break ;; esac
    done
    hit "$rid" "$f"
  done < <(find "$TARGET_C" \
             \( "${PSEUDO_PRUNES[@]}" \) -prune -o \
             \( -type d \( -name __pycache__ -o -name .pytest_cache \) \) -prune -o \
             \( -type f -o -type l \) \( -false "${find_expr[@]}" \) -print 2>>"$ERR_TMP" || true)
fi

# --- 3. secrets-dir rule ----------------------------------------------------
# The narrow writers store one raw value file per credential name; the
# gate-time contract is empty dirs (plus the public fixture dummy while
# the gate fixture is installed). Byte-exact compare via cmp so binary
# values cannot slip past a text comparison.
value_allowed() {  # value_allowed <file> -> 0 iff content exactly equals an allow entry
  local a
  for a in "${ALLOW_VALUES[@]+"${ALLOW_VALUES[@]}"}"; do
    printf '%s' "$a" > "$allow_tmp"
    if cmp -s "$1" "$allow_tmp"; then return 0; fi
  done
  return 1
}
for sdir in "$TARGET_C/home/swapd/secrets" "$TARGET_C/home/swapd/inference-secrets"; do
  if [[ -L "$sdir" ]]; then
    hit "secret-store-symlink" "$sdir"      # writers create real dirs only
    continue
  fi
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
  done < <(find "$sdir" -mindepth 1 -maxdepth 1 -print0 2>>"$ERR_TMP" || true)
done

if [[ -s "$ERR_TMP" ]]; then
  n="$(wc -l < "$ERR_TMP")"
  if ((n == 1)); then plural="y"; else plural="ies"; fi
  echo "baked-secrets-scan: WARNING: $n unreadable entr$plural skipped (fail-open — investigate):" >&2
  head -5 "$ERR_TMP" >&2
fi

if ((hits > 0)); then
  echo "baked-secrets-scan: REFUSED — $hits hit(s) under $TARGET_C" >&2
  exit 1
fi
echo "baked-secrets-scan: clean — $TARGET_C"
exit 0

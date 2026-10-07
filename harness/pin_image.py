"""The pinned golden-image record (#1087 slice 2, F3b).

After the operator builds the golden image (deploy/golden-image/build-image.sh),
completes the interactive gate (docs/GOLDEN_IMAGE_GATE_PROCEDURE.md) and pushes
the image, this tool records the DIGEST-PINNED image ref in
deploy/golden-image/pinned-image.json. The record is the #905 Fly driver's
consumption contract (docs/FLY_DRIVER_RESEARCH.md F3b: "the driver takes the
pinned ref as operator-set config and references it at machine create").

The pin is a trust anchor: the driver boots whatever it names. So the writer
is fail-closed:
- the registry host is fixed to registry.fly.io (the only registry the F3b
  driver contract names),
- the ref must be digest-pinned (a bare tag is never launchable),
- the tree the pin is recorded from must be clean and names its own
  sparkvm_sha/sparkvm_version (the tree is the pin, same discipline as
  build-image.sh),
- the referenced gate record must exist, name the same image_version, and be
  a COMPLETED pass (a skeleton is not a gate),
- repinning the same sparkvm_sha to a different digest needs --force.

The reader (read_pin / pin_image_ref) is what the driver imports; it raises
PinnedImageError on a missing or invalid record so the driver cannot provision
from an unpinned or hand-tampered ref.

stdlib only. No credentials are ever read, written, or printed here — the
operator holds the registry push credential; this tool only sees the public
digest the push produced.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

PIN_SCHEMA = "sparkvm/pinned-image@1"
PIN_PATH_REL = os.path.join("deploy", "golden-image", "pinned-image.json")
GATE_RECORD_SCHEMA = "sparkvm/golden-image-gate-record@1"
REGISTRY_HOST = "registry.fly.io"

# Same semver grammar as scripts/sparkvm_version.py (_SEMVER_RE). The drift
# test in test_pin_image.py asserts both patterns accept/reject identically
# on a fixed corpus, so this copy cannot drift silently.
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# Docker repository name component: lowercase alnum, separators [._-] singly.
_NAME_COMPONENT_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
# Docker's strict tag grammar ([\w][\w.-]{0,127}) plus "+", which the repo's
# own D-P1 tag convention uses (<version>+<sha12>, build-image.sh / CI).
_TAG_RE = re.compile(r"^[\w][\w.+-]{0,127}$")


class PinnedImageError(Exception):
    """Raised when the pinned-image record is missing or fails validation."""


def repo_root_from_here():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True, timeout=30,
    )


def _clean_tree(repo):
    # Tracked files must be clean: the pin names HEAD, so HEAD must equal the
    # tree being pinned. Untracked files are ignored — the gate record and the
    # pin file itself are produced during the publish+pin flow and are not
    # part of any commit yet; they cannot change what HEAD names.
    p = _run_git(repo, "-c", "status.showUntrackedFiles=no",
                 "status", "--porcelain")
    if p.returncode != 0:
        raise PinnedImageError(f"cannot inspect tree: {p.stderr.strip()}")
    if p.stdout.strip():
        raise PinnedImageError(
            "refusing to pin with uncommitted changes to tracked files — "
            "commit or stash first (a pin naming a SHA the tree does not "
            "contain would lie to the provision-time injector preflight)"
        )


def _tree_sha(repo):
    p = _run_git(repo, "rev-parse", "HEAD")
    if p.returncode != 0:
        raise PinnedImageError(f"cannot resolve HEAD: {p.stderr.strip()}")
    return p.stdout.strip()


def _tree_version(repo):
    path = os.path.join(repo, "VERSION")
    try:
        with open(path, encoding="utf-8") as f:
            version = f.read().strip()
    except OSError as e:
        raise PinnedImageError(f"cannot read VERSION: {e}")
    if not _SEMVER_RE.match(version):
        raise PinnedImageError(f"VERSION {version!r} is not valid semver")
    return version


def _split_digest_ref(image_ref):
    """Split '<host>/<repo>@sha256:<digest>' -> (host, repo, digest).

    Raises PinnedImageError on any shape violation.
    """
    if "@" not in image_ref:
        raise PinnedImageError(
            f"image ref is not digest-pinned (no @digest): {image_ref!r}")
    ref, _, digest = image_ref.partition("@")
    if not _DIGEST_RE.match(digest):
        raise PinnedImageError(
            f"image digest must be sha256:<64 lowercase hex>: {digest!r}")
    host, sep, repo = ref.partition("/")
    if not sep:
        raise PinnedImageError(
            f"image ref has no registry host: {image_ref!r}")
    if host != REGISTRY_HOST:
        raise PinnedImageError(
            f"registry host {host!r} is not the F3b driver contract host "
            f"{REGISTRY_HOST!r} — the driver cannot consume it")
    components = repo.split("/")
    if len(components) != 2 or not all(_NAME_COMPONENT_RE.match(c)
                                      for c in components):
        raise PinnedImageError(
            f"image repo path must be <app>/<image> in lowercase docker-name "
            f"form: {repo!r}")
    return host, repo, digest


def validate_tag_ref(tag_ref, digest):
    """Validate the human tag ref; the tag must name the same digest image.

    We cannot query the registry (no creds here), so the check is structural:
    same host, same repo path as the digest-pinned ref, well-formed tag.
    """
    if ":" not in tag_ref or "@" in tag_ref:
        raise PinnedImageError(
            f"tag ref must be <host>/<repo>:<tag>: {tag_ref!r}")
    repo_part, _, tag = tag_ref.rpartition(":")
    host, sep, repo = repo_part.partition("/")
    if not sep or host != REGISTRY_HOST:
        raise PinnedImageError(
            f"tag ref must use the F3b contract host {REGISTRY_HOST!r}: "
            f"{tag_ref!r}")
    if not _TAG_RE.match(tag):
        raise PinnedImageError(f"malformed image tag: {tag!r}")
    # The digest is bound to the digest-pinned ref; the tag ref rides along
    # as the human handle the operator pushed under. digest is unused here
    # beyond the signature — the binding is documented, not checkable offline.
    _ = digest
    return repo, tag


def validate_record(rec):
    """Validate a parsed pinned-image record dict. Returns the record."""
    if not isinstance(rec, dict):
        raise PinnedImageError("pinned-image record must be a JSON object")
    if rec.get("schema") != PIN_SCHEMA:
        raise PinnedImageError(
            f"schema must be {PIN_SCHEMA!r}, got {rec.get('schema')!r}")
    for field in ("image", "sparkvm_sha", "sparkvm_version", "pinned_at",
                  "pinned_by"):
        if not rec.get(field):
            raise PinnedImageError(f"pinned-image record missing {field!r}")
    _split_digest_ref(rec["image"])
    if not _SHA_RE.match(rec["sparkvm_sha"]):
        raise PinnedImageError(
            f"sparkvm_sha must be a 40-char lowercase hex commit: "
            f"{rec['sparkvm_sha']!r}")
    if not _SEMVER_RE.match(rec["sparkvm_version"]):
        raise PinnedImageError(
            f"sparkvm_version is not valid semver: "
            f"{rec['sparkvm_version']!r}")
    if rec.get("tag"):
        digest = rec["image"].partition("@")[2]
        validate_tag_ref(rec["tag"], digest)
    if not isinstance(rec.get("pinned_by"), str) or \
            not rec["pinned_by"].strip():
        raise PinnedImageError("pinned_by must be a non-empty operator name")
    # pinned_at is informational; it must at least parse as ISO-8601.
    try:
        datetime.datetime.fromisoformat(rec["pinned_at"])
    except (ValueError, TypeError):
        raise PinnedImageError(
            f"pinned_at is not ISO-8601: {rec['pinned_at']!r}")
    return rec


def _load_gate_record(path):
    try:
        with open(path, encoding="utf-8") as f:
            gate = json.load(f)
    except (OSError, ValueError) as e:
        raise PinnedImageError(f"cannot read gate record {path}: {e}")
    if not isinstance(gate, dict) or gate.get("schema") != GATE_RECORD_SCHEMA:
        raise PinnedImageError(
            f"gate record {path} is not a {GATE_RECORD_SCHEMA} record")
    return gate


def _check_gate_record(gate, sha, gate_label):
    if gate.get("image_version") != sha:
        raise PinnedImageError(
            f"gate record {gate_label} names image_version "
            f"{gate.get('image_version')!r}, not the pinned tree {sha!r} — "
            "the gate must cover exactly the image being pinned")
    interactive = gate.get("interactive_gate") or {}
    if interactive.get("status") != "complete" or \
            interactive.get("verdict") != "pass":
        raise PinnedImageError(
            f"gate record {gate_label} is not a completed pass "
            f"(status={interactive.get('status')!r}, "
            f"verdict={interactive.get('verdict')!r}) — an image without a "
            "completed gate record does not publish, and an unpublished "
            "image does not pin")


def write_pin(repo=None, image_ref=None, tag_ref=None, gate_record=None,
              pinned_by=None, force=False):
    """Validate and write deploy/golden-image/pinned-image.json.

    Returns the record dict. Refuses (raises PinnedImageError) on any trust
    violation; no-ops (returns the existing record) when the identical pin
    is already recorded.
    """
    if repo is None:
        repo = repo_root_from_here()
    if not image_ref:
        raise PinnedImageError("--image-ref is required")
    if not pinned_by or not pinned_by.strip():
        raise PinnedImageError("--pinned-by is required (operator principal)")
    _clean_tree(repo)
    sha = _tree_sha(repo)
    version = _tree_version(repo)

    _split_digest_ref(image_ref)
    digest = image_ref.partition("@")[2]
    if tag_ref:
        validate_tag_ref(tag_ref, digest)

    if gate_record is None:
        gate_record = os.path.join(repo, f"gate-record-{sha[:12]}.json")
    gate_label = os.path.relpath(gate_record, repo) \
        if os.path.isabs(gate_record) else gate_record
    gate = _load_gate_record(gate_record)
    _check_gate_record(gate, sha, gate_label)

    record = {
        "schema": PIN_SCHEMA,
        "image": image_ref,
        "tag": tag_ref,
        "sparkvm_sha": sha,
        "sparkvm_version": version,
        "gate_record": gate_label,
        "gate_verdict": "pass",
        "pinned_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "pinned_by": pinned_by.strip(),
    }
    validate_record(record)

    pin_path = os.path.join(repo, PIN_PATH_REL)
    if os.path.exists(pin_path):
        try:
            with open(pin_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, ValueError) as e:
            raise PinnedImageError(
                f"existing pin record is unreadable ({e}) — fix or remove it "
                "by hand before pinning")
        if existing.get("image") == image_ref and \
                existing.get("sparkvm_sha") == sha:
            print("pin-image: already pinned — no change")
            return validate_record(existing)
        if existing.get("sparkvm_sha") == sha and not force:
            raise PinnedImageError(
                f"a different image is already pinned for {sha[:12]} "
                f"({existing.get('image')!r}) — refusing to silently repin; "
                "pass --force to replace it (re-push case)")
        print(f"pin-image: replacing pin for "
              f"{existing.get('sparkvm_sha', '?')[:12]}")

    tmp = pin_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    os.replace(tmp, pin_path)
    print(f"pin-image: pinned {image_ref}")
    return record


def read_pin(repo=None):
    """Read and validate the committed pin. The #905 driver's import contract.

    Raises PinnedImageError when no pin exists or the record fails
    validation — the driver must treat that as "do not provision".
    """
    if repo is None:
        repo = repo_root_from_here()
    pin_path = os.path.join(repo, PIN_PATH_REL)
    try:
        with open(pin_path, encoding="utf-8") as f:
            rec = json.load(f)
    except FileNotFoundError:
        raise PinnedImageError(
            f"no pinned image ({PIN_PATH_REL} missing) — the golden image "
            "has not been published+pinned; refusing to provision")
    except (OSError, ValueError) as e:
        raise PinnedImageError(f"pinned-image record unreadable: {e}")
    return validate_record(rec)


def pin_image_ref(repo=None):
    """The digest-pinned ref F3b's provision passes to the Machines API."""
    return read_pin(repo)["image"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Record (pin) or read the digest-pinned golden-image "
                    "ref the #905 Fly driver consumes (F3b).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pin = sub.add_parser("pin", help="validate and write the pin record")
    pin.add_argument("--image-ref", required=True,
                     help="digest-pinned ref, e.g. "
                     "registry.fly.io/<app>/sparkvm-golden@sha256:<digest>")
    pin.add_argument("--tag-ref", default=None,
                     help="human tag pushed under, e.g. "
                     "registry.fly.io/<app>/sparkvm-golden:0.6.0+<sha12>")
    pin.add_argument("--gate-record", default=None,
                     help="completed gate record (default: "
                     "gate-record-<sha12>.json at the repo root)")
    pin.add_argument("--pinned-by", required=True,
                     help="operator principal recording the pin")
    pin.add_argument("--force", action="store_true",
                     help="allow repinning the same sparkvm_sha to a "
                     "different digest (re-push case)")

    sub.add_parser("show", help="print the current validated pin record")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "pin":
            write_pin(image_ref=args.image_ref, tag_ref=args.tag_ref,
                      gate_record=args.gate_record, pinned_by=args.pinned_by,
                      force=args.force)
        else:
            print(json.dumps(read_pin(), indent=2))
    except PinnedImageError as e:
        print(f"pin-image: ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

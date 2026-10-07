"""Tests for harness/pin_image.py (the pinned golden-image record, #1087 slice 2)."""

import importlib.util
import json
import os
import subprocess

import pytest

import pin_image
from pin_image import (
    PinnedImageError,
    PIN_SCHEMA,
    read_pin,
    pin_image_ref,
    validate_record,
    validate_tag_ref,
    write_pin,
)

HARNESS = os.path.dirname(os.path.abspath(__file__))
DIGEST = "sha256:" + "ab" * 32
DIGEST2 = "sha256:" + "cd" * 32
IMAGE_REF = f"registry.fly.io/sparkvm-prod/sparkvm-golden@{DIGEST}"
TAG_REF = "registry.fly.io/sparkvm-prod/sparkvm-golden:0.6.0+abcdef123456"


def make_repo(tmp_path):
    """A scratch git repo with a clean tree and a VERSION file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=30)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo,
                   check=True, timeout=30)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo,
                   check=True, timeout=30)
    (repo / "VERSION").write_text("0.6.0\n")
    (repo / "deploy" / "golden-image").mkdir(parents=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=30)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo,
                   check=True, timeout=30)
    return str(repo)


def head(repo):
    return subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True,
                          timeout=30).stdout.strip()


def gate_record(repo, sha, status="complete", verdict="pass"):
    """A gate record file in the repo, completed or skeleton as asked."""
    rec = {
        "schema": "sparkvm/golden-image-gate-record@1",
        "image_version": sha,
        "built_from_version": "0.6.0",
        "interactive_gate": {
            "status": status,
            "canonical_task": "fixture",
            "round_trip": "ok",
            "filing_count": "ok",
            "teardown_attestation": "ok",
            "verdict": verdict,
        },
    }
    path = os.path.join(repo, f"gate-record-{sha[:12]}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    return path


def pin_args(repo, sha, **kw):
    if "gate_record" not in kw:
        kw["gate_record"] = gate_record(repo, sha)
    args = dict(repo=repo, image_ref=IMAGE_REF, tag_ref=TAG_REF,
                pinned_by="op@example")
    args.update(kw)
    return args


# --- digest-ref validation -------------------------------------------------

def test_split_digest_ref_ok():
    host, repo_path, digest = pin_image._split_digest_ref(IMAGE_REF)
    assert host == "registry.fly.io"
    assert repo_path == "sparkvm-prod/sparkvm-golden"
    assert digest == DIGEST


@pytest.mark.parametrize("bad,why", [
    ("registry.fly.io/sparkvm-prod/sparkvm-golden:0.6.0",
     "tag-only ref is not launchable"),
    ("registry.fly.io/sparkvm-prod/sparkvm-golden@sha256:" + "ab" * 31,
     "short digest"),
    ("registry.fly.io/sparkvm-prod/sparkvm-golden@sha256:" + "AB" * 32,
     "uppercase digest"),
    ("registry.fly.io/sparkvm-prod/sparkvm-golden@md5:" + "ab" * 16,
     "wrong algorithm"),
    ("ghcr.io/sparkvm-prod/sparkvm-golden@" + DIGEST,
     "wrong registry host"),
    ("registry.fly.io/sparkvm-golden@" + DIGEST,
     "single path component"),
    ("registry.fly.io/SparkVM-Prod/sparkvm-golden@" + DIGEST,
     "uppercase app name"),
    ("registry.fly.io//sparkvm-golden@" + DIGEST,
     "empty component"),
    ("just-a-string", "no host, no digest"),
])
def test_split_digest_ref_rejects(bad, why):
    with pytest.raises(PinnedImageError):
        pin_image._split_digest_ref(bad)


def test_validate_tag_ref_ok():
    repo_path, tag = validate_tag_ref(TAG_REF, DIGEST)
    assert repo_path == "sparkvm-prod/sparkvm-golden"
    assert tag == "0.6.0+abcdef123456"


@pytest.mark.parametrize("bad", [
    "registry.fly.io/sparkvm-prod/sparkvm-golden@" + DIGEST,  # digest form
    "ghcr.io/sparkvm-prod/sparkvm-golden:0.6.0",  # wrong host
    "registry.fly.io/sparkvm-prod/sparkvm-golden:not a tag",  # spaces
])
def test_validate_tag_ref_rejects(bad):
    with pytest.raises(PinnedImageError):
        validate_tag_ref(bad, DIGEST)


# --- record validation -----------------------------------------------------

def valid_record():
    return {
        "schema": PIN_SCHEMA,
        "image": IMAGE_REF,
        "tag": TAG_REF,
        "sparkvm_sha": "a" * 40,
        "sparkvm_version": "0.6.0",
        "gate_record": "gate-record-abcdef123456.json",
        "gate_verdict": "pass",
        "pinned_at": "2026-10-06T21:00:00+00:00",
        "pinned_by": "op@example",
    }


def test_validate_record_ok():
    assert validate_record(valid_record())["image"] == IMAGE_REF


def test_validate_record_tag_optional():
    rec = valid_record()
    rec["tag"] = None
    assert validate_record(rec)["tag"] is None


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(schema="wrong"),
    lambda r: r.update(image=TAG_REF),  # tag-only image: not launchable
    lambda r: r.update(sparkvm_sha="abc"),  # short sha
    lambda r: r.update(sparkvm_sha="A" * 40),  # uppercase sha
    lambda r: r.update(sparkvm_version="0.6"),  # not semver
    lambda r: r.update(pinned_at="not-a-date"),
    lambda r: r.update(pinned_by="  "),
    lambda r: r.pop("pinned_by"),
])
def test_validate_record_rejects(mutate):
    rec = valid_record()
    mutate(rec)
    with pytest.raises(PinnedImageError):
        validate_record(rec)


def test_semver_drift_guard():
    """This module's semver copy must match scripts/sparkvm_version.py."""
    spec = importlib.util.spec_from_file_location(
        "sparkvm_version",
        os.path.join(HARNESS, "..", "scripts", "sparkvm_version.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    corpus = ["0.6.0", "1.2.3", "0.0.0-unknown", "10.20.30-rc.1",
              "0.6", "v0.6.0", "1.2.3.4", "", "latest", "0.6.0+build.5"]
    for v in corpus:
        mine = bool(pin_image._SEMVER_RE.match(v))
        theirs = bool(mod._SEMVER_RE.match(v))
        assert mine == theirs, f"semver drift on {v!r}"


# --- writer / reader --------------------------------------------------------

def test_write_pin_roundtrip(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    rec = write_pin(**pin_args(repo, sha))
    assert rec["image"] == IMAGE_REF
    assert rec["sparkvm_sha"] == sha
    assert rec["sparkvm_version"] == "0.6.0"
    assert rec["tag"] == TAG_REF
    assert rec["pinned_by"] == "op@example"

    pin_path = os.path.join(repo, "deploy", "golden-image",
                            "pinned-image.json")
    assert os.path.exists(pin_path)
    assert read_pin(repo)["image"] == IMAGE_REF
    assert pin_image_ref(repo) == IMAGE_REF


def test_write_pin_idempotent_same_image(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    args = pin_args(repo, sha)
    first = write_pin(**args)
    second = write_pin(**args)
    assert second == first


def test_write_pin_refuses_dirty_tree(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    # Untracked artifacts (the gate record) are fine; uncommitted changes to
    # tracked files make HEAD lie about the tree.
    (tmp_path / "repo" / "VERSION").write_text("9.9.9\n")
    with pytest.raises(PinnedImageError, match="uncommitted changes"):
        write_pin(**pin_args(repo, sha))


def test_write_pin_refuses_skeleton_gate(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    with pytest.raises(PinnedImageError, match="not a completed pass"):
        write_pin(**pin_args(repo, sha, gate_record=gate_record(
            repo, sha, status="pending", verdict="not-run")))


def test_write_pin_refuses_failed_gate(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    with pytest.raises(PinnedImageError, match="not a completed pass"):
        write_pin(**pin_args(repo, sha, gate_record=gate_record(
            repo, sha, status="complete", verdict="fail")))


def test_write_pin_refuses_gate_for_other_sha(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    with pytest.raises(PinnedImageError, match="exactly the image"):
        write_pin(**pin_args(repo, sha, gate_record=gate_record(
            repo, "b" * 40)))


def test_write_pin_refuses_wrong_registry(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    bad = f"ghcr.io/sparkvm-prod/sparkvm-golden@{DIGEST}"
    with pytest.raises(PinnedImageError, match="registry host"):
        write_pin(**pin_args(repo, sha, image_ref=bad))


def test_write_pin_requires_pinned_by(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    with pytest.raises(PinnedImageError, match="pinned-by"):
        write_pin(**pin_args(repo, sha, pinned_by=""))


def test_repin_same_sha_new_digest_needs_force(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    write_pin(**pin_args(repo, sha))
    new_ref = f"registry.fly.io/sparkvm-prod/sparkvm-golden@{DIGEST2}"
    with pytest.raises(PinnedImageError, match="--force"):
        write_pin(**pin_args(repo, sha, image_ref=new_ref))
    rec = write_pin(**pin_args(repo, sha, image_ref=new_ref, force=True))
    assert rec["image"] == new_ref


def test_pin_forward_to_new_sha(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    write_pin(**pin_args(repo, sha))
    (tmp_path / "repo" / "VERSION").write_text("0.7.0\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path / "repo",
                   check=True, timeout=30)
    subprocess.run(["git", "commit", "-qm", "bump"], cwd=tmp_path / "repo",
                   check=True, timeout=30)
    sha2 = head(repo)
    assert sha2 != sha
    rec = write_pin(**pin_args(repo, sha2))
    assert rec["sparkvm_sha"] == sha2
    assert rec["sparkvm_version"] == "0.7.0"


def test_write_pin_refuses_bad_version_file(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    (tmp_path / "repo" / "VERSION").write_text("not-semver\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path / "repo",
                   check=True, timeout=30)
    subprocess.run(["git", "commit", "-qm", "bad"], cwd=tmp_path / "repo",
                   check=True, timeout=30)
    with pytest.raises(PinnedImageError, match="semver"):
        write_pin(**pin_args(repo, sha))


def test_read_pin_missing_raises(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(PinnedImageError, match="not been published"):
        read_pin(repo)


def test_read_pin_rejects_tampered_record(tmp_path):
    repo = make_repo(tmp_path)
    sha = head(repo)
    write_pin(**pin_args(repo, sha))
    pin_path = os.path.join(repo, "deploy", "golden-image",
                            "pinned-image.json")
    with open(pin_path, encoding="utf-8") as f:
        rec = json.load(f)
    # Tamper: swap in a tag-only ref a hand edit could introduce.
    rec["image"] = TAG_REF
    with open(pin_path, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    with pytest.raises(PinnedImageError):
        read_pin(repo)


def test_read_pin_rejects_corrupt_json(tmp_path):
    repo = make_repo(tmp_path)
    pin_path = os.path.join(repo, "deploy", "golden-image",
                            "pinned-image.json")
    with open(pin_path, "w", encoding="utf-8") as f:
        f.write("{not json")
    with pytest.raises(PinnedImageError):
        read_pin(repo)

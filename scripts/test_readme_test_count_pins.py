"""Pin test: "(N tests)" claims in READMEs/docs must match the test files.

Drift class: component READMEs and docs state how many tests a test file
holds ("`test_foo.py` (N tests)"), and the count goes stale when tests are
added, removed, or consolidated — or is wrong at write time (four of the
claims pinned here were already stale the day they were written). A stale
count misleads contributors about suite size and erodes trust in the docs.

Contract (extends the deploy/plane-cron precedent,
`test_readme_test_count_matches` in
`deploy/plane-cron/test_verify_plane_cron.py`):
- Each registry entry names a doc, a test file, and an anchor regex with
  exactly one capture group for the stated count. The anchor must match
  exactly once in the doc, so a second mention can never shadow the pin.
- The count is the number of `test_*` functions pytest would collect
  from the test file (module level + class methods; a `test_*` def
  nested inside a function body is never collected and does not count),
  counted via `ast` (not regex). This is test *functions*, not
  parametrized expansions: a parametrized test counts once, and adding
  parametrization does not change the pinned number (unlike the
  plane-cron pin, which forbids parametrization outright —
  `hosted/test_push_sender.py` already parametrizes).
- One convention for every entry, so the pinned number always agrees
  with what `pytest --collect-only` reports for an unparametrized
  suite. (The original top-level-only convention assumed flat files;
  the site/waitlistd entry added a class-based suite, and the counting
  function was updated instead of the number.)

To pin a new claim: add one registry entry. To change a suite: update the
stated count in the doc in the same PR — CI fails otherwise. And the
anti-drift test at the bottom of this file (`test_all_test_count_claims_are_registered`)
scans every `*.md` for the claim shape and fails CI on any claim not covered by
a registry entry — so a new claim can never land unregistered the way the
`scripts/test_waitlist_jobs.py` claim did.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (doc path relative to repo root, test file path relative to repo root,
#  anchor regex with exactly one capture group for the stated count)
_CLAIMS = [
    (
        "hosted/README.md",
        "hosted/test_push_crypto.py",
        r"`test_push_crypto\.py` \((\d+) tests\)",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_payload.py",
        r"`test_push_payload\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sender.py",
        r"`test_push_sender\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sweep.py",
        r"`test_push_sweep\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sweep_port_conformance.py",
        r"`test_push_sweep_port_conformance\.py` \((\d+) tests\)",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sweep_async.py",
        r"`test_push_sweep_async\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_subscriptions_async.py",
        r"`test_push_subscriptions_async\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_events_async.py",
        r"`test_push_events_async\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_enqueue_async.py",
        r"`test_push_enqueue_async\.py` \((\d+) tests",
    ),
    (
        "harness/README.md",
        "harness/test_key_registry.py",
        r"`test_key_registry\.py` \((\d+) tests",
    ),
    (
        "docs/PHONE_HOME_S6_READINESS_2026-10-11.md",
        "pairing/test_phone_home.py",
        r"`pairing/test_phone_home\.py` \((\d+) tests\)",
    ),
    (
        "docs/D9_PUSH_SWEEP_OPERATOR_GUIDE.md",
        "hosted/test_push_sweep.py",
        # The count sits on the line after the file reference, which itself
        # sits inside a `python3 -m pytest ...` command span (no opening
        # backtick before the path).
        r"hosted/test_push_sweep\.py`\s*\((\d+) tests",
    ),
    (
        # Second mention of the plane-cron suite's count outside its own
        # README (which has its own precedent pin): the registry must cover
        # every doc that states a count, or the class recurs through the
        # unpinned mention.
        "docs/SCHEDULER_HOME_CONVERGENCE_2026-10-12.md",
        "deploy/plane-cron/test_verify_plane_cron.py",
        r"`test_verify_plane_cron\.py` \((\d+) tests\)",
    ),
    (
        "site/README.md",
        "scripts/test_waitlistd.py",
        r"`scripts/test_waitlistd\.py`, (\d+) tests",
    ),
    (
        # The slice-3a README wrote its count claim without registering it,
        # and the claim was wrong at write time (21 vs 33 actual) — the
        # failure mode the anti-drift test below exists to close.
        "site/README.md",
        "scripts/test_waitlist_jobs.py",
        r"`scripts/test_waitlist_jobs\.py`,\s*(\d+) tests",
    ),
]


def _all_test_function_count(test_path: Path) -> int:
    """`test_*` functions pytest would collect: module level + class methods.

    Only functions NOT nested inside another function body are counted —
    a `test_*` def nested inside a function is never collected by pytest,
    so counting it would let the pin pass while disagreeing with
    `--collect-only`. (Module-level `if`/`try` bodies still count: their
    functions land in the module namespace.)
    """
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    count = 0
    stack = [(tree, False)]  # (node, inside_a_function_body)
    while stack:
        node, inside_fn = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not inside_fn and child.name.startswith("test_"):
                    count += 1
                stack.append((child, True))
            else:
                stack.append((child, inside_fn))
    return count


def test_readme_test_count_claims_match():
    failures = []
    for doc_rel, test_rel, anchor in _CLAIMS:
        doc = REPO / doc_rel
        test_file = REPO / test_rel
        assert doc.is_file(), f"pinned doc missing: {doc_rel}"
        assert test_file.is_file(), f"pinned test file missing: {test_rel}"
        matches = re.findall(anchor, doc.read_text(encoding="utf-8"))
        if len(matches) != 1:
            failures.append(
                f"{doc_rel}: anchor for {test_rel} matched "
                f"{len(matches)} times (want exactly 1)"
            )
            continue
        stated = int(matches[0])
        actual = _all_test_function_count(test_file)
        if stated != actual:
            failures.append(
                f"{doc_rel} says {test_rel} has {stated} tests; "
                f"the file holds {actual} test functions"
            )
    assert not failures, (
        "stale test-count claims:\n" + "\n".join(failures)
    )


def test_confirm_readme_directory_counts_match():
    """Pin the confirm/README.md suite-size pair (directory total).

    Unlike the _CLAIMS entries (one test file, one number), confirm/
    states a *directory* total as an env-conditional pair: the count with
    the optional `cryptography` package absent vs installed
    (requirements-test.txt ships it, so CI always sees the installed
    number). The whole-file skip lives in confirm/test_push.py, which
    calls pytest.importorskip("cryptography") at module level — every
    test function in that file skips when the package is absent.

    Counting convention: all `test_*` functions at any nesting level,
    parametrization-neutral (a parametrized test counts once). The README
    phrases these as collected-item counts ("275 collected", "320 with it
    installed"), which equals the function count only while confirm/ has
    no parametrized tests; the tripwire below fails the pin if
    parametrization lands, so the claims can't silently understate what
    pytest collects.
    """
    doc = REPO / "confirm/README.md"
    text = doc.read_text(encoding="utf-8")

    with_matches = re.findall(r"(\d+) with it installed", text)
    assert len(with_matches) == 1, (
        "confirm/README.md: with-crypto anchor matched "
        f"{len(with_matches)} times (want exactly 1)"
    )
    without_matches = re.findall(
        r"\((\d+) collected when the optional `cryptography` package is absent",
        text,
    )
    assert len(without_matches) == 1, (
        "confirm/README.md: without-crypto anchor matched "
        f"{len(without_matches)} times (want exactly 1)"
    )
    stated_with = int(with_matches[0])
    stated_without = int(without_matches[0])

    suite_dir = REPO / "confirm"
    test_files = sorted(suite_dir.glob("test_*.py"))
    assert test_files, "confirm/test_*.py: no test files found"
    parametrized = []
    for p in test_files:
        ptree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(ptree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                and any(
                    "parametrize" in ast.dump(d) for d in node.decorator_list
                )
            ):
                parametrized.append(f"{p.name}::{node.name}")
        for node in ptree.body:
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "pytestmark"
                    for t in node.targets
                )
                and "parametrize" in ast.dump(node.value)
            ):
                parametrized.append(f"{p.name}::<module pytestmark>")
    assert not parametrized, (
        "confirm/: parametrized tests break the collected-count claims "
        "(the README states collected items but the pin counts test "
        "functions): " + ", ".join(parametrized) + " — reconcile the "
        "README numbers and this pin before re-adding"
    )
    total = sum(_all_test_function_count(p) for p in test_files)

    def _has_module_skip(path: Path) -> bool:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return any(
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "attr", "") == "importorskip"
            for node in tree.body
        )

    gated_files = [p for p in test_files if _has_module_skip(p)]
    assert [p.name for p in gated_files] == ["test_push.py"], (
        "confirm/: the without-crypto derivation assumes test_push.py is "
        "the ONLY module-level-skipped file; module-level-skipped files "
        f"are now {[p.name for p in gated_files]} — update the README "
        "pair and this pin"
    )
    gated = sum(_all_test_function_count(p) for p in gated_files)

    failures = []
    if stated_with != total:
        failures.append(
            f"confirm/README.md states {stated_with} (with cryptography); "
            f"confirm/test_*.py holds {total} test functions"
        )
    if stated_without != total - gated:
        failures.append(
            f"confirm/README.md states {stated_without} (without "
            f"cryptography); expected {total} - {gated} (test_push.py "
            f"is the only gated file) = {total - gated} — if a second "
            f"file gained a module-level skip, update this pin's "
            f"gated-file assumption"
        )
    assert not failures, "stale confirm/ test-count claims:\n" + "\n".join(failures)


# A `test_*.py` mention followed (within a short window, spanning an
# optional line break and comma/paren) by an "(N tests)"-shaped count is a
# stated suite-size claim — the shape the registry above pins.
_CLAIM_FILE_RE = re.compile(r"(?<![\w/.-])([\w./-]*test_[\w.-]*\.py)")
_CLAIM_COUNT_RE = re.compile(r"^`?\s*[,(]?\s*(\d+)\s+tests?\b")
_CLAIM_WINDOW = 100


def _resolve_test_file(mention):
    """Resolve a doc's test-file mention to a repo-relative path.

    A bare basename is resolved by searching the tree; it must be unique.
    A literal relative path must exist. Failure is loud — an unresolvable
    mention is itself a doc defect.
    """
    direct = REPO / mention
    if direct.is_file():
        return direct.relative_to(REPO).as_posix()
    candidates = sorted(
        p.relative_to(REPO).as_posix()
        for p in REPO.rglob(mention.split("/")[-1])
        if p.is_file() and ".git" not in p.parts
    )
    assert candidates, (
        f"doc mentions test file {mention!r} which does not exist in the repo"
    )
    assert len(candidates) == 1, (
        f"doc mentions ambiguous test file {mention!r}: {candidates} — "
        "disambiguate with a path"
    )
    return candidates[0]


def test_all_test_count_claims_are_registered():
    """Anti-drift: every stated suite-size claim must be pinned.

    A claim that never gets a _CLAIMS entry rots silently — the
    `scripts/test_waitlist_jobs.py` claim sat in site/README.md for weeks
    wrong at write time (21 vs 33 actual) with nothing able to catch it,
    because the count-pinning test only checks registered claims. This
    scanner finds every `test_*.py` (N tests)-shaped claim in every `*.md`
    and requires its (doc, test file) pair to be in the registry, so a new
    claim fails CI until it is pinned in the same PR.
    """
    registered = {(doc, test) for doc, test, _anchor in _CLAIMS}
    unregistered = []
    failures = []
    for md in sorted(REPO.rglob("*.md")):
        if ".git" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")
        for m in _CLAIM_FILE_RE.finditer(text):
            window = text[m.end() : m.end() + _CLAIM_WINDOW]
            cm = _CLAIM_COUNT_RE.match(window)
            if not cm:
                continue
            mention = m.group(1)
            try:
                resolved = _resolve_test_file(mention)
            except AssertionError as e:
                failures.append(f"{md.relative_to(REPO)}: {e}")
                continue
            pair = (md.relative_to(REPO).as_posix(), resolved)
            if pair not in registered:
                unregistered.append(
                    f"{pair[0]}: claim about {resolved} ({cm.group(1)} tests) "
                    "has no _CLAIMS entry — register it in this file's "
                    "registry in the same PR"
                )
    assert not failures, "\n".join(failures)
    assert not unregistered, (
        "unregistered test-count claims:\n" + "\n".join(unregistered)
    )

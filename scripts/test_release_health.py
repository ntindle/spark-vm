#!/usr/bin/env python3
"""Hermetic tests for scripts/release_health.py.

All tests exercise the pure consistency core and the output parsers —
nothing here touches the network. Each test pins behavior that a neuter
must break (verified by neutering, then reverted).
"""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_health
from release_health import (  # noqa: E402
    EXIT_DRIFT,
    EXIT_ERROR,
    EXIT_OK,
    _next_link,
    _parse_ls_remote,
    _parse_ls_remote_deref,
    _parse_releases_page,
    check_consistency,
    check_gate_coverage,
    fetch_gate_verdict_for_sha,
    fetch_releases,
    is_release_tag,
    main,
)


def _rel(tag, draft=False, prerelease=False):
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


class GrammarTest(unittest.TestCase):
    def test_release_grammar_accepts(self):
        for t in ("v0.1.0", "v1.2.3", "v0.6.0-rc.1", "v10.20.30+build.1"):
            self.assertTrue(is_release_tag(t), t)

    def test_release_grammar_rejects(self):
        for t in (
            "main", "v1.2", "v1.2.3.4", "01.2.3", "v1.2.3-", "v1.02.3",
            "ghost/20261002-2129", "refs/tags/v0.6.0", "", None, 123,
        ):
            self.assertFalse(is_release_tag(t), repr(t))


class LsRemoteParseTest(unittest.TestCase):
    def test_collapses_deref_lines(self):
        out = "aaa\trefs/tags/v0.6.0\nbbb\trefs/tags/v0.6.0^{}\n"
        self.assertEqual(_parse_ls_remote(out), ["v0.6.0"])

    def test_skips_non_tag_refs(self):
        out = "aaa\trefs/heads/main\nbbb\trefs/tags/v0.5.0\n"
        self.assertEqual(_parse_ls_remote(out), ["v0.5.0"])

    def test_empty_and_garbage(self):
        self.assertEqual(_parse_ls_remote(""), [])
        self.assertEqual(_parse_ls_remote("not a line\n"), [])


class ReleasesParseTest(unittest.TestCase):
    def test_normalizes(self):
        rows = _parse_releases_page([
            {"tag_name": "v0.6.0", "draft": False, "prerelease": False},
            {"tag_name": "v0.5.0", "draft": True, "prerelease": False},
        ])
        self.assertEqual(rows, [_rel("v0.6.0"), _rel("v0.5.0", draft=True)])

    def test_skips_malformed(self):
        rows = _parse_releases_page([
            {"tag_name": None}, "junk", 42, {"no_tag": 1},
            {"tag_name": "v0.6.0"},
        ])
        self.assertEqual(rows, [_rel("v0.6.0")])

    def test_non_list_payload(self):
        self.assertEqual(_parse_releases_page({"x": 1}), [])
        self.assertEqual(_parse_releases_page(None), [])


class PaginationTest(unittest.TestCase):
    def test_next_link_present(self):
        link = ('<https://api.github.com/repos/o/r/releases?page=2>; rel="next", '
                '<https://api.github.com/repos/o/r/releases?page=5>; rel="last"')
        self.assertEqual(
            _next_link(link),
            "https://api.github.com/repos/o/r/releases?page=2",
        )

    def test_next_link_absent(self):
        link = '<https://api.github.com/repos/o/r/releases?page=1>; rel="last"'
        self.assertIsNone(_next_link(link))

    def test_next_link_malformed(self):
        self.assertIsNone(_next_link(""))
        self.assertIsNone(_next_link(None))
        self.assertIsNone(_next_link("not a link header"))
        self.assertIsNone(_next_link('<unclosed; rel="next"'))

    def test_fetch_releases_consumes_all_pages(self):
        pages = [
            ([{"tag_name": "v0.6.0", "draft": False, "prerelease": False}],
             "https://api.github.com/page2"),
            ([{"tag_name": "v0.5.0", "draft": False, "prerelease": False}],
             None),
        ]
        calls = []
        real = release_health._api_get

        def stub(url, token):
            calls.append(url)
            page, nxt = pages[len(calls) - 1]
            return page, nxt

        release_health._api_get = stub
        try:
            rows = fetch_releases("o/r")
        finally:
            release_health._api_get = real
        self.assertEqual(
            rows, [_rel("v0.6.0"), _rel("v0.5.0")])
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].startswith("https://api.github.com/repos/o/r/releases"))

    def test_fetch_releases_single_page(self):
        real = release_health._api_get
        release_health._api_get = (
            lambda url, token: ([_rel("v0.6.0")], None)
        )
        try:
            rows = fetch_releases("o/r", api_url="https://example.invalid")
        finally:
            release_health._api_get = real
        self.assertEqual(rows, [_rel("v0.6.0")])


class ConsistencyTest(unittest.TestCase):
    def test_clean_pair_is_ok(self):
        d = check_consistency(["v0.6.0"], [_rel("v0.6.0")])
        self.assertEqual(d, [])

    def test_tag_without_release_is_drift(self):
        d = check_consistency(["v0.6.0", "v0.5.0"], [_rel("v0.6.0")])
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "tag-without-release")
        self.assertEqual(d[0]["tag"], "v0.5.0")

    def test_draft_does_not_satisfy(self):
        d = check_consistency(["v0.6.0"], [_rel("v0.6.0", draft=True)])
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "tag-without-release")

    def test_prerelease_satisfies(self):
        # A prerelease is published (visible); the check is about the publish
        # step, not the release type.
        d = check_consistency(["v0.6.0"], [_rel("v0.6.0", prerelease=True)])
        self.assertEqual(d, [])

    def test_release_without_tag_is_drift(self):
        d = check_consistency([], [_rel("v9.9.9")])
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "release-without-tag")
        self.assertEqual(d[0]["tag"], "v9.9.9")

    def test_non_release_tags_ignored(self):
        d = check_consistency(
            ["ghost/20261002-2129", "v0.6.0"], [_rel("v0.6.0")]
        )
        self.assertEqual(d, [])

    def test_release_tag_not_in_grammar_is_drift(self):
        d = check_consistency(
            ["weird"], [{"tag_name": "weird", "draft": False, "prerelease": False}]
        )
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "release-without-tag")

    def test_empty_is_clean(self):
        self.assertEqual(check_consistency([], []), [])

    def test_malformed_inputs_never_raise(self):
        d = check_consistency([None, 42, "v0.6.0"], ["junk", None, _rel("v0.6.0")])
        self.assertEqual(d, [])


class TagShaParseTest(unittest.TestCase):
    def test_deref_wins_over_tag_object(self):
        out = ("aaa\trefs/tags/v0.6.0\n"
               "bbb\trefs/tags/v0.6.0^{}\n")
        self.assertEqual(_parse_ls_remote_deref(out), {"v0.6.0": "bbb"})

    def test_lightweight_tag_falls_back_to_plain_sha(self):
        out = "ccc\trefs/tags/v0.5.0\n"
        self.assertEqual(_parse_ls_remote_deref(out), {"v0.5.0": "ccc"})

    def test_skips_non_tag_refs_and_garbage(self):
        out = ("aaa\trefs/heads/main\n"
               "not a line\n"
               "ddd\trefs/tags/v0.4.0^{}\n")
        self.assertEqual(_parse_ls_remote_deref(out), {"v0.4.0": "ddd"})
        self.assertEqual(_parse_ls_remote_deref(""), {})


def _gate_api_stub(runs_for_sha, jobs_for_run):
    """Stub _api_get: runs_for_sha maps sha -> runs payload list;
    jobs_for_run maps run id -> jobs payload list."""
    def stub(url, token):
        if "/actions/workflows/release.yml/runs" in url:
            sha = url.split("head_sha=")[1].split("&")[0]
            return {"workflow_runs": runs_for_sha.get(sha, [])}, None
        run_id = int(url.split("/actions/runs/")[1].split("/")[0])
        return {"jobs": jobs_for_run.get(run_id, [])}, None
    return stub


def _run_obj(run_id, status="completed", updated="2026-10-19T00:00:00Z"):
    return {"id": run_id, "status": status, "updated_at": updated}


def _job(name, conclusion):
    return {"name": name, "conclusion": conclusion}


class GateVerdictTest(unittest.TestCase):
    SUFFIX = "build recipe + baked-secrets scan + manifest preflight"

    def test_success(self):
        stub = _gate_api_stub(
            {"abc": [_run_obj(1)]},
            {1: [_job("release", "success"),
                 _job("golden-image build gate / " + self.SUFFIX, "success")]},
        )
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("success", 1))

    def test_failure(self):
        stub = _gate_api_stub(
            {"abc": [_run_obj(1)]},
            {1: [_job(self.SUFFIX, "failure")]},
        )
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("failure", 1))

    def test_cancelled_counts_as_failure(self):
        stub = _gate_api_stub(
            {"abc": [_run_obj(1)]},
            {1: [_job(self.SUFFIX, "cancelled")]},
        )
        v, _ = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual(v, "failure")

    def test_pending_when_run_in_flight(self):
        stub = _gate_api_stub({"abc": [_run_obj(7, status="in_progress")]}, {})
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("pending", 7))

    def test_missing_when_no_run(self):
        stub = _gate_api_stub({}, {})
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("missing", None))

    def test_not_applicable_when_run_predates_gate(self):
        stub = _gate_api_stub(
            {"abc": [_run_obj(1)]},
            {1: [_job("release", "success")]},
        )
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("not-applicable", 1))

    def test_malformed_jobs_payload_is_loud(self):
        def bad_jobs(url, token):
            if "/actions/runs/" in url:
                return {"unexpected": True}, None
            return _gate_api_stub({"abc": [_run_obj(1)]}, {})(url, token)
        with self.assertRaises(RuntimeError):
            fetch_gate_verdict_for_sha("o/r", "abc", _api_get=bad_jobs)

    def test_latest_completed_run_wins(self):
        stub = _gate_api_stub(
            {"abc": [_run_obj(1, updated="2026-10-18T00:00:00Z"),
                     _run_obj(2, updated="2026-10-19T00:00:00Z")]},
            {1: [_job(self.SUFFIX, "success")],
             2: [_job(self.SUFFIX, "failure")]},
        )
        v, rid = fetch_gate_verdict_for_sha("o/r", "abc", _api_get=stub)
        self.assertEqual((v, rid), ("failure", 2))


class GateCoverageTest(unittest.TestCase):
    def test_success_is_clean(self):
        d = check_gate_coverage({"v0.6.0"}, {"v0.6.0": "aaa"},
                                {"aaa": ("success", 1)})
        self.assertEqual(d, [])

    def test_not_applicable_is_clean(self):
        d = check_gate_coverage({"v0.6.0"}, {"v0.6.0": "aaa"},
                                {"aaa": ("not-applicable", 1)})
        self.assertEqual(d, [])

    def test_failure_is_drift_with_run_id(self):
        d = check_gate_coverage({"v0.6.0"}, {"v0.6.0": "aaa"},
                                {"aaa": ("failure", 99)})
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "gate-failed")
        self.assertEqual(d[0]["tag"], "v0.6.0")
        self.assertIn("99", d[0]["detail"])

    def test_pending_and_missing_are_unverified(self):
        d = check_gate_coverage(
            {"v0.6.0", "v0.5.0"},
            {"v0.6.0": "aaa", "v0.5.0": "bbb"},
            {"aaa": ("pending", 7), "bbb": ("missing", None)})
        kinds = {x["tag"]: x["kind"] for x in d}
        self.assertEqual(kinds, {"v0.6.0": "gate-unverified",
                                 "v0.5.0": "gate-unverified"})

    def test_unknown_sha_is_unverified(self):
        d = check_gate_coverage({"v0.6.0"}, {}, {})
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "gate-unverified")

    def test_unpublished_tags_not_checked(self):
        # A tag with no published release owes no gate verdict — the
        # consistency check owns that drift class.
        d = check_gate_coverage(set(), {"v0.6.0": "aaa"},
                                {"aaa": ("failure", 1)})
        self.assertEqual(d, [])

    def test_malformed_inputs_never_raise(self):
        d = check_gate_coverage({None, 42, "v0.6.0"},
                                {"v0.6.0": None}, {None: ("bogus", 1)})
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["kind"], "gate-unverified")


class MainExitCodesTest(unittest.TestCase):
    def _run(self, tags, releases):
        # The gate fetchers are pinned green so these tests keep exercising
        # the consistency core only (the gate core has its own test class).
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                ["--repo", "o/r"],
                _fetch_tags=lambda repo: tags,
                _fetch_releases=lambda repo, url: releases,
                _fetch_tag_shas=lambda repo: {
                    t: "sha-" + t for t in tags if isinstance(t, str)},
                _fetch_gate_verdicts=lambda repo, shas, url: {
                    s: ("success", 1) for s in shas.values()
                    if isinstance(s, str)},
            )
        return code, buf.getvalue()

    def test_exit_ok_clean(self):
        code, out = self._run(["v0.6.0"], [_rel("v0.6.0")])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("OK", out)

    def test_exit_drift(self):
        code, out = self._run(["v0.6.0", "v0.5.0"], [_rel("v0.6.0")])
        self.assertEqual(code, EXIT_DRIFT)
        self.assertIn("tag-without-release", out)
        self.assertIn("v0.5.0", out)

    def test_exit_error_on_fetch_failure(self):
        def boom(repo):
            raise RuntimeError("nope")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--repo", "o/r"], _fetch_tags=boom,
                        _fetch_releases=lambda r, u: [])
        self.assertEqual(code, EXIT_ERROR)

    def test_json_shape(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                ["--repo", "o/r", "--json"],
                _fetch_tags=lambda repo: ["v0.6.0"],
                _fetch_releases=lambda repo, url: [],
                _fetch_tag_shas=lambda repo: {"v0.6.0": "sha-v0.6.0"},
                _fetch_gate_verdicts=lambda repo, shas, url: {},
            )
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, EXIT_DRIFT)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["repo"], "o/r")
        self.assertEqual(payload["drifts"][0]["kind"], "tag-without-release")


class MainGateTest(unittest.TestCase):
    def _run(self, argv, tags, releases, shas, verdicts):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                argv,
                _fetch_tags=lambda repo: tags,
                _fetch_releases=lambda repo, url: releases,
                _fetch_tag_shas=lambda repo: shas,
                _fetch_gate_verdicts=lambda repo, s, url: verdicts,
            )
        return code, buf.getvalue()

    def test_gate_failure_is_drift(self):
        code, out = self._run(
            ["--repo", "o/r"], ["v0.6.0"], [_rel("v0.6.0")],
            {"v0.6.0": "aaa"}, {"aaa": ("failure", 99)})
        self.assertEqual(code, EXIT_DRIFT)
        self.assertIn("gate-failed", out)
        self.assertIn("v0.6.0", out)

    def test_gate_clean_is_ok(self):
        code, out = self._run(
            ["--repo", "o/r"], ["v0.6.0"], [_rel("v0.6.0")],
            {"v0.6.0": "aaa"}, {"aaa": ("success", 1)})
        self.assertEqual(code, EXIT_OK)
        self.assertIn("golden-image gate passed", out)

    def test_skip_gate(self):
        def boom(repo, shas, url):
            raise AssertionError("gate fetch must not run with --skip-gate")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                ["--repo", "o/r", "--skip-gate"],
                _fetch_tags=lambda repo: ["v0.6.0"],
                _fetch_releases=lambda repo, url: [_rel("v0.6.0")],
                _fetch_tag_shas=lambda repo: (_ for _ in ()).throw(
                    AssertionError("must not run")),
                _fetch_gate_verdicts=boom,
            )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("no verdict on the golden-image gate", buf.getvalue())

    def test_json_includes_gate_drifts(self):
        code, out = self._run(
            ["--repo", "o/r", "--json"], ["v0.6.0"], [_rel("v0.6.0")],
            {"v0.6.0": "aaa"}, {"aaa": ("missing", None)})
        payload = json.loads(out)
        self.assertEqual(code, EXIT_DRIFT)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["gate_drifts"][0]["kind"], "gate-unverified")

    def test_gate_error_is_operational_error(self):
        def boom(repo):
            raise RuntimeError("nope")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                ["--repo", "o/r"],
                _fetch_tags=lambda repo: ["v0.6.0"],
                _fetch_releases=lambda repo, url: [_rel("v0.6.0")],
                _fetch_tag_shas=boom,
                _fetch_gate_verdicts=lambda repo, s, url: {},
            )
        self.assertEqual(code, EXIT_ERROR)


if __name__ == "__main__":
    unittest.main()

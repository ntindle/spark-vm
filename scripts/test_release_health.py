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
from release_health import (  # noqa: E402
    EXIT_DRIFT,
    EXIT_ERROR,
    EXIT_OK,
    _parse_ls_remote,
    _parse_releases_page,
    check_consistency,
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


class MainExitCodesTest(unittest.TestCase):
    def _run(self, tags, releases):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(
                ["--repo", "o/r"],
                _fetch_tags=lambda repo: tags,
                _fetch_releases=lambda repo, url: releases,
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
            )
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, EXIT_DRIFT)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["repo"], "o/r")
        self.assertEqual(payload["drifts"][0]["kind"], "tag-without-release")


if __name__ == "__main__":
    unittest.main()

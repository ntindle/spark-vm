"""Tests for the rulesets-as-code deliverables (issue #174).

Pure-local: schema validation of deploy/rulesets/*.json plus behavior of
scripts/apply-rulesets.sh in its offline modes (dry-run, usage errors).
Nothing here touches the GitHub API — applying a ruleset is an owner
decision, exercised with --execute by a human.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULESETS = ROOT / "deploy" / "rulesets"
SCRIPT = ROOT / "scripts" / "apply-rulesets.sh"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def ci_job_check_names(ci_yml_path):
    """Check-run names GitHub derives from ci.yml's jobs: `name:` if set, else the job id.

    Purpose-built minimal parser (no PyYAML — the CI python-tests job
    installs only pytest, so this must not need anything else). It
    understands only this file's shape:

        jobs:
          <job-id>:          # exactly two-space indent
            name: <display>   # first four-space-indented `name:` wins

    Anything else (missing `jobs:` key, zero parsed jobs) raises, so a
    future reformat of ci.yml fails loudly instead of silently comparing
    the wrong thing.
    """
    lines = Path(ci_yml_path).read_text().splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        raise ValueError(f"{ci_yml_path}: no top-level `jobs:` key")
    names = []
    job_id = None
    job_name = None
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break  # next top-level key: left the jobs: section
        if indent == 2 and line.rstrip().endswith(":"):
            if job_id is not None:
                names.append(job_name or job_id)
            job_id = stripped[:-1]
            job_name = None
        elif (
            indent == 4
            and job_id is not None
            and job_name is None
            and stripped.startswith("name:")
        ):
            job_name = stripped[len("name:"):].strip()
    if job_id is not None:
        names.append(job_name or job_id)
    if not names:
        raise ValueError(f"{ci_yml_path}: parsed zero jobs under `jobs:`")
    return set(names)


def load(name):
    return json.loads((RULESETS / name).read_text())


class TestTagRulesets(unittest.TestCase):
    def test_base_is_valid_active_tag_ruleset(self):
        d = load("tag-protection-vstar.json")
        self.assertEqual(d["target"], "tag")
        self.assertEqual(d["enforcement"], "active")
        self.assertTrue(d["conditions"]["ref_name"]["include"])
        self.assertTrue(d["rules"])

    def test_base_covers_vstar_refs(self):
        d = load("tag-protection-vstar.json")
        includes = d["conditions"]["ref_name"]["include"]
        self.assertTrue(includes)
        for ref in includes:
            self.assertTrue(
                ref.startswith("refs/tags/v"),
                f"tag ruleset must only match v* tag refs, got {ref}",
            )

    def test_base_blocks_update_and_deletion(self):
        types = {r["type"] for r in load("tag-protection-vstar.json")["rules"]}
        self.assertIn("update", types)
        self.assertIn("deletion", types)

    def test_no_dead_tag_name_pattern_rule(self):
        # The tag_name_pattern rule was removed: with operator "starts_with"
        # GitHub interprets the pattern literally, so "v*" would match only
        # tags literally beginning "v*" (i.e. nothing real). Scoping to v*
        # tags is done by the ref_name condition, which uses fnmatch.
        for name in ("tag-protection-vstar.json", "tag-protection-vstar-strict.json"):
            types = {r["type"] for r in load(name)["rules"]}
            self.assertNotIn("tag_name_pattern", types, name)

    def test_base_has_no_bypass(self):
        # The base variant is absolute: even the owner cannot move a tag.
        self.assertNotIn("bypass_actors", load("tag-protection-vstar.json"))

    def test_strict_adds_creation_rule(self):
        base = {r["type"] for r in load("tag-protection-vstar.json")["rules"]}
        strict = {r["type"] for r in load("tag-protection-vstar-strict.json")["rules"]}
        self.assertEqual(strict - base, {"creation"})

    def test_strict_bypasses_only_the_release_workflow_actor(self):
        actors = load("tag-protection-vstar-strict.json").get("bypass_actors", [])
        self.assertEqual(len(actors), 1)
        self.assertEqual(actors[0]["actor_type"], "Integration")
        self.assertEqual(actors[0]["actor_id"], 41898282)  # github-actions[bot]
        self.assertEqual(actors[0]["bypass_mode"], "always")

    def test_strict_is_an_alternative_not_a_second_ruleset(self):
        # Same name/target/refs: applying one replaces the other.
        base = load("tag-protection-vstar.json")
        strict = load("tag-protection-vstar-strict.json")
        self.assertEqual(base["name"], strict["name"])
        self.assertEqual(base["target"], strict["target"])
        self.assertEqual(
            base["conditions"]["ref_name"]["include"],
            strict["conditions"]["ref_name"]["include"],
        )


class TestMainBranchRuleset(unittest.TestCase):
    def test_covers_main_only(self):
        d = load("main-branch-protection.json")
        self.assertEqual(d["target"], "branch")
        self.assertEqual(d["enforcement"], "active")
        self.assertEqual(d["conditions"]["ref_name"]["include"], ["refs/heads/main"])

    def test_blocks_deletion_and_force_push(self):
        types = {r["type"] for r in load("main-branch-protection.json")["rules"]}
        self.assertIn("deletion", types)
        self.assertIn("non_fast_forward", types)

    def test_requires_pr_but_no_human_approval(self):
        pr = next(
            r for r in load("main-branch-protection.json")["rules"]
            if r["type"] == "pull_request"
        )
        # The improvement loop self-merges; a human-approval gate would brick it.
        self.assertEqual(pr["parameters"]["required_approving_review_count"], 0)

    def test_requires_all_ci_checks_green(self):
        checks = next(
            r for r in load("main-branch-protection.json")["rules"]
            if r["type"] == "required_status_checks"
        )
        contexts = {c["context"] for c in checks["parameters"]["required_status_checks"]}
        # Exact set equality in BOTH directions: the declared ruleset must
        # require exactly the checks ci.yml defines — no lagging behind a
        # renamed/added job, and no requiring a check that no longer exists.
        self.assertEqual(contexts, ci_job_check_names(CI_YML))
        self.assertTrue(checks["parameters"]["strict_required_status_checks_policy"])

    def test_ci_job_check_names_are_the_declared_four(self):
        # Known-good anchor: the protection is *supposed* to require exactly
        # these four checks. A ci.yml job rename/add/remove must update this
        # set deliberately, under review, together with the ruleset JSON —
        # the equality test above then forces the JSON to follow.
        self.assertEqual(
            ci_job_check_names(CI_YML),
            {
                "python tests",
                "shellcheck",
                "markdown link check",
                "PNG screenshot smoke test",
            },
        )

    def _declared_contexts(self):
        checks = next(
            r for r in load("main-branch-protection.json")["rules"]
            if r["type"] == "required_status_checks"
        )
        return {c["context"] for c in checks["parameters"]["required_status_checks"]}

    def _parse_variant(self, variant_text):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            f.write(variant_text)
            path = f.name
        try:
            return ci_job_check_names(path)
        finally:
            os.unlink(path)

    def test_parser_fires_on_an_added_job(self):
        # Non-vacuity: a fifth ci.yml job must change the parsed set, so the
        # exact-equality guard cannot pass while the ruleset JSON lags behind.
        variant = (
            CI_YML.read_text()
            + "\n  extra-job:\n    name: extra check\n    runs-on: ubuntu-latest\n"
        )
        parsed = self._parse_variant(variant)
        self.assertIn("extra check", parsed)
        self.assertNotEqual(parsed, self._declared_contexts())

    def test_parser_fires_on_a_renamed_job(self):
        variant = CI_YML.read_text().replace("name: shellcheck", "name: shell lint", 1)
        self.assertNotEqual(variant, CI_YML.read_text())  # the replace landed
        parsed = self._parse_variant(variant)
        self.assertIn("shell lint", parsed)
        self.assertNotIn("shellcheck", parsed)
        self.assertNotEqual(parsed, self._declared_contexts())

    def test_parser_prefers_job_id_when_name_absent(self):
        # GitHub falls back to the job id when `name:` is absent; the parser
        # must too — here the fallback reproduces the same check name, so the
        # declared set still matches.
        variant = CI_YML.read_text().replace("    name: shellcheck\n", "", 1)
        self.assertNotEqual(variant, CI_YML.read_text())  # the replace landed
        parsed = self._parse_variant(variant)
        self.assertIn("shellcheck", parsed)  # falls back to the job id
        self.assertEqual(parsed, self._declared_contexts())

    def test_parser_raises_on_unreadable_shape(self):
        with self.assertRaises(ValueError):
            self._parse_variant("on: push\n")  # no `jobs:` key at all
        with self.assertRaises(ValueError):
            self._parse_variant("jobs:\n")  # `jobs:` with zero jobs


class TestNoSecretsInRulesets(unittest.TestCase):
    def test_no_token_like_values(self):
        for f in RULESETS.glob("*.json"):
            text = f.read_text().lower()
            for needle in ("bearer", "token", "ghp_", "github_pat_"):
                self.assertNotIn(needle, text, f"{f.name} must not carry credentials")


class TestApplyScript(unittest.TestCase):
    def run_script(self, *args, env_token=None):
        env = dict(os.environ)
        env.pop("GITHUB_TOKEN", None)
        if env_token is not None:
            env["GITHUB_TOKEN"] = env_token
        return subprocess.run(
            [str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=str(ROOT),
        )

    def test_dry_run_needs_no_token(self):
        p = self.run_script("--file", "deploy/rulesets/tag-protection-vstar.json")
        self.assertEqual(p.returncode, 0)
        self.assertIn("dry-run", p.stdout)
        self.assertIn("release-tag-protection", p.stdout)

    def test_dry_run_describes_refs_and_rules(self):
        p = self.run_script("--file", "deploy/rulesets/main-branch-protection.json")
        self.assertIn("refs/heads/main", p.stdout)
        self.assertIn("pull_request", p.stdout)

    def test_execute_without_token_refuses(self):
        p = self.run_script("--file", "deploy/rulesets/tag-protection-vstar.json",
                     "--execute", "--yes")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("GITHUB_TOKEN", p.stderr)

    def test_execute_requires_yes_even_with_token(self):
        # --execute without --yes must refuse BEFORE any network call.
        p = self.run_script("--file", "deploy/rulesets/tag-protection-vstar.json",
                            "--execute", env_token="ghp_faketoken1234567890")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("--execute needs --yes", p.stderr)
        self.assertNotIn("ghp_faketoken1234567890", p.stdout + p.stderr)

    def test_check_without_token_refuses(self):
        p = self.run_script("--file", "deploy/rulesets/tag-protection-vstar.json", "--check")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("GITHUB_TOKEN", p.stderr)

    def test_missing_file_flag_errors(self):
        p = self.run_script()
        self.assertNotEqual(p.returncode, 0)

    def test_nonexistent_file_errors(self):
        p = self.run_script("--file", "deploy/rulesets/nope.json")
        self.assertNotEqual(p.returncode, 0)

    def test_invalid_json_errors(self):
        bad = Path("/tmp/apply_rulesets_bad.json")
        bad.write_text("{not json")
        p = self.run_script("--file", str(bad))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("not valid JSON", p.stderr)

    def test_missing_name_errors(self):
        noname = Path("/tmp/apply_rulesets_noname.json")
        noname.write_text('{"foo": 1}')
        try:
            p = self.run_script("--file", str(noname))
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("no .name", p.stderr)
        finally:
            noname.unlink(missing_ok=True)

    def test_dry_run_never_prints_the_token(self):
        p = self.run_script("--file", "deploy/rulesets/tag-protection-vstar.json",
                     env_token="ghp_faketoken1234567890")
        self.assertEqual(p.returncode, 0)
        self.assertNotIn("ghp_faketoken1234567890", p.stdout)
        self.assertNotIn("ghp_faketoken1234567890", p.stderr)


class TestNormalizeFilter(unittest.TestCase):
    FILTER = ROOT / "scripts" / "ruleset-normalize.jq"

    def norm(self, doc):
        p = subprocess.run(
            ["jq", "-c", "-f", str(self.FILTER)],
            input=json.dumps(doc), capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_canonicalizes_live_envelope(self):
        # A canned "live" payload: reordered rules, shuffled keys, and API
        # envelope fields (id, source, _links) the declared file lacks.
        live = {
            "id": 12345,
            "source": {"type": "Repository"},
            "_links": {"self": {"href": "https://api.github.com/..."}},
            "name": "release-tag-protection",
            "enforcement": "active",
            "target": "tag",
            "conditions": {"ref_name": {"exclude": [], "include": ["refs/tags/v*"]}},
            "rules": [
                {"type": "deletion", "parameters": {}},
                {"type": "update", "parameters": {}},
            ],
        }
        self.assertEqual(self.norm(live), self.norm(load("tag-protection-vstar.json")))

    def test_detects_enforcement_drift(self):
        declared = load("tag-protection-vstar.json")
        mutated = json.loads(json.dumps(declared))
        mutated["enforcement"] = "disabled"
        self.assertNotEqual(self.norm(mutated), self.norm(declared))

    def test_detects_rule_drift(self):
        declared = load("tag-protection-vstar.json")
        mutated = json.loads(json.dumps(declared))
        mutated["rules"] = [r for r in mutated["rules"] if r["type"] != "deletion"]
        self.assertNotEqual(self.norm(mutated), self.norm(declared))

    def test_detects_bypass_drift(self):
        declared = load("tag-protection-vstar-strict.json")
        mutated = json.loads(json.dumps(declared))
        mutated["bypass_actors"] = []
        self.assertNotEqual(self.norm(mutated), self.norm(declared))


if __name__ == "__main__":
    unittest.main()

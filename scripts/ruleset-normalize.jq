# Canonical semantic form of a repository ruleset, for drift comparison.
#
# Used by scripts/apply-rulesets.sh (normalize()) and directly by
# scripts/test_apply_rulesets.py, so drift detection is covered offline.
# Compares only the fields the declared files control: API envelope fields
# (id, source, _links, ...) and rule ordering/key order are ignored.
{name, target, enforcement,
 bypass_actors: (.bypass_actors // []),
 conditions,
 rules: [.rules[] | {type, parameters: (.parameters // {})}] | sort_by(.type)}

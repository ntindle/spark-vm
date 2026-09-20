"""Hermetic tests for the bdrive fixed action protocol.

Covers bdrive/protocol.py (action vocabulary, call validation, receipt
semantics, ref_scope lifecycle, the post-navigation rule),
bdrive/observation.py (AX observation schema + history redaction), and
bdrive/config.py (deployment config, env overrides, fail-loud values).

Stdlib + pytest only. No browser, no socket, no network.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# NOTE: sys.path is restored by the autouse fixture below so the
# full-repo one-liner keeps its import isolation (CONTRIBUTING.md).


@pytest.fixture(autouse=True)
def _restore_sys_path():
    # NOTE: the module-level sys.path insert above runs at import time,
    # before any fixture, so `before` already contains the
    # browser-driver entry — this restores sys.path to that import-time
    # state after each test (it does not remove the entry) and drops
    # any bdrive.* modules imported *during* a test. Net effect: no
    # test leaves import state behind for the full-repo one-liner
    # (CONTRIBUTING.md).
    before = list(sys.path)
    before_modules = set(sys.modules)
    yield
    sys.path[:] = before
    for name in [n for n in sys.modules if n not in before_modules]:
        if name == "bdrive" or name.startswith("bdrive."):
            del sys.modules[name]


from bdrive import protocol as P  # noqa: E402
from bdrive import observation as O  # noqa: E402
from bdrive import config as C  # noqa: E402


def call(actions, session="s1", ref_scope="tok", **extra):
    payload = {"session": session, "ref_scope": ref_scope, "actions": actions}
    payload.update(extra)
    return payload


def expect_code(payload, code, scope=None):
    with pytest.raises(P.ProtocolError) as exc:
        P.validate_call(payload, scope=scope)
    assert exc.value.code == code, "got %r: %s" % (exc.value.code, exc.value)


# ---------------------------------------------------------------------------
# Vocabulary: unknown actions are rejected, not interpreted
# ---------------------------------------------------------------------------


def test_unknown_action_rejected():
    expect_code(call([{"action": "eval", "script": "1"}]), "unknown_action")


def test_action_name_is_case_sensitive():
    expect_code(call([{"action": "Click", "ref": "@e1"}]), "unknown_action")


def test_empty_actions_rejected():
    expect_code(call([]), "bad_envelope")


def test_missing_session_rejected():
    payload = {"actions": [{"action": "snapshot"}]}
    expect_code(payload, "bad_envelope")


def test_non_object_call_rejected():
    expect_code(["not", "a", "dict"], "bad_envelope")


def test_unknown_parameter_rejected_not_ignored():
    # A misspelled parameter must fail loud, never be silently dropped.
    expect_code(
        call([{"action": "click", "ref": "@e1", "reff": "@e1"}]), "bad_params"
    )


def test_all_spec_actions_accepted():
    # goto sits last: the post-navigation rule forbids tree actions
    # after a navigation inside the same array. snapshot is excluded:
    # SPEC §4 forbids combining it with other actions (tested alone).
    actions = [
        {"action": "open"},
        {"action": "back"},
        {"action": "forward"},
        {"action": "reload"},
        {"action": "state"},
        {"action": "click", "ref": "@e1"},
        {"action": "fill", "ref": "@e2", "text": "hi"},
        {"action": "type", "ref": "@e2", "text": "hi"},
        {"action": "press", "key": "Enter"},
        {"action": "select", "ref": "@e3", "value": "x"},
        {"action": "check", "ref": "@e4"},
        {"action": "look"},
        {"action": "get_text"},
        {"action": "wait", "time_ms": 500},
        {"action": "cookies_clear"},
        {"action": "hover", "ref": "@e5"},
        {"action": "scroll", "direction": "down"},
        {"action": "uncheck", "ref": "@e6"},
        {"action": "focus", "ref": "@e7"},
        {"action": "get_html"},
        {"action": "get_attr", "ref": "@e8", "attribute": "href"},
        {"action": "get_value", "ref": "@e9"},
        {"action": "gesture", "instruction": "draw", "gesture": "circle"},
        {"action": "upload", "ref": "@e10", "grant_ids": ["g1"]},
        {"action": "download", "ref": "@e11"},
        {"action": "pdf"},
        {"action": "fill_card", "job": "job-1"},
        {"action": "goto", "url": "https://example.com"},
    ]
    scope = P.RefScope()
    token = scope.rotate()
    validated = P.validate_call(call(actions, ref_scope=token), scope=scope)
    assert [a.name for a in validated.actions] == [a["action"] for a in actions]
    # A lone snapshot is valid on its own, no ref_scope needed.
    P.validate_call(call([{"action": "snapshot"}], ref_scope=None))


def test_action_stage_split_matches_spec():
    v1 = {a for a in P.ACTION_NAMES if P.action_stage(a) == "v1"}
    assert v1 == {
        "open", "goto", "back", "forward", "reload", "state", "click",
        "fill", "type", "press", "select", "check", "snapshot", "look",
        "get_text", "wait", "cookies_clear",
    }
    assert len(P.ACTION_NAMES) == 29


# ---------------------------------------------------------------------------
# goto: http/https only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "file:///etc/passwd",
    "data:text/html,<h1>x</h1>",
    "ftp://example.com/x",
])
def test_goto_scheme_policy(url):
    expect_code(call([{"action": "goto", "url": url}]), "bad_goto_scheme")


def test_goto_scheme_case_insensitive():
    P.validate_call(call([{"action": "goto", "url": "HTTPS://example.com"}]))


def test_goto_missing_url():
    expect_code(call([{"action": "goto"}]), "bad_params")


def test_goto_hsurr_query_allowed():
    # Placeholders may appear in the query; the proxy swaps on egress.
    P.validate_call(
        call([{"action": "goto",
               "url": "https://example.com/login?tok=hsurr:acme"}])
    )


# ---------------------------------------------------------------------------
# Parameter validation per action
# ---------------------------------------------------------------------------


def test_click_kind_enum():
    P.validate_call(call([{"action": "click", "ref": "@e1", "kind": "double"}]))
    expect_code(
        call([{"action": "click", "ref": "@e1", "kind": "middle"}]), "bad_params"
    )


def test_ref_format():
    for bad in ("e1", "@e", "@1", "@E1", "@e1x", "", "@ e1"):
        expect_code(call([{"action": "click", "ref": bad}]), "bad_params")


def test_fill_text_must_be_string():
    expect_code(call([{"action": "fill", "ref": "@e1"}]), "bad_params")
    expect_code(
        call([{"action": "fill", "ref": "@e1", "text": 42}]), "bad_params"
    )


def test_press_key_required():
    expect_code(call([{"action": "press"}]), "bad_params")
    P.validate_call(call([{"action": "press", "key": "Shift+Tab"}]))


def test_wait_exactly_one_of():
    expect_code(call([{"action": "wait"}]), "bad_params")
    expect_code(
        call([{"action": "wait", "text": "x", "time_ms": 5}]), "bad_params"
    )
    expect_code(
        call([{"action": "wait", "time_ms": 0}]), "bad_params"
    )
    P.validate_call(call([{"action": "wait", "text": "Ready"}]))
    P.validate_call(call([{"action": "wait", "text_gone": "Loading"}]))
    P.validate_call(call([{"action": "wait", "time_ms": 1500}]))


def test_upload_grant_ids():
    expect_code(
        call([{"action": "upload", "ref": "@e1", "grant_ids": []}]), "bad_params"
    )
    expect_code(
        call([{"action": "upload", "ref": "@e1"}]), "bad_params"
    )
    P.validate_call(
        call([{"action": "upload", "ref": "@e1", "grant_ids": ["g1", "g2"]}])
    )


def test_gesture_params():
    expect_code(call([{"action": "gesture", "gesture": "circle"}]), "bad_params")
    expect_code(
        call([{"action": "gesture", "instruction": "i",
               "gesture": "circle", "max_points": 0}]),
        "bad_params",
    )
    P.validate_call(call([{"action": "gesture", "instruction": "i",
                           "gesture": "circle", "click_hold_ms": 400}]))


def test_timeout_ms_bounds():
    P.validate_call(call([{"action": "snapshot", "timeout_ms": 15000}]))
    expect_code(call([{"action": "snapshot", "timeout_ms": 0}]), "bad_params")
    expect_code(call([{"action": "snapshot", "timeout_ms": -5}]), "bad_params")
    expect_code(
        call([{"action": "snapshot", "timeout_ms": 300_001}]), "bad_params"
    )
    expect_code(
        call([{"action": "snapshot", "timeout_ms": "15"}]), "bad_params"
    )


def test_fill_card_needs_job_not_values():
    expect_code(call([{"action": "fill_card"}]), "bad_params")
    # …and it must never accept a value payload, by design.
    expect_code(
        call([{"action": "fill_card", "job": "j1", "number": "4111"}]),
        "bad_params",
    )
    P.validate_call(call([{"action": "fill_card", "job": "j1"}]))


# ---------------------------------------------------------------------------
# ref_scope lifecycle
# ---------------------------------------------------------------------------


def test_ref_action_without_scope_rejected():
    expect_code(
        call([{"action": "click", "ref": "@e1"}], ref_scope=None),
        "missing_ref_scope",
        scope=P.RefScope(),
    )


def test_snapshot_never_combined_with_actions():
    # SPEC §4: snapshot is an observation-only call, never combined
    # with actions in the same array.
    expect_code(
        call([{"action": "snapshot"}, {"action": "state"}]),
        "snapshot_not_alone",
    )
    expect_code(
        call([
            {"action": "goto", "url": "https://example.com"},
            {"action": "snapshot"},
        ]),
        "snapshot_not_alone",
    )
    # A lone snapshot is a valid observation-only call, no ref_scope.
    P.validate_call(
        call([{"action": "snapshot"}], ref_scope=None),
        scope=P.RefScope(),
    )


def test_stale_scope_rejected():
    scope = P.RefScope()
    old = scope.rotate()
    scope.rotate()  # a newer observation arrived
    expect_code(
        call([{"action": "click", "ref": "@e1"}], ref_scope=old),
        "stale_ref_scope",
        scope=scope,
    )


def test_live_scope_accepted():
    scope = P.RefScope()
    token = scope.rotate()
    validated = P.validate_call(
        call([{"action": "click", "ref": "@e1"}], ref_scope=token),
        scope=scope,
    )
    assert validated.ref_scope == token


def test_scope_tokens_are_unguessable_and_unique():
    scope = P.RefScope()
    tokens = {scope.rotate() for _ in range(50)}
    assert len(tokens) == 50
    assert all(t.startswith("rs_") for t in tokens)


def test_scope_accepts_rejects_non_strings():
    scope = P.RefScope()
    scope.rotate()
    assert not scope.accepts(None)
    assert not scope.accepts(42)
    assert not scope.accepts("")


# ---------------------------------------------------------------------------
# Post-navigation rule (SPEC §4)
# ---------------------------------------------------------------------------


def test_post_navigation_allows_exact_text_wait():
    P.validate_call(call([
        {"action": "goto", "url": "https://example.com"},
        {"action": "wait", "text": "Welcome"},
    ]))


def test_post_navigation_allows_ref_free_observations():
    P.validate_call(call([
        {"action": "goto", "url": "https://example.com"},
        {"action": "look"},
        {"action": "get_text"},
        {"action": "get_html"},
        {"action": "state"},
    ]))


@pytest.mark.parametrize("later", [
    {"action": "click", "ref": "@e1"},
    # {"action": "snapshot"} has its own stricter rule (snapshot_not_alone)
    {"action": "wait", "time_ms": 500},
    {"action": "wait", "text_gone": "Loading"},
    {"action": "get_text", "ref": "@e1"},
    {"action": "fill", "ref": "@e1", "text": "x"},
])
def test_post_navigation_rejects_stale_tree_use(later):
    scope = P.RefScope()
    token = scope.rotate()
    expect_code(
        call([
            {"action": "goto", "url": "https://example.com"},
            later,
        ], ref_scope=token),
        "post_navigation_violation",
        scope=scope,
    )


def test_second_goto_in_same_array_rejected():
    # The post-navigation rule is strict: after a goto, only an
    # exact-text wait or ref-free look/get_text/get_html/state may
    # follow — a second navigation must be its own call (each call ends
    # with a terminal observation anyway, SPEC §4).
    expect_code(call([
        {"action": "goto", "url": "https://example.com"},
        {"action": "look"},
        {"action": "goto", "url": "https://example.org"},
    ]), "post_navigation_violation")


def test_no_navigation_no_restriction():
    scope = P.RefScope()
    token = scope.rotate()
    P.validate_call(call([
        {"action": "click", "ref": "@e1"},
        {"action": "wait", "time_ms": 100},
    ], ref_scope=token), scope=scope)


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


def test_receipt_statuses():
    for status in ("completed", "unknown", "not_started"):
        r = P.ActionReceipt(action="click", status=status)
        assert r.to_dict()["status"] == status


def test_receipt_reason_only_on_not_started():
    P.ActionReceipt(action="click", status="not_started",
                    actionability_reason="obscured")
    with pytest.raises(P.ProtocolError):
        P.ActionReceipt(action="click", status="completed",
                        actionability_reason="obscured")
    with pytest.raises(P.ProtocolError):
        P.ActionReceipt(action="click", status="unknown",
                        actionability_reason="timeout")


def test_receipt_unknown_reason_rejected():
    with pytest.raises(P.ProtocolError):
        P.ActionReceipt(action="click", status="not_started",
                        actionability_reason="sleepy")


def test_receipt_reasons_cover_spec_set():
    assert set(P.ACTIONABILITY_REASONS) == {
        "not_visible", "obscured", "disabled", "not_editable",
        "not_hittable", "unstable", "timeout",
    }


def test_call_result_round_trip():
    result = P.CallResult(
        session="s1",
        receipts=[P.ActionReceipt("goto", "completed"),
                  P.ActionReceipt("click", "not_started",
                                  actionability_reason="disabled")],
        observation=None,
        stopped_at=1,
    )
    d = result.to_dict()
    assert d["stopped_at"] == 1
    assert d["receipts"][1]["actionability_reason"] == "disabled"


# ---------------------------------------------------------------------------
# Observation schema
# ---------------------------------------------------------------------------


def _node(ref="@e1", **kw):
    node = {"ref": ref, "role": "button", "name": "OK",
            "enabled": True, "visible": True}
    node.update(kw)
    return node


def test_observation_round_trip():
    obs = O.build_observation(
        "https://example.com", "Example", "target-1", "rs_1_abc",
        [_node(), _node(ref="@e2", children=[_node(ref="@e3")])],
    )
    O.validate_observation(obs)
    assert obs["ax"][1]["children"][0]["ref"] == "@e3"


def test_observation_rejects_bad_node():
    with pytest.raises(P.ProtocolError):
        O.build_observation("https://x", "t", "tgt", "rs", [_node(ref="e1")])
    with pytest.raises(P.ProtocolError):
        O.build_observation("https://x", "t", "tgt", "rs",
                            [_node(enabled="yes")])


def test_observation_rejects_unknown_fields():
    with pytest.raises(P.ProtocolError):
        O.build_observation("https://x", "t", "tgt", "rs",
                            [_node(extra="nope")])


def test_redact_for_history_drops_tree_keeps_envelope():
    obs = O.build_observation(
        "https://example.com", "Example", "target-1", "rs_1_abc",
        [_node(), _node(ref="@e2", children=[_node(ref="@e3")])],
    )
    red = O.redact_for_history(obs)
    assert red["ax_redacted"] is True
    assert red["ax_node_count"] == 3
    assert "ax" not in red
    assert red["url"] == "https://example.com"
    assert red["ref_scope"] == "rs_1_abc"


# ---------------------------------------------------------------------------
# Config: deployment facts, env-overridable, fail loud
# ---------------------------------------------------------------------------


def test_config_defaults_match_spec():
    cfg = C.load_config(env={})
    assert cfg.socket_path == "/run/bdrive/bdrive.sock"
    assert cfg.profile_dir == "/home/bdrive/profile"
    assert cfg.proxy_url == "http://127.0.0.1:18080"
    assert cfg.session_ttl_s == 1800
    assert cfg.service_user == "bdrive"
    assert cfg.client_group == "bdrive-clients"


def test_config_env_overrides():
    cfg = C.load_config(env={
        "BDRIVE_PROXY_URL": "http://proxy.internal:18080",
        "BDRIVE_SOCKET": "/tmp/test-bdrive.sock",
        "BDRIVE_SESSION_TTL_S": "600",
    })
    assert cfg.proxy_url == "http://proxy.internal:18080"
    assert cfg.socket_path == "/tmp/test-bdrive.sock"
    assert cfg.session_ttl_s == 600


def test_config_rejects_bad_values():
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_SOCKET": "relative/path.sock"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_PROXY_URL": "gopher://x"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_SESSION_TTL_S": "0"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_SESSION_TTL_S": "soon"})


def test_config_reads_real_environment(monkeypatch):
    monkeypatch.setenv("BDRIVE_LOOK_MAX_BYTES", "42")
    cfg = C.load_config()
    assert cfg.look_max_bytes == 42


# ---------------------------------------------------------------------------
# Round-2 fixes: adversarial-review blockers (Product/QA/Security/Eng)
# ---------------------------------------------------------------------------


def test_non_string_action_names_rejected_as_protocol_error():
    # A daemon catching only ProtocolError must see a clean rejection,
    # never a raw TypeError, for attacker-controlled names.
    for bad in (["click"], {"$ne": 1}, None, 42, ("click",)):
        expect_code(call([{"action": bad, "ref": "@e1"}]), "unknown_action")
    for fn in (P.action_stage, P.action_needs_ref, P.is_observation_only):
        with pytest.raises(P.ProtocolError) as exc:
            fn(["click"])
        assert exc.value.code == "unknown_action"
        with pytest.raises(P.ProtocolError):
            fn("no_such_action")


def test_ref_with_trailing_newline_rejected():
    expect_code(
        call([{"action": "click", "ref": "@e1\n"}]), "bad_params"
    )


def test_optional_ref_actions_need_live_scope():
    # press/scroll/get_text/get_html take an optional ref; when they
    # carry one, the ref_scope token is required and must be live —
    # the confused-deputy hole is closed on optional refs too.
    scope = P.RefScope()
    stale = scope.rotate()
    live = scope.rotate()  # a newer observation arrived; `stale` is dead
    for action in (
        {"action": "press", "key": "Enter", "ref": "@e9"},
        {"action": "scroll", "ref": "@e9"},
        {"action": "get_text", "ref": "@e9"},
        {"action": "get_html", "ref": "@e9"},
    ):
        expect_code(
            call([action], ref_scope=None), "missing_ref_scope", scope=scope
        )
        expect_code(
            call([action], ref_scope=""), "missing_ref_scope", scope=scope
        )
        expect_code(
            call([action], ref_scope=stale), "stale_ref_scope", scope=scope
        )
        P.validate_call(call([action], ref_scope=live), scope=scope)


def test_optional_ref_actions_without_ref_need_no_scope():
    for action in (
        {"action": "press", "key": "Enter"},
        {"action": "scroll", "direction": "down"},
        {"action": "get_text"},
        {"action": "get_html"},
    ):
        P.validate_call(call([action], ref_scope=None))


def test_durations_capped_at_max_timeout():
    expect_code(
        call([{"action": "wait", "time_ms": 10 ** 15}]), "timeout_too_large"
    )
    expect_code(
        call([{
            "action": "gesture", "instruction": "draw",
            "gesture": "circle", "click_hold_ms": 10 ** 15,
        }]),
        "timeout_too_large",
    )
    # At the cap is fine.
    P.validate_call(call([{"action": "wait", "time_ms": P.MAX_TIMEOUT_MS}]))


def test_actions_array_capped():
    expect_code(
        call([{"action": "state"}] * (P.MAX_ACTIONS_PER_CALL + 1)),
        "too_many_actions",
    )
    P.validate_call(call([{"action": "state"}] * P.MAX_ACTIONS_PER_CALL))


def test_wait_text_must_be_non_empty():
    expect_code(call([{"action": "wait", "text": ""}]), "bad_params")
    expect_code(call([{"action": "wait", "text_gone": ""}]), "bad_params")
    expect_code(call([{"action": "wait", "text": 42}]), "bad_params")


def test_goto_requires_scheme():
    expect_code(call([{"action": "goto", "url": "http"}]), "bad_goto_scheme")
    expect_code(call([{"action": "goto", "url": "example.com"}]),
                "bad_goto_scheme")


def test_param_key_table_covers_vocabulary():
    assert set(P._ACTION_KEYS) == set(P.ACTION_NAMES)


def test_validated_params_are_frozen():
    validated = P.validate_call(call([
        {"action": "fill", "ref": "@e1", "text": "secret"},
        {"action": "upload", "ref": "@e2", "grant_ids": ["g1"]},
    ], ref_scope="tok"))
    fill, upload = validated.actions
    with pytest.raises(TypeError):
        fill.params["text"] = "MUTATED"
    with pytest.raises(TypeError):
        upload.params["grant_ids"] = []
    assert isinstance(upload.params["grant_ids"], tuple)
    # Nested values are detached from the caller's payload.
    payload = call([{"action": "upload", "ref": "@e2", "grant_ids": ["g1"]}])
    before = P.validate_call(payload, scope=None)
    payload["actions"][0]["grant_ids"].append("gX")
    assert before.actions[0].params["grant_ids"] == ("g1",)


def test_redacted_params_hide_field_contents():
    validated = P.validate_call(call([
        {"action": "fill", "ref": "@e1", "text": "p@ssw0rd"},
        {"action": "click", "ref": "@e2"},
        {"action": "upload", "ref": "@e3", "grant_ids": ["g1"]},
        {"action": "goto", "url": "https://x.test/?token=abc"},
    ], ref_scope="tok"))
    fill, click, upload, goto = validated.actions
    assert fill.redacted_params() == {"ref": "@e1", "text": "<redacted>"}
    assert goto.redacted_params() == {"url": "<redacted>"}
    assert click.redacted_params() == {"ref": "@e2"}
    assert upload.redacted_params() == {"ref": "@e3", "grant_ids": ["g1"]}


def test_timeout_ms_edge_values_rejected():
    expect_code(
        call([{"action": "snapshot", "timeout_ms": False}]), "bad_params"
    )
    expect_code(
        call([{"action": "snapshot", "timeout_ms": None}]), "bad_params"
    )


def test_non_dict_action_objects_rejected():
    expect_code(call(["click"]), "bad_params")
    expect_code(call([None]), "bad_params")


def test_scroll_param_validation():
    expect_code(
        call([{"action": "scroll", "direction": "sideways"}]), "bad_params"
    )
    expect_code(call([{"action": "scroll", "pixels": 0}]), "bad_params")
    expect_code(call([{"action": "scroll", "pixels": -10}]), "bad_params")
    P.validate_call(call([{"action": "scroll", "pixels": 400,
                           "direction": "down"}]))


def test_upload_rejects_empty_grant_id():
    expect_code(
        call([{"action": "upload", "ref": "@e1", "grant_ids": ["g1", ""]}]),
        "bad_params",
    )


def test_select_get_attr_press_param_edges():
    expect_code(
        call([{"action": "select", "ref": "@e1", "value": 42}]), "bad_params"
    )
    expect_code(
        call([{"action": "get_attr", "ref": "@e1", "attribute": ""}]),
        "bad_params",
    )
    expect_code(
        call([{"action": "press", "key": "Enter", "ref": "@nope"}]),
        "bad_params",
    )


def test_bad_receipt_status_rejected():
    with pytest.raises(P.ProtocolError) as exc:
        P.ActionReceipt(action="click", status="bogus")
    assert exc.value.code == "bad_receipt"


def test_call_result_to_dict_with_observation():
    result = P.CallResult(
        session="s1",
        receipts=[P.ActionReceipt(action="goto", status="completed")],
        observation={"url": "https://example.com"},
        stopped_at=None,
    )
    out = result.to_dict()
    assert out["observation"] == {"url": "https://example.com"}
    assert out["receipts"] == [{"action": "goto", "status": "completed"}]


def test_validated_action_timeout_defaults_to_zero():
    validated = P.validate_call(call([{"action": "snapshot"}], ref_scope=None))
    assert validated.actions[0].timeout_ms == 0


def test_config_empty_values_fail_loud():
    # A present-but-empty value must fail loud, never silently fall
    # back to the default (that would deploy under different settings
    # than the operator set).
    for key in ("BDRIVE_SOCKET", "BDRIVE_PROFILE_DIR", "BDRIVE_JOB_BASE_DIR",
                "BDRIVE_PROXY_URL", "BDRIVE_SESSION_TTL_S",
                "BDRIVE_LOOK_MAX_BYTES", "BDRIVE_USER", "BDRIVE_CLIENT_GROUP"):
        with pytest.raises(C.ConfigError):
            C.load_config(env={key: ""})


def test_config_rejects_non_string_values():
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_SOCKET": 8080})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_PROXY_URL": None})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_SESSION_TTL_S": True})


def test_config_defaults_win_when_env_unset(monkeypatch):
    for key in ("BDRIVE_SOCKET", "BDRIVE_PROFILE_DIR", "BDRIVE_PROXY_URL",
                "BDRIVE_JOB_BASE_DIR", "BDRIVE_SESSION_TTL_S",
                "BDRIVE_LOOK_MAX_BYTES", "BDRIVE_USER", "BDRIVE_CLIENT_GROUP"):
        monkeypatch.delenv(key, raising=False)
    cfg = C.load_config()
    assert cfg.socket_path == "/run/bdrive/bdrive.sock"
    assert cfg.proxy_url == "http://127.0.0.1:18080"
    assert cfg.session_ttl_s == 1800
    assert cfg.service_user == "bdrive"
    assert cfg.client_group == "bdrive-clients"


def test_observation_frame_edges():
    def obs(**kw):
        base = {
            "url": "https://example.com",
            "title": "T",
            "target": "doc-1",
            "ref_scope": "rs_1_abc",
            "ax": [{"ref": "@e1", "role": "button", "name": "OK",
                    "visible": True, "enabled": True}],
        }
        base.update(kw)
        return base

    node = {"ref": "@e1", "role": "button", "name": "OK",
            "visible": True, "enabled": True, "frame": "main"}
    O.validate_observation(obs(ax=[node]))
    with pytest.raises(O.ProtocolError):
        O.validate_observation(obs(ax=[dict(node, frame="")]))


# ---------------------------------------------------------------------------
# Round-3 fixes: security re-review blockers (B1–B5)
# ---------------------------------------------------------------------------


def test_non_ascii_ref_scope_rejected_as_protocol_error():
    # B1: hmac.compare_digest raises TypeError on non-ASCII str; the
    # module's fail-closed contract demands ProtocolError instead — the
    # exact path a compromised orchestrator would fuzz.
    scope = P.RefScope()
    scope.rotate()
    assert not scope.accepts("rs_\U0001F600evil")
    with pytest.raises(P.ProtocolError) as exc:
        P.validate_call(
            call([{"action": "click", "ref": "@e1"}],
                 ref_scope="rs_\U0001F600evil"),
            scope=scope,
        )
    assert exc.value.code == "stale_ref_scope"


def _deep_tree(depth):
    node = {"ref": "@e1", "role": "button", "name": "x",
            "enabled": True, "visible": True}
    root = node
    for _ in range(depth):
        child = {"ref": "@e1", "role": "button", "name": "x",
                 "enabled": True, "visible": True}
        node["children"] = [child]
        node = child
    return [root]


def test_deeply_nested_ax_tree_rejected_as_protocol_error():
    # B2: the AX tree is page-derived (attacker-controlled); a hostile
    # page must not crash the daemon with RecursionError.
    obs = {"url": "https://x", "title": "t", "target": "tgt",
           "ref_scope": "rs", "ax": _deep_tree(2000)}
    with pytest.raises(P.ProtocolError) as exc:
        O.validate_observation(obs)
    assert exc.value.code == "bad_observation"
    # A deep-but-legal tree still validates and redacts without recursion.
    red = O.redact_for_history(
        {"url": "https://x", "title": "t", "target": "tgt",
         "ref_scope": "rs", "ax": _deep_tree(500)})
    assert red["ax_node_count"] == 501


def test_call_duration_budget():
    # B3: 256 x 300s waits must not validate (a 21.3h serial wedge).
    scope = P.RefScope()
    token = scope.rotate()
    with pytest.raises(P.ProtocolError) as exc:
        P.validate_call(
            call([{"action": "wait", "time_ms": 300_000}] * 256,
                 ref_scope=token),
            scope=scope,
        )
    assert exc.value.code == "call_budget_exceeded"
    # At the budget (2 x 300s) is fine.
    P.validate_call(
        call([{"action": "wait", "time_ms": 300_000}] * 2,
             ref_scope=token),
        scope=scope,
    )


def test_param_length_cap():
    # B4: giant string params fail loud — and the rejection must not
    # echo the giant value into the error/log line.
    big = "x" * (P.MAX_PARAM_LEN + 1)
    with pytest.raises(P.ProtocolError) as exc:
        P.validate_call(call([{"action": "goto", "url": "https://x/" + big}]))
    assert exc.value.code == "bad_params"
    assert big not in str(exc.value)
    # Exactly at the cap is fine.
    P.validate_call(call([{"action": "goto",
                           "url": "https://x/" + "u" * (P.MAX_PARAM_LEN - 10)}]))


def test_grant_ids_count_cap():
    # B4: unbounded grant_ids is a memory DoS from one call.
    with pytest.raises(P.ProtocolError) as exc:
        P.validate_call(call([{"action": "upload", "ref": "@e1",
                               "grant_ids": ["g%d" % i
                                             for i in
                                             range(P.MAX_GRANT_IDS + 1)]}]))
    assert exc.value.code == "bad_params"
    P.validate_call(call([{"action": "upload", "ref": "@e1",
                           "grant_ids": ["g%d" % i
                                         for i in range(P.MAX_GRANT_IDS)]}]))


def test_redacted_params_cover_wait_and_gesture():
    # B5: wait.text/text_gone and gesture.instruction are page/operator
    # text and must be redacted from logs like any other field contents.
    validated = P.validate_call(call([
        {"action": "wait", "text": "Account balance: $12,345.67"},
        {"action": "wait", "text_gone": "Loading secrets"},
        {"action": "gesture", "instruction": "circle the SSN field",
         "gesture": "circle"},
    ], ref_scope="tok"))
    wait_text, wait_gone, gesture = validated.actions
    assert wait_text.redacted_params() == {"text": "<redacted>"}
    assert wait_gone.redacted_params() == {"text_gone": "<redacted>"}
    assert gesture.redacted_params()["instruction"] == "<redacted>"
    assert gesture.redacted_params()["gesture"] == "circle"

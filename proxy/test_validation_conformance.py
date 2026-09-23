"""Conformance test for the credential-validation grammars (#150).

The credential-name, allowed-host, and placement grammars are replicated
in four WRITE-path places: the `cred` CLI, `cred-ui/cred-ui.py`,
`proxy/cred-registry-set`, and `credlib` (NAME_RE). They must
accept/reject the same corpus — drift here is a security-relevant
inconsistency (the frontend accepting what the writer rejects, or vice
versa), and drift had already happened: the CLI and writer accepted
unbounded names and hosts and unbounded placement args while cred-ui capped
them, and the CLI/writer accepted `_`/`.` in custom header names while
cred-ui rejected them.

A fifth copy lives in `proxy/swap_addon.py` (NAME_RE): the proxy's READ
side, which filters which on-disk secret files get loaded into the
served-secrets map. It is intentionally a SUPERSET of the contract
(unbounded `[A-Za-z0-9_-]+`) — strict-on-write / liberal-on-read, so
secrets written before the 64-char cap keep being served after upgrade.
This test asserts the superset relationship for accepts and deliberately
does NOT assert it for rejects.

Canonical contract (every write-path implementation below agrees on it):
- name / entry:  ^[A-Za-z0-9_-]{1,64}$
- host:          ^\\.?[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*$, total length <= 253,
                 each dot-separated label <= 63 chars
- placement:     bearer_header | url_path_segment |
                 custom_header:<arg> | query_param:<arg>,
                 with arg ^[A-Za-z0-9_.-]{1,64}$; the bare kinds take no arg.

Deliberate carve-out (upgrade path): the writer's pure-management verbs
(`remove`, `add-host`/`remove-host`, method/path limit verbs,
`set-scrub`) use a legacy-tolerant charset-only name/host check, so
pre-existing over-long names/bindings stay manageable without
hand-editing the registry as root. CREATION (`set`, new `add-host`
bindings) always enforces the canonical contract. Legacy names remain
servable; to fully re-register a legacy credential, `remove` it and
re-create under a canonical name.

Each implementation is driven through its natural interface:
- `cred` CLI: check_name / check_host / parse_placement
  (CredentialError = reject)
- cred-ui: NAME_RE / host_ok / placement_json (False / ValueError = reject)
- writer: real `cred-registry-set` subprocesses against a temp
  registry file (CRED_REGISTRY_FILE/CRED_REGISTRY_LOCK overrides);
  non-zero exit = reject. The corpus uses the `set`/`add-host` creation
  paths, which enforce the canonical contract.
- credlib: NAME_RE (name grammar only; it is the fourth copy the issue names)
- swap_addon: NAME_RE (read-side superset, accepts-only assertion)

Known boundary (documented, not a divergence): the writer also accepts the
dict form {"url_path_segment": <name>}, which the swap addon honors
(area == "path", target ignored) but neither the CLI nor cred-ui can
produce. It is outside the shared user-facing corpus by construction.

Second known boundary: at the raw-function level, ("bearer_header", "")
diverges — cred-ui's placement_json treats "" as absent (accepts), while
the CLI ("bearer_header:" spec) and the writer ({"bearer_header": ""})
reject. End-to-end this is unreachable: the UI serializes bare kinds
without an arg (and clears the arg field when a bare kind is selected),
so the writer never sees the divergent form.

This test is the executable contract, not a shared module, because the
components deploy as separate artifacts into different privilege domains
(userland `cred`, the cred-ui service, the root-owned 0755 sudo writer)
— a shared import would need a fourth cross-domain artifact with
atomic-update requirements, where skew fails silently instead of failing
loudly in CI. #150's preferred end-state (a shared module) remains open;
until then, this test is the thing that must stay green.

Non-string inputs are out of scope for the corpus (cred-ui's host_ok
fail-closes on them; the CLI/writer assume strings — #118 class).

Run from the repo root:  python3 -m pytest proxy/test_validation_conformance.py -q
"""

import importlib.util
import json
import os
import subprocess
from importlib.machinery import SourceFileLoader

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLI_PATH = os.path.join(REPO, "cred")
UI_PATH = os.path.join(REPO, "cred-ui", "cred-ui.py")
WRITER_PATH = os.path.join(REPO, "proxy", "cred-registry-set")
CREDLIB_PATH = os.path.join(REPO, "credlib", "dynamic_credentials.py")
SWAP_ADDON_PATH = os.path.join(REPO, "proxy", "swap_addon.py")


def _load_cli():
    # `cred` has no .py extension, so spec_from_file_location cannot pick a
    # loader — name one explicitly.
    loader = SourceFileLoader("cred_cli", CLI_PATH)
    spec = importlib.util.spec_from_loader("cred_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_ui():
    # Same exec-with-fake-__file__ pattern as cred-ui/tests/test_cred_ui_http.py:
    # cred-ui.py only binds its server under __main__, so importing is safe.
    spec = importlib.util.spec_from_loader("credui_conformance", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = UI_PATH
    src = open(UI_PATH, encoding="utf-8").read()
    exec(compile(src, UI_PATH, "exec"), mod.__dict__)
    return mod


def _load_credlib():
    spec = importlib.util.spec_from_file_location("credlib_conformance",
                                                  CREDLIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_swap_addon():
    # swap_addon.py is stdlib-only at import time (no mitmproxy import at
    # module level), so it loads safely here.
    spec = importlib.util.spec_from_file_location("swapaddon_conformance",
                                                  SWAP_ADDON_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()
ui = _load_ui()
credlib = _load_credlib()
swap_addon = _load_swap_addon()


@pytest.fixture()
def registry(tmp_path):
    """A hermetic writer target: the writer honors CRED_REGISTRY_FILE and
    CRED_REGISTRY_LOCK overrides, so no sudo, swapd, or real store is touched."""
    reg = tmp_path / "credentials.json"
    lock = tmp_path / "credentials.json.lock"
    env = dict(os.environ,
               CRED_REGISTRY_FILE=str(reg),
               CRED_REGISTRY_LOCK=str(lock))
    return env


def _writer(args, env):
    p = subprocess.run(["bash", WRITER_PATH] + args,
                       env=env, capture_output=True, timeout=30)
    return p.returncode == 0


# --- accept/reject probes, one per implementation ---------------------------

def _cli_name(name):
    try:
        cli.check_name(name)
        return True
    except cli.CredentialError:
        return False


def _ui_name(name):
    return bool(ui.NAME_RE.match(name))


def _credlib_name(name):
    return bool(credlib.NAME_RE.match(name))


def _writer_name(name, env):
    # `set` validates name, entry, and placement; entry/placement are fixed
    # valid so the verdict isolates the name grammar.
    return _writer(["set", name, "access_token", '"bearer_header"'], env)


def _cli_host(host):
    try:
        cli.check_host(host)
        return True
    except cli.CredentialError:
        return False


def _ui_host(host):
    return bool(ui.host_ok(host))


def _writer_host(host, env):
    return _writer(["add-host", "probehost", host], env)


def _cli_placement(kind, value):
    spec = kind if value is None else "%s:%s" % (kind, value)
    try:
        cli.parse_placement(spec)
        return True
    except cli.CredentialError:
        return False


def _ui_placement(kind, value):
    try:
        ui.placement_json(kind, value if value is not None else "")
        return True
    except ValueError:
        return False


def _writer_placement(kind, value, env):
    # The writer consumes the already-serialized placement JSON, exactly as
    # the CLI (json.dumps of parse_placement's result) and cred-ui
    # (placement_json) produce it.
    pjson = json.dumps(kind if value is None else {kind: value})
    return _writer(["set", "probeplacement", "access_token", pjson], env)


# --- corpora ----------------------------------------------------------------

NAME_CASES = [
    # (value, expect_accept)
    ("github", True),
    ("a", True),
    ("A-9_z", True),
    ("under_score-9", True),
    ("-leading", True),          # charset allows it everywhere (shared looseness)
    ("x" * 64, True),
    ("x" * 65, False),           # the 64-cap divergence, now canonical
    ("", False),
    ("has space", False),
    ("a/b", False),
    ("a.b", False),               # dots are not in the name charset
]

HOST_CASES = [
    ("example.com", True),
    (".example.com", True),       # leading-dot subdomain form
    ("EXAMPLE.com", True),        # CLI/writer lowercase; UI matches A-Z
    ("a.b.c.d", True),
    ("xn--nxasmq6b.example", True),
    ("-lead.com", True),          # leading-hyphen labels: accepted everywhere
    ("a" * 63 + ".com", True),
    # total exactly 253 with all labels <= 63: accept
    ("a" * 63 + "." + "a" * 63 + "." + "a" * 63 + "." + "a" * 61, True),
    ("", False),
    ("example.com:8080", False),  # ports are dead config (swap addon strips them)
    ("under_score.com", False),
    ("a..b", False),
    ("a b.com", False),
    ("münchen.de", False),        # ASCII-only charset
    ("a" * 64 + ".com", False),   # label > 63
    ("a." * 126 + "ab", False),   # total 254 > 253, labels all 1-char
]

PLACEMENT_CASES = [
    # ((kind, value), expect_accept)
    (("bearer_header", None), True),
    (("url_path_segment", None), True),
    (("custom_header", "X-Api-Key"), True),
    (("custom_header", "X_Api_Key"), True),   # the charset divergence, now canonical
    (("custom_header", "X.Api.Key"), True),   # (dots likewise)
    (("query_param", "api_key"), True),
    (("query_param", "api-key"), True),
    (("custom_header", "X" * 64), True),
    (("custom_header", "X" * 65), False),     # the 64-cap divergence, now canonical
    (("query_param", "q" * 65), False),
    (("custom_header", ""), False),
    (("custom_header", "Has Space"), False),
    (("custom_header", "X:weird"), False),    # colon is the kind/value separator
    (("bogus_kind", "x"), False),
    (("bearer_header", "ignored"), False),    # bare kinds take no arg
    # ("url_path_segment", "seg") is deliberately absent: the writer accepts
    # the dict form {"url_path_segment": <name>} (honored by the swap addon,
    # target ignored) but neither the CLI nor cred-ui can produce it — it is
    # outside the shared user-facing corpus by construction (see module
    # docstring).
]


@pytest.mark.parametrize("name,expected", NAME_CASES)
def test_name_grammar_conformance(name, expected, registry):
    results = {
        "cred CLI": _cli_name(name),
        "cred-ui": _ui_name(name),
        "cred-registry-set": _writer_name(name, registry),
        "credlib": _credlib_name(name),
    }
    assert set(results.values()) == {expected}, (
        "name grammar diverged for %r: %s (expected all %s)"
        % (name, results, expected)
    )


@pytest.mark.parametrize("name,expected", NAME_CASES)
def test_swap_addon_name_grammar_is_superset(name, expected):
    # Read side stays a superset: every name the canonical contract
    # accepts must be loadable by the addon. Rejects are deliberately not
    # asserted — the addon is intentionally looser (strict-on-write /
    # liberal-on-read), so legacy on-disk secrets keep being served.
    if expected:
        assert swap_addon.NAME_RE.match(name), (
            "swap_addon.NAME_RE no longer a superset: rejects %r" % (name,))


@pytest.mark.parametrize("host,expected", HOST_CASES)
def test_host_grammar_conformance(host, expected, registry):
    results = {
        "cred CLI": _cli_host(host),
        "cred-ui": _ui_host(host),
        "cred-registry-set": _writer_host(host, registry),
    }
    assert set(results.values()) == {expected}, (
        "host grammar diverged for %r: %s (expected all %s)"
        % (host, results, expected)
    )


@pytest.mark.parametrize("kind_value,expected", PLACEMENT_CASES)
def test_placement_grammar_conformance(kind_value, expected, registry):
    kind, value = kind_value
    results = {
        "cred CLI": _cli_placement(kind, value),
        "cred-ui": _ui_placement(kind, value),
        "cred-registry-set": _writer_placement(kind, value, registry),
    }
    assert set(results.values()) == {expected}, (
        "placement grammar diverged for %r: %s (expected all %s)"
        % (kind_value, results, expected)
    )


# --- legacy-management upgrade path ------------------------------------------

LEGACY_NAME = "n" * 70          # creatable before the 64-cap, servable today
LEGACY_ENTRY = "e" * 70
LEGACY_HOST = "h" * 70 + ".example.com"   # first label over the 63 cap


def _legacy_registry(tmp_path):
    """A registry as it could exist from before the canonical caps: written
    directly, bypassing `set`'s creation-time checks — the same shape an
    upgraded box could carry."""
    reg = tmp_path / "credentials.json"
    reg.write_text(json.dumps({
        LEGACY_NAME: {
            LEGACY_ENTRY: {"placement": "bearer_header"},
            "allowed_hosts": [LEGACY_HOST],
        },
    }), encoding="utf-8")
    lock = tmp_path / "credentials.json.lock"
    return dict(os.environ,
                CRED_REGISTRY_FILE=str(reg),
                CRED_REGISTRY_LOCK=str(lock))


class TestLegacyManagementUpgradePath:
    """Pre-cap credentials stay manageable through the narrow writer:
    remove/remove-host work on legacy names/hosts; creation (`set`) and
    new `add-host` bindings stay strict; the RESERVED_ENTRIES guard holds
    on the legacy path too."""

    def test_remove_legacy_credential(self, tmp_path):
        assert _writer(["remove", LEGACY_NAME], _legacy_registry(tmp_path))

    def test_remove_legacy_entry(self, tmp_path):
        assert _writer(["remove", LEGACY_NAME, LEGACY_ENTRY],
                       _legacy_registry(tmp_path))

    def test_remove_host_legacy_binding(self, tmp_path):
        assert _writer(["remove-host", LEGACY_NAME, LEGACY_HOST],
                       _legacy_registry(tmp_path))

    def test_set_still_rejects_legacy_name(self, tmp_path):
        # Creation always enforces the canonical contract.
        assert not _writer(["set", LEGACY_NAME, "access_token",
                            '"bearer_header"'], _legacy_registry(tmp_path))

    def test_add_host_rejects_overlong_new_binding(self, tmp_path):
        # New bindings are always canonical, even on a legacy credential.
        assert not _writer(["add-host", LEGACY_NAME, LEGACY_HOST],
                           _legacy_registry(tmp_path))

    def test_add_host_accepts_canonical_binding_on_legacy_name(self, tmp_path):
        assert _writer(["add-host", LEGACY_NAME, "api.example.com"],
                       _legacy_registry(tmp_path))

    def test_remove_reserved_entry_still_rejected(self, tmp_path):
        assert not _writer(["remove", LEGACY_NAME, "allowed_hosts"],
                           _legacy_registry(tmp_path))

    def test_set_scrub_works_on_legacy_entry(self, tmp_path):
        assert _writer(["set-scrub", LEGACY_NAME, LEGACY_ENTRY, "true"],
                       _legacy_registry(tmp_path))

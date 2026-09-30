"""Tests for credlib/credvalidate.py — the single-source validation contract.

Issue #706: the credential/entry/host contract used to live in four
independent copies (cred, cred-ui, proxy/cred-registry-set,
credlib/dynamic_credentials.py), synced only by comments. Now
credlib/credvalidate.py is canonical:

- credlib consumers import it directly (same directory).
- cred-ui imports it from its staged install dir (or the checkout).
- proxy/cred-registry-set imports it from next to the deployed writer.
- `cred` keeps a machine-checked MIRROR (manual-copy CLI, no installer):
  this file asserts the mirror's atoms are identical to the module's.

Two layers here: (1) unit tests pin the module's own accept/reject
behavior, including the ValueError-not-TypeError fail-closed contract for
non-string input; (2) parity tests pin that every consumer enforces the
same contract — atom-identical for the `cred` mirror, behavior-identical
for the runtime importers, and source-absence pins so nobody reintroduces
a local copy in the writer.

Run from the repo root:  python3 -m pytest credlib/test_credvalidate.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import credvalidate as cv  # noqa: E402
from credvalidate import (  # noqa: E402
    HOST_LABEL_MAX_LEN,
    HOST_MAX_LEN,
    RESERVED_ENTRIES,
    check_entry,
    check_entry_legacy,
    check_host,
    check_host_legacy,
    check_name,
    check_name_legacy,
)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_cred():
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("cred_cli", os.path.join(REPO, "cred"))
    spec = importlib.util.spec_from_loader("cred_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_ui():
    import importlib.util
    path = os.path.join(REPO, "cred-ui", "cred-ui.py")
    spec = importlib.util.spec_from_loader("credui_cv", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = path
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"),
         mod.__dict__)
    return mod


cred = _load_cred()
ui = _load_ui()


# ---------------------------------------------------------------- module unit

class TestCanonicalName:
    @pytest.mark.parametrize("name", ["a", "api-key_2", "x" * 64,
                                      "UPPER", "0"])
    def test_accepts(self, name):
        assert check_name(name) == name

    @pytest.mark.parametrize("name", ["", "x" * 65, "has space", "dot.name",
                                      "semi;colon", "unié", None, 123,
                                      ["a"], "a/b"])
    def test_rejects(self, name):
        with pytest.raises(ValueError):
            check_name(name)


class TestLegacyName:
    @pytest.mark.parametrize("name", ["a", "x" * 64, "x" * 500])
    def test_accepts(self, name):
        assert check_name_legacy(name) == name

    @pytest.mark.parametrize("name", ["", "has space", None, 42])
    def test_rejects(self, name):
        with pytest.raises(ValueError):
            check_name_legacy(name)


class TestEntry:
    @pytest.mark.parametrize("name", ["access_token", "x" * 64])
    def test_entry_accepts(self, name):
        assert check_entry(name) == name

    @pytest.mark.parametrize("name", list(RESERVED_ENTRIES))
    def test_entry_rejects_reserved(self, name):
        with pytest.raises(ValueError):
            check_entry(name)
        with pytest.raises(ValueError):
            check_entry_legacy(name)

    def test_entry_rejects_bad_charset(self):
        with pytest.raises(ValueError):
            check_entry("has space")

    def test_entry_legacy_accepts_long(self):
        assert check_entry_legacy("x" * 200) == "x" * 200


class TestHost:
    def test_canonical_accepts_and_folds_case(self):
        assert check_host("Example.COM") == "example.com"
        assert check_host(".example.com") == ".example.com"
        assert check_host("a-b.c9") == "a-b.c9"

    def test_canonical_boundary_lengths(self):
        ok = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 61
        assert len(ok) == 253
        assert check_host(ok) == ok
        with pytest.raises(ValueError):
            check_host(ok + "e")  # 254
        with pytest.raises(ValueError):
            check_host("a" * 64 + ".example.com")  # 64-char label

    @pytest.mark.parametrize("host", ["", "has space", "under_score.com",
                                      "host:8080", "a..b", ".",
                                      None, 123, ["x"]])
    def test_canonical_rejects(self, host):
        with pytest.raises(ValueError):
            check_host(host)

    def test_legacy_shape_only(self):
        long_host = "a" * 300 + ".example.com"
        with pytest.raises(ValueError):
            check_host(long_host)  # canonical: over the 253 cap
        assert check_host_legacy(long_host) == long_host  # still removable
        with pytest.raises(ValueError):
            check_host_legacy("under_score.com")

    def test_non_string_is_value_error_not_type_error(self):
        # Fail-closed contract: no TypeError may escape on any input.
        for bad in (None, 123, 4.5, ["x"], {"x": 1}, b"bytes"):
            with pytest.raises(ValueError):
                check_name(bad)
            with pytest.raises(ValueError):
                check_host(bad)


# ------------------------------------------------------- consumer parity

CORPUS_ACCEPT_CANONICAL = ["a", "api-key_2", "x" * 64, "UPPER"]
CORPUS_REJECT_CANONICAL = ["", "x" * 65, "has space", "dot.name", None, 123]
CORPUS_ACCEPT_LEGACY = ["a", "x" * 500]
CORPUS_REJECT_LEGACY = ["", "has space", None]
CORPUS_HOSTS_ACCEPT = ["example.com", ".example.com", "Example.COM",
                       "a-b.c9", "a" * 63 + ".example.com"]
CORPUS_HOSTS_REJECT = ["", "under_score.com", "host:8080", "a..b",
                       "a" * 64 + ".example.com", None, 123]


def _cred_accepts(fn, value):
    try:
        fn(value)
    except cred.CredentialError:
        return False
    return True


class TestCredMirrorParity:
    """`cred` mirrors the contract atoms; they must stay identical."""

    def test_regex_atoms_identical(self):
        assert cred.NAME_RE.pattern == cv.NAME_RE.pattern
        assert cred.NAME_LEGACY_RE.pattern == cv.NAME_LEGACY_RE.pattern
        assert cred.HOST_RE.pattern == cv.HOST_SHAPE_RE.pattern

    def test_caps_and_reserved_identical(self):
        assert cred.HOST_MAX_LEN == HOST_MAX_LEN
        assert cred.HOST_LABEL_MAX_LEN == HOST_LABEL_MAX_LEN
        assert tuple(cred.RESERVED_ENTRIES) == tuple(RESERVED_ENTRIES)

    def test_reserved_entries_membership_pinned(self):
        # The finding-34b boundary is the reason this module exists: a
        # member dropped consistently from the module AND the mirror would
        # pass every other test green, so the content itself is pinned.
        expected = ("allowed_hosts", "allowed_methods", "allowed_paths",
                    "grants")
        assert tuple(RESERVED_ENTRIES) == expected
        assert tuple(cred.RESERVED_ENTRIES) == expected

    @pytest.mark.parametrize("name", CORPUS_ACCEPT_CANONICAL)
    def test_canonical_agrees_accept(self, name):
        assert _cred_accepts(cred.check_name, name)
        assert check_name(name) == name

    @pytest.mark.parametrize("name", CORPUS_REJECT_CANONICAL)
    def test_canonical_agrees_reject(self, name):
        assert not _cred_accepts(cred.check_name, name)
        with pytest.raises(ValueError):
            check_name(name)

    @pytest.mark.parametrize("name", CORPUS_ACCEPT_LEGACY)
    def test_legacy_agrees_accept(self, name):
        assert _cred_accepts(cred.check_name_legacy, name)

    @pytest.mark.parametrize("name", CORPUS_REJECT_LEGACY)
    def test_legacy_agrees_reject(self, name):
        assert not _cred_accepts(cred.check_name_legacy, name)

    @pytest.mark.parametrize("name", list(RESERVED_ENTRIES))
    def test_entry_reserved_agrees(self, name):
        assert not _cred_accepts(cred.check_entry, name)
        assert not _cred_accepts(cred.check_entry_legacy, name)

    @pytest.mark.parametrize("host", CORPUS_HOSTS_ACCEPT)
    def test_host_agrees_accept(self, host):
        assert cred.check_host(host) == check_host(host) == host.lower()

    @pytest.mark.parametrize("host", CORPUS_HOSTS_REJECT)
    def test_host_agrees_reject(self, host):
        with pytest.raises(cred.CredentialError):
            cred.check_host(host)
        with pytest.raises(ValueError):
            check_host(host)

    def test_mirror_banner_present(self):
        # The DO-NOT-EDIT banner is the human-facing half of the parity
        # contract; the assertions above are the executable half.
        src = open(os.path.join(REPO, "cred"), encoding="utf-8").read()
        assert "MACHINE-CHECKED MIRROR (issue #706)" in src
        assert "credlib/credvalidate.py" in src


class TestCredUiImportsContract:
    """cred-ui must consume the module, not redefine it."""

    def test_imported_names_are_the_module(self):
        assert ui.check_name is cv.check_name
        assert ui.check_name_legacy is cv.check_name_legacy
        assert ui.check_entry is cv.check_entry
        assert ui.check_host is cv.check_host
        assert ui.check_host_legacy is cv.check_host_legacy

    @pytest.mark.parametrize("host", CORPUS_HOSTS_ACCEPT)
    def test_host_ok_agrees(self, host):
        assert ui.host_ok(host) is True

    @pytest.mark.parametrize("host", CORPUS_HOSTS_REJECT)
    def test_host_ok_rejects(self, host):
        assert ui.host_ok(host) is False

    @pytest.mark.parametrize("host", CORPUS_HOSTS_ACCEPT + ["a" * 300
                                                            + ".example.com"])
    def test_host_ok_legacy_shape(self, host):
        assert ui.host_ok_legacy(host) is True

    def test_host_ok_legacy_rejects_shape(self):
        assert ui.host_ok_legacy("under_score.com") is False
        assert ui.host_ok_legacy("") is False

    @pytest.mark.parametrize("name", CORPUS_ACCEPT_LEGACY)
    def test_name_ok_legacy(self, name):
        assert ui.name_ok_legacy(name) is True

    @pytest.mark.parametrize("name", CORPUS_REJECT_LEGACY)
    def test_name_ok_legacy_rejects(self, name):
        assert ui.name_ok_legacy(name) is False

    def test_no_local_contract_definitions(self):
        src = open(os.path.join(REPO, "cred-ui", "cred-ui.py"),
                   encoding="utf-8").read()
        for local in ("NAME_RE = re.compile", "NAME_LEGACY_RE = re.compile",
                      "ENTRY_RE = re.compile", "RESERVED_ENTRIES = (",
                      "_HOST_SHAPE_RE = ", "_HOST_RE = "):
            assert local not in src, \
                "cred-ui.py reintroduces a local contract copy: %r" % local


class TestCredlibImportsContract:
    """credlib must consume the module, not redefine it (same-dir import)."""

    def test_no_local_contract_definitions(self):
        src = open(os.path.join(REPO, "credlib", "dynamic_credentials.py"),
                   encoding="utf-8").read()
        for local in ('NAME_LEGACY_RE = re.compile',
                      'NAME_RE = re.compile'):
            assert local not in src, \
                "dynamic_credentials.py reintroduces a local contract copy: %r" \
                % local
        assert "from credvalidate import NAME_LEGACY_RE" in src


class TestWriterImportsContract:
    """The writer's python section must consume the module, not redefine it."""

    @staticmethod
    def _python_section():
        src = open(os.path.join(REPO, "proxy", "cred-registry-set"),
                   encoding="utf-8").read()
        return src.split("<<'PYEOF'", 1)[1]

    def test_imports_module(self):
        py = self._python_section()
        assert "import credvalidate as _cv" in py

    def test_no_local_contract_definitions(self):
        py = self._python_section()
        for local in ("RESERVED_ENTRIES = (", "HOST_MAX_LEN = ",
                      're.match(r"^[A-Za-z0-9_-]{1,64}$"',
                      're.match(r"^[A-Za-z0-9_-]+$"',
                      're.match(r"^\\.?[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*$"'):
            assert local not in py, \
                "cred-registry-set reintroduces a local contract copy: %r" \
                % local

    def test_module_dir_resolution_is_wrapper_derived(self):
        src = open(os.path.join(REPO, "proxy", "cred-registry-set"),
                   encoding="utf-8").read()
        # The wrapper exports the dir from its own $0; the python section
        # must not trust a caller-settable name for it.
        assert '_CREDVALIDATE_BASE="$(cd "$(dirname -- "$_cv_self")" && pwd -P)"' \
            in src
        assert 'os.environ.get("_CREDVALIDATE_BASE")' in src

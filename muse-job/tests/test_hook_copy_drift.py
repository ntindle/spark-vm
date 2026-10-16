"""Pin hook-copy sync (issue #21, item 1).

The trust-validation primitives are duplicated across the standalone plugin
hooks by design:

- `_SID_RE` in session-start.py, session-end.py, stop.py
- `_ANSI_RE` in session-end.py, stop.py
- `_append_event` in session-end.py, stop.py

Hooks carry no imports of each other so the plugin deploys as independent
scripts; duplication is load-bearing. Every copy carries a "HOOK-COPY SYNC"
comment naming the set. This test fails loudly on drift between the copies,
so the sync contract moves only by editing this test (deliberate) alongside
every copy.

Non-vacuity (verified by neutering, then reverted): narrowing one _SID_RE
to {1,64} fails the pattern-identity tests; deleting one _ANSI_RE
alternative in session-end.py fails the corpus tests; extending one
_ANSI_RE to also strip tab/newline fails the strictness pins; deleting
both islink(evdir) checks in one _append_event fails the symlink-refusal
leg; deleting O_NOFOLLOW in one _append_event fails the symlinked-file
leg; deleting the fstat/S_ISREG refusal in one _append_event fails the
FIFO-with-reader leg; sort_keys=True or a 0o600 mode in one _append_event
fails the byte-identity test; deleting a HOOK-COPY SYNC marker or omitting
a sibling from the claimed copy set fails the comment-presence test.
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "plugin" / "hooks"

SID_COPIES = ("session-start.py", "session-end.py", "stop.py")
ANSI_COPIES = ("session-end.py", "stop.py")
APPEND_COPIES = ("session-end.py", "stop.py")

# The canonical sid contract: every copy must carry exactly this.
CANONICAL_SID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"

# Adversarial corpus for the ANSI/control sanitizer: every entry must
# sanitize identically in every _ANSI_RE copy.
ANSI_CORPUS = [
    "\x1b[2Klabel overwritten",  # CSI erase-line
    "\x1b[31;1mred\x1b[0m",  # SGR colors
    "\x1b]0;window title\x07text",  # OSC terminated by BEL
    "\x1b]0;window title\x1b\\text",  # OSC terminated by ST
    "\x1bcreset follows",  # bare ESC (reset)
    "\x1b7save\x1b8restore",  # bare ESC save/restore
    "line1\r   fake verified-done",  # CR + padding (issue #23 B6)
    "\x00\x08\x0b\x0c\x0e\x1f\x7f\x80\x9f",  # C0/C1 controls
    "\x1b[?25lhidden cursor\x1b[?25h",  # private-mode CSI
    "plain text stays untouched",
    "a\tb\nc",  # tab + newline are preserved by design
    "line1\nline2\tindented",  # tabs/newlines survive, controls die
    "mixed\r\n\t\x1b[2Ktail",  # CR stripped, newline+tab preserved, CSI stripped
]

# Exact-output pins: prove the sanitizer is not a vacuous no-op.
ANSI_EXPECTED = {
    "\x1b[2Klabel": "label",
    "\x1b[31mred\x1b[0m": "red",
    "\x1b]0;t\x07x": "x",
    "\x1b]0;t\x1b\\x": "x",
    "\x1bc": "c",  # bare ESC strips only the ESC byte
    "a\rb": "ab",
    "\x00a\x7f": "a",
    "\x9f": "",
    "a\tb\n": "a\tb\n",  # tab/newline preserved — strictness drift fails
    "line1\nline2\tindented": "line1\nline2\tindented",
    "a\r\nb": "a\nb",  # CR stripped, newline kept
}

# Each copy site that must carry the sync-contract comment.
SYNC_SITES = {
    "session-start.py": ("_SID_RE",),
    "session-end.py": ("_SID_RE", "_ANSI_RE", "_append_event"),
    "stop.py": ("_SID_RE", "_ANSI_RE", "_append_event"),
}

# The full copy set per primitive — the comment at each site must name
# every sibling, so a future editor knows which files to edit together.
COPY_SETS = {
    "_SID_RE": set(SID_COPIES),
    "_ANSI_RE": set(ANSI_COPIES),
    "_append_event": set(APPEND_COPIES),
}


def _mod_name(filename):
    return "hookdrift_" + filename.replace("-", "_").replace(".", "_")


def _load(filename):
    mod_name = _mod_name(filename)
    sys.modules.pop(mod_name, None)
    loader = importlib.machinery.SourceFileLoader(
        mod_name, str(HOOKS_DIR / filename)
    )
    spec = importlib.util.spec_from_loader(mod_name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    loader.exec_module(mod)
    return mod


MODS = {
    f: _load(f)
    for f in set(SID_COPIES) | set(ANSI_COPIES) | set(APPEND_COPIES)
}


class TestSidReSync:
    def test_patterns_identical_across_copies(self):
        patterns = {f: MODS[f]._SID_RE.pattern for f in SID_COPIES}
        assert len(set(patterns.values())) == 1, (
            f"_SID_RE drift between hook copies: {patterns}"
        )

    def test_patterns_match_canonical_contract(self):
        for f in SID_COPIES:
            assert MODS[f]._SID_RE.pattern == CANONICAL_SID_PATTERN, (
                f"{f} _SID_RE diverged from the canonical contract — "
                "update every copy and this test together"
            )

    def test_behavioral_parity_on_edge_cases(self):
        cases = ["abc-123_X", "a" * 128, "a" * 129, "../evil",
                 "semi;colon", "with space", ""]
        for case in cases:
            results = {
                f: bool(MODS[f]._SID_RE.match(case)) for f in SID_COPIES
            }
            assert len(set(results.values())) == 1, (
                f"_SID_RE behavioral drift on {case!r}: {results}"
            )


class TestAnsiReSync:
    def test_copies_agree_on_corpus(self):
        outs = {
            f: tuple(MODS[f]._ANSI_RE.sub("", s) for s in ANSI_CORPUS)
            for f in ANSI_COPIES
        }
        assert len(set(outs.values())) == 1, (
            "_ANSI_RE corpus drift: "
            + "; ".join(
                f"{f}: {[repr(a) for a, b in zip(v, next(iter(outs.values()))) if a != b][:3]}"
                for f, v in outs.items()
            )
        )

    def test_sanitizer_is_not_vacuous(self):
        for src, want in ANSI_EXPECTED.items():
            for f in ANSI_COPIES:
                got = MODS[f]._ANSI_RE.sub("", src)
                assert got == want, (
                    f"{f} _ANSI_RE.sub({src!r}) = {got!r}, want {want!r}"
                )


class TestAppendEventParity:
    def _call(self, filename, tmp_path, evdir, sid, evt):
        # Never raises, by contract.
        MODS[filename]._append_event(evdir, sid, evt)

    def test_valid_write_identical(self, tmp_path):
        for f in APPEND_COPIES:
            evdir = os.path.join(str(tmp_path), f"ev_{_mod_name(f)}")
            self._call(f, tmp_path, evdir, "abc-123_X", {"k": "v"})
            path = os.path.join(evdir, "abc-123_X.jsonl")
            assert os.path.isfile(path), f"{f}: valid write produced no file"
            assert open(path).read().splitlines() == [json.dumps({"k": "v"})]

    def test_bad_sid_writes_nothing(self, tmp_path):
        for f in APPEND_COPIES:
            evdir = os.path.join(str(tmp_path), f"ev_{_mod_name(f)}")
            self._call(f, tmp_path, evdir, "../evil", {"k": "v"})
            assert not os.path.exists(evdir), (
                f"{f}: bad sid created the events dir"
            )

    def test_symlinked_evdir_refused(self, tmp_path):
        for f in APPEND_COPIES:
            target = os.path.join(str(tmp_path), f"target_{_mod_name(f)}")
            os.makedirs(target)
            link = os.path.join(str(tmp_path), f"link_{_mod_name(f)}")
            os.symlink(target, link)
            self._call(f, tmp_path, link, "abc-123_X", {"k": "v"})
            assert not os.path.exists(
                os.path.join(target, "abc-123_X.jsonl")
            ), f"{f}: wrote through a symlinked events dir"

    def test_readerless_fifo_does_not_hang(self, tmp_path):
        for f in APPEND_COPIES:
            evdir = os.path.join(str(tmp_path), f"ev_{_mod_name(f)}")
            os.makedirs(evdir)
            os.mkfifo(os.path.join(evdir, "f1.jsonl"))
            # O_NONBLOCK must fail fast with ENXIO, never block.
            self._call(f, tmp_path, evdir, "f1", {"k": "v"})

    def test_symlinked_event_file_refuses_write(self, tmp_path):
        # O_NOFOLLOW must refuse a symlinked <sid>.jsonl — the issue #3
        # cross-job tampering primitive this flag exists for.
        for f in APPEND_COPIES:
            evdir = os.path.join(str(tmp_path), f"ev_{_mod_name(f)}")
            os.makedirs(evdir)
            victim = os.path.join(str(tmp_path), f"victim_{_mod_name(f)}.txt")
            with open(victim, "w") as fh:
                fh.write("victim")
            os.symlink(victim, os.path.join(evdir, "f1.jsonl"))
            # O_NOFOLLOW -> ELOOP -> caught -> return; no exception escapes.
            self._call(f, tmp_path, evdir, "f1", {"k": "v"})
            assert open(victim).read() == "victim", (
                f"{f}: wrote through a symlinked event file — "
                "O_NOFOLLOW is missing or drifted"
            )

    def test_copies_produce_byte_identical_trees(self, tmp_path):
        # Per-copy sanity is not enough: the copies must produce the same
        # bytes (a sort_keys=True or mode drift in one copy is still a
        # drift). Identical relative layout, multi-key unsorted event.
        old_umask = os.umask(0o022)
        try:
            trees = {}
            for f in APPEND_COPIES:
                root = os.path.join(str(tmp_path), _mod_name(f))
                evdir = os.path.join(root, "events")
                self._call(f, tmp_path, evdir, "f1", {"z": 1, "a": 2})
                path = os.path.join(evdir, "f1.jsonl")
                trees[f] = (
                    open(path, "rb").read(),
                    oct(os.stat(path).st_mode & 0o777),
                )
            assert len(set(trees.values())) == 1, (
                f"_append_event byte drift between copies: {trees}"
            )
            mode = trees[APPEND_COPIES[0]][1]
            assert mode == "0o644", (
                f"event file mode {mode}, want 0o644 — the os.open mode "
                "argument drifted"
            )
        finally:
            os.umask(old_umask)

    def test_fifo_with_reader_refuses_write(self, tmp_path):
        # A FIFO *with* a reader opens fine (O_NONBLOCK succeeds), so only
        # the fstat/S_ISREG refusal keeps event bytes off it. Drift here is
        # a security boundary, not a nit.
        for f in APPEND_COPIES:
            evdir = os.path.join(str(tmp_path), f"ev_{_mod_name(f)}")
            os.makedirs(evdir)
            path = os.path.join(evdir, "f1.jsonl")
            os.mkfifo(path)
            reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            try:
                self._call(f, tmp_path, evdir, "f1", {"k": "v"})
                assert os.read(reader, 4096) == b"", (
                    f"{f}: wrote event bytes into a FIFO with a reader — "
                    "the fstat/S_ISREG refusal is missing or drifted"
                )
            finally:
                os.close(reader)


class TestSyncCommentsPresent:
    def test_every_copy_site_carries_the_sync_marker(self):
        for filename, names in SYNC_SITES.items():
            src = (HOOKS_DIR / filename).read_text(encoding="utf-8")
            for name in names:
                if name == "_append_event":
                    idx = src.index("def _append_event")
                else:
                    idx = src.index(f"{name} = re.compile")
                window = src[max(0, idx - 700) : idx + 700]
                assert "HOOK-COPY SYNC" in window, (
                    f"{filename}:{name} lost its sync-contract comment"
                )
                assert "test_hook_copy_drift.py" in window, (
                    f"{filename}:{name} comment must name the sync test"
                )
                assert "issue #21" in window, (
                    f"{filename}:{name} comment must cite the tracking issue"
                )
                for sibling in COPY_SETS[name] - {filename}:
                    assert sibling in window, (
                        f"{filename}:{name} comment must name sibling "
                        f"{sibling} — the claimed copy set is what tells "
                        "a future editor which files to edit together"
                    )

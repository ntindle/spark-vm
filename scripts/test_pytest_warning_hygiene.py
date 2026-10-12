#!/usr/bin/env python3
r"""Pin the repo's test-output hygiene: the suite must emit no warnings.

Two wart classes, both cheap to introduce and both training contributors
to ignore test output:

1. **Invalid escape sequences** — a non-raw docstring containing ``\\w``,
   ``\\```, etc. raises SyntaxWarning at import time (or at ``ast.parse``
   time, which is how the suite tripped over the third instance). Three
   instances shipped: ``jail/test_build_smoke.py``,
   ``deploy/golden-image/test_golden_image.py``, and ``proxy/swap_addon.py``
   (a product docstring whose literal backslash example the suite's
   handler-surface pin parses); all fixed with raw docstrings (in
   ``test_build_smoke.py`` the raw form also restores the prose's intended
   two-byte ``\"``, which the old form had collapsed to ``"`` — the other
   two rendered as-written, since invalid escapes are preserved literally).
2. **Bytes-valued environment writes** — ``monkeypatch.setenv`` (or
   ``os.environ`` / ``os.putenv``) with a bytes value emits PytestWarning
   ("converted to str implicitly"), and the implicit ``str()`` is the
   repr — ``"b'...'"`` — not the bytes' content.
   (``scripts/test_waitlist_invites.py`` passed the bytes HMAC ``KEY``
   straight through; fixed with ``KEY.decode("ascii")``.)

Non-vacuity (verified by neutering on scratch copies, then reverted):
restoring any non-raw docstring fails the compile leg; restoring the
raw-``KEY`` setenv fails the AST leg.
"""

import ast
import configparser
import subprocess
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _test_modules():
    """Every test_*.py under pytest.ini's testpaths (the same module set
    pytest imports when a contributor runs the suite)."""
    cfg = configparser.ConfigParser()
    cfg.read(REPO_ROOT / "pytest.ini")
    dirs = cfg["pytest"]["testpaths"].split()
    modules = []
    for d in dirs:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        modules.extend(sorted(root.rglob("test_*.py")))
    assert modules, "no test modules found — the scan is vacuous"
    return modules


def test_no_invalid_escape_sequences_in_py_files():
    """Every tracked .py file must compile with SyntaxWarning as an
    error — a non-raw docstring/regex with an invalid escape fails this.
    The whole tree (not just test modules): a SyntaxWarning fires at
    import/parse time for any of them, and the suite's handler-surface pin
    ast.parses the whole repo, so a product-file wart still pollutes
    contributor test output."""
    offenders = []
    for module in _all_py_files():
        try:
            source = module.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            offenders.append(f"{module.relative_to(REPO_ROOT)}: unreadable ({e})")
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", SyntaxWarning)
                compile(source, str(module), "exec")
        except SyntaxError as e:  # SyntaxWarning subclasses SyntaxError
            offenders.append(f"{module.relative_to(REPO_ROOT)}: {e}")
    assert not offenders, (
        ".py files with invalid escape sequences (SyntaxWarning):\n"
        + "\n".join(offenders)
        + "\n— make the string raw (r\"\"\") or double the backslash"
    )


def _all_py_files():
    """Every tracked .py file in the repo."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=REPO_ROOT, check=True,
            capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise AssertionError(f"git ls-files failed — cannot enumerate "
                             f".py files: {e}")
    files = [REPO_ROOT / p for p in out.stdout.splitlines() if p]
    assert files, "no .py files found — the scan is vacuous"
    return files


class _BytesEnvWriteVisitor(ast.NodeVisitor):
    """Flag environment writes whose value is bytes.

    Coverage is deliberately broad — the pin's contract is "no bytes
    into the environment", and a narrow pin gives false confidence:

    - values: bytes constants, names bound to bytes (any scope; a name
      rebound to a non-bytes constant anywhere is dropped, so rebinding
      can never false-positive), ``.encode()`` results, ``bytes(...)``
      calls, and bytes ``BinOp``s (``b"a" + b"b"``).
    - write sites: ``X.setenv(name, value)`` / ``X.putenv(name, value)``
      on any receiver (``monkeypatch``, ``os``, or an alias), bare
      ``setenv``/``putenv`` names (from-imports), keyword ``value=``,
      ``os.environ["K"] = v`` / ``environ["K"] = v`` (from-import),
      ``os.environ.update({...})`` with bytes values, and
      ``os.environ.setdefault(k, v)`` / ``environ.setdefault(k, v)``.
    """

    def __init__(self):
        self.bytes_names = set()
        self.offenses = []

    def _is_bytes_value(self, node):
        if isinstance(node, ast.Constant):
            return isinstance(node.value, bytes)
        if isinstance(node, ast.Name):
            return node.id in self.bytes_names
        if isinstance(node, ast.Call):
            func = node.func
            # "text".encode(...) / bytes(...)
            if isinstance(func, ast.Attribute) and func.attr == "encode":
                return True
            return isinstance(func, ast.Name) and func.id == "bytes"
        if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Mult)):
            return (self._is_bytes_value(node.left)
                    or self._is_bytes_value(node.right))
        return False

    def _is_environ_obj(self, node):
        # os.environ, or bare `environ` (from os import environ)
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            return (isinstance(node.value, ast.Name)
                    and node.value.id == "os")
        return isinstance(node, ast.Name) and node.id == "environ"

    def _receiver_label(self, func):
        # Render dotted receivers (os.environ.update, monkeypatch.setenv)
        # instead of <expr> placeholders.
        if not isinstance(func, ast.Attribute):
            return func.id  # bare setenv/putenv name
        parts = []
        node = func.value
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        parts.append(func.attr)
        return ".".join(parts) if parts else "<expr>"

    def visit_Module(self, node):
        # Pre-pass: bytes-bound names at any scope. A name counts iff it
        # has at least one bytes-valued binding and no binding to a
        # non-bytes constant (rebinding drops it — avoids false
        # positives). Chained names (a = KEY) resolve via fixpoint.
        bindings = []  # (name, value_node)
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        bindings.append((target.id, child.value))
            elif (isinstance(child, ast.AnnAssign)
                    and isinstance(child.target, ast.Name)
                    and child.value is not None):
                bindings.append((child.target.id, child.value))
        for _ in range(4):
            grown = False
            for name, value in bindings:
                if name not in self.bytes_names \
                        and self._is_bytes_value(value):
                    self.bytes_names.add(name)
                    grown = True
            if not grown:
                break
        for name, value in bindings:
            if (isinstance(value, ast.Constant)
                    and not isinstance(value.value, bytes)):
                self.bytes_names.discard(name)
        self.generic_visit(node)

    def _check_call_values(self, node, label, values):
        if any(self._is_bytes_value(v) for v in values):
            self.offenses.append(
                f"line {node.lineno}: {label} with a bytes value")

    def visit_Call(self, node):
        func = node.func
        attr = (func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else None)
        if attr in ("setenv", "putenv"):
            # setenv(name, value) / putenv(name, value), incl. keyword
            # form setenv(name=..., value=...)
            values = list(node.args[1:]) + [
                kw.value for kw in node.keywords if kw.arg == "value"]
            self._check_call_values(
                node, self._receiver_label(func), values)
        elif (attr in ("update", "setdefault")
                and isinstance(func, ast.Attribute)
                and self._is_environ_obj(func.value)):
            if attr == "update":
                # os.environ.update({...}) — flag bytes dict values
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        self._check_call_values(
                            node, self._receiver_label(func),
                            [v for v in arg.values if v is not None])
            else:
                # setdefault(key, default) / setdefault(key, default=...)
                values = list(node.args[1:]) + [
                    kw.value for kw in node.keywords
                    if kw.arg == "default"]
                self._check_call_values(
                    node, self._receiver_label(func), values)
        self.generic_visit(node)

    def visit_Assign(self, node):
        # os.environ["X"] = <bytes> / environ["X"] = <bytes>
        for target in node.targets:
            if (isinstance(target, ast.Subscript)
                    and self._is_environ_obj(target.value)
                    and self._is_bytes_value(node.value)):
                self.offenses.append(
                    f"line {target.lineno}: environ[...] = bytes")
        self.generic_visit(node)


def test_no_bytes_valued_env_writes_in_test_modules():
    """No test module may write bytes into the environment — the implicit
    str() is the repr, and pytest warns (PytestWarning)."""
    offenders = []
    for module in _test_modules():
        try:
            source = module.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            offenders.append(
                f"{module.relative_to(REPO_ROOT)}: unreadable ({e})")
            continue
        try:
            tree = ast.parse(source, filename=str(module))
        except SyntaxError as e:
            # The compile leg pins syntax separately; record and move on
            # rather than crashing this leg.
            offenders.append(
                f"{module.relative_to(REPO_ROOT)}: unparseable ({e})")
            continue
        visitor = _BytesEnvWriteVisitor()
        visitor.visit(tree)
        for offense in visitor.offenses:
            offenders.append(f"{module.relative_to(REPO_ROOT)}: {offense}")
    assert not offenders, (
        "test modules writing bytes-valued environment variables:\n"
        + "\n".join(offenders)
        + "\n— decode to str at the write site (e.g. KEY.decode(\"ascii\"))"
    )

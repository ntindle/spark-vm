#!/usr/bin/env python3
"""Pin: docs/CREDENTIAL_VEND_CONTRACT.md keeps its four security pins.

The vend contract is the design the #890 plane vend endpoint and the #891
box-side fetch path implement, and four of its security decisions arrived
as filed findings from the 2026-10-13 arch deep-read:

(a) #1401 — the mint endpoint's auth surface must be the plane's
    no-oracle 401 convention, not a 403 that oracles enrollment;
(b) #1402 — secret issuance requires a `current` box token; a `grace`
    (post-rotation) token mints nothing (grace is for continuity traffic);
(c) #1403 — `vend_values.alg` is exactly `aes-128-gcm`, the algorithm the
    stdlib-only worker can actually implement — never AES-256;
(d) #1406 — a manifest write is one D1 batch over `vend_manifest` and
    `vend_values` (never statement-by-statement), and the tombstone-clear
    rule's "fresh value" is a decrypt-compare with the data key.

A contract edit that quietly reintroduces a 403, lets a grace token mint,
re-pins AES-256, or drops the atomicity unit would hand the #890 builder
an unaudited security downgrade — so these tests pin the doc text.
Needle-based on the doc; multi-word needles use \\s+ so doc line-wraps
don't false-fail. Stdlib-only. Run from the repo root:
`python3 -m pytest scripts/test_credential_vend_contract.py`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "CREDENTIAL_VEND_CONTRACT.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _needle(*words: str) -> re.Pattern:
    """Multi-word doc needle tolerant of line wraps."""
    return re.compile(r"\s+".join(re.escape(w) for w in words))


def _section(text: str, heading: str) -> str:
    """Return the doc region from `heading` to the next same-or-higher-level heading."""
    level = len(heading) - len(heading.lstrip("#"))
    m = re.search(re.escape(heading), text)
    assert m, f"heading {heading!r} missing from the vend contract"
    rest = text[m.end():]
    nxt = re.search(rf"(?m)^#{{1,{level}}}\s", rest)
    return rest[: nxt.start()] if nxt else rest


def test_no_403_claim_in_section_2_1():
    """#1401: §2.1 (the route spec) never names a 403 response for the mint endpoint."""
    mint = _section(_doc(), "### 2.1 Endpoints and auth")
    assert "403" not in mint.replace("#1403", ""), (
        "§2.1 must not claim a 403 anywhere on the mint route"
    )
    assert _needle("wrong-box", "token", "reads", "the", "same", "unattributed",
                   "`401`", "as", "an", "unknown", "token").search(mint)
    assert "no-oracle" in mint
    assert _needle("reuses", "the", "plane's", "shared", "box-auth", "gate").search(mint)


def test_revoked_and_expired_stay_401_with_holder_messages():
    """#1401: revoked/expired are 401 (not 403), with distinct holder-visible messages."""
    mint = _section(_doc(), "### 2.1 Endpoints and auth")
    assert _needle("Revoked", "and", "expired", "tokens", "also", "`401`").search(mint)
    assert '"box revoked"' in mint
    assert '"token expired"' in mint


def test_issuance_requires_current_gate():
    """#1402: §2.1b pins the current-only gate with the rotation-naming 401 message."""
    text = _doc()
    assert "(issue #1402)" in text
    gate = _section(text, "### 2.1b Token-state gate for issuance (issue #1402)")
    assert _needle("grace", "is", "for", "continuity", "traffic;",
                   "issuance", "requires").search(gate)
    assert "token superseded" in gate  # rotation-naming message, never "token expired"
    assert _needle("re-mint", "with", "the", "current", "token").search(gate)
    assert _needle("falls", "back", "to", "the", "re-bootstrap", "path").search(gate)


def test_grace_token_mints_nothing():
    """#1402: the §2.1 Mint row says a grace token mints nothing, not just 'is limited'."""
    mint = _section(_doc(), "### 2.1 Endpoints and auth")
    assert _needle("a", "`grace`", "token", "mints", "nothing",
                   "and", "reads", "`401`").search(mint)
    assert _needle("requires", "a", "**`current`**", "box", "token").search(mint)


def test_alg_is_exactly_aes_128_gcm():
    """#1403: the schema pins 'aes-128-gcm'; AES-256 (any spelling) appears
    only inside an explicit denial."""
    text = _doc()
    # A 32-char lookbehind is not enough ("not an option, consider AES-256"
    # passes it): every mention must sit inside an explicit denial phrase.
    denials = [m.span() for m in re.finditer(
        r"(?:not an|rather than(?: an)?|never)\s+aes[-_ ]?256", text, re.IGNORECASE)]
    mentions = [m.span() for m in re.finditer(r"aes[-_ ]?256", text, re.IGNORECASE)]
    assert mentions, "expected at least the §3 denial mention"
    for start, end in mentions:
        assert any(d0 <= start and end <= d1 for d0, d1 in denials), (
            f"AES-256 named outside an explicit denial: "
            f"...{text[max(0, start-60):end+40]}...")
    schema = _section(text, "### 2.4 D1 schema (plane)")
    assert "alg TEXT /* 'aes-128-gcm'" in schema
    custody = _section(text, "## 3. Custody: where secret values rest on the plane (G50.9)")
    assert "AES-128-GCM" in custody
    assert "#1403" in custody


def _acceptance_item(accept: str, num: str) -> str:
    """Return the full multi-line body of §10 item `num` ('10.' style)."""
    m = re.search(rf"(?m)^{re.escape(num)}\s+", accept)
    assert m, f"acceptance item {num} missing from §10"
    body = accept[m.end():]
    nxt = re.search(r"(?m)^\d+\.\s+", body)
    return body[: nxt.start()] if nxt else body


def test_manifest_write_atomicity_is_one_d1_batch():
    """#1406: §2.1a pins the atomicity unit — one D1 batch over both tables,
    never statement-by-statement."""
    text = _doc()
    assert "(issue #1406)" in text
    write = _section(text, "### 2.1a Manifest write schema and validation")
    assert _needle("one", "D1", "batch").search(write)
    assert _needle("vend_manifest").search(write) and _needle("vend_values").search(write)
    assert _needle("MUST", "NOT").search(write) and "statement-by-statement" in write
    assert _needle("any", "statement", "failure", "rolls", "the", "whole",
                   "write", "back").search(write)
    assert _needle("partial", "manifest", "is", "never", "observable").search(write)
    assert "#990" in write  # D1-batch-portable atomic statements precedent


def test_tombstone_clear_needs_decrypt_compare():
    """#1406: the tombstone-clear "fresh value" rule names the decrypt-compare
    mechanism — decrypt vend_values.ciphertext with the data key, constant-time
    compare, identical plaintext leaves revoked_at set."""
    text = _doc()
    write = _section(text, "### 2.1a Manifest write schema and validation")
    assert _needle("decrypts", "`vend_values.ciphertext`", "with", "the", "data",
                   "key").search(write)
    assert "constant time" in write
    assert _needle("identical", "plaintext", "leaves").search(write)
    assert "`revoked_at`" in write
    assert _needle("does", "not", "silently").search(write) and "un-revoke" in write


def test_acceptance_covers_atomicity_pin():
    """§10 acceptance item 13 names the atomicity pin and cites #1406."""
    accept = _section(_doc(), "## 10. Acceptance (S6 — testable)")
    item13 = _acceptance_item(accept, "13.")
    assert "#1406" in item13
    assert _needle("one", "D1", "batch").search(item13)
    assert _needle("rolls", "the", "whole", "write", "back").search(item13)
    # Denial-worded like items 10-12: states what is refused, not just the allowlist.
    assert _needle("never", "leaves", "a", "partial", "manifest").search(item13)
    assert _needle("does", "not", "clear", "`revoked_at`").search(item13)


def test_acceptance_covers_all_three_pins():
    """The §10 acceptance checklist names one item per pin, each citing its issue."""
    accept = _section(_doc(), "## 10. Acceptance (S6 — testable)")
    for num, issue in (("10.", "#1401"), ("11.", "#1402"), ("12.", "#1403")):
        assert issue in _acceptance_item(accept, num), (
            f"acceptance item {num} must cite {issue}"
        )


def test_acceptance_items_are_denial_worded():
    """§10 items 10-12 must state the denial (what is refused), not just the allowlist."""
    accept = _section(_doc(), "## 10. Acceptance (S6 — testable)")
    item10 = _acceptance_item(accept, "10.")
    assert "never `403`" in item10
    item11 = _acceptance_item(accept, "11.")
    assert "mints nothing" in item11
    assert "never `200`" in item11
    item12 = _acceptance_item(accept, "12.")
    assert _needle("not", "an", "AES-256").search(item12)

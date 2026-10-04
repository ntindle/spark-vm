"""Tests for hosted/push_payload.py — the #970 (GP4) construction-time
payload scrub. Every test here must fail against a naive identity
implementation (no scrub / no bound); the non-vacuity note in the
RUNLOG records the neutering check.
"""

import pytest

from hosted.push_payload import (
    MAX_SUMMARY_BYTES,
    build_push_payload,
    scrub_push_text,
)


def test_clean_text_unchanged():
    assert scrub_push_text("Box requests: restart the demo") == \
        "Box requests: restart the demo"


def test_c0_controls_stripped():
    assert scrub_push_text("a\x00b\x07c\x1fd") == "abcd"


def test_newline_and_tab_stripped():
    # Summaries are lock-screen one-liners; embedded line breaks and tabs
    # are removed, not preserved.
    assert scrub_push_text("line1\nline2\rline3\tend") == "line1line2line3end"


def test_c1_controls_stripped():
    assert scrub_push_text("a\x80b\x9fc") == "abc"


def test_ansi_escape_killed():
    # The ESC byte is stripped, so the escape sequence cannot survive.
    assert scrub_push_text("alert\x1b[31mred") == "alert[31mred"
    assert "\x1b" not in scrub_push_text("\x1b]0;spoofed title\x07")


def test_del_stripped():
    assert scrub_push_text("a\x7fb") == "ab"


def test_overlong_truncated_with_ellipsis_within_byte_bound():
    s = "x" * (MAX_SUMMARY_BYTES + 50)
    out = scrub_push_text(s)
    assert out.endswith("…")
    assert len(out.encode("utf-8")) <= MAX_SUMMARY_BYTES
    # The kept prefix is the input prefix (no reordering, no substitution).
    assert out == "x" * (MAX_SUMMARY_BYTES - 3) + "…"


def test_truncation_never_splits_code_point():
    # 4-byte emoji; truncation must stop at a boundary, never emit a
    # replacement character or a partial byte sequence.
    s = "🚨" * 100
    out = scrub_push_text(s)
    out.encode("utf-8")  # raises on surrogates/partial sequences
    assert "�" not in out
    assert len(out.encode("utf-8")) <= MAX_SUMMARY_BYTES
    # 63 4-byte emoji = 252 bytes of payload + 3-byte ellipsis = 255
    # (<= 256; the remaining byte can't fit another 4-byte code point).
    assert out == "🚨" * 63 + "…"


def test_exact_bound_untouched_no_spurious_ellipsis():
    s = "y" * MAX_SUMMARY_BYTES
    assert scrub_push_text(s) == s
    # Multi-byte: exactly at the bound is also untouched.
    s2 = "é" * (MAX_SUMMARY_BYTES // 2)
    assert scrub_push_text(s2) == s2


def test_truncation_accounts_multibyte_ellipsis():
    s = "z" * (MAX_SUMMARY_BYTES + 1)
    out = scrub_push_text(s)
    assert out.endswith("…")
    assert len(out.encode("utf-8")) == MAX_SUMMARY_BYTES
    assert out == "z" * (MAX_SUMMARY_BYTES - 3) + "…"


def test_controls_stripped_before_length_accounting():
    # Controls are removed first, so a string whose only excess is control
    # bytes is not truncated.
    s = "w" * MAX_SUMMARY_BYTES + "\x00" * 100
    assert scrub_push_text(s) == "w" * MAX_SUMMARY_BYTES


def test_custom_max_bytes():
    assert scrub_push_text("abcdef", max_bytes=6) == "abcdef"
    assert scrub_push_text("abcdef", max_bytes=5) == "ab…"


def test_max_bytes_too_small_is_fail_closed():
    with pytest.raises(ValueError):
        scrub_push_text("abc", max_bytes=2)


def test_non_str_value_is_fail_closed():
    for bad in (None, 123, b"bytes", ["list"]):
        with pytest.raises(TypeError):
            scrub_push_text(bad)


def test_non_int_max_bytes_rejected():
    with pytest.raises(TypeError):
        scrub_push_text("abc", max_bytes="256")


def test_build_payload_shape_and_keys():
    p = build_push_payload("aid-123", 3600, "please approve")
    assert set(p) == {"aid", "ttl_s", "summary"}
    assert p == {"aid": "aid-123", "ttl_s": 3600,
                "summary": "please approve"}


def test_build_payload_scrubs_hostile_summary():
    p = build_push_payload("aid-1", 60, "\x1b[2Kspoofed: allow all\x07" +
                           "z" * 1000)
    assert "\x1b" not in p["summary"]
    assert "\x07" not in p["summary"]
    assert len(p["summary"].encode("utf-8")) <= MAX_SUMMARY_BYTES
    assert p["summary"].endswith("…")


def test_build_payload_rejects_bad_aid():
    for bad in ("", None, 123):
        with pytest.raises(ValueError):
            build_push_payload(bad, 60, "s")


def test_build_payload_rejects_bad_ttl():
    for bad in (0, -5, True, "60", 1.5):
        with pytest.raises(ValueError):
            build_push_payload("aid-1", bad, "s")


def test_build_payload_rejects_non_str_summary():
    with pytest.raises(TypeError):
        build_push_payload("aid-1", 60, None)


def test_build_payload_mapping_is_immutable():
    # Post-hoc key addition must fail at the boundary — a secret cannot
    # be smuggled into the payload after construction without an
    # explicit, reviewable dict() copy.
    p = build_push_payload("aid-1", 60, "s")
    with pytest.raises(TypeError):
        p["auth"] = "secret"
    with pytest.raises(TypeError):
        del p["aid"]


def test_no_secrets_in_payload_shape():
    # The builder takes no token/subscription/VAPID argument and emits no
    # such key; a future "extra fields" addition must go through review.
    import inspect
    sig = inspect.signature(build_push_payload)
    assert set(sig.parameters) == {"aid", "ttl_s", "summary"}

"""Push payload construction discipline for the plane Web Push sender.

Issue #970 (GP4 of docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md). The push path
is a hostile-*box* surface: box-controlled strings (approval reason,
box_name, ...) flow into payloads the plane VAPID-signs and delivers to
the owner's lock screen. A compromised box must not be able to smuggle
terminal-injection, spoofing text, or unbounded bytes into a payload.

This module pins the single construction-time rule the sender's enqueue
boundary applies to every payload field it does not itself mint:

  1. control-character strip (C0 + C1, including ESC — ANSI escape
     sequences die here), and
  2. an explicit byte-length bound, truncating with an ellipsis without
     ever splitting a UTF-8 code point.

Modeled on the #902 `_plane_text` class (`pairing/spark_pair.py`), but a
different rule: `_plane_text` is display-only (its docstring: "Stored
values and control-flow comparisons always use the raw value — this is
for terminal display only") and unbounded. Payload construction needs a
byte bound because the sender encrypts and transmits the bytes.

Payload shape (decision D4, "go look" payloads): aid + TTL + scrubbed
summary only. Never secrets — the builder takes no bearer token, no
subscription key, and no VAPID material as arguments, and returns an
immutable mapping so keys cannot be added post-hoc without an explicit,
reviewable copy. (The module cannot police what a caller does after an
explicit copy — the guarantee is the builder's interface and the
returned mapping's immutability, not caller discipline.)

Scope note: this module is push-construction only. The owner-facing
decision surface (#954) deliberately shows the FULL raw text so the
owner can judge it; do not apply this scrub on the dashboard read path.
"""

import re
from types import MappingProxyType

# The single construction rule: strip C0 and C1 controls (incl. ESC),
# then enforce the byte bound. The control-char class here is identical
# to #902's `_plane_text` (`pairing/spark_pair.py`); what differs is the
# application, not the class: `_plane_text` is display-only, unbounded,
# and total (never raises), while this rule is construction-time — a
# byte bound plus fail-closed typing — because the output becomes signed
# and transmitted bytes.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")

# Maximum summary size in the payload: byte-exact, enforced on the
# UTF-8 encoding (not the str length) so multi-byte text cannot smuggle
# more bytes than the bound.
MAX_SUMMARY_BYTES = 256

# Single ellipsis char (3 bytes in UTF-8); accounted for inside the byte
# bound so a truncated payload never exceeds MAX_SUMMARY_BYTES.
_ELLIPSIS = "…"


def scrub_push_text(value, max_bytes=MAX_SUMMARY_BYTES):
    """Scrub one box-controlled string for inclusion in a push payload.

    Strips C0/C1 control characters, then truncates to `max_bytes` UTF-8
    bytes with an ellipsis appended, never splitting a code point.
    Returns the scrubbed string.

    Raises TypeError on a non-str `value` (fail-closed: the enqueue
    boundary must never silently stringify an unexpected type into a
    signed payload), and ValueError on a `max_bytes` that cannot hold
    even the ellipsis. A lone surrogate raises UnicodeEncodeError at
    the encode step — also fail-closed (no payload emitted), and
    unreachable over the real WSS path, where text frames are valid
    UTF-8.
    """
    if not isinstance(value, str):
        raise TypeError(
            "scrub_push_text requires a str, got %s" % type(value).__name__
        )
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
        raise TypeError("max_bytes must be an int")
    ellipsis_bytes = len(_ELLIPSIS.encode("utf-8"))
    if max_bytes < ellipsis_bytes:
        raise ValueError("max_bytes must be at least %d" % ellipsis_bytes)

    stripped = _CONTROL_CHARS.sub("", value)
    encoded = stripped.encode("utf-8")
    if len(encoded) <= max_bytes:
        return stripped

    # Byte-exact truncation at a code-point boundary, reserving room for
    # the ellipsis. Walking chars keeps the accounting independent of
    # how many bytes each code point takes.
    budget = max_bytes - ellipsis_bytes
    used = 0
    kept = []
    for ch in stripped:
        ch_bytes = len(ch.encode("utf-8"))
        if used + ch_bytes > budget:
            break
        kept.append(ch)
        used += ch_bytes
    return "".join(kept) + _ELLIPSIS


def build_push_payload(aid, ttl_s, summary):
    """Build the signed device payload dict for one approval page.

    Shape is exactly {"aid", "ttl_s", "summary"} (D4). `aid` is
    plane-minted (validated non-empty, never box-controlled free text);
    `summary` is the single box-controlled field and is scrubbed by
    `scrub_push_text`. Returns an immutable mapping (MappingProxyType):
    post-hoc key addition raises TypeError, so a secret cannot be
    smuggled into the payload after construction without an explicit,
    reviewable `dict()` copy.
    """
    if not isinstance(aid, str) or not aid:
        raise ValueError("aid must be a non-empty str")
    if not isinstance(ttl_s, int) or isinstance(ttl_s, bool) or ttl_s <= 0:
        raise ValueError("ttl_s must be a positive int")
    return MappingProxyType({
        "aid": aid,
        "ttl_s": ttl_s,
        "summary": scrub_push_text(summary),
    })

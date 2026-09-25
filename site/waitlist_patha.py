#!/usr/bin/env python3
"""waitlist_patha — the Path-A email parser (H15 build, slice 3 remainder).

Implements docs/WAITLIST_OPERATIONS.md §2 (Path A — Muse via email,
primary) on top of waitlistd.WaitlistService:

    - parse: extract owner-email candidates from the body, apply the
      exclusion list (the From address, the inbox's own address, any
      @agentmail.to address) before counting; an explicit `Owner: addr`
      line overrides extraction. Optional: the Muse's ed25519 pubkey
      (single `ssh-ed25519 AAAA…` line — pre-registration hint only) and
      one use-case line (≤280 chars, verbatim).
    - exactly one candidate → validated row via submit_email — accepted
      regardless of the auth verdict. §2/§6: per-owner dedup on the
      normalized address; re-submits refresh the timestamp; the path-A
      confirm opener goes out. The confirm email is a double opt-in
      challenge to the *owner address* (not a reply to the sender):
      the protection is the human click, per §3 ("Sybil resistance
      comes from the confirm gate plus launch capacity, not from
      sender attestation") and §6 ("the confirm gate is what makes
      spraying worthless"). Third-party mail is bounded by the unified
      §4 3/24h per-address cap (confirms + reminders + invites +
      clarifications + forget-requests counted together), so a
      rotatable From cannot turn the intake into a mail cannon;
    - zero or ≥2 candidates → the §2 clarification reply — ONLY when the
      inbound message passes SPF/DKIM/DMARC alignment on the From domain.
      Unauthenticated ambiguous mail is silently triaged: the parser never
      sends a *reply* to an unauthenticated sender (§6 — no backscatter).
      (The signup and forget paths above/below DO send owner-bound mail
      on unauthenticated input — that is deliberate, not a hole; see the
      signup and forget bullets.);
    - a reply saying "forget me" → the §5 confirmation email containing
      the signed forget link (never direct deletion — Reply From is
      forgeable, that's a deletion oracle). The confirmation goes to the
      row's owner — the signed link (proving inbox access), not the
      From, is what authorizes the deletion. Forget intent is checked
      BEFORE the per-sender intake gate: a spam-prevention limit must
      never swallow a deletion request;
    - per-sender rate limit: 3 submissions / sender / day (§6).

The parser never authenticates mail itself: the operator's inbound reader
runs SPF/DKIM/DMARC and passes the verdict as --auth {pass,fail}; the
verdict is recorded on the row (inbound_auth) and gates the
clarification reply. Garbage auth values are rejected loudly — a
fail-open default on the backscatter gate would be the wrong shape.

Operator shape (one message per invocation; the operator's inbox agent
feeds raw messages to stdin):

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... WAITLIST_INBOX=waitlist@... \\
        waitlist_patha.py --auth pass < message.eml

Config (env — same fail-loud contract as waitlistd/waitlist_jobs):
    WAITLIST_HMAC_KEY    operator HMAC key — REQUIRED, fail loud if unset.
    WAITLIST_DATA        operator-owned data dir — REQUIRED, fail loud if
                         unset or unwritable. Never the repo.
    WAITLIST_PUBLIC_HOST public origin for links in queued email
                         (default https://waitlist.example.invalid).
    WAITLIST_INBOX       the dedicated waitlist inbox address — REQUIRED
                         (it is on the parser's exclusion list; a message
                         that only quotes the inbox address must not
                         resolve to a candidate).

stdlib only. Tested by scripts/test_waitlist_patha.py.
"""

import email
import email.policy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from waitlistd import (  # noqa: E402
    MAX_EMAIL_LEN,
    WaitlistService,
    data_lock,
    normalize_email,
)

# The exclusion list (§2): the From address, the inbox's own address, and
# any @agentmail.to address are never owner candidates (signature lines,
# CCs, and quoted threads routinely contain ≥2 addresses — counting them
# would bounce the primary converting path into the ask-again loop).
AGENTMAIL_DOMAIN = "agentmail.to"

OWNER_LINE_RE = re.compile(r"(?im)^owner:\s*(\S+)\s*$")
PUBKEY_LINE_RE = re.compile(r"(?m)^ssh-ed25519\s+([A-Za-z0-9+/=]+)\s*$")
USECASE_LINE_RE = re.compile(r"(?im)^use case:\s*(.+?)\s*$")
# Candidate extraction: email-shaped tokens in the body. The labeled
# Owner: line is handled first (it overrides extraction); everything
# else is regex-found and exclusion-filtered.
CANDIDATE_RE = re.compile(
    r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}"
)
FORGET_RE = re.compile(r"(?<![\w@.+-])forget[-\s]?me(?![\w@-])", re.IGNORECASE)
MAX_USECASE_CHARS = 280
# Intake size cap: anything bigger than 1 MiB is not a signup email.
# parse_message itself has no cap (the email library handles headers),
# so the CLI enforces this on the raw bytes before triaging.
MAX_RAW_BYTES = 1024 * 1024


def parse_message(raw):
    """Parse a raw RFC822 message into (from_addr, subject, body_text).

    Prefers the first text/plain part; falls back to the raw payload
    decoded loosely. from_addr is the raw From header (may be empty).
    Raises ValueError on unparseable input.
    """
    try:
        msg = email.message_from_string(raw, policy=email.policy.default)
    except Exception as exc:
        raise ValueError(f"unparseable message: {exc}") from exc
    from_addr = str(msg.get("From", "") or "")
    subject = str(msg.get("Subject", "") or "")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and \
                    not part.get_filename():
                try:
                    body = part.get_content()
                except Exception:
                    body = ""
                break
    else:
        try:
            body = msg.get_content()
        except Exception:
            body = ""
    if not isinstance(body, str):
        body = ""
    if not body and not from_addr and not subject:
        raise ValueError("empty message")
    return from_addr, subject, body


def _strip_display_name(addr):
    """Turn 'Jane <jane@x.com>' into 'jane@x.com'; leave bare addresses."""
    m = re.search(r"<([^<>]+)>", addr)
    return (m.group(1) if m else addr).strip()


def extract_owner_candidate(body, from_addr, inbox_addr):
    """Return the single validated owner candidate, or None.

    §2 parsing: an explicit `Owner: addr` line overrides extraction.
    The override is still sanity-filtered, but ONLY against the
    inbox's own address and @agentmail.to — naming those as the owner
    is pathological (a confirm email addressed to the inbox itself, or
    to an agent address that can never approve spend). The From
    address is deliberately NOT excluded from the override: a
    human-driven Muse's From address routinely IS the owner's address,
    and extraction's From-exclusion exists to disambiguate among
    multiple candidates, not to veto an explicit statement. Exactly
    one candidate → return it (validated + normalized); zero or ≥2 →
    None (the caller sends the clarification reply or triages).
    """
    m = OWNER_LINE_RE.search(body)
    if m:
        owner = normalize_email(m.group(1).strip().strip("<>"))
        if owner:
            inbox_norm = normalize_email(_strip_display_name(inbox_addr))
            if owner == inbox_norm or \
                    owner.endswith("@" + AGENTMAIL_DOMAIN):
                return None  # pathological override: clarify
        return owner  # None when the labeled line is not a valid address
    excluded = set()
    for addr in (from_addr, inbox_addr):
        norm = normalize_email(_strip_display_name(addr))
        if norm:
            excluded.add(norm)
    candidates = set()
    for tok in CANDIDATE_RE.findall(body):
        norm = normalize_email(tok)
        if not norm or len(tok) > MAX_EMAIL_LEN:
            continue
        if norm in excluded:
            continue
        if norm.endswith("@" + AGENTMAIL_DOMAIN):
            continue
        candidates.add(norm)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


FORGET_NEGATED_RE = re.compile(
    r"\b(do\s*(?:n'?t|not)|does\s*(?:n'?t|not)|did\s*(?:n'?t|not)|never)"
    r"\s+forget[-\s]?me\b",
    re.IGNORECASE)


def detect_forget_intent(subject, body):
    """True when the message is a "forget me" reply (§5).

    Negated forms ("please don't forget me") are NOT forget intent —
    routing those to the deletion flow would be the wrong shape."""
    text = f"{subject or ''}\n{body or ''}"
    if FORGET_NEGATED_RE.search(text):
        return False
    return bool(FORGET_RE.search(text))


def extract_pubkey(body):
    """The optional single-line `ssh-ed25519 AAAA…` (§2) — a
    pre-registration hint only, never trusted. Returns the full key line
    or None."""
    m = PUBKEY_LINE_RE.search(body)
    if not m:
        return None
    return f"ssh-ed25519 {m.group(1)}"


def extract_usecase(body):
    """The optional `Use case: ...` line (§2) — stored verbatim, max 280
    chars. Returns None when absent."""
    m = USECASE_LINE_RE.search(body)
    if not m:
        return None
    return m.group(1).strip()[:MAX_USECASE_CHARS]


def process_inbound(service, raw, *, auth, inbox_addr):
    """Process one inbound message against the service.

    Returns an outcome dict with at least an "outcome" key:
      "accepted"              new row created (confirm email queued)
      "resubmitted"           existing pending row refreshed
      "confirmed"             row already confirmed (idempotent)
      "confirm_capped"        accepted; re-send suppressed by the cap
      "clarified"             clarification reply spooled (auth=pass)
      "clarification_capped"  clarification suppressed by the cap
      "forget_request_sent"   §5 forget-confirmation email spooled
      "forget_request_capped" forget confirmation suppressed by the cap
      "already_invited"       owner already holds a claim email — no-op
      "already_claimed"       owner already claimed the invite
                              (signed_up is terminal) — no-op
      "intake_limited"        per-sender 3/day tripped — silent
      "triage"                silent triage (unauthenticated or garbage);
                              outcome["reason"] + ["triage_file"] say why

    Forget intent is checked BEFORE the intake gate (§5's deletion right
    outranks the §6 spam budget): a sender who burned their 3/day and
    then says "forget me" still gets the confirmation email. The intake
    limit itself is enforced atomically inside submit_email (check +
    ledger record under the lock), so process_inbound never pre-checks.
    Clarification/triage replies do not consume intake budget.
    """
    if auth not in ("pass", "fail"):
        raise ValueError(f"auth must be 'pass' or 'fail', got {auth!r}")
    try:
        from_raw, subject, body = parse_message(raw)
    except ValueError as exc:
        service.triage_inbound(raw, f"unparseable: {exc}")
        return {"outcome": "triage", "reason": "unparseable"}
    sender = normalize_email(_strip_display_name(from_raw))
    if not sender:
        service.triage_inbound(raw, "no usable From address")
        return {"outcome": "triage", "reason": "no_from"}

    # The §5 forget path: a reply saying "forget me" is never honored on
    # its own — it triggers the confirmation email with the signed link.
    # Checked before the intake gate: a deletion request must never be
    # swallowed by a spam-prevention limit.
    if detect_forget_intent(subject, body):
        outcome, row = service.handle_forget_reply(sender)
        if outcome == "no_row":
            triaged = service.triage_inbound(
                raw, "forget-me reply with no matching row")
            return {"outcome": "triage", "reason": "forget_no_row",
                    "triage_file": triaged}
        return {"outcome": outcome,
                "entry_id": row["entry_id"] if row else None}

    owner = extract_owner_candidate(body, from_raw, inbox_addr)
    if owner is None:
        if auth != "pass":
            # §2/§6: clarification replies only on DMARC-aligned mail —
            # unauthenticated mail is silently triaged (no backscatter).
            triaged = service.triage_inbound(
                raw, "ambiguous owner candidates, unauthenticated mail")
            return {"outcome": "triage", "reason": "ambiguous_unauth",
                    "triage_file": triaged}
        sent = service.spool_clarification(sender)
        return {"outcome": "clarified" if sent else "clarification_capped"}

    outcome, row = service.submit_email(
        owner=owner, sender=sender, inbound_auth=(auth == "pass"),
        pubkey=extract_pubkey(body), usecase=extract_usecase(body))
    if outcome == "intake_limited":
        triaged = service.triage_inbound(
            raw, "per-sender intake limit (3/day)")
        return {"outcome": "intake_limited", "triage_file": triaged}
    result = {"outcome": {"created": "accepted"}.get(outcome, outcome),
              "entry_id": row["entry_id"] if row else None}
    return result


def load_config(argv):
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(__doc__ + "\n")
        raise SystemExit(0)
    auth = None
    for i, arg in enumerate(argv):
        if arg == "--auth" and i + 1 < len(argv):
            auth = argv[i + 1]
    if auth not in ("pass", "fail"):
        sys.stderr.write(
            "waitlist_patha: --auth {pass,fail} is required — the "
            "operator's inbound reader supplies the SPF/DKIM/DMARC "
            f"verdict (got {auth!r}).\n")
        raise SystemExit(2)
    key_raw = os.environ.get("WAITLIST_HMAC_KEY")
    if not key_raw:
        sys.stderr.write(
            "waitlist_patha: WAITLIST_HMAC_KEY is not set — refusing to "
            "run without the operator HMAC key.\n")
        raise SystemExit(2)
    try:
        key = bytes.fromhex(key_raw)
    except ValueError:
        key = key_raw.encode("utf-8")
    if len(key) < 16:
        sys.stderr.write(
            "waitlist_patha: WAITLIST_HMAC_KEY is too short "
            "(need >= 16 bytes).\n")
        raise SystemExit(2)
    data_dir = os.environ.get("WAITLIST_DATA")
    if not data_dir:
        sys.stderr.write(
            "waitlist_patha: WAITLIST_DATA is not set — refusing to run "
            "without an operator-owned data dir.\n")
        raise SystemExit(2)
    if not os.path.isdir(data_dir) or not os.access(data_dir, os.W_OK):
        sys.stderr.write(
            f"waitlist_patha: WAITLIST_DATA={data_dir!r} is not a writable "
            "directory.\n")
        raise SystemExit(2)
    inbox = os.environ.get("WAITLIST_INBOX")
    if not inbox or not normalize_email(inbox):
        sys.stderr.write(
            "waitlist_patha: WAITLIST_INBOX is not set — refusing to run "
            "without the dedicated inbox address (exclusion list).\n")
        raise SystemExit(2)
    host = os.environ.get("WAITLIST_PUBLIC_HOST",
                           "https://waitlist.example.invalid")
    return auth, key, data_dir, host, normalize_email(inbox)


def main(argv):
    auth, key, data_dir, host, inbox = load_config(argv)
    # Read BYTES and enforce the cap on byte length: sys.stdin.read()
    # counts characters, so 1 MiB of 4-byte UTF-8 (4 MiB of raw input)
    # would slip past a character cap. Decode lossily afterward — the
    # pipeline triages anything it can't parse, and undecodable input
    # must never crash the triage write with surrogate escapes.
    raw_bytes = sys.stdin.buffer.read(MAX_RAW_BYTES + 1)
    if not raw_bytes.strip():
        sys.stderr.write("waitlist_patha: no message on stdin.\n")
        raise SystemExit(2)
    service = WaitlistService(data_dir, key, host)
    if len(raw_bytes) > MAX_RAW_BYTES:
        # Oversize intake: never parse it, just triage the head for the
        # operator to eyeball. The cap keeps a hostile feed from making
        # the parser chew gigabytes.
        triaged = service.triage_inbound(
            raw_bytes[:MAX_RAW_BYTES], "message exceeds 1 MiB intake cap")
        sys.stdout.write(f"waitlist_patha: triage ({triaged})\n")
        return 0
    raw = raw_bytes.decode("utf-8", errors="replace")
    # submit_email / handle_forget_reply / spool_clarification take the
    # data + thread locks themselves — the single-message CLI holds none.
    result = process_inbound(service, raw, auth=auth, inbox_addr=inbox)
    sys.stdout.write(f"waitlist_patha: {result['outcome']}"
                     + (f" entry={result['entry_id']}"
                        if result.get("entry_id") else "")
                     + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Day-1 operator funnel query pack (docs/FUNNEL_MEASUREMENT.md section 7).

Reads a JSONL export of the waitlist operator store's `funnel_events` table
and prints the day-1 operator query pack: the primary page-conversion
metric plus the secondary, interim, and diagnostic numbers the funnel docs
prescribe.

Input row shape (one JSON object per line):
    {"event": "page_view_day", "at": "2026-09-20T00:00:00Z", "ref": "2026-09-20", "attrs": {"count": 123}}

- `event`: one of page_view_day, crawler_hits, cta_click, waitlist_submitted,
  confirm_sent, confirmed, reminder_sent, invite_sent, claimed
  (docs/FUNNEL_MEASUREMENT.md section 3.4; plus optional signup_started /
  identity_linked for the bridge line).
- `at`: ISO-8601 timestamp (trailing "Z" accepted).
- `ref`: the waitlist row id, or the day-bucket (YYYY-MM-DD) for rollup rows.
- `attrs`: small key-value map. Rollup rows (page_view_day, crawler_hits,
  cta_click) carry a pre-aggregated count under attrs["count"]; a rollup
  row without "count" is read as 1. Row events (waitlist_submitted,
  confirmed, ...) are one object per emission.

Windowing is cohort-based, not per-row: rollup rows (page_view_day,
crawler_hits, cta_click) filter on their own day-bucket date, while the
row-event metrics filter on the *anchor* event's date — a confirmation
that lands after the window still counts for a submission inside it.

Privacy posture: the script never sees an IP or a raw user agent. Unique
visitors come from the pre-aggregated page_view_day rollups, whose
day-buckets were computed server-side with the daily-rotating HMAC salt
(FUNNEL_MEASUREMENT.md section 3.1); crawlers are already excluded there
and reported separately as crawler_hits. Nothing in this script's input
can be joined across days, which is the point.

Usage:
    python3 scripts/funnel_metrics.py --events funnel_events.jsonl
    python3 scripts/funnel_metrics.py --events funnel_events.jsonl --since 2026-09-13 --until 2026-09-19

Exit 0 on a printed report, 2 on bad input/arguments. The report is plain
text on stdout so the operator can paste it into the weekly funnel note.
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

KNOWN_EVENTS = {
    "page_view_day",
    "crawler_hits",
    "cta_click",
    "waitlist_submitted",
    "confirm_sent",
    "confirmed",
    "reminder_sent",
    "invite_sent",
    "claimed",
    # Bridge-line events; not yet emitted by any build (land with signup).
    "signup_started",
    "identity_linked",
}

ROLLUP_EVENTS = {"page_view_day", "crawler_hits", "cta_click"}


def parse_ts(value):
    """Parse an ISO-8601 timestamp into an aware datetime; raise ValueError."""
    if not isinstance(value, str):
        raise ValueError(f"bad timestamp: {value!r}")
    text = value.strip().replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"unparseable timestamp: {value!r}")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def load_events(path):
    """Load JSONL funnel_events rows; raise ValueError with a line number."""
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: bad JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{lineno}: row must be an object")
            event = obj.get("event")
            if event not in KNOWN_EVENTS:
                raise ValueError(
                    f"{path}:{lineno}: unknown event {event!r} "
                    f"(expected one of {sorted(KNOWN_EVENTS)})"
                )
            rows.append(
                {
                    "event": event,
                    "at": parse_ts(obj.get("at")),
                    "ref": obj.get("ref"),
                    "attrs": obj.get("attrs") or {},
                }
            )
    return rows


def rollup_count(rows, event):
    """Sum pre-aggregated rollup rows (attrs.count; missing count reads as 1)."""
    total = 0
    for row in rows:
        if row["event"] != event:
            continue
        if event in ROLLUP_EVENTS and not isinstance(row["ref"], str):
            raise ValueError(f"rollup event {event} needs a day-bucket ref")
        count = row["attrs"].get("count", 1)
        if not isinstance(count, int) or count < 0:
            raise ValueError(
                f"rollup event {event}: attrs.count must be a non-negative int, "
                f"got {count!r}"
            )
        total += count
    return total


def row_ids(rows, event):
    return {r["ref"] for r in rows if r["event"] == event and r["ref"] is not None}


def median_hours(durations):
    if not durations:
        return None
    ordered = sorted(durations)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def ratio(num, den):
    if den == 0:
        return "n/a (denominator 0)"
    return f"{num}/{den} = {100.0 * num / den:.1f}%"


def fmt_hours(value):
    return "n/a (no rows)" if value is None else f"{value:.1f}h"


def hours_between(later, earlier):
    return (later - earlier).total_seconds() / 3600.0


def compute(rows, since, until):
    """Compute the section-7 query pack over the inclusive [since, until] window.

    Latencies additionally require the follow-on to not precede the anchor:
    a negative duration is data rot — excluded from the median, not averaged.
    """
    pack = {"since": since.isoformat(), "until": until.isoformat()}

    def in_window(r):
        return since <= r["at"].date() <= until

    rollups = [r for r in rows if in_window(r)]

    # Primary: confirmed (submitted in window) / unique visitors in window.
    submitted_in_window = {
        r["ref"]
        for r in rows
        if r["event"] == "waitlist_submitted" and in_window(r)
    }
    confirmed_rows = [r for r in rows if r["event"] == "confirmed"]
    confirmed_from_window = [
        r for r in confirmed_rows if r["ref"] in submitted_in_window
    ]
    pack["visitors"] = rollup_count(rollups, "page_view_day")
    pack["confirmed_submitted_in_window"] = len(
        {r["ref"] for r in confirmed_from_window}
    )

    # Secondary: cta_click by src.
    by_src = {}
    uncategorized = 0
    for row in rollups:
        if row["event"] != "cta_click":
            continue
        count = row["attrs"].get("count", 1)
        src = row["attrs"].get("src")
        if src:
            by_src[src] = by_src.get(src, 0) + count
        else:
            uncategorized += count
    pack["cta_by_src"] = dict(sorted(by_src.items()))
    pack["cta_uncategorized"] = uncategorized

    # Confirm rate, interim, split per section 6: raw vs DMARC-aligned.
    # Both splits are cohort-scoped: rows submitted inside the window.
    sent = [
        r
        for r in rows
        if r["event"] == "confirm_sent" and r["ref"] in submitted_in_window
    ]
    submitted_by_ref = {
        r["ref"]: r
        for r in rows
        if r["event"] == "waitlist_submitted" and r["ref"] in submitted_in_window
    }
    aligned_refs = {
        ref
        for ref, r in submitted_by_ref.items()
        if r["attrs"].get("inbound_auth") is True
    }
    raw_sent = len({r["ref"] for r in sent})
    aligned_sent = len({r["ref"] for r in sent if r["ref"] in aligned_refs})
    raw_confirmed = len({r["ref"] for r in confirmed_from_window})
    aligned_confirmed = len(
        {r["ref"] for r in confirmed_from_window if r["ref"] in aligned_refs}
    )
    pack["confirm_rate_raw"] = (raw_confirmed, raw_sent)
    pack["confirm_rate_aligned"] = (aligned_confirmed, aligned_sent)
    # Spray signature: gap between the raw and aligned splits, never averaged.
    pack["spray_gap_pp"] = (
        None
        if raw_sent == 0 or aligned_sent == 0
        else 100.0 * aligned_confirmed / aligned_sent
        - 100.0 * raw_confirmed / raw_sent
    )

    # Reminder lift: confirmed via=reminder / reminder_sent, cohort-scoped.
    reminded = {
        r["ref"]
        for r in rows
        if r["event"] == "reminder_sent" and r["ref"] in submitted_in_window
    }
    via_reminder = {
        r["ref"]
        for r in confirmed_from_window
        if r["attrs"].get("via") == "reminder" or r["ref"] in reminded
    }
    pack["reminder_lift"] = (len(via_reminder), len(reminded))

    # Invite -> claim, cohort-scoped on invite_sent in the window.
    invite_rows = {
        r["ref"]: r["at"] for r in rows if r["event"] == "invite_sent" and in_window(r)
    }
    claim_at = {r["ref"]: r["at"] for r in rows if r["event"] == "claimed"}
    invite_claim_hours = [
        hours_between(claim_at[ref], invite_rows[ref])
        for ref in invite_rows
        if ref in claim_at and claim_at[ref] >= invite_rows[ref]
    ]
    pack["invite_claim"] = (
        len({ref for ref in invite_rows if ref in claim_at}),
        len(invite_rows),
        median_hours(invite_claim_hours),
    )

    # Submit -> confirm latency, cohort-scoped on submission.
    submitted_at = {
        r["ref"]: r["at"]
        for r in rows
        if r["event"] == "waitlist_submitted" and r["ref"] in submitted_in_window
    }
    confirm_at = {r["ref"]: r["at"] for r in confirmed_from_window}
    submit_confirm_hours = [
        hours_between(confirm_at[ref], submitted_at[ref])
        for ref in confirm_at
        if ref in submitted_at and confirm_at[ref] >= submitted_at[ref]
    ]
    pack["submit_confirm_median_hours"] = median_hours(submit_confirm_hours)

    # Diagnostics.
    pack["crawler_hits"] = rollup_count(rollups, "crawler_hits")
    pack["rows_read"] = len(rows)

    # Bridge: kept visible, never folded into the page metric. The signup
    # build has not landed its events yet; if it has, compute them.
    linked = {
        r["ref"]
        for r in rows
        if r["event"] == "identity_linked" and r["ref"] in submitted_in_window
    }
    confirmed_refs = {r["ref"] for r in confirmed_from_window}
    pack["bridge"] = (len(linked), len(confirmed_refs))
    pack["bridge_instrumented"] = bool(
        row_ids(rows, "signup_started") or row_ids(rows, "identity_linked")
    )

    return pack


def report(pack):
    raw_n, raw_d = pack["confirm_rate_raw"]
    ali_n, ali_d = pack["confirm_rate_aligned"]
    inv_claimed, inv_sent, inv_med = pack["invite_claim"]
    rem_n, rem_d = pack["reminder_lift"]
    lines = [
        f"Funnel metrics pack — window {pack['since']}..{pack['until']} "
        f"(UTC, inclusive; per docs/FUNNEL_MEASUREMENT.md section 7)",
        f"  rows read: {pack['rows_read']}",
        "",
        "PRIMARY (page conversion)",
        f"  confirmed (submitted in window) / unique visitors: "
        f"{ratio(pack['confirmed_submitted_in_window'], pack['visitors'])}",
        "",
        "SECONDARY (CTA click-through by section src)",
    ]
    if pack["cta_by_src"]:
        for src, count in pack["cta_by_src"].items():
            lines.append(f"  {src}: {count}")
    else:
        lines.append("  (no cta_click rows in window)")
    if pack["cta_uncategorized"]:
        lines.append(f"  (uncategorized — missing src: {pack['cta_uncategorized']})")
    lines += [
        "",
        "INTERIM CONFIRM RATE (labeled interim per doc section 8 — answers "
        "'did the email work', not 'did the page work')",
        f"  raw: {ratio(raw_n, raw_d)}",
        f"  DMARC-aligned senders only: {ratio(ali_n, ali_d)}",
    ]
    if pack["spray_gap_pp"] is None:
        lines.append("  spray-gap: n/a (one split has no confirm_sent rows)")
    else:
        lines.append(
            f"  spray-gap (aligned minus raw): "
            f"{pack['spray_gap_pp']:+.1f}pp — a widening positive gap is the "
            f"manufactured-row signature (doc section 6)"
        )
    lines += [
        "",
        "REMINDER LIFT",
        f"  confirmed via reminder / reminder_sent: {ratio(rem_n, rem_d)}",
        "",
        "INVITE -> CLAIM",
        f"  claimed / invite_sent: {ratio(inv_claimed, inv_sent)}; "
        f"median invite->claim: {fmt_hours(inv_med)}",
        "",
        "SUBMIT -> CONFIRM LATENCY",
        f"  median waitlist_submitted->confirmed: "
        f"{fmt_hours(pack['submit_confirm_median_hours'])}",
        "",
        "BRIDGE (kept visible, never folded into the page metric)",
    ]
    bridge_n, bridge_d = pack["bridge"]
    if pack["bridge_instrumented"]:
        lines.append(
            f"  identity-linked / confirmed waitlist entries: "
            f"{ratio(bridge_n, bridge_d)}"
        )
    else:
        lines.append(
            "  not instrumented yet: no signup_started/identity_linked events "
            "in the store — the waitlist->identity-linked drop-off becomes "
            "measurable when the signup build lands its events"
        )
    lines += [
        "",
        "SHARE-SIGNAL (excluded from the primary denominator by construction)",
        f"  crawler_hits in window: {pack['crawler_hits']}",
    ]
    return "\n".join(lines) + "\n"


def default_window(today):
    until = today
    return until - timedelta(days=6), until


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Day-1 operator funnel query pack "
        "(docs/FUNNEL_MEASUREMENT.md section 7)."
    )
    parser.add_argument(
        "--events",
        required=True,
        help="JSONL export of the funnel_events table (one row per line).",
    )
    parser.add_argument(
        "--since", help="window start (YYYY-MM-DD, inclusive). Default: 7 days ago."
    )
    parser.add_argument(
        "--until", help="window end (YYYY-MM-DD, inclusive). Default: today (UTC)."
    )
    args = parser.parse_args(argv)

    try:
        until = date.fromisoformat(args.until) if args.until else date.today()
    except ValueError:
        print(f"error: --until is not a date: {args.until!r}", file=sys.stderr)
        return 2
    try:
        since = date.fromisoformat(args.since) if args.since else default_window(until)[0]
    except ValueError:
        print(f"error: --since is not a date: {args.since!r}", file=sys.stderr)
        return 2
    if since > until:
        print("error: --since is after --until", file=sys.stderr)
        return 2

    try:
        rows = load_events(args.events)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        pack = compute(rows, since, until)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(report(pack))
    return 0


if __name__ == "__main__":
    sys.exit(main())

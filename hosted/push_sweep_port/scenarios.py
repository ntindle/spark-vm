"""Scenario definitions for the D9 sweep D-PP-2 conformance set (#1566 S2).

Each scenario is a dict:

    {
      "name": str,                       # also the recorded file stem
      "doc": str,                        # what the scenario pins
      "build": fn(conn) -> spec,         # create the fixture DB state
    }

The spec returned by ``build``:

    {
      "now_epoch": int,                  # pinned sweep clock (D73)
      "registry": {box_id: owner},       # resolve_owner mapping (D2)
      "derive_stale": [(box_id, epoch)] | None,
      "derive_token_warnings": [(box_id, token_hash)] | None,
      "sweep_kwargs": {...},             # extra sweep_once kwargs
      "record_adapter": fn | None,       # two-arg (box_id, aid) adapter
    }

The DDL below is the #988 contract tables plus the D57 partial unique
index plus the `approvals` fixture pinning the #872 record shape — the
same DDL `hosted/test_push_sweep.py` uses. Fixtures are scenario DBs,
not the live database: no fixture reads or writes outside its own
in-memory database.
"""

from datetime import datetime, timedelta, timezone

from hosted import push_enqueue, push_sweep

T0 = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
EPOCH_T0 = int(T0.timestamp())

DDL = """
CREATE TABLE approvals (
  box_id       TEXT NOT NULL,
  aid          TEXT NOT NULL,
  owner_id     TEXT NOT NULL,
  summary      TEXT NOT NULL,
  detail       TEXT,
  status       TEXT NOT NULL,
  decision     TEXT,
  decision_seq INTEGER,
  decided_by   TEXT,
  decided_at   REAL,
  created_at   INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  PRIMARY KEY (box_id, aid)
);
CREATE TABLE IF NOT EXISTS push_budget_counters (
  scope_type   TEXT NOT NULL,
  scope_id     TEXT NOT NULL,
  window_start TEXT NOT NULL,
  count        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_type, scope_id, window_start)
);
CREATE TABLE IF NOT EXISTS push_send_results (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL,
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  event_kind      TEXT NOT NULL,
  event_key       TEXT NOT NULL,
  outcome         TEXT NOT NULL,
  http_status     INTEGER,
  latency_ms      REAL,
  sent_at         REAL,
  vapid_key_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_send_results_dedup
  ON push_send_results(box_id, event_kind, event_key);
CREATE INDEX IF NOT EXISTS idx_push_send_results_tenant
  ON push_send_results(owner_principal, at);
CREATE TABLE IF NOT EXISTS push_digest_state (
  owner_principal TEXT NOT NULL,
  window_start    TEXT NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  enqueued_at     TEXT,
  PRIMARY KEY (owner_principal, window_start)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
  ON push_send_results(box_id, event_kind, event_key)
  WHERE outcome IN ('queued', 'suppressed_budget', 'suppressed_terminal');
"""


def new_db():
    """A fresh in-memory fixture database with the DDL applied."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    return conn


def file_approval(conn, box_id, aid, *, ttl, age, status="pending",
                  decision=None, decision_seq=None, owner="owner-1"):
    """File one #872-shaped approval; times are offsets from the pinned T0."""
    created = EPOCH_T0 - age
    conn.execute(
        "INSERT INTO approvals (box_id, aid, owner_id, summary, status,"
        " decision, decision_seq, created_at, expires_at)"
        " VALUES (?, ?, ?, 's', ?, ?, ?, ?, ?)",
        (box_id, aid, owner, status, decision, decision_seq,
         created, created + ttl))
    conn.commit()


def registry(mapping):
    """A D2 registry resolver over a fixed mapping (never a box assertion)."""
    def resolve_owner(box_id):
        return mapping[box_id]

    return resolve_owner


def derive(items):
    """Wrap a fixed item list as a sweep watcher derivation."""
    def _derive(conn, moment):
        return iter(list(items))

    return _derive


def base_spec(**overrides):
    """The default spec: pinned clock, no watchers, no extra kwargs."""
    spec = {
        "now_epoch": EPOCH_T0,
        "registry": {"box-a": "owner-1"},
        "derive_stale": None,
        "derive_token_warnings": None,
        "derive_stale_raiser": False,
        "sweep_kwargs": {},
        "record_adapter": None,
    }
    spec.update(overrides)
    return spec


def insert_result_row(conn, *, at, owner_principal, box_id, device,
                      event_kind, event_key, outcome):
    """Pre-insert one push_send_results row (the post-prior-sweep state)."""
    conn.execute(
        "INSERT INTO push_send_results"
        " (at, owner_principal, box_id, device, event_kind, event_key,"
        "  outcome, http_status, latency_ms, sent_at, vapid_key_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)",
        (at, owner_principal, box_id, device, event_kind, event_key,
         outcome))
    conn.commit()


def set_budget(conn, scope_type, scope_id, window_start, count):
    """Pre-fill a budget counter (the at-bound / mid-window state)."""
    conn.execute(
        "INSERT INTO push_budget_counters"
        " (scope_type, scope_id, window_start, count)"
        " VALUES (?, ?, ?, ?)",
        (scope_type, scope_id, window_start, count))
    conn.commit()


# --- scenario builders ------------------------------------------------


def build_reminder_due(conn):
    """One due reminder: created 400s ago, 600s TTL — past the D8 half."""
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    return base_spec()


def build_reminder_terminal_clock(conn):
    """Pending approval terminal by the clock only (expires_at < now).

    The D68 hint still selects it (it is pending and undecided); gate-1
    finds the record terminal and writes exactly one idempotent D61
    `suppressed_terminal` audit row — no page, ever.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=900)
    return base_spec()


def build_reminder_decided(conn):
    """A decided approval is never a candidate: zero pages, zero audits."""
    file_approval(conn, "box-a", "r1", ttl=600, age=400, status="approved",
                  decision="approve", decision_seq=1)
    return base_spec()


def build_digest_pending(conn):
    """One pending digest window (count > 0, enqueued_at NULL)."""
    window = push_enqueue.hour_bucket(T0)
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start, count)"
        " VALUES (?, ?, ?)",
        ("owner-1", window, 3))
    conn.commit()
    return base_spec()


def build_reminders_disabled(conn):
    """reminders_enabled=False: the reminder pass reports skipped, the
    digest pass still fires — the D71 retirement shape."""
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    window = push_enqueue.hour_bucket(T0)
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start, count)"
        " VALUES (?, ?, ?)",
        ("owner-1", window, 3))
    conn.commit()
    return base_spec(sweep_kwargs={"reminders_enabled": False})


def build_watchers_wired(conn):
    """Both cadence-driven watchers wired with deterministic derivations."""
    return base_spec(
        derive_stale=[("box-a", "epoch-5")],
        derive_token_warnings=[("box-a", "th-1")],
    )


def build_poisoned_candidate(conn):
    """Two due reminders; the adapter raises for one of them.

    The raising candidate is counted `poisoned` and skipped (D78) — the
    pass continues and the healthy candidate still pages.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    file_approval(conn, "box-a", "r2", ttl=600, age=400)
    real = push_sweep.make_record_adapter(conn, EPOCH_T0)

    def adapter(box_id, aid):
        if aid == "r2":
            raise RuntimeError("fixture poison: r2's record is corrupt")
        return real(box_id, aid)

    return base_spec(record_adapter=adapter)


def build_budget_already_exhausted(conn):
    """time_budget_s=0: every pass sees an already-spent budget.

    Deterministic (no wall-clock race): the deadline is computed as
    tick_start + 0, so the first check already reports exhausted. Pins
    the D103 fail-closed shape — passes stop before any candidate, the
    summary reports budget_truncated, and everything stays due.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    return base_spec(
        sweep_kwargs={"time_budget_s": 0},
        derive_stale=[("box-a", "epoch-5")],
    )


def build_reminder_already_paged(conn):
    """A due reminder whose page row already exists (D75 anti-join).

    The post-first-sweep state: the page went out on an earlier tick.
    The hint's anti-join must exclude it — the candidate is never
    re-selected, the policy's duplicate path is never even reached,
    and a truncated sweep's remainder is actually reached next tick.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    key = push_enqueue.event_key_for("reminder", "owner-1", "box-a", "r1")
    insert_result_row(
        conn, at=T0.isoformat(), owner_principal="owner-1", box_id="box-a",
        device="", event_kind="reminder", event_key=key,
        outcome="queued")
    return base_spec()


def build_multi_owner_isolation(conn):
    """Two owners, two boxes: pages, digests, and budgets stay per-owner.

    Tenant isolation is the central hosted-product risk a port could
    silently break while staying "conformant" on single-owner fixtures:
    every queued page, digest row, and budget counter must be scoped to
    its own owner.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400, owner="owner-1")
    file_approval(conn, "box-b", "r2", ttl=600, age=400, owner="owner-2")
    window = push_enqueue.hour_bucket(T0)
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start, count)"
        " VALUES (?, ?, ?)",
        ("owner-2", window, 2))
    conn.commit()
    return base_spec(registry={"box-a": "owner-1", "box-b": "owner-2"})


def build_reminders_truncated(conn):
    """Small page cap: the pass stops at max_pages and reports it (D69).

    Keyset pagination is ordered by (box_id, aid): r1 and r2 page, r3
    stays due for the next tick, and `pages_truncated` is the operator
    alert (distinct from the D103 time-budget stop).
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    file_approval(conn, "box-a", "r2", ttl=600, age=400)
    file_approval(conn, "box-a", "r3", ttl=600, age=400)
    return base_spec(sweep_kwargs={"page_size": 2, "max_pages": 1})


def build_digests_truncated(conn):
    """Small window cap: the digest pass stops at max_windows (D1383).

    Three pending windows, oldest first: the first two fire, the third
    stays pending for the next tick, and `digests_truncated` is the
    operator alert — behavior-preserving, never a skip.
    """
    for hours_ago in (2, 1, 0):
        moment = T0 - timedelta(hours=hours_ago)
        window = push_enqueue.hour_bucket(moment)
        conn.execute(
            "INSERT INTO push_digest_state"
            " (owner_principal, window_start, count)"
            " VALUES (?, ?, ?)",
            ("owner-1", window, 2))
    conn.commit()
    return base_spec(sweep_kwargs={"max_windows": 2})


def build_reminder_over_budget(conn):
    """A due reminder with both budget scopes at bound (D10/D54).

    The reminder is suppressed (no page, no budget consumed) and
    coalesces into the digest (count+1, enqueued_at NULL); the same
    sweep's digest pass then attempts the window and is itself
    suppressed at the owner bound — its suppression audit carries the
    U+0000 "suppressed" suffix (D77), never the exact page key.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    window = push_enqueue.hour_bucket(T0)
    set_budget(conn, "box", "box-a", window,
               push_enqueue.BOX_BOUND_DEFAULT)
    set_budget(conn, "owner", "owner-1", window,
               push_enqueue.OWNER_BOUND_DEFAULT)
    return base_spec()


def build_digest_over_budget(conn):
    """A pending digest window with the owner budget at bound (D77).

    The digest is suppressed — no page, `enqueued_at` stays NULL so a
    later sweep retries, and the suppression audit row (suffixed key)
    is the record. The window must stay retryable, never wedged.
    """
    window = push_enqueue.hour_bucket(T0)
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start, count)"
        " VALUES (?, ?, ?)",
        ("owner-1", window, 4))
    conn.commit()
    set_budget(conn, "owner", "owner-1", window,
               push_enqueue.OWNER_BOUND_DEFAULT)
    return base_spec()


def build_stale_epoch_quiet(conn):
    """A new stale epoch within 4h of the last stale page (F7/D62).

    The pre-inserted `accepted` row (a delivered page, not just a
    queued work item) arms the quiet window: the new epoch is
    suppressed with no row written and no budget consumed.
    """
    key = push_enqueue.event_key_for(
        "heartbeat_stale", "owner-1", "box-a", "epoch-4")
    insert_result_row(
        conn, at=(T0 - timedelta(hours=1)).isoformat(),
        owner_principal="owner-1", box_id="box-a", device="",
        event_kind="heartbeat_stale", event_key=key, outcome="accepted")
    return base_spec(derive_stale=[("box-a", "epoch-5")])


def build_reminder_terminal_clock_replay(conn):
    """The D61 audit replayed: the audit row already exists (D61).

    The post-first-sweep state for a clock-terminal approval. The
    gate-1 SELECT fast-path finds the existing audit row, writes
    nothing, and the terminal approval accrues exactly one audit row
    no matter how many overlapping sweeps observe it.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=900)
    page_key = push_enqueue.event_key_for(
        "reminder", "owner-1", "box-a", "r1")
    insert_result_row(
        conn, at=(T0 - timedelta(minutes=30)).isoformat(),
        owner_principal="owner-1", box_id="box-a", device="",
        event_kind="reminder", event_key=page_key + "\x00superseded",
        outcome="suppressed_terminal")
    return base_spec()


def build_derivation_poisoned(conn):
    """A derivation that raises at call time (D78, watcher level).

    The stale watcher is counted `poisoned` once and stops; the token
    watcher still runs — a derivation failure stops only its own
    watcher, never the whole sweep.
    """
    return base_spec(derive_stale_raiser=True,
                     derive_token_warnings=[("box-a", "th-1")])


def build_reminder_mid_transition(conn):
    """A pending approval with decision_seq set is never a candidate.

    The D68 hint's `decision_seq IS NULL` predicate excludes the
    mid-transition row (decision recorded, not yet consumed): it is
    not counted in candidates_seen and produces no disposition.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400,
                  decision="approve", decision_seq=1)
    return base_spec()


def build_reminders_multi_page(conn):
    """Keyset pagination advances across pages (D69).

    Three due reminders with page_size=2, max_pages=2: the first page
    takes r1+r2, the keyset predicate advances past them, the second
    page takes r3 — pages_truncated stays False and all three page.
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=400)
    file_approval(conn, "box-a", "r2", ttl=600, age=400)
    file_approval(conn, "box-a", "r3", ttl=600, age=400)
    return base_spec(sweep_kwargs={"page_size": 2, "max_pages": 2})


def build_digest_already_enqueued(conn):
    """A digest window with enqueued_at set never re-fires (D76).

    The pending-window scan's `enqueued_at IS NULL` predicate skips the
    already-fired window: zero dispositions, the row untouched.
    """
    window = push_enqueue.hour_bucket(T0)
    conn.execute(
        "INSERT INTO push_digest_state (owner_principal, window_start,"
        " count, enqueued_at) VALUES (?, ?, ?, ?)",
        ("owner-1", window, 3, "2026-10-05T11:00:00+00:00"))
    conn.commit()
    return base_spec()


def build_d8_ttl_boundary(conn):
    """The D8 TTL bound: ttl=200 never a candidate, ttl=400 pages (300 bound).

    The hint's `(expires_at - created_at) >= 300` predicate and the
    policy's gate agree on the bound (#1507): the short-TTL approval
    is not counted in candidates_seen and produces nothing; the
    400s-TTL approval is due and pages exactly once.
    """
    file_approval(conn, "box-a", "short", ttl=200, age=150)
    file_approval(conn, "box-a", "r1", ttl=400, age=300)
    return base_spec()


def build_reminders_poisoned_multi_page(conn):
    """Keyset pagination under poison, with cross-box aid ordering
    (D68/D69/D78).

    Three due approvals across three boxes, aids chosen to cross box
    order (box-a/r3, box-b/r1, box-c/r2), at page_size=1/max_pages=3.
    With the keyset predicate the sweep pages (box-a,r3) → (box-b,r1)
    → (box-c,r2); r1's record read poisons (D78) and the healthy
    candidates still page — {queued: 2, poisoned: 1}, candidates_seen=3.
    Dropping the keyset predicate re-selects (box-a,r3) on page 2,
    which the D75 anti-join masks (empty page → break), so r1/r2 are
    never reached: {queued: 1}, candidates_seen=1. Flipping the ORDER
    BY changes the page order, which shows up in push_send_results'
    id order even when the disposition set is identical.
    """
    file_approval(conn, "box-a", "r3", ttl=600, age=400, owner="owner-1")
    file_approval(conn, "box-b", "r1", ttl=600, age=400, owner="owner-2")
    file_approval(conn, "box-c", "r2", ttl=600, age=400, owner="owner-3")
    real = push_sweep.make_record_adapter(conn, EPOCH_T0)

    def adapter(box_id, aid):
        if aid == "r1":
            raise RuntimeError("fixture poison: r1's record is corrupt")
        return real(box_id, aid)

    return base_spec(
        record_adapter=adapter,
        sweep_kwargs={"page_size": 1, "max_pages": 3},
        registry={"box-a": "owner-1", "box-b": "owner-2",
                  "box-c": "owner-3"})


def build_d68_half_ttl_boundary(conn):
    """The half-TTL hint predicate's exclusion direction (D68).

    ttl=600, age=100: due under the ttl>=300 (D8) predicate but
    excluded by the half-TTL hint predicate (`age >= ttl/2` required,
    100 < 300). The point of this scenario is the HINT's exclusion:
    a port that drops the half-TTL predicate selects the candidate,
    the policy gate then reports not-due, and the summary stops
    matching the record (candidates_seen=0, empty reminder map).
    """
    file_approval(conn, "box-a", "r1", ttl=600, age=100)
    return base_spec()


SCENARIOS = [
    {"name": "reminder_due",
     "doc": "One due reminder produces exactly one queued page.",
     "build": build_reminder_due},
    {"name": "reminder_terminal_clock",
     "doc": "A clock-terminal pending approval writes exactly one "
            "idempotent suppressed_terminal audit row — no page.",
     "build": build_reminder_terminal_clock},
    {"name": "reminder_decided",
     "doc": "A decided approval is never a candidate: zero pages, "
            "zero audit rows.",
     "build": build_reminder_decided},
    {"name": "digest_pending",
     "doc": "A pending digest window fires one digest page and stamps "
            "enqueued_at.",
     "build": build_digest_pending},
    {"name": "reminders_disabled",
     "doc": "reminders_enabled=False: reminder pass skipped, digest "
            "pass unaffected (the D71 retirement shape).",
     "build": build_reminders_disabled},
    {"name": "watchers_wired",
     "doc": "Both watcher derivations wired: one stale page and one "
            "token-expiry warning page.",
     "build": build_watchers_wired},
    {"name": "poisoned_candidate",
     "doc": "A raising candidate is counted poisoned and skipped; the "
            "healthy candidate still pages (D78).",
     "build": build_poisoned_candidate},
    {"name": "budget_already_exhausted",
     "doc": "time_budget_s=0: every pass stops before any candidate; "
            "the summary reports budget_truncated (D103).",
     "build": build_budget_already_exhausted},
    {"name": "reminder_already_paged",
     "doc": "A due reminder whose page row already exists is anti-joined "
            "out of the hint: never re-selected, zero new rows (D75).",
     "build": build_reminder_already_paged},
    {"name": "multi_owner_isolation",
     "doc": "Two owners, two boxes: every page, digest row, and budget "
            "counter stays scoped to its own owner (tenant isolation).",
     "build": build_multi_owner_isolation},
    {"name": "reminders_truncated",
     "doc": "page_size=2, max_pages=1: the pass pages r1+r2, r3 stays "
            "due, pages_truncated is the operator alert (D69).",
     "build": build_reminders_truncated},
    {"name": "digests_truncated",
     "doc": "max_windows=2 over three pending windows: two fire, one "
            "stays pending, digests_truncated is the operator alert "
            "(D1383).",
     "build": build_digests_truncated},
    {"name": "reminder_over_budget",
     "doc": "Both budget scopes at bound: the reminder is suppressed "
            "and coalesces into the digest; the same sweep's digest "
            "attempt is suppressed with the suffixed audit key (D10, "
            "D54, D77).",
     "build": build_reminder_over_budget},
    {"name": "digest_over_budget",
     "doc": "Pending digest window with the owner budget at bound: "
            "suppressed, enqueued_at stays NULL, the window stays "
            "retryable (D77).",
     "build": build_digest_over_budget},
    {"name": "stale_epoch_quiet",
     "doc": "A new stale epoch within 4h of the last stale page: "
            "suppressed_quiet_period, no row, no budget (F7/D62).",
     "build": build_stale_epoch_quiet},
    {"name": "reminder_terminal_clock_replay",
     "doc": "The D61 audit row already exists: gate-1 writes nothing, "
            "the terminal approval accrues exactly one audit row (D61).",
     "build": build_reminder_terminal_clock_replay},
    {"name": "derivation_poisoned",
     "doc": "The stale derivation raises at call time: counted "
            "poisoned once, the token watcher still runs (D78).",
     "build": build_derivation_poisoned},
    {"name": "reminder_mid_transition",
     "doc": "A pending approval with decision_seq set is never a "
            "candidate: not counted, no disposition (D68).",
     "build": build_reminder_mid_transition},
    {"name": "reminders_multi_page",
     "doc": "Three due reminders, page_size=2, max_pages=2: the keyset "
            "predicate advances, all three page, pages_truncated stays "
            "False (D69).",
     "build": build_reminders_multi_page},
    {"name": "digest_already_enqueued",
     "doc": "A digest window with enqueued_at set never re-fires: zero "
            "dispositions, the row untouched (D76).",
     "build": build_digest_already_enqueued},
    {"name": "d8_ttl_boundary",
     "doc": "ttl=200 never a candidate, ttl=400 pages exactly once — the "
            "hint and the gate agree on the 300s bound (D8, #1507).",
     "build": build_d8_ttl_boundary},
    {"name": "reminders_poisoned_multi_page",
     "doc": "Keyset pagination under poison with cross-box aid ordering: "
            "three pages in (box,a) order, one poisoned, the rest page "
            "(D68/D69/D78).",
     "build": build_reminders_poisoned_multi_page},
    {"name": "d68_half_ttl_boundary",
     "doc": "ttl=600, age=100 is excluded by the half-TTL hint "
            "predicate: zero candidates, zero dispositions (D68).",
     "build": build_d68_half_ttl_boundary},
]


def scenario_names():
    """The fixture names, in canonical order."""
    return [s["name"] for s in SCENARIOS]

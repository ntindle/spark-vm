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

from datetime import datetime, timezone

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
        "sweep_kwargs": {},
        "record_adapter": None,
    }
    spec.update(overrides)
    return spec


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
]


def scenario_names():
    """The fixture names, in canonical order."""
    return [s["name"] for s in SCENARIOS]

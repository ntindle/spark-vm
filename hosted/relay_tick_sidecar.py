"""Shared tick-sidecar observability for the relay-liveness drivers.

Extracted (behavior-identical) from ``hosted/relay_auto_driver.py`` (S1):
the watermark-sidecar read-modify-write, the journal-note append, and
the note-scrub the S1 auto-driver and the S5 probe driver
(``hosted/relay_probe_driver.py``, issue #1725) both need.

Public surface on purpose: the S5 module uses these directly, and the
loop's review precedent is "never reach into underscore helpers"
(the 20261020-1159 turn). ``relay_auto_driver`` keeps underscore
aliases so its test suite (which reaches the old private names)
passes unchanged.

Stdlib-only. The lock/symlink discipline is unchanged: a pre-planted
symlink at the sidecar or lock path raises ``OSError`` with
``errno.ELOOP`` loud (#1741); corrupt sidecar content restarts from
empty with the fail-visible note (D-AC-7).
"""

import errno
import json
import os
import tempfile
import unicodedata
from datetime import datetime, timezone
from typing import Optional

try:
    import fcntl
except ImportError:  # non-Linux platforms; the estate is Linux
    fcntl = None


def now_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def scrub_note(text: str) -> str:
    """Strip control and invisible-format characters from a journal note.

    The only characters that survive are ``\\n``/``\\t`` (which the
    journal format uses) and text whose Unicode category is none of
    the spoofing classes:
    - Cc (controls): C0, DEL, AND the C1 controls U+0080-U+009F.
      The pre-#1738 scrub kept C1 (``ord() >= 0x20``); C1 CSI
      (U+009B) is a live terminal-escape introducer on ECMA-48
      terminals, so "terminal-escape injection is handled" was only
      true for the 7-bit ESC encoding — the whole Cc class goes now.
    - Cf (format): bidi overrides U+202A-U+202E, isolates
      U+2066-U+2069, zero-width controls U+200B-U+200D, BOM U+FEFF,
      and the rest of the class (soft hyphen, interlinear annotation
      anchors, ...). These reorder or hide displayed text for anyone
      rendering the journal (fleet console, status feed) — a
      display-layer spoofing primitive (issue #1738). Deliberate
      over-scrub: Cf also holds legitimate RTL controls (LRM/RLM
      U+200E/U+200F, ARABIC LETTER MARK U+061C, ...) — acceptable
      because tick notes are machine-generated English, and a future
      RTL-text use must not "fix" this back without a threat review.
    - Zl/Zp (line/paragraph separators U+2028/U+2029): line
      terminators on JS-rendered surfaces (status feed, React
      console) — a hostile note could forge extra journal lines or
      split an alert line.
    - Cs (surrogates): a lone surrogate is never valid text —
      ``str.encode('utf-8')`` raises ``UnicodeEncodeError``, so any
      non-escaping writer or cross-language consumer (e.g. the future
      S2-port side) would choke; the scrub removes them rather than
      trusting every downstream writer to escape.
    - Mn variation selectors U+FE00-U+FE0F / U+E0100-U+E01EF (#1776):
      invisible code points that alter adjacent-text presentation,
      and they are Mn — not Cf — so the category predicate cannot
      catch them; dropped by explicit range instead (other Mn, like
      combining diacritics, stay).
    Side effect to know: ZWJ (U+200D) stripping splits multi-person
    emoji into separate glyphs — acceptable for a plain-text security
    journal. Fail-closed typing: non-str input is stringified, never
    dropped.
    """
    if not isinstance(text, str):
        text = str(text)
    return "".join(ch for ch in text if _scrub_keep(ch))


def _is_variation_selector(ch: str) -> bool:
    """True for the two Unicode variation-selector ranges.

    U+FE00-U+FE0F (VS1-VS16) and U+E0100-U+E01EF (VS17-VS256) are
    category Mn, not Cf, so the category-based :func:`_scrub_keep`
    cannot catch them — yet they are invisible code points that alter
    the presentation of adjacent text in the journal (the #1776 class).
    Range-exact, never class-wide: other Mn (combining diacritics) stay.
    """
    o = ord(ch)
    return 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF


def _scrub_keep(ch: str) -> bool:
    """Keep predicate for :func:`scrub_note`: the two legitimate
    controls, plus text in none of the spoofing classes (Cc, Cf, Cs,
    Zl, Zp) and outside the Mn variation-selector ranges (U+FE00-U+FE0F,
    U+E0100-U+E01EF — #1776: Mn, not Cf, so the class scrub misses
    them). Purely category-based otherwise — no ord() cutoffs, so the
    whole Cc class (C0, DEL, C1) is covered."""
    if ch in ("\n", "\t"):
        return True
    if _is_variation_selector(ch):
        return False
    return unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Zl", "Zp")


def atomic_write_json_0600(path: str, obj: dict) -> None:
    """Write *obj* as JSON to *path* atomically, mode 0600.

    Temp file (O_EXCL via mkstemp, 0600 by construction) + fsync +
    os.replace. A symlink AT the destination fails loud instead of
    redirecting the watermark into an arbitrary file.
    """
    if os.path.islink(path):
        raise OSError("refusing to write through symlink: %r" % (path,))
    parent = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".tmp-relay-ticks-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _open_sidecar_lock(lock_path: str):
    """Open the watermark sidecar lock without following symlinks.

    The lock serializes the sidecar's read-modify-write across
    processes. A pre-planted symlink at the lock path would silently
    move the flock onto another file (lock-desync across sweep
    processes, or a lock-DoS via a permanently-held lock) — the same
    plant class the gate lane pins O_NOFOLLOW for (#1720). O_NOFOLLOW
    refuses the plant loudly (ELOOP); the caller's observability
    handler turns that into a LOUD record, never a silent wedge.
    """
    flags = os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    try:
        return os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise


def _read_sidecar_nofollow(path: str) -> dict:
    """Read the JSON sidecar without following symlinks (#1741).

    The write path (``atomic_write_json_0600``) refuses a symlink at the
    destination loudly; the read pins the same discipline so a
    pre-planted symlink cannot influence which bytes feed the
    read-modify-write merge. O_NOFOLLOW refuses the plant with ELOOP
    (fail-loud); a missing file is still FileNotFoundError (the normal
    first run).
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fh = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with fh:
        return json.load(fh)


# D-AC-7 fail-visible text for a corrupt/unparseable watermark sidecar.
# Hoisted so the pre-loop hint path and the bulk-write path note the
# identical bytes (a drift between the two would fork the operator's
# reading of "history was lost").
CORRUPT_SIDECAR_LOUD = (
    "LOUD: watermark sidecar was corrupt/unparseable — "
    "restarted from empty; prior per-tenant last-tick "
    "history lost, staleness self-heals from this tick"
)


def read_sidecar_marks(path: str):
    """Read half of the watermark sidecar read-modify-write.

    Returns ``(marks, corrupt)``: the parsed sidecar dict — or ``{}``
    when the file is missing, unparseable, or holds non-dict
    per-tenant values (D-AC-11: valid JSON with garbage values is the
    same corruption class as unparseable content) — and whether the
    content was corrupt/unparseable-or-schema-invalid. A missing file
    is the normal first run, NOT corruption (no history exists to
    lose). A symlink at the sidecar path raises ``OSError`` with
    ``errno.ELOOP`` loud (#1741): a plant is never restarted-from-empty
    over.

    Feeds the sweep-level bulk write (``write_sidecar_bulk``) — #1739
    collapsed N per-tenant read-modify-writes per sweep into one, and
    the pre-loop hint read and the locked merge must agree on what
    "corrupt" means.
    """
    try:
        marks = _read_sidecar_nofollow(path)
        if not isinstance(marks, dict):
            raise ValueError("sidecar content is not a JSON object")
        # #1843 / D-AC-11: valid JSON whose per-tenant values are not
        # record dicts (garbage-but-valid JSON) is the same corruption
        # class as unparseable content. A garbage value cannot feed the
        # S4 staleness rule or ride the merge as ground truth — so the
        # sidecar restarts from empty, fail-visible per D-AC-7 (the LOUD
        # note fires on the corrupt=True path). The check is "is it a
        # dict", deliberately not a field whitelist: records gain fields
        # over time and the read must not reject a newer writer's shape.
        for tenant_id, value in marks.items():
            if not isinstance(value, dict):
                raise ValueError(
                    "sidecar value for tenant %r is not a record dict"
                    % (tenant_id,)
                )
    except FileNotFoundError:
        # Normal first run: no history to lose, nothing to say.
        return {}, False
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            # #1741: symlink plant — refuse loud, like the write path.
            # A plant must never be restarted from empty over (that
            # would silently discard the evidence of the plant). errno
            # is preserved so a handler can distinguish a plant from a
            # disk error programmatically.
            raise OSError(
                errno.ELOOP,
                "refusing to read watermark through symlink: %r"
                % (path,),
            ) from exc
        # Corrupt/unreadable content: restart from empty, but
        # fail-visible per D-AC-7 — the caller notes it LOUD.
        return {}, True
    except ValueError:
        # Corrupt/unreadable content (incl. JSONDecodeError, which is a
        # ValueError): restart from empty, fail-visible per D-AC-7.
        return {}, True
    return marks, False


def write_sidecar_bulk(path: str, records: dict, corrupt_note=None,
                          already_noted=False) -> bool:
    """One read-modify-write of the watermark sidecar for a whole sweep.

    ``records`` maps tenant_id -> record; every entry merges over the
    freshly-read sidecar in a SINGLE locked read-modify-write. #1739:
    the old per-tenant ``_update_watermark`` re-read the ENTIRE sidecar
    JSON and rewrote it atomically for every tenant, so one sweep over
    N tenants was N full read-modify-write cycles of a file holding N
    records — O(N^2) JSON IO on the probe cadence. This is O(N).

    Returns True when the sidecar was corrupt (unparseable or
    schema-invalid per-tenant values, D-AC-11) and history
    restarted from empty (D-AC-7 fail-visible — the caller notes it
    LOUD); a missing file is the normal first run, not corruption.
    A symlink plant raises ``OSError`` with ``errno.ELOOP`` loud
    (#1741).

    ``corrupt_note`` / ``already_noted`` serve the mid-sweep-corruption
    path: when the fresh read inside this RMW finds a corrupt sidecar
    that the caller had NOT already noted (``already_noted=False``),
    the note is appended to every record INSIDE the locked RMW, before
    the merge — so it lands in the sidecar, not just the caller's
    in-memory copies. (Appending after the write returns cannot reach
    the disk; a past revision did exactly that and the comment lied
    about it.)

    The lock is held only for this read-modify-write — never across the
    sweep's drive phase — so a slow tenant cannot wedge a concurrent
    sweeper's observability, and the fresh locked read means a
    concurrent sweeper's records are merged, never lost.
    """
    lock_path = path + ".lock"
    with _open_sidecar_lock(lock_path) as lf:
        if fcntl is not None:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            marks, corrupt = read_sidecar_marks(path)
            if corrupt and not already_noted and corrupt_note is not None:
                for rec in records.values():
                    rec["notes"].append(corrupt_note)
            marks.update(records)
            atomic_write_json_0600(path, marks)
        finally:
            if fcntl is not None:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    return corrupt



def append_journal_note(journal_store_dir: str, event: dict) -> Optional[str]:
    """Append one tick-note event to the fleet event journal.

    Returns an error string (not raised): the watermark is the primary
    S4 input, the journal is secondary — a wedged journal must not
    wedge the wiring sweep. The fleet ``events`` module is imported
    lazily so this module stays import-light; it is stdlib-only, so
    the import never leaves the stdlib boundary.
    """
    try:
        from fleet import events as fleet_events

        _, _, err = fleet_events.append_events(journal_store_dir, [event])
        return err
    except Exception as exc:  # noqa: BLE001 — journal is secondary
        return "journal append failed: %s: %s" % (type(exc).__name__, exc)



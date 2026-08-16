"""Checkpoint retention sweep — SQLite growth is unbounded otherwise (every
node execution writes a checkpoint row; PLAN.md's Architecture section has
measured numbers). Piggybacks on every completed request instead of running
as a separate process — Cloud Run's min-instances=0 means there's no
long-lived process to host a real scheduler — gated by a timestamp stored
in the same DB so the actual sweep runs at most once per MIN_INTERVAL
regardless of request volume.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

RETENTION = timedelta(days=5)
MIN_INTERVAL = timedelta(hours=48)


def _ensure_meta_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS cleanup_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()


def _last_cleanup_at(conn: sqlite3.Connection) -> datetime | None:
    row = conn.execute("SELECT value FROM cleanup_meta WHERE key = 'last_cleanup_at'").fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def _set_last_cleanup_at(conn: sqlite3.Connection, when: datetime) -> None:
    conn.execute(
        "INSERT INTO cleanup_meta (key, value) VALUES ('last_cleanup_at', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (when.isoformat(),),
    )
    conn.commit()


def maybe_cleanup(conn: sqlite3.Connection, checkpointer) -> int:
    """Runs the retention sweep only if it hasn't run in MIN_INTERVAL.
    Deletes threads (all checkpoints + writes) whose most recent checkpoint
    is older than RETENTION. Returns the number of threads deleted (0 if
    skipped or nothing qualified)."""
    _ensure_meta_table(conn)
    now = datetime.now(timezone.utc)
    last = _last_cleanup_at(conn)
    if last is not None and now - last < MIN_INTERVAL:
        return 0

    cutoff = now - RETENTION
    deleted = 0
    thread_ids = [row[0] for row in conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()]
    for thread_id in thread_ids:
        tup = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
        if tup is None:
            continue
        ts = datetime.fromisoformat(tup.checkpoint["ts"])
        if ts < cutoff:
            checkpointer.delete_thread(thread_id)
            deleted += 1

    _set_last_cleanup_at(conn, now)
    return deleted

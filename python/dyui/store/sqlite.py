"""SQLite store (the default): stdlib ``sqlite3`` in WAL mode, run off-loop.

Every operation runs in a worker thread via :func:`asyncio.to_thread`,
serialized by a lock over one connection. Schema changes are applied through
numbered migrations recorded in ``dyui_migrations``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

from .base import DEFAULT_TITLE, now_ms

__all__ = ["SQLiteStore", "MIGRATIONS"]

log = logging.getLogger("dyui")
T = TypeVar("T")

MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            """CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                title_locked INTEGER NOT NULL DEFAULT 0,
                session TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )""",
            "CREATE INDEX threads_user_updated ON threads(user_id, updated_at DESC)",
            """CREATE TABLE messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                data TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )""",
            "CREATE INDEX messages_thread_seq ON messages(thread_id, seq)",
            """CREATE TABLE files (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                size INTEGER NOT NULL,
                path TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )""",
        ],
    ),
]
"""Ordered schema migrations: ``(version, [sql, ...])``."""


class SQLiteStore:
    """A :class:`~dyui.store.Store` backed by a SQLite file.

    Args:
        path: Database file path (parent directories are created on first use).
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    # ---------------------------------------------------------- plumbing
    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._migrate(conn)
            self._conn = conn
        return self._conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS dyui_migrations (version INTEGER PRIMARY KEY, applied_at INTEGER)")
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM dyui_migrations").fetchone()[0]
        for version, statements in MIGRATIONS:
            if version <= current:
                continue
            conn.execute("BEGIN")
            try:
                for sql in statements:
                    conn.execute(sql)
                conn.execute("INSERT INTO dyui_migrations(version, applied_at) VALUES (?, ?)", (version, now_ms()))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            log.debug("applied dyui schema migration %d", version)

    def _sync(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            return fn(self._connect())

    async def _run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._sync, fn)

    @staticmethod
    def _thread(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "title_locked": bool(row["title_locked"]),
            "session": json.loads(row["session"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ---------------------------------------------------------- threads
    async def create_thread(self, user_id: str, *, title: str = DEFAULT_TITLE) -> dict[str, Any]:
        ts = now_ms()
        tid = f"t_{secrets.token_hex(8)}"

        def op(c: sqlite3.Connection) -> None:
            c.execute(
                "INSERT INTO threads(id, user_id, title, title_locked, session, created_at, updated_at)"
                " VALUES (?, ?, ?, 0, '{}', ?, ?)",
                (tid, user_id, title, ts, ts),
            )

        await self._run(op)
        return {"id": tid, "user_id": user_id, "title": title, "title_locked": False, "session": {},
                "created_at": ts, "updated_at": ts}

    async def get_thread(self, thread_id: str) -> Optional[dict[str, Any]]:
        row = await self._run(lambda c: c.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone())
        return self._thread(row) if row else None

    async def list_threads(self, user_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = await self._run(
            lambda c: c.execute(
                "SELECT * FROM threads WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (user_id, int(limit)),
            ).fetchall()
        )
        return [self._thread(r) for r in rows]

    async def update_thread(self, thread_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        sets: list[str] = []
        args: list[Any] = []
        if fields.get("title") is not None:
            sets.append("title = ?")
            args.append(str(fields["title"]))
        if fields.get("title_locked") is not None:
            sets.append("title_locked = ?")
            args.append(1 if fields["title_locked"] else 0)
        if fields.get("session") is not None:
            sets.append("session = ?")
            args.append(json.dumps(fields["session"], ensure_ascii=False, default=str))
        if fields.get("updated_at") is not None:
            sets.append("updated_at = ?")
            args.append(int(fields["updated_at"]))
        if sets:
            sql = f"UPDATE threads SET {', '.join(sets)} WHERE id = ?"
            await self._run(lambda c: c.execute(sql, (*args, thread_id)))
        return await self.get_thread(thread_id)

    async def delete_thread(self, thread_id: str) -> bool:
        def op(c: sqlite3.Connection) -> bool:
            c.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
            return c.execute("DELETE FROM threads WHERE id = ?", (thread_id,)).rowcount > 0

        return await self._run(op)

    # --------------------------------------------------------- messages
    async def get_messages(self, thread_id: str) -> list[dict[str, Any]]:
        rows = await self._run(
            lambda c: c.execute("SELECT data FROM messages WHERE thread_id = ? ORDER BY seq", (thread_id,)).fetchall()
        )
        return [json.loads(r["data"]) for r in rows]

    async def get_message(self, thread_id: str, message_id: str) -> Optional[dict[str, Any]]:
        row = await self._run(
            lambda c: c.execute(
                "SELECT data FROM messages WHERE thread_id = ? AND id = ?", (thread_id, message_id)
            ).fetchone()
        )
        return json.loads(row["data"]) if row else None

    async def put_message(self, thread_id: str, message: dict[str, Any]) -> None:
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":"), default=str)
        created = int(message.get("created_at") or now_ms())

        def op(c: sqlite3.Connection) -> None:
            c.execute(
                "INSERT INTO messages(id, thread_id, data, created_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (message["id"], thread_id, data, created),
            )

        await self._run(op)

    async def delete_messages_after(self, thread_id: str, message_id: str, *, inclusive: bool = False) -> int:
        def op(c: sqlite3.Connection) -> int:
            row = c.execute("SELECT seq FROM messages WHERE thread_id = ? AND id = ?", (thread_id, message_id)).fetchone()
            if row is None:
                return 0
            cmp = ">=" if inclusive else ">"
            return c.execute(f"DELETE FROM messages WHERE thread_id = ? AND seq {cmp} ?", (thread_id, row["seq"])).rowcount

        return await self._run(op)

    # ------------------------------------------------------------ files
    async def put_file(self, record: dict[str, Any]) -> None:
        def op(c: sqlite3.Connection) -> None:
            c.execute(
                "INSERT OR REPLACE INTO files(id, user_id, name, type, size, path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record["id"], record["user_id"], record["name"], record["type"], int(record["size"]),
                 str(record["path"]), int(record.get("created_at") or now_ms())),
            )

        await self._run(op)

    async def get_file(self, file_id: str) -> Optional[dict[str, Any]]:
        row = await self._run(lambda c: c.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone())
        return dict(row) if row else None

    async def close(self) -> None:
        def op() -> None:
            with self._lock:
                if self._conn is not None:
                    self._conn.close()
                    self._conn = None

        await asyncio.to_thread(op)

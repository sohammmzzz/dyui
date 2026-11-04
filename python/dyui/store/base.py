"""The :class:`Store` protocol and record helpers.

Records are plain dicts:

- **thread**: ``{id, user_id, title, title_locked, session, created_at, updated_at}``
- **message**: the protocol ``Message`` shape (SPEC §4) plus optional
  server-only ``meta``; stored and returned verbatim.
- **file**: ``{id, user_id, name, type, size, path, created_at}``

Timestamps are integer milliseconds since the epoch.
"""
from __future__ import annotations

import time
from typing import Any, Optional, Protocol, runtime_checkable

__all__ = ["Store", "now_ms", "DEFAULT_TITLE"]

DEFAULT_TITLE = "New chat"


def now_ms() -> int:
    """Current time in integer milliseconds since the epoch."""
    return int(time.time() * 1000)


@runtime_checkable
class Store(Protocol):
    """Persistence backend for threads, messages and uploaded-file metadata.

    Implement this protocol to plug in your own database; pass an instance as
    ``App(persist=...)``. All methods are coroutines.
    """

    async def create_thread(self, user_id: str, *, title: str = DEFAULT_TITLE) -> dict[str, Any]:
        """Create and return a new thread record."""
        ...

    async def get_thread(self, thread_id: str) -> Optional[dict[str, Any]]:
        """Return a thread record (without messages) or ``None``."""
        ...

    async def list_threads(self, user_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        """Return the user's threads, most recently updated first."""
        ...

    async def update_thread(self, thread_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        """Update ``title``, ``title_locked``, ``session`` and/or ``updated_at``."""
        ...

    async def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and its messages. Returns whether it existed."""
        ...

    async def get_messages(self, thread_id: str) -> list[dict[str, Any]]:
        """Return a thread's messages in insertion order."""
        ...

    async def get_message(self, thread_id: str, message_id: str) -> Optional[dict[str, Any]]:
        """Return one message or ``None``."""
        ...

    async def put_message(self, thread_id: str, message: dict[str, Any]) -> None:
        """Insert or replace a message (by ``id``); replacing keeps its position."""
        ...

    async def delete_messages_after(self, thread_id: str, message_id: str, *, inclusive: bool = False) -> int:
        """Delete messages after ``message_id`` (and it, if ``inclusive``). Returns the count."""
        ...

    async def put_file(self, record: dict[str, Any]) -> None:
        """Save uploaded-file metadata."""
        ...

    async def get_file(self, file_id: str) -> Optional[dict[str, Any]]:
        """Return uploaded-file metadata or ``None``."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...

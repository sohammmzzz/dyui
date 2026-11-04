"""Persistence: the :class:`Store` protocol plus SQLite and in-memory stores."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from .base import DEFAULT_TITLE, Store, now_ms
from .memory import MemoryStore
from .sqlite import SQLiteStore

__all__ = ["Store", "SQLiteStore", "MemoryStore", "make_store", "now_ms", "DEFAULT_TITLE"]


def make_store(persist: Union[bool, str, Path, Any], data_dir: Path) -> Any:
    """Resolve an ``App(persist=...)`` value into a store instance.

    Args:
        persist: ``True`` → SQLite at ``<data_dir>/dyui.db``; a path → SQLite
            there; ``False`` → :class:`MemoryStore`; a store instance → itself.
        data_dir: The app's data directory.

    Raises:
        TypeError: For anything else.
    """
    if persist is True:
        return SQLiteStore(data_dir / "dyui.db")
    if persist is False or persist is None:
        return MemoryStore()
    if isinstance(persist, (str, Path)):
        return SQLiteStore(Path(persist).expanduser())
    if all(hasattr(persist, m) for m in ("create_thread", "get_messages", "put_message")):
        return persist
    raise TypeError(f"persist must be a bool, a path or a Store, got {type(persist).__name__}")

"""Store contract: the same suite runs against SQLiteStore and MemoryStore."""
from __future__ import annotations

import asyncio

import pytest

from dyui.store import make_store
from dyui.store.base import DEFAULT_TITLE
from dyui.store.memory import MemoryStore
from dyui.store.sqlite import SQLiteStore


@pytest.fixture(params=["memory", "sqlite"])
async def store(request, tmp_path):
    s = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "db" / "dyui.db")
    yield s
    await s.close()


def msg(mid, role="user", text="hi", **extra):
    return {"id": mid, "role": role, "created_at": 1, "status": "done",
            "parts": [{"type": "text", "text": text}], **extra}


async def test_thread_lifecycle(store):
    t = await store.create_thread("u1")
    assert t["title"] == DEFAULT_TITLE and t["user_id"] == "u1"
    assert t["created_at"] > 1_000_000_000_000  # milliseconds
    got = await store.get_thread(t["id"])
    assert got["id"] == t["id"] and got["session"] == {}
    up = await store.update_thread(t["id"], title="Trip", title_locked=True, session={"k": [1, "ü"]}, updated_at=5)
    assert up["title"] == "Trip" and up["title_locked"] and up["session"] == {"k": [1, "ü"]}
    assert await store.delete_thread(t["id"]) is True
    assert await store.get_thread(t["id"]) is None
    assert await store.get_messages(t["id"]) == []


async def test_list_threads_scoped_and_ordered(store):
    a = await store.create_thread("u1")
    b = await store.create_thread("u1")
    await store.create_thread("u2")
    await store.update_thread(a["id"], updated_at=10**13)  # most recent
    rows = await store.list_threads("u1")
    assert [r["id"] for r in rows] == [a["id"], b["id"]]
    assert all(r["user_id"] == "u1" for r in rows)
    assert await store.list_threads("nobody") == []
    assert len(await store.list_threads("u1", limit=1)) == 1


async def test_messages_order_upsert_and_delete_after(store):
    t = await store.create_thread("u")
    for i in range(5):
        await store.put_message(t["id"], msg(f"m{i}", "user" if i % 2 == 0 else "assistant", f"t{i}"))
    assert [m["id"] for m in await store.get_messages(t["id"])] == ["m0", "m1", "m2", "m3", "m4"]
    await store.put_message(t["id"], msg("m1", "assistant", "edited", feedback=1))  # upsert keeps position
    ms = await store.get_messages(t["id"])
    assert [m["id"] for m in ms] == ["m0", "m1", "m2", "m3", "m4"]
    assert ms[1]["parts"][0]["text"] == "edited" and ms[1]["feedback"] == 1
    assert (await store.get_message(t["id"], "m3"))["parts"][0]["text"] == "t3"
    assert await store.get_message(t["id"], "nope") is None
    n = await store.delete_messages_after(t["id"], "m2")
    assert n == 2 and [m["id"] for m in await store.get_messages(t["id"])] == ["m0", "m1", "m2"]
    n = await store.delete_messages_after(t["id"], "m1", inclusive=True)
    assert n == 2 and [m["id"] for m in await store.get_messages(t["id"])] == ["m0"]
    assert await store.delete_messages_after(t["id"], "missing") == 0


async def test_messages_isolated_between_threads(store):
    a = await store.create_thread("u")
    b = await store.create_thread("u")
    await store.put_message(a["id"], msg("x"))
    assert await store.get_messages(b["id"]) == []
    assert await store.get_message(b["id"], "x") is None


async def test_rich_parts_round_trip(store):
    t = await store.create_thread("u")
    m = {"id": "m", "role": "assistant", "created_at": 2, "status": "done", "meta": {"llm_text": "x"},
         "parts": [{"type": "ui", "node": {"id": "c_1", "ui": "card", "props": {"title": "Ünï 日本"},
                                           "children": [{"id": "c_1-0", "ui": "stat", "props": {"label": "a", "value": 1.5}}]}},
                   {"type": "step", "step": {"id": "s", "title": "t", "status": "done", "logs": ["a"]}},
                   {"type": "reasoning", "text": "r", "duration_ms": 3}]}
    await store.put_message(t["id"], m)
    assert await store.get_message(t["id"], "m") == m


async def test_files(store):
    rec = {"id": "f_1", "user_id": "u", "name": "a.txt", "type": "text/plain", "size": 3, "path": "/x"}
    await store.put_file(rec)
    got = await store.get_file("f_1")
    assert {k: got[k] for k in rec} == rec
    assert await store.get_file("f_nope") is None


async def test_concurrent_writes(store):
    t = await store.create_thread("u")
    await asyncio.gather(*(store.put_message(t["id"], msg(f"m{i}")) for i in range(30)))
    assert len(await store.get_messages(t["id"])) == 30


async def test_sql_injection_strings_are_data(store):
    evil = "x'); DROP TABLE threads; --"
    t = await store.create_thread(evil)
    await store.update_thread(t["id"], title=evil)
    await store.put_message(t["id"], msg(evil, text=evil))
    assert (await store.get_thread(t["id"]))["title"] == evil
    assert (await store.list_threads(evil))[0]["id"] == t["id"]
    assert (await store.get_message(t["id"], evil))["parts"][0]["text"] == evil


async def test_sqlite_persists_across_instances(tmp_path):
    path = tmp_path / "p.db"
    s1 = SQLiteStore(path)
    t = await s1.create_thread("u")
    await s1.put_message(t["id"], msg("m"))
    await s1.close()
    s2 = SQLiteStore(path)
    assert (await s2.get_thread(t["id"]))["user_id"] == "u"
    assert [m["id"] for m in await s2.get_messages(t["id"])] == ["m"]
    await s2.close()


def test_make_store(tmp_path):
    assert isinstance(make_store(False, tmp_path), MemoryStore)
    assert isinstance(make_store(True, tmp_path), SQLiteStore)
    assert isinstance(make_store(str(tmp_path / "x.db"), tmp_path), SQLiteStore)
    custom = MemoryStore()
    assert make_store(custom, tmp_path) is custom

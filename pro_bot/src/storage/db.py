from __future__ import annotations

import aiosqlite
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0,
    pnl REAL NOT NULL DEFAULT 0,
    strategy TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT,
    exchange_order_id TEXT,
    time TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    meta TEXT
);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

    async def insert_trade(self, **fields: Any) -> None:
        keys = ",".join(fields.keys())
        placeholders = ",".join([":" + k for k in fields.keys()])
        sql = f"INSERT INTO trades ({keys}) VALUES ({placeholders})"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(sql, fields)
            await db.commit()

    async def insert_order(self, **fields: Any) -> None:
        keys = ",".join(fields.keys())
        placeholders = ",".join([":" + k for k in fields.keys()])
        sql = f"INSERT INTO orders ({keys}) VALUES ({placeholders})"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(sql, fields)
            await db.commit()

    async def upsert_kv(self, k: str, v: str) -> None:
        sql = "INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(sql, (k, v))
            await db.commit()

    async def get_kv(self, k: str) -> Optional[str]:
        sql = "SELECT v FROM kv WHERE k=?"
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(sql, (k,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else None
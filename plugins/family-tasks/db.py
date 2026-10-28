"""SQLite persistence for the family-tasks plugin."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Sequence

from plugins.plugin_storage import plugin_db

PLUGIN_ID = "family-tasks"
DEFAULT_KIDS = ("Itamar", "Alona", "Shahar", "Yuval")
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = plugin_db(PLUGIN_ID)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"family-tasks database version {version} is newer than supported {SCHEMA_VERSION}"
        )
    if version == 0:
        conn.executescript(
            """
            CREATE TABLE kids (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE sources (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                platform TEXT,
                external_message_id TEXT,
                sender TEXT,
                received_at TEXT NOT NULL,
                raw_text TEXT,
                extracted_text TEXT,
                content_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE entries (
                id TEXT PRIMARY KEY,
                source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
                kind TEXT NOT NULL CHECK (kind IN ('do', 'bring', 'remember', 'event')),
                title TEXT NOT NULL,
                details TEXT,
                starts_at TEXT,
                ends_at TEXT,
                due_at TEXT,
                all_day INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
                timezone TEXT NOT NULL,
                location TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed', 'cancelled')),
                original_date_text TEXT,
                confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE entry_kids (
                entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
                kid_id TEXT NOT NULL REFERENCES kids(id) ON DELETE RESTRICT,
                PRIMARY KEY (entry_id, kid_id)
            );

            CREATE TABLE reminder_deliveries (
                entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
                reminder_key TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                destination TEXT,
                PRIMARY KEY (entry_id, reminder_key)
            );

            CREATE INDEX entries_due_idx ON entries(status, due_at);
            CREATE INDEX entries_start_idx ON entries(status, starts_at);
            CREATE INDEX entry_kids_kid_idx ON entry_kids(kid_id, entry_id);
            CREATE UNIQUE INDEX sources_external_idx
                ON sources(platform, external_message_id)
                WHERE external_message_id IS NOT NULL AND external_message_id != '';
            """
        )
        now = utc_now()
        conn.executemany(
            "INSERT INTO kids(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [(uuid.uuid4().hex, name, now, now) for name in DEFAULT_KIDS],
        )
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def source_hash(
    *,
    source_type: str,
    platform: str | None,
    external_message_id: str | None,
    content: str,
    kids: Sequence[str],
) -> str:
    payload = json.dumps(
        {
            "source_type": source_type.strip().lower(),
            "platform": (platform or "").strip().lower(),
            "external_message_id": (external_message_id or "").strip(),
            "content": " ".join(content.split()),
            "kids": sorted(k.casefold() for k in kids),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

"""Deterministic task validation, storage, and querying."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db

VALID_KINDS = {"do", "bring", "remember", "event"}
VALID_STATUSES = {"open", "completed", "cancelled"}


def timezone_for(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def _aliases(row: sqlite3.Row) -> list[str]:
    try:
        value = json.loads(row["aliases_json"] or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value if str(item).strip()]


def list_kids(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    owned = conn is None
    conn = conn or db.connect()
    try:
        rows = conn.execute(
            "SELECT id, name, aliases_json, active FROM kids ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "aliases": _aliases(row),
                "active": bool(row["active"]),
            }
            for row in rows
        ]
    finally:
        if owned:
            conn.close()


def resolve_kids(
    names: Sequence[str], conn: sqlite3.Connection
) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, name, aliases_json FROM kids WHERE active=1"
    ).fetchall()
    lookup: dict[str, sqlite3.Row] = {}
    for row in rows:
        lookup[row["name"].strip().casefold()] = row
        for alias in _aliases(row):
            lookup[alias.strip().casefold()] = row

    resolved: list[sqlite3.Row] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for name in names:
        clean = str(name).strip()
        row = lookup.get(clean.casefold())
        if row is None:
            unknown.append(clean)
        elif row["id"] not in seen:
            resolved.append(row)
            seen.add(row["id"])
    if unknown:
        available = ", ".join(sorted(row["name"] for row in rows))
        raise ValueError(f"Unknown kid(s): {', '.join(unknown)}. Available: {available}")
    if not resolved:
        raise ValueError("At least one kid must be specified")
    return resolved


def _parse_datetime(value: Any, tz: ZoneInfo, *, all_day: bool = False) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            parsed = datetime.combine(date.fromisoformat(text), time.min, tzinfo=tz)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
    except ValueError as exc:
        raise ValueError(f"Invalid date/time {text!r}; use ISO 8601") from exc
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def save_extraction(
    *,
    source_type: str,
    content: str,
    extracted: dict[str, Any],
    explicit_kids: Sequence[str],
    timezone_name: str,
    platform: str | None = None,
    external_message_id: str | None = None,
    sender: str | None = None,
    received_at: str | None = None,
) -> dict[str, Any]:
    source_type = (source_type or "text").strip().lower()
    if source_type not in {"text", "image", "email", "whatsapp", "telegram", "manual"}:
        raise ValueError(f"Unsupported source_type: {source_type}")
    items = extracted.get("entries")
    if not isinstance(items, list):
        raise ValueError("Extraction did not return an entries list")
    if extracted.get("needs_clarification"):
        question = _clean_optional(extracted.get("clarification_question"))
        raise ValueError(question or "The source needs clarification before it can be saved")
    if not items:
        return {"created": [], "duplicate": False, "message": "No actionable entries found"}

    tz = timezone_for(timezone_name)
    received = _parse_datetime(received_at, tz) if received_at else db.utc_now()
    extraction_kids = extracted.get("kids") if isinstance(extracted.get("kids"), list) else []
    source_kids = list(explicit_kids) or [str(k) for k in extraction_kids]

    with db.transaction() as conn:
        resolved_source_kids = resolve_kids(source_kids, conn)
        canonical_source_kids = [row["name"] for row in resolved_source_kids]
        digest = db.source_hash(
            source_type=source_type,
            platform=platform,
            external_message_id=external_message_id,
            content=content,
            kids=canonical_source_kids,
        )
        existing = conn.execute(
            "SELECT id FROM sources WHERE content_hash=?", (digest,)
        ).fetchone()
        if existing is not None:
            rows = _fetch_entries(conn, source_id=existing["id"], timezone_name=timezone_name)
            return {"created": rows, "duplicate": True, "message": "Source was already ingested"}

        source_id = uuid.uuid4().hex
        raw_text = content if source_type != "image" else None
        extracted_text = content if source_type == "image" else None
        conn.execute(
            """
            INSERT INTO sources(
                id, source_type, platform, external_message_id, sender,
                received_at, raw_text, extracted_text, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_type,
                _clean_optional(platform),
                _clean_optional(external_message_id),
                _clean_optional(sender),
                received,
                raw_text,
                extracted_text,
                digest,
                db.utc_now(),
            ),
        )

        created_ids: list[str] = []
        now = db.utc_now()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Every extracted entry must be an object")
            kind = str(item.get("kind") or "").strip().lower()
            if kind not in VALID_KINDS:
                raise ValueError(f"Invalid entry kind: {kind!r}")
            title = str(item.get("title") or "").strip()
            if not title:
                raise ValueError("Every extracted entry requires a title")
            item_names = item.get("kids") if isinstance(item.get("kids"), list) else []
            resolved = resolve_kids(item_names or canonical_source_kids, conn)
            all_day = bool(item.get("all_day"))
            entry_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO entries(
                    id, source_id, kind, title, details, starts_at, ends_at,
                    due_at, all_day, timezone, location, original_date_text,
                    confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    source_id,
                    kind,
                    title,
                    _clean_optional(item.get("details")),
                    _parse_datetime(item.get("starts_at"), tz, all_day=all_day),
                    _parse_datetime(item.get("ends_at"), tz, all_day=all_day),
                    _parse_datetime(item.get("due_at"), tz, all_day=all_day),
                    int(all_day),
                    timezone_name,
                    _clean_optional(item.get("location")),
                    _clean_optional(item.get("original_date_text")),
                    float(item["confidence"]) if item.get("confidence") is not None else None,
                    now,
                    now,
                ),
            )
            conn.executemany(
                "INSERT INTO entry_kids(entry_id, kid_id) VALUES (?, ?)",
                [(entry_id, row["id"]) for row in resolved],
            )
            created_ids.append(entry_id)

        return {
            "created": _fetch_entries(
                conn, entry_ids=created_ids, timezone_name=timezone_name
            ),
            "duplicate": False,
            "message": f"Saved {len(created_ids)} entr{'y' if len(created_ids) == 1 else 'ies'}",
        }


def _local_iso(value: str | None, timezone_name: str) -> str | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone_for(timezone_name)).isoformat(timespec="minutes")


def _row_to_entry(
    row: sqlite3.Row, kid_names: Sequence[str], timezone_name: str
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "details": row["details"],
        "kids": list(kid_names),
        "starts_at": _local_iso(row["starts_at"], timezone_name),
        "ends_at": _local_iso(row["ends_at"], timezone_name),
        "due_at": _local_iso(row["due_at"], timezone_name),
        "all_day": bool(row["all_day"]),
        "timezone": timezone_name,
        "location": row["location"],
        "status": row["status"],
        "original_date_text": row["original_date_text"],
        "confidence": row["confidence"],
        "source_id": row["source_id"],
    }


def _fetch_entries(
    conn: sqlite3.Connection,
    *,
    entry_ids: Sequence[str] | None = None,
    source_id: str | None = None,
    timezone_name: str,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if entry_ids is not None:
        if not entry_ids:
            return []
        where.append(f"e.id IN ({','.join('?' for _ in entry_ids)})")
        params.extend(entry_ids)
    if source_id:
        where.append("e.source_id=?")
        params.append(source_id)
    sql = "SELECT e.* FROM entries e"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(e.due_at, e.starts_at, e.created_at), e.created_at"
    rows = conn.execute(sql, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        kids = [
            kid["name"]
            for kid in conn.execute(
                """
                SELECT k.name FROM kids k
                JOIN entry_kids ek ON ek.kid_id=k.id
                WHERE ek.entry_id=? ORDER BY k.name COLLATE NOCASE
                """,
                (row["id"],),
            ).fetchall()
        ]
        result.append(_row_to_entry(row, kids, timezone_name))
    return result


def _boundary(value: str | None, tz: ZoneInfo, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    text = value.strip().lower()
    today = datetime.now(tz).date()
    aliases = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "week": today + timedelta(days=6),
    }
    target = aliases.get(text)
    if target is None:
        if len(value.strip()) == 10:
            target = date.fromisoformat(value)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or tz).astimezone(timezone.utc)
    local = datetime.combine(target, time.max if end else time.min, tzinfo=tz)
    return local.astimezone(timezone.utc)


def query_entries(
    *,
    timezone_name: str,
    kid: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kinds: Sequence[str] | None = None,
    status: str = "open",
    include_undated: bool = False,
    search: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if status not in VALID_STATUSES and status != "all":
        raise ValueError(f"Invalid status: {status}")
    clean_kinds = [str(kind).lower() for kind in kinds or []]
    invalid = set(clean_kinds) - VALID_KINDS
    if invalid:
        raise ValueError(f"Invalid kinds: {', '.join(sorted(invalid))}")
    tz = timezone_for(timezone_name)
    start = _boundary(date_from, tz)
    end = _boundary(date_to, tz, end=True)

    conn = db.connect()
    try:
        joins = ""
        where: list[str] = []
        params: list[Any] = []
        if kid:
            resolved = resolve_kids([kid], conn)[0]
            joins += " JOIN entry_kids filter_ek ON filter_ek.entry_id=e.id"
            where.append("filter_ek.kid_id=?")
            params.append(resolved["id"])
        if status != "all":
            where.append("e.status=?")
            params.append(status)
        if clean_kinds:
            where.append(f"e.kind IN ({','.join('?' for _ in clean_kinds)})")
            params.extend(clean_kinds)
        temporal = "COALESCE(e.due_at, e.starts_at)"
        range_parts: list[str] = []
        range_params: list[Any] = []
        if start:
            range_parts.append(f"{temporal}>=?")
            range_params.append(start.isoformat(timespec="seconds"))
        if end:
            range_parts.append(f"{temporal}<=?")
            range_params.append(end.isoformat(timespec="seconds"))
        if range_parts:
            clause = " AND ".join(range_parts)
            where.append(f"(({clause}) OR {temporal} IS NULL)" if include_undated else clause)
            params.extend(range_params)
        if search:
            where.append("(e.title LIKE ? OR e.details LIKE ? OR e.location LIKE ?)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        sql = f"SELECT DISTINCT e.* FROM entries e{joins}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(e.due_at, e.starts_at, '9999'), e.created_at LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        rows = conn.execute(sql, params).fetchall()
        return _fetch_entries(
            conn,
            entry_ids=[row["id"] for row in rows],
            timezone_name=timezone_name,
        )
    finally:
        conn.close()


def resolve_entry(conn: sqlite3.Connection, reference: str) -> sqlite3.Row:
    clean = reference.strip().lower()
    rows = conn.execute(
        "SELECT * FROM entries WHERE lower(id)=? OR lower(id) LIKE ?",
        (clean, clean + "%"),
    ).fetchall()
    if not rows:
        raise ValueError(f"No entry matches {reference!r}")
    exact = [row for row in rows if row["id"].lower() == clean]
    if exact:
        return exact[0]
    if len(rows) > 1:
        raise ValueError(f"Entry reference {reference!r} is ambiguous")
    return rows[0]


def get_entry(reference: str, *, timezone_name: str) -> dict[str, Any]:
    conn = db.connect()
    try:
        row = resolve_entry(conn, reference)
        return _fetch_entries(
            conn, entry_ids=[row["id"]], timezone_name=timezone_name
        )[0]
    finally:
        conn.close()


def set_status(reference: str, status: str, *, timezone_name: str) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    with db.transaction() as conn:
        row = resolve_entry(conn, reference)
        now = db.utc_now()
        conn.execute(
            "UPDATE entries SET status=?, completed_at=?, updated_at=? WHERE id=?",
            (status, now if status == "completed" else None, now, row["id"]),
        )
        return _fetch_entries(
            conn, entry_ids=[row["id"]], timezone_name=timezone_name
        )[0]


def delete_entry(reference: str) -> dict[str, Any]:
    with db.transaction() as conn:
        row = resolve_entry(conn, reference)
        conn.execute("DELETE FROM entries WHERE id=?", (row["id"],))
        return {"deleted": row["id"]}


def edit_entry(
    reference: str,
    changes: dict[str, Any],
    *,
    timezone_name: str,
) -> dict[str, Any]:
    allowed = {
        "kind", "title", "details", "starts_at", "ends_at", "due_at",
        "all_day", "location", "kids",
    }
    supplied = {key: value for key, value in changes.items() if key in allowed and value is not None}
    if not supplied:
        raise ValueError("No editable fields were supplied")
    tz = timezone_for(timezone_name)
    with db.transaction() as conn:
        row = resolve_entry(conn, reference)
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in supplied.items():
            if key == "kids":
                continue
            if key == "kind" and str(value).lower() not in VALID_KINDS:
                raise ValueError(f"Invalid entry kind: {value}")
            if key == "title" and not str(value).strip():
                raise ValueError("Title cannot be empty")
            if key in {"starts_at", "ends_at", "due_at"}:
                value = _parse_datetime(value, tz)
            elif key == "all_day":
                value = int(bool(value))
            elif key == "kind":
                value = str(value).lower()
            else:
                value = _clean_optional(value)
            assignments.append(f"{key}=?")
            params.append(value)
        if assignments:
            assignments.append("updated_at=?")
            params.extend([db.utc_now(), row["id"]])
            conn.execute(
                f"UPDATE entries SET {', '.join(assignments)} WHERE id=?", params
            )
        if "kids" in supplied:
            names = supplied["kids"]
            if not isinstance(names, list):
                raise ValueError("kids must be a list")
            resolved = resolve_kids(names, conn)
            conn.execute("DELETE FROM entry_kids WHERE entry_id=?", (row["id"],))
            conn.executemany(
                "INSERT INTO entry_kids(entry_id, kid_id) VALUES (?, ?)",
                [(row["id"], kid["id"]) for kid in resolved],
            )
        return _fetch_entries(
            conn, entry_ids=[row["id"]], timezone_name=timezone_name
        )[0]


def format_agenda(entries: Iterable[dict[str, Any]]) -> str:
    rows = list(entries)
    if not rows:
        return ""
    lines: list[str] = []
    for entry in rows:
        when = entry["due_at"] or entry["starts_at"] or "undated"
        if entry["all_day"] and when != "undated":
            when = when[:10]
        kids = ", ".join(entry["kids"])
        marker = {"do": "DO", "bring": "BRING", "remember": "REMEMBER", "event": "EVENT"}[entry["kind"]]
        line = f"- {when} [{kids}] {marker}: {entry['title']} (id: {entry['id'][:8]})"
        if entry.get("location"):
            line += f" @ {entry['location']}"
        lines.append(line)
    return "\n".join(lines)

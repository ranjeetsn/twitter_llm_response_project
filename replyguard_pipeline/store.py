"""Small SQLite store shared by both UIs and the Kafka workers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from replyguard_pipeline.config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def ensure_database() -> None:
    connection = _connect()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tweets (
                tweet_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                author_handle TEXT NOT NULL,
                created_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS responses (
                tweet_id TEXT PRIMARY KEY REFERENCES tweets(tweet_id),
                draft_text TEXT,
                model_name TEXT NOT NULL DEFAULT '',
                created_at TEXT,
                status TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_note TEXT
            );
            CREATE TABLE IF NOT EXISTS activity (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                event TEXT NOT NULL,
                tweet_id TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_tweets_received_at
                ON tweets(received_at DESC);
            CREATE INDEX IF NOT EXISTS idx_activity_occurred_at
                ON activity(occurred_at DESC);
            """
        )
    finally:
        connection.close()


def _event(connection: sqlite3.Connection, tweet_id: str, event: str, details: str = "") -> None:
    connection.execute(
        "INSERT INTO activity (occurred_at, event, tweet_id, details) VALUES (?, ?, ?, ?)",
        (utc_now(), event, tweet_id, details[:300]),
    )


def record_tweet(event: dict[str, Any]) -> bool:
    ensure_database()
    tweet_id = str(event["tweet_id"])
    text = str(event["text"])
    handle = str(event.get("author_handle") or "@demo_user")[:64]
    created_at = str(event.get("created_at") or utc_now())
    received_at = utc_now()
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO tweets
                   (tweet_id, text, author_handle, created_at, received_at, status)
                   VALUES (?, ?, ?, ?, ?, 'received')""",
                (tweet_id, text, handle, created_at, received_at),
            )
            if cursor.rowcount:
                _event(connection, tweet_id, "tweet_received", "Stored from incoming Kafka topic")
            return bool(cursor.rowcount)
    finally:
        connection.close()


def queue_response(tweet_id: str) -> bool:
    """Mark a tweet ready for the response queue, preserving completed reviews."""
    ensure_database()
    connection = _connect()
    try:
        with connection:
            row = connection.execute(
                "SELECT status FROM responses WHERE tweet_id = ?", (tweet_id,)
            ).fetchone()
            if row and row["status"] in {"awaiting_review", "approved", "rejected"}:
                return False
            if not connection.execute(
                "SELECT 1 FROM tweets WHERE tweet_id = ?", (tweet_id,)
            ).fetchone():
                return False
            connection.execute(
                """INSERT INTO responses (tweet_id, status)
                   VALUES (?, 'queued')
                   ON CONFLICT(tweet_id) DO UPDATE SET
                     draft_text = NULL,
                     model_name = '',
                     created_at = NULL,
                     status = 'queued',
                     reviewed_by = NULL,
                     reviewed_at = NULL,
                     review_note = NULL
                   WHERE responses.status IN ('queued', 'failed')""",
                (tweet_id,),
            )
            connection.execute(
                "UPDATE tweets SET status = 'queued_for_response', error = NULL WHERE tweet_id = ?",
                (tweet_id,),
            )
            _event(connection, tweet_id, "response_queued", "Added to response request topic")
            return True
    finally:
        connection.close()


def response_is_complete(tweet_id: str) -> bool:
    ensure_database()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT status FROM responses WHERE tweet_id = ?", (tweet_id,)
        ).fetchone()
        return bool(row and row["status"] in {"awaiting_review", "approved", "rejected"})
    finally:
        connection.close()


def save_response(tweet_id: str, draft_text: str, model_name: str) -> bool:
    ensure_database()
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """UPDATE responses
                   SET draft_text = ?, model_name = ?, created_at = ?, status = 'awaiting_review'
                   WHERE tweet_id = ? AND status = 'queued'""",
                (draft_text, model_name, utc_now(), tweet_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "UPDATE tweets SET status = 'awaiting_review', error = NULL WHERE tweet_id = ?",
                    (tweet_id,),
                )
                _event(connection, tweet_id, "draft_ready", f"Draft created by {model_name}")
            return bool(cursor.rowcount)
    finally:
        connection.close()


def update_response_draft(tweet_id: str, draft_text: str, reviewer: str) -> bool:
    if not draft_text.strip() or len(draft_text) > 280:
        raise ValueError("Draft must contain 1 to 280 characters.")
    ensure_database()
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """UPDATE responses SET draft_text = ?, created_at = ?
                   WHERE tweet_id = ? AND status = 'awaiting_review'""",
                (draft_text.strip(), utc_now(), tweet_id),
            )
            if cursor.rowcount:
                _event(connection, tweet_id, "draft_edited", f"Draft edited by {reviewer}")
            return bool(cursor.rowcount)
    finally:
        connection.close()


def mark_response_failed(tweet_id: str, error: str) -> None:
    ensure_database()
    connection = _connect()
    safe_error = error[:240]
    try:
        with connection:
            connection.execute(
                """UPDATE responses SET status = 'failed', review_note = ?
                   WHERE tweet_id = ? AND status = 'queued'""",
                (safe_error, tweet_id),
            )
            connection.execute(
                "UPDATE tweets SET status = 'failed', error = ? WHERE tweet_id = ?",
                (safe_error, tweet_id),
            )
            _event(connection, tweet_id, "response_failed", safe_error)
    finally:
        connection.close()


def decide_response(tweet_id: str, decision: str, reviewer: str, note: str) -> bool:
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    ensure_database()
    reviewed_at = utc_now()
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """UPDATE responses SET status = ?, reviewed_by = ?, reviewed_at = ?, review_note = ?
                   WHERE tweet_id = ? AND status = 'awaiting_review'""",
                (decision, reviewer, reviewed_at, note[:300], tweet_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "UPDATE tweets SET status = ?, error = NULL WHERE tweet_id = ?",
                    (decision, tweet_id),
                )
                _event(connection, tweet_id, f"reply_{decision}", note)
            return bool(cursor.rowcount)
    finally:
        connection.close()


def list_tweets(limit: int = 100) -> list[dict[str, Any]]:
    ensure_database()
    connection = _connect()
    try:
        rows = connection.execute(
            """SELECT t.tweet_id, t.text, t.author_handle, t.created_at, t.received_at,
                      t.status AS tweet_status, t.error,
                      r.draft_text, r.model_name, r.created_at AS response_created_at,
                      r.status AS response_status, r.reviewed_by, r.reviewed_at, r.review_note
               FROM tweets t LEFT JOIN responses r ON r.tweet_id = t.tweet_id
               ORDER BY t.received_at DESC LIMIT ?""",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_tweet(tweet_id: str) -> dict[str, Any] | None:
    return next((row for row in list_tweets(limit=1000) if row["tweet_id"] == tweet_id), None)


def pipeline_counts() -> dict[str, int]:
    rows = list_tweets(limit=1000)
    counts: dict[str, int] = {}
    for row in rows:
        status = row["response_status"] or row["tweet_status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def list_activity(limit: int = 200) -> list[dict[str, Any]]:
    ensure_database()
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT occurred_at, event, tweet_id, details FROM activity ORDER BY event_id DESC LIMIT ?",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()

"""Persistent state management via SQLite — tracks seen/replied posts."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS replied_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    url TEXT,
    replied_at TEXT NOT NULL,
    reply_text TEXT,
    status TEXT NOT NULL DEFAULT 'replied',
    UNIQUE(platform, post_id)
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_replied_posts_lookup
ON replied_posts(platform, post_id)
"""


class StateManager:
    """Thread-safe SQLite-backed state manager for seen/replied posts."""

    def __init__(self, db_path: str = "./data/state.db"):
        self.db_path = Path(db_path)
        self._is_memory = str(db_path) == ":memory:"
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        if self._is_memory:
            # In-memory: use a single persistent connection so tables survive
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._is_memory and self._conn is not None:
            return self._conn
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        """Close connection only if not the persistent in-memory one."""
        if not self._is_memory:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(CREATE_TABLE_SQL)
                conn.execute(CREATE_INDEX_SQL)
                conn.commit()
            finally:
                self._close_conn(conn)
        logger.info(f"State database initialized at {self.db_path}")

    def is_already_replied(self, platform: str, post_id: str) -> bool:
        """Check if a post has already been replied to."""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "SELECT 1 FROM replied_posts WHERE platform = ? AND post_id = ?",
                    (platform, post_id),
                )
                return cur.fetchone() is not None
            finally:
                self._close_conn(conn)

    def mark_replied(self, platform: str, post_id: str, url: str = "",
                     reply_text: str = "", status: str = "replied") -> None:
        """Record a reply to prevent duplicate responses."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO replied_posts "
                    "(platform, post_id, url, replied_at, reply_text, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (platform, post_id, url, now, reply_text, status),
                )
                conn.commit()
            finally:
                self._close_conn(conn)

    def get_reply_count(self, platform: Optional[str] = None) -> int:
        """Get total reply count, optionally filtered by platform."""
        with self._lock:
            conn = self._get_conn()
            try:
                if platform:
                    cur = conn.execute(
                        "SELECT COUNT(*) FROM replied_posts WHERE platform = ?",
                        (platform,),
                    )
                else:
                    cur = conn.execute("SELECT COUNT(*) FROM replied_posts")
                return cur.fetchone()[0]
            finally:
                self._close_conn(conn)

    def get_recent_replies(self, limit: int = 10) -> list[dict]:
        """Get most recent replies for reporting."""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "SELECT platform, post_id, url, replied_at, status "
                    "FROM replied_posts ORDER BY replied_at DESC LIMIT ?",
                    (limit,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "platform": r[0],
                        "post_id": r[1],
                        "url": r[2],
                        "replied_at": r[3],
                        "status": r[4],
                    }
                    for r in rows
                ]
            finally:
                self._close_conn(conn)

    def mark_skipped(self, platform: str, post_id: str, url: str = "",
                     reason: str = "") -> None:
        """Mark a post as intentionally skipped."""
        self.mark_replied(platform, post_id, url, reason, status="skipped")

    def mark_error(self, platform: str, post_id: str, url: str = "",
                   error: str = "") -> None:
        """Mark a post that encountered an error."""
        self.mark_replied(platform, post_id, url, error, status="error")

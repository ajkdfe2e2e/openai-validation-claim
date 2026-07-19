"""SQLite：去重 / 申请历史 / NPO 库。"""

from __future__ import annotations

import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS jp_npos(
    corporate_number TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_kana TEXT,
    address TEXT,
    postal_code TEXT,
    representative TEXT,
    certified_ymd TEXT,
    info_url TEXT,
    is_recognized INTEGER NOT NULL DEFAULT 0,
    used_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_jp_npos_used ON jp_npos(used_at);
CREATE INDEX IF NOT EXISTS ix_jp_npos_recognized ON jp_npos(is_recognized);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    invite_id TEXT NOT NULL,
    corporate_number TEXT,
    organisation_name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    website TEXT,
    contact_first_name TEXT NOT NULL,
    contact_last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    language TEXT,
    status TEXT NOT NULL,
    submission_id TEXT,
    raw_response TEXT,
    note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_submissions_corpnum ON submissions(corporate_number);
CREATE UNIQUE INDEX IF NOT EXISTS ux_submissions_email ON submissions(email);
CREATE INDEX IF NOT EXISTS ix_submissions_created ON submissions(created_at);
"""

MIGRATIONS = (
    "ALTER TABLE submissions ADD COLUMN confirmed_at TEXT",
    "ALTER TABLE submissions ADD COLUMN confirm_note TEXT",
    "ALTER TABLE submissions ADD COLUMN confirm_mail_id TEXT",
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for sql in MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # 列已存在


# ---- NPO 库 ----
def count_npos(*, recognized_only: bool = False) -> int:
    sql = "SELECT count(*) FROM jp_npos"
    if recognized_only:
        sql += " WHERE is_recognized=1"
    with get_conn() as conn:
        return int(conn.execute(sql).fetchone()[0])


def count_unused_npos(*, recognized_only: bool = False) -> int:
    sql = "SELECT count(*) FROM jp_npos WHERE used_at IS NULL"
    if recognized_only:
        sql += " AND is_recognized=1"
    with get_conn() as conn:
        return int(conn.execute(sql).fetchone()[0])


def pick_unused_npo(*, recognized_only: bool = False, mark_used: bool = True) -> dict[str, Any] | None:
    """随机取一个未用过的 NPO，可标记 used_at（推荐：申请前先标记，避免并发抽取相同）。"""
    sql = "SELECT * FROM jp_npos WHERE used_at IS NULL"
    if recognized_only:
        sql += " AND is_recognized=1"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
        if not rows:
            return None
        chosen = random.choice(rows)
        if mark_used:
            conn.execute(
                "UPDATE jp_npos SET used_at=? WHERE corporate_number=?",
                (datetime.now(timezone.utc).isoformat(), chosen["corporate_number"]),
            )
    return dict(chosen)


def release_npo(corporate_number: str) -> None:
    """申请失败可回收 used_at 标记。"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE jp_npos SET used_at=NULL WHERE corporate_number=?", (corporate_number,)
        )


def get_npo(corporate_number: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM jp_npos WHERE corporate_number=?", (corporate_number,)
        ).fetchone()
    return dict(row) if row else None


# ---- 申请历史 ----
def is_email_used(email: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM submissions WHERE email=? LIMIT 1", (email,)
        ).fetchone()
    return row is not None


def insert_submission(
    *, invite_id: str, corporate_number: str | None, organisation_name: str,
    country_code: str, website: str | None,
    contact_first_name: str, contact_last_name: str, email: str,
    language: str | None, status: str, submission_id: str | None,
    raw_response: str | None, note: str | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO submissions(
                created_at, invite_id, corporate_number, organisation_name, country_code,
                website, contact_first_name, contact_last_name, email, language,
                status, submission_id, raw_response, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(), invite_id, corporate_number,
                organisation_name, country_code, website,
                contact_first_name, contact_last_name, email, language,
                status, submission_id, raw_response, note,
            ),
        )
        return int(cur.lastrowid)


def list_submissions(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_submission(row_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (row_id,)).fetchone()
    return dict(row) if row else None


def update_status(row_id: int, status: str, note: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE submissions SET status=?, note=? WHERE id=?", (status, note, row_id)
        )


# ---- 邮箱确认 ----
def list_unconfirmed(limit: int = 500) -> list[dict[str, Any]]:
    """已提交但尚未点确认链接的历史记录。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM submissions
               WHERE status='submitted' AND confirmed_at IS NULL
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_confirmed(row_id: int, note: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE submissions SET confirmed_at=?, confirm_note=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), note, row_id),
        )


def list_submitted(limit: int = 500) -> list[dict[str, Any]]:
    """已提交的全部历史，含已确认的（用于二次验证再检查）。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE status='submitted' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_confirmed_with_mail(row_id: int, mail_id: str | None, note: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE submissions SET confirmed_at=?, confirm_note=?, confirm_mail_id=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), note, mail_id, row_id),
        )

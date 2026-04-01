"""账目数据库模块"""

import sqlite3
from pathlib import Path
from typing import Optional

LEDGER_DB = "data/ledger.db"


def init_ledger_db() -> None:
    Path(LEDGER_DB).parent.mkdir(exist_ok=True)
    with sqlite3.connect(LEDGER_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                recorded_by TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                anomaly_flag TEXT,
                anomaly_reason TEXT,
                reviewed_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def write_entry(
    datetime: str,
    type_: str,
    amount: float,
    description: str,
    recorded_by: str = "accountant",
    anomaly_flag: Optional[str] = None,
    anomaly_reason: Optional[str] = None,
) -> int:
    with sqlite3.connect(LEDGER_DB) as conn:
        cursor = conn.execute(
            """INSERT INTO ledger (datetime, type, amount, description, recorded_by, anomaly_flag, anomaly_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime,
                type_,
                amount,
                description,
                recorded_by,
                anomaly_flag,
                anomaly_reason,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_entries(
    date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = "SELECT * FROM ledger WHERE 1=1"
    params = []

    if date:
        query += " AND datetime LIKE ?"
        params.append(f"{date}%")
    if status:
        query += " AND status = ?"
        params.append(status)

    query += f" ORDER BY id DESC LIMIT {limit}"

    with sqlite3.connect(LEDGER_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_entry_status(
    entry_id: int, status: str, reviewed_by: str = "auditor"
) -> None:
    with sqlite3.connect(LEDGER_DB) as conn:
        conn.execute(
            "UPDATE ledger SET status = ?, reviewed_by = ? WHERE id = ?",
            (status, reviewed_by, entry_id),
        )
        conn.commit()

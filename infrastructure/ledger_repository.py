"""账目 Repository 抽象层

提供数据库操作的抽象接口，支持未来迁移到其他数据库。
"""

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


LEDGER_DB = "data/ledger.db"


@dataclass
class LedgerEntry:
    """账目条目数据类"""

    id: int
    datetime: str
    type: str
    amount: float
    description: str
    recorded_by: str
    status: str
    anomaly_flag: Optional[str]
    anomaly_reason: Optional[str]
    reviewed_by: Optional[str]
    created_at: str


class ILedgerRepository(ABC):
    """账目仓库抽象接口"""

    @abstractmethod
    def init_db(self) -> None:
        """初始化数据库"""
        pass

    @abstractmethod
    def write(
        self,
        datetime: str,
        type_: str,
        amount: float,
        description: str,
        recorded_by: str,
        anomaly_flag: Optional[str] = None,
        anomaly_reason: Optional[str] = None,
    ) -> int:
        """写入账目条目"""
        pass

    @abstractmethod
    def get(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询账目列表"""
        pass

    @abstractmethod
    def update_status(
        self, entry_id: int, status: str, reviewed_by: str = "auditor"
    ) -> None:
        """更新账目状态"""
        pass

    @abstractmethod
    def get_by_id(self, entry_id: int) -> Optional[dict]:
        """根据 ID 获取账目"""
        pass


class SQLiteLedgerRepository(ILedgerRepository):
    """SQLite 实现的账目仓库"""

    def __init__(self, db_path: str = LEDGER_DB):
        self._db_path = db_path

    def init_db(self) -> None:
        """初始化数据库"""
        Path(self._db_path).parent.mkdir(exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
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
                """
            )

    def write(
        self,
        datetime: str,
        type_: str,
        amount: float,
        description: str,
        recorded_by: str = "accountant",
        anomaly_flag: Optional[str] = None,
        anomaly_reason: Optional[str] = None,
    ) -> int:
        """写入账目条目"""
        with sqlite3.connect(self._db_path) as conn:
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

    def get(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询账目列表"""
        query = "SELECT * FROM ledger WHERE 1=1"
        params = []

        if date:
            query += " AND datetime LIKE ?"
            params.append(f"{date}%")
        if status:
            query += " AND status = ?"
            params.append(status)

        query += f" ORDER BY id DESC LIMIT {limit}"

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_status(
        self, entry_id: int, status: str, reviewed_by: str = "auditor"
    ) -> None:
        """更新账目状态"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE ledger SET status = ?, reviewed_by = ? WHERE id = ?",
                (status, reviewed_by, entry_id),
            )
            conn.commit()

    def get_by_id(self, entry_id: int) -> Optional[dict]:
        """根据 ID 获取账目"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM ledger WHERE id = ?", (entry_id,)
            ).fetchone()
            return dict(row) if row else None


_ledger_repository: Optional[SQLiteLedgerRepository] = None


def get_ledger_repository() -> SQLiteLedgerRepository:
    """获取全局账目仓库实例（单例）"""
    global _ledger_repository
    if _ledger_repository is None:
        _ledger_repository = SQLiteLedgerRepository()
    return _ledger_repository


def init_ledger_repository() -> None:
    """初始化全局账目仓库"""
    repo = get_ledger_repository()
    repo.init_db()


def write_entry(
    datetime: str,
    type_: str,
    amount: float,
    description: str,
    recorded_by: str = "accountant",
    anomaly_flag: Optional[str] = None,
    anomaly_reason: Optional[str] = None,
) -> int:
    """写入账目条目（使用全局仓库）"""
    return get_ledger_repository().write(
        datetime, type_, amount, description, recorded_by, anomaly_flag, anomaly_reason
    )


def get_entries(
    date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询账目列表（使用全局仓库）"""
    return get_ledger_repository().get(date, status, limit)


def update_entry_status(
    entry_id: int, status: str, reviewed_by: str = "auditor"
) -> None:
    """更新账目状态（使用全局仓库）"""
    get_ledger_repository().update_status(entry_id, status, reviewed_by)


def init_ledger_db() -> None:
    """初始化数据库（向后兼容）"""
    init_ledger_repository()

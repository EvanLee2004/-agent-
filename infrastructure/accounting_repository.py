"""分录驱动账务仓库实现。

该模块新增两类 Repository：
1. `IChartOfAccountsRepository` / `SQLiteChartOfAccountsRepository`
   负责会计科目表的初始化与查询。
2. `IJournalRepository` / `SQLiteJournalRepository`
   负责凭证头、分录行的持久化与读取。

设计原则：
- 账务的主存储切换到“凭证 + 分录 + 科目”结构。
- 仍然使用项目现有的 SQLite 数据库文件，避免额外部署成本。
- 不直接依赖 Agent 或 LLM，只处理数据库读写。
"""

import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from domain.models import AccountSubject, JournalLine, JournalVoucher, VoucherDraft
from infrastructure.ledger_repository import LEDGER_DB


class IChartOfAccountsRepository(ABC):
    """科目表仓库接口。"""

    @abstractmethod
    def init_db(self) -> None:
        """初始化科目表。"""
        pass

    @abstractmethod
    def upsert_subjects(self, subjects: list[AccountSubject]) -> None:
        """批量写入或更新科目。"""
        pass

    @abstractmethod
    def list_subjects(self) -> list[AccountSubject]:
        """列出全部科目。"""
        pass

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[AccountSubject]:
        """按编码查询科目。"""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[AccountSubject]:
        """按名称查询科目。"""
        pass


class IJournalRepository(ABC):
    """凭证仓库接口。"""

    @abstractmethod
    def init_db(self) -> None:
        """初始化凭证表与分录表。"""
        pass

    @abstractmethod
    def create_voucher(
        self,
        voucher: VoucherDraft,
        recorded_by: str,
    ) -> int:
        """创建凭证并返回主键。"""
        pass

    @abstractmethod
    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """根据主键读取凭证。"""
        pass

    @abstractmethod
    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """获取最近一张凭证。"""
        pass

    @abstractmethod
    def list_vouchers(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[JournalVoucher]:
        """列出凭证。"""
        pass

    @abstractmethod
    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str] = None,
    ) -> None:
        """更新凭证状态。"""
        pass


class SQLiteChartOfAccountsRepository(IChartOfAccountsRepository):
    """SQLite 科目表仓库实现。"""

    def __init__(self, db_path: str = LEDGER_DB):
        self._db_path = db_path

    def init_db(self) -> None:
        """初始化科目表。"""
        Path(self._db_path).parent.mkdir(exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_subject (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    normal_balance TEXT NOT NULL,
                    description TEXT DEFAULT ''
                )
                """
            )

    def upsert_subjects(self, subjects: list[AccountSubject]) -> None:
        """批量写入默认科目。

        使用 UPSERT 的原因是：
        - 首次启动可以自动建表和灌默认科目
        - 后续如果补充说明文字，也能够无损更新
        """
        if not subjects:
            return

        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO account_subject (code, name, category, normal_balance, description)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    normal_balance = excluded.normal_balance,
                    description = excluded.description
                """,
                [
                    (
                        subject.code,
                        subject.name,
                        subject.category,
                        subject.normal_balance,
                        subject.description,
                    )
                    for subject in subjects
                ],
            )
            conn.commit()

    def list_subjects(self) -> list[AccountSubject]:
        """列出全部科目。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT code, name, category, normal_balance, description FROM account_subject ORDER BY code"
            ).fetchall()
            return [
                AccountSubject(
                    code=row["code"],
                    name=row["name"],
                    category=row["category"],
                    normal_balance=row["normal_balance"],
                    description=row["description"],
                )
                for row in rows
            ]

    def get_by_code(self, code: str) -> Optional[AccountSubject]:
        """按编码查询科目。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT code, name, category, normal_balance, description
                FROM account_subject
                WHERE code = ?
                """,
                (code,),
            ).fetchone()
            if row is None:
                return None
            return AccountSubject(
                code=row["code"],
                name=row["name"],
                category=row["category"],
                normal_balance=row["normal_balance"],
                description=row["description"],
            )

    def get_by_name(self, name: str) -> Optional[AccountSubject]:
        """按名称查询科目。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT code, name, category, normal_balance, description
                FROM account_subject
                WHERE name = ?
                """,
                (name,),
            ).fetchone()
            if row is None:
                return None
            return AccountSubject(
                code=row["code"],
                name=row["name"],
                category=row["category"],
                normal_balance=row["normal_balance"],
                description=row["description"],
            )


class SQLiteJournalRepository(IJournalRepository):
    """SQLite 凭证仓库实现。"""

    def __init__(self, db_path: str = LEDGER_DB):
        self._db_path = db_path

    def init_db(self) -> None:
        """初始化凭证表和分录表。"""
        Path(self._db_path).parent.mkdir(exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_voucher (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    voucher_number TEXT UNIQUE,
                    voucher_date TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source_text TEXT DEFAULT '',
                    recorded_by TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    anomaly_flag TEXT,
                    anomaly_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column_exists(conn, "journal_voucher", "reviewed_by", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_line (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    voucher_id INTEGER NOT NULL,
                    line_no INTEGER NOT NULL,
                    subject_code TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    debit_amount REAL NOT NULL DEFAULT 0,
                    credit_amount REAL NOT NULL DEFAULT 0,
                    description TEXT DEFAULT '',
                    FOREIGN KEY(voucher_id) REFERENCES journal_voucher(id) ON DELETE CASCADE
                )
                """
            )

    def create_voucher(
        self,
        voucher: VoucherDraft,
        recorded_by: str,
    ) -> int:
        """持久化凭证。

        这里在同一事务中完成：
        1. 写入凭证头
        2. 生成规范化凭证编号
        3. 写入全部分录行

        这样可以避免“有凭证头但没有分录行”的半成品状态。
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(
                """
                INSERT INTO journal_voucher (
                    voucher_date,
                    summary,
                    source_text,
                    recorded_by,
                    status,
                    reviewed_by,
                    anomaly_flag,
                    anomaly_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    voucher.voucher_date,
                    voucher.summary,
                    voucher.source_text or "",
                    recorded_by,
                    "pending",
                    None,
                    voucher.anomaly_flag,
                    voucher.anomaly_reason,
                ),
            )
            voucher_id = cursor.lastrowid or 0
            voucher_number = self._build_voucher_number(voucher.voucher_date, voucher_id)
            conn.execute(
                "UPDATE journal_voucher SET voucher_number = ? WHERE id = ?",
                (voucher_number, voucher_id),
            )

            conn.executemany(
                """
                INSERT INTO journal_line (
                    voucher_id,
                    line_no,
                    subject_code,
                    subject_name,
                    debit_amount,
                    credit_amount,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        voucher_id,
                        index,
                        line.subject_code,
                        line.subject_name,
                        line.debit_amount,
                        line.credit_amount,
                        line.description,
                    )
                    for index, line in enumerate(voucher.lines, start=1)
                ],
            )
            conn.commit()
            return voucher_id

    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """根据主键读取凭证。"""
        vouchers = self._fetch_vouchers("WHERE v.id = ?", [voucher_id], limit=1)
        return vouchers[0] if vouchers else None

    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """获取最近一张凭证。"""
        vouchers = self._fetch_vouchers("", [], limit=1)
        return vouchers[0] if vouchers else None

    def list_vouchers(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[JournalVoucher]:
        """按日期前缀列出凭证。"""
        where_clauses: list[str] = []
        params: list[object] = []
        if date:
            where_clauses.append("v.voucher_date LIKE ?")
            params.append(f"{date}%")
        if status:
            where_clauses.append("v.status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return self._fetch_vouchers(where_sql, params, limit=limit)

    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str] = None,
    ) -> None:
        """更新凭证状态。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE journal_voucher
                SET status = ?, reviewed_by = ?
                WHERE id = ?
                """,
                (status, reviewed_by, voucher_id),
            )
            conn.commit()

    def _fetch_vouchers(
        self,
        where_sql: str,
        params: list[object],
        limit: int,
    ) -> list[JournalVoucher]:
        """统一查询凭证并装配其分录行。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            header_rows = conn.execute(
                f"""
                SELECT
                    v.id,
                    v.voucher_number,
                    v.voucher_date,
                    v.summary,
                    v.source_text,
                    v.recorded_by,
                    v.status,
                    v.reviewed_by,
                    v.anomaly_flag,
                    v.anomaly_reason,
                    v.created_at
                FROM journal_voucher v
                {where_sql}
                ORDER BY v.id DESC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()

            vouchers: list[JournalVoucher] = []
            for header in header_rows:
                line_rows = conn.execute(
                    """
                    SELECT
                        id,
                        voucher_id,
                        subject_code,
                        subject_name,
                        debit_amount,
                        credit_amount,
                        description
                    FROM journal_line
                    WHERE voucher_id = ?
                    ORDER BY line_no ASC
                    """,
                    (header["id"],),
                ).fetchall()
                vouchers.append(
                    JournalVoucher(
                        id=header["id"],
                        voucher_number=header["voucher_number"],
                        voucher_date=header["voucher_date"],
                        summary=header["summary"],
                        source_text=header["source_text"],
                        recorded_by=header["recorded_by"],
                        status=header["status"],
                        reviewed_by=header["reviewed_by"],
                        anomaly_flag=header["anomaly_flag"],
                        anomaly_reason=header["anomaly_reason"],
                        created_at=header["created_at"],
                        lines=[
                            JournalLine(
                                id=line["id"],
                                voucher_id=line["voucher_id"],
                                subject_code=line["subject_code"],
                                subject_name=line["subject_name"],
                                debit_amount=float(line["debit_amount"]),
                                credit_amount=float(line["credit_amount"]),
                                description=line["description"],
                            )
                            for line in line_rows
                        ],
                    )
                )
            return vouchers

    @staticmethod
    def _build_voucher_number(voucher_date: str, voucher_id: int) -> str:
        """生成稳定、可读的凭证编号。"""
        normalized_date = voucher_date.replace("-", "")
        return f"JV-{normalized_date}-{voucher_id:05d}"

    @staticmethod
    def _ensure_column_exists(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        """为已有 SQLite 表补充缺失列。"""
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {str(row[1]) for row in rows}
        if column_name in existing_columns:
            return
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


_chart_repository: Optional[SQLiteChartOfAccountsRepository] = None
_journal_repository: Optional[SQLiteJournalRepository] = None


def get_chart_of_accounts_repository() -> SQLiteChartOfAccountsRepository:
    """获取默认科目表仓库单例。"""
    global _chart_repository
    if _chart_repository is None:
        _chart_repository = SQLiteChartOfAccountsRepository()
    return _chart_repository


def get_journal_repository() -> SQLiteJournalRepository:
    """获取默认凭证仓库单例。"""
    global _journal_repository
    if _journal_repository is None:
        _journal_repository = SQLiteJournalRepository()
    return _journal_repository


def init_accounting_db() -> None:
    """初始化新版账务表结构。"""
    get_chart_of_accounts_repository().init_db()
    get_journal_repository().init_db()

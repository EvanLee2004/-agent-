"""SQLite 凭证仓储实现。"""

import sqlite3
from pathlib import Path
from typing import Optional

from accounting.journal_line import JournalLine
from accounting.journal_repository import JournalRepository
from accounting.journal_voucher import JournalVoucher
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.record_voucher_command import RecordVoucherCommand


DEFAULT_ACCOUNTING_DB = "data/ledger.db"
CREATE_VOUCHER_TABLE_SQL = """
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
CREATE_LINE_TABLE_SQL = """
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
INSERT_VOUCHER_SQL = """
INSERT INTO journal_voucher (
    voucher_date, summary, source_text, recorded_by, status,
    reviewed_by, anomaly_flag, anomaly_reason
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
UPDATE_VOUCHER_NUMBER_SQL = "UPDATE journal_voucher SET voucher_number = ? WHERE id = ?"
INSERT_LINE_SQL = """
INSERT INTO journal_line (
    voucher_id, line_no, subject_code, subject_name,
    debit_amount, credit_amount, description
)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
SELECT_VOUCHER_COLUMNS_SQL = """
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
"""
SELECT_LINE_ROWS_SQL = """
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
"""


def _ensure_database_directory(database_path: str) -> None:
    """确保数据库目录存在。"""
    Path(database_path).parent.mkdir(exist_ok=True)


def _create_tables(connection: sqlite3.Connection) -> None:
    """初始化凭证主表和分录表。"""
    connection.execute(CREATE_VOUCHER_TABLE_SQL)
    connection.execute(CREATE_LINE_TABLE_SQL)


def _build_voucher_number(voucher_date: str, voucher_id: int) -> str:
    """生成凭证编号。"""
    return f"JV-{voucher_date.replace('-', '')}-{voucher_id:05d}"


def _build_line_rows(voucher_id: int, command: RecordVoucherCommand) -> list[tuple]:
    """构造待写入的分录行。"""
    return [
        (
            voucher_id,
            line_number,
            line.subject_code,
            line.subject_name,
            line.debit_amount,
            line.credit_amount,
            line.description,
        )
        for line_number, line in enumerate(command.voucher_draft.lines, start=1)
    ]


def _build_line_models(line_rows: list[sqlite3.Row]) -> list[JournalLine]:
    """把分录行结果转换为领域模型。"""
    return [
        JournalLine(
            line_id=line_row["id"],
            voucher_id=line_row["voucher_id"],
            subject_code=line_row["subject_code"],
            subject_name=line_row["subject_name"],
            debit_amount=float(line_row["debit_amount"]),
            credit_amount=float(line_row["credit_amount"]),
            description=line_row["description"],
        )
        for line_row in line_rows
    ]


def _build_journal_voucher(voucher_row: sqlite3.Row, lines: list[JournalLine]) -> JournalVoucher:
    """把数据库行转换为凭证模型。"""
    return JournalVoucher(
        voucher_id=voucher_row["id"],
        voucher_number=voucher_row["voucher_number"],
        voucher_date=voucher_row["voucher_date"],
        summary=voucher_row["summary"],
        source_text=voucher_row["source_text"],
        recorded_by=voucher_row["recorded_by"],
        status=voucher_row["status"],
        reviewed_by=voucher_row["reviewed_by"],
        anomaly_flag=voucher_row["anomaly_flag"],
        anomaly_reason=voucher_row["anomaly_reason"],
        created_at=voucher_row["created_at"],
        lines=lines,
    )


def _load_voucher_lines(connection: sqlite3.Connection, voucher_id: int) -> list[JournalLine]:
    """读取某张凭证的全部分录。"""
    line_rows = connection.execute(SELECT_LINE_ROWS_SQL, (voucher_id,)).fetchall()
    return _build_line_models(line_rows)


class SQLiteJournalRepository(JournalRepository):
    """SQLite 凭证仓储实现。"""

    def __init__(self, database_path: str = DEFAULT_ACCOUNTING_DB):
        self._database_path = database_path

    def initialize_storage(self) -> None:
        """初始化凭证存储。"""
        _ensure_database_directory(self._database_path)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            _create_tables(connection)
            self._ensure_reviewed_by_column(connection)

    def create_voucher(self, command: RecordVoucherCommand, recorded_by: str) -> int:
        """创建凭证。"""
        voucher = command.voucher_draft
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                INSERT_VOUCHER_SQL,
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
            voucher_id = int(cursor.lastrowid or 0)
            connection.execute(
                UPDATE_VOUCHER_NUMBER_SQL,
                (_build_voucher_number(voucher.voucher_date, voucher_id), voucher_id),
            )
            connection.executemany(INSERT_LINE_SQL, _build_line_rows(voucher_id, command))
            connection.commit()
        return voucher_id

    def get_voucher_by_id(self, voucher_id: int) -> Optional[JournalVoucher]:
        """按主键查询凭证。"""
        vouchers = self._fetch_vouchers("WHERE v.id = ?", [voucher_id], 1)
        if vouchers:
            return vouchers[0]
        return None

    def get_latest_voucher(self) -> Optional[JournalVoucher]:
        """查询最新凭证。"""
        vouchers = self._fetch_vouchers("", [], 1)
        if vouchers:
            return vouchers[0]
        return None

    def list_vouchers(self, query: QueryVouchersQuery) -> list[JournalVoucher]:
        """按条件查询凭证。"""
        clauses = []
        params: list[object] = []
        if query.date_prefix:
            clauses.append("v.voucher_date LIKE ?")
            params.append(f"{query.date_prefix}%")
        if query.status:
            clauses.append("v.status = ?")
            params.append(query.status)
        where_sql = ""
        if clauses:
            where_sql = f"WHERE {' AND '.join(clauses)}"
        return self._fetch_vouchers(where_sql, params, query.limit)

    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str],
    ) -> None:
        """更新凭证状态。"""
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                UPDATE journal_voucher
                SET status = ?, reviewed_by = ?
                WHERE id = ?
                """,
                (status, reviewed_by, voucher_id),
            )
            connection.commit()

    def _fetch_vouchers(
        self,
        where_sql: str,
        params: list[object],
        limit: int,
    ) -> list[JournalVoucher]:
        """查询凭证及其分录。"""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            voucher_rows = connection.execute(
                f"{SELECT_VOUCHER_COLUMNS_SQL} {where_sql} ORDER BY v.id DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
            return [self._build_journal_voucher(connection, voucher_row) for voucher_row in voucher_rows]

    def _build_journal_voucher(
        self,
        connection: sqlite3.Connection,
        voucher_row: sqlite3.Row,
    ) -> JournalVoucher:
        """构造凭证模型。"""
        lines = _load_voucher_lines(connection, int(voucher_row["id"]))
        return _build_journal_voucher(voucher_row, lines)

    def _ensure_reviewed_by_column(self, connection: sqlite3.Connection) -> None:
        """兼容旧数据库缺少 reviewed_by 列的情况。

        该兼容只保留在 SQLite 实现里，是因为真实用户可能已经持有旧数据库文件。
        兼容逻辑不向上泄漏，避免污染业务服务。
        """
        rows = connection.execute("PRAGMA table_info(journal_voucher)").fetchall()
        existing_columns = {str(row[1]) for row in rows}
        if "reviewed_by" in existing_columns:
            return
        connection.execute("ALTER TABLE journal_voucher ADD COLUMN reviewed_by TEXT")

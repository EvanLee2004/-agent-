"""SQLite 凭证仓储实现。"""

from calendar import monthrange
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Optional

from accounting.account_balance import AccountBalance
from accounting.accounting_error import AccountingError
from accounting.accounting_period import AccountingPeriod
from accounting.journal_line import JournalLine
from accounting.journal_repository import JournalRepository
from accounting.journal_voucher import JournalVoucher
from accounting.ledger_entry import LedgerEntry
from accounting.query_vouchers_query import QueryVouchersQuery
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.trial_balance_report import TrialBalanceReport
from configuration.defaults import DEFAULT_DB
from configuration.schema_migration_service import (
    CREATE_ACCOUNTING_PERIOD_TABLE_SQL,
    SchemaMigrationService,
)
from configuration.sqlite_database_runtime import prepare_sqlite_connection


POSTED_REPORT_STATUSES = ("posted", "reversed")
OPEN_PERIOD_STATUS = "open"
CLOSED_PERIOD_STATUS = "closed"
VALID_PERIOD_STATUSES = {OPEN_PERIOD_STATUS, CLOSED_PERIOD_STATUS}
VALID_VOUCHER_STATUSES = {
    "draft",
    "pending",
    "reviewed",
    "posted",
    "voided",
    "reversed",
}

CREATE_VOUCHER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS journal_voucher (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_name TEXT,
    voucher_sequence INTEGER,
    voucher_number TEXT UNIQUE,
    voucher_date TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_text TEXT DEFAULT '',
    recorded_by TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    reviewed_by TEXT,
    source_voucher_id INTEGER,
    lifecycle_action TEXT DEFAULT 'normal',
    posted_at TEXT,
    voided_at TEXT,
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
    period_name, voucher_sequence, voucher_number, voucher_date,
    summary, source_text, recorded_by, status, reviewed_by,
    source_voucher_id, lifecycle_action, posted_at, voided_at,
    anomaly_flag, anomaly_reason
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
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
    v.period_name,
    v.voucher_sequence,
    v.voucher_number,
    v.voucher_date,
    v.summary,
    v.source_text,
    v.recorded_by,
    v.status,
    v.reviewed_by,
    v.source_voucher_id,
    v.lifecycle_action,
    v.posted_at,
    v.voided_at,
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
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def _create_tables(connection: sqlite3.Connection) -> None:
    """初始化凭证、分录和会计期间表。"""
    connection.execute(CREATE_ACCOUNTING_PERIOD_TABLE_SQL)
    connection.execute(CREATE_VOUCHER_TABLE_SQL)
    connection.execute(CREATE_LINE_TABLE_SQL)


def _build_period_name(voucher_date: str) -> str:
    """从凭证日期推导会计期间。"""
    try:
        parsed_date = datetime.strptime(voucher_date, "%Y-%m-%d")
    except ValueError as error:
        raise AccountingError("voucher_date 必须使用 YYYY-MM-DD 格式") from error
    return parsed_date.strftime("%Y%m")


def _build_period_dates(period_name: str) -> tuple[str, str]:
    """从 YYYYMM 构造期间起止日期。"""
    if len(period_name) != 6 or not period_name.isdigit():
        raise AccountingError("period_name 必须使用 YYYYMM 格式")
    year = int(period_name[:4])
    month = int(period_name[4:])
    if month < 1 or month > 12:
        raise AccountingError("period_name 月份必须在 01 到 12 之间")
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def _build_voucher_number(period_name: str, voucher_sequence: int) -> str:
    """生成期间内连续凭证编号。"""
    return f"JV-{period_name}-{voucher_sequence:04d}"


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


def _build_reversal_line_rows(voucher_id: int, original: JournalVoucher) -> list[tuple]:
    """构造红冲凭证分录行。

    红冲不删除原凭证，而是新建借贷方向相反的凭证。这样报表只需要按已过账凭证
    汇总借贷发生额，红冲影响会自然抵减，审计链路也能追溯到原凭证。
    """
    return [
        (
            voucher_id,
            line_number,
            line.subject_code,
            line.subject_name,
            line.credit_amount,
            line.debit_amount,
            f"红冲 {original.voucher_number}: {line.description}",
        )
        for line_number, line in enumerate(original.lines, start=1)
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


def _build_journal_voucher(
    voucher_row: sqlite3.Row, lines: list[JournalLine]
) -> JournalVoucher:
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
        period_name=voucher_row["period_name"] or "",
        voucher_sequence=int(voucher_row["voucher_sequence"] or 0),
        source_voucher_id=voucher_row["source_voucher_id"],
        lifecycle_action=voucher_row["lifecycle_action"] or "normal",
        posted_at=voucher_row["posted_at"],
        voided_at=voucher_row["voided_at"],
    )


def _build_period(row: sqlite3.Row) -> AccountingPeriod:
    """把数据库行转换为会计期间模型。"""
    return AccountingPeriod(
        period_name=row["period_name"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        status=row["status"],
        closed_at=row["closed_at"],
    )


def _load_voucher_lines(
    connection: sqlite3.Connection, voucher_id: int
) -> list[JournalLine]:
    """读取某张凭证的全部分录。"""
    line_rows = connection.execute(SELECT_LINE_ROWS_SQL, (voucher_id,)).fetchall()
    return _build_line_models(line_rows)


class SQLiteJournalRepository(JournalRepository):
    """SQLite 凭证仓储实现。"""

    def __init__(self, database_path: str = DEFAULT_DB):
        self._database_path = database_path

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return self._database_path

    def initialize_storage(self) -> None:
        """初始化凭证存储并执行 schema 迁移。"""
        _ensure_database_directory(self._database_path)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection, enable_wal=True)
            _create_tables(connection)
            connection.commit()
        SchemaMigrationService(self._database_path).migrate()

    def create_voucher(self, command: RecordVoucherCommand, recorded_by: str) -> int:
        """创建凭证。"""
        voucher = command.voucher_draft
        period_name = _build_period_name(voucher.voucher_date)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_period_open(connection, period_name)
            voucher_sequence = self._next_voucher_sequence(connection, period_name)
            voucher_number = _build_voucher_number(period_name, voucher_sequence)
            cursor = connection.execute(
                INSERT_VOUCHER_SQL,
                (
                    period_name,
                    voucher_sequence,
                    voucher_number,
                    voucher.voucher_date,
                    voucher.summary,
                    voucher.source_text or "",
                    recorded_by,
                    "pending",
                    None,
                    None,
                    "normal",
                    None,
                    None,
                    voucher.anomaly_flag,
                    voucher.anomaly_reason,
                ),
            )
            if not cursor.lastrowid:
                raise AccountingError("凭证写入失败")
            voucher_id = int(cursor.lastrowid)
            connection.executemany(
                INSERT_LINE_SQL, _build_line_rows(voucher_id, command)
            )
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
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._fetch_vouchers(where_sql, params, query.limit)

    def update_status(
        self,
        voucher_id: int,
        status: str,
        reviewed_by: Optional[str],
    ) -> None:
        """更新凭证状态。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT period_name FROM journal_voucher WHERE id = ?",
                (voucher_id,),
            ).fetchone()
            if row is None:
                raise AccountingError(f"凭证 {voucher_id} 不存在或已删除")
            self._ensure_period_open(connection, str(row[0]))
            cursor = connection.execute(
                """
                UPDATE journal_voucher
                SET status = ?, reviewed_by = ?
                WHERE id = ?
                """,
                (status, reviewed_by, voucher_id),
            )
            if cursor.rowcount == 0:
                raise AccountingError(f"凭证 {voucher_id} 不存在或已删除")
            connection.commit()

    def list_periods(self) -> list[AccountingPeriod]:
        """列出全部会计期间。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT period_name, start_date, end_date, status, closed_at
                FROM accounting_period
                ORDER BY period_name ASC
                """
            ).fetchall()
        return [_build_period(row) for row in rows]

    def open_period(self, period_name: str) -> AccountingPeriod:
        """打开或创建会计期间。"""
        start_date, end_date = _build_period_dates(period_name)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute(
                """
                INSERT INTO accounting_period (period_name, start_date, end_date, status)
                VALUES (?, ?, ?, 'open')
                ON CONFLICT(period_name) DO UPDATE SET
                    status = 'open',
                    closed_at = NULL
                """,
                (period_name, start_date, end_date),
            )
            connection.commit()
        period = self._get_period(period_name)
        if period is None:
            raise AccountingError(f"会计期间 {period_name} 打开失败")
        return period

    def close_period(self, period_name: str) -> AccountingPeriod:
        """关闭会计期间。"""
        period = self._get_period(period_name)
        if period is None:
            raise AccountingError(f"会计期间 {period_name} 不存在")
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute(
                """
                UPDATE accounting_period
                SET status = 'closed', closed_at = datetime('now', 'utc')
                WHERE period_name = ?
                """,
                (period_name,),
            )
            connection.commit()
        closed_period = self._get_period(period_name)
        if closed_period is None:
            raise AccountingError(f"会计期间 {period_name} 关闭失败")
        return closed_period

    def post_voucher(self, voucher_id: int) -> JournalVoucher:
        """将凭证标记为已过账。"""
        voucher = self.get_voucher_by_id(voucher_id)
        if voucher is None:
            raise AccountingError(f"凭证 {voucher_id} 不存在")
        if voucher.status in POSTED_REPORT_STATUSES:
            return voucher
        if voucher.status == "voided":
            raise AccountingError("已作废凭证不能过账")
        self._require_period_open(voucher.period_name)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute(
                """
                UPDATE journal_voucher
                SET status = 'posted', posted_at = COALESCE(posted_at, datetime('now', 'utc'))
                WHERE id = ?
                """,
                (voucher_id,),
            )
            connection.commit()
        posted = self.get_voucher_by_id(voucher_id)
        if posted is None:
            raise AccountingError(f"凭证 {voucher_id} 不存在")
        return posted

    def void_voucher(self, voucher_id: int) -> JournalVoucher:
        """作废未过账凭证。"""
        voucher = self.get_voucher_by_id(voucher_id)
        if voucher is None:
            raise AccountingError(f"凭证 {voucher_id} 不存在")
        if voucher.status in POSTED_REPORT_STATUSES:
            raise AccountingError("已过账凭证不能作废，请使用红冲")
        if voucher.status == "voided":
            return voucher
        self._require_period_open(voucher.period_name)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute(
                """
                UPDATE journal_voucher
                SET status = 'voided', voided_at = datetime('now', 'utc')
                WHERE id = ?
                """,
                (voucher_id,),
            )
            connection.commit()
        voided = self.get_voucher_by_id(voucher_id)
        if voided is None:
            raise AccountingError(f"凭证 {voucher_id} 不存在")
        return voided

    def reverse_voucher(self, command: ReverseVoucherCommand) -> JournalVoucher:
        """创建红冲凭证并保留原凭证的财务影响。"""
        original = self.get_voucher_by_id(command.voucher_id)
        if original is None:
            raise AccountingError(f"凭证 {command.voucher_id} 不存在")
        if original.status not in POSTED_REPORT_STATUSES:
            raise AccountingError("只有已过账凭证可以红冲")
        existing_reversal = self._get_reversal_by_source(command.voucher_id)
        if existing_reversal is not None:
            return existing_reversal
        reversal_date = command.reversal_date or original.voucher_date
        period_name = _build_period_name(reversal_date)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_period_open(connection, period_name)
            voucher_sequence = self._next_voucher_sequence(connection, period_name)
            voucher_number = _build_voucher_number(period_name, voucher_sequence)
            cursor = connection.execute(
                INSERT_VOUCHER_SQL,
                (
                    period_name,
                    voucher_sequence,
                    voucher_number,
                    reversal_date,
                    f"红冲 {original.voucher_number}: {original.summary}",
                    original.source_text,
                    command.recorded_by,
                    "posted",
                    "system",
                    original.voucher_id,
                    "reversal",
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    None,
                    None,
                    None,
                ),
            )
            if not cursor.lastrowid:
                raise AccountingError("红冲凭证写入失败")
            reversal_id = int(cursor.lastrowid)
            connection.executemany(
                INSERT_LINE_SQL, _build_reversal_line_rows(reversal_id, original)
            )
            connection.execute(
                """
                UPDATE journal_voucher
                SET status = 'reversed'
                WHERE id = ?
                """,
                (original.voucher_id,),
            )
            connection.commit()
        reversed_voucher = self.get_voucher_by_id(reversal_id)
        if reversed_voucher is None:
            raise AccountingError("红冲凭证写入失败")
        return reversed_voucher

    def _get_reversal_by_source(self, source_voucher_id: int) -> JournalVoucher | None:
        """查找某张凭证已生成的红冲凭证。"""
        vouchers = self._fetch_vouchers(
            "WHERE v.source_voucher_id = ? AND v.lifecycle_action = 'reversal'",
            [source_voucher_id],
            1,
        )
        if not vouchers:
            return None
        return vouchers[0]

    def list_account_balances(
        self,
        period_name: str | None = None,
    ) -> list[AccountBalance]:
        """查询已过账凭证形成的科目余额。"""
        where_sql, params = self._build_posted_where(period_name)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    l.subject_code,
                    l.subject_name,
                    s.normal_balance,
                    ROUND(SUM(l.debit_amount), 2) AS debit_total,
                    ROUND(SUM(l.credit_amount), 2) AS credit_total
                FROM journal_line l
                JOIN journal_voucher v ON v.id = l.voucher_id
                LEFT JOIN account_subject s ON s.code = l.subject_code
                {where_sql}
                GROUP BY l.subject_code, l.subject_name, s.normal_balance
                ORDER BY l.subject_code ASC
                """,
                params,
            ).fetchall()
        return [self._build_account_balance(row) for row in rows]

    def list_ledger_entries(
        self,
        period_name: str | None = None,
        subject_code: str | None = None,
        limit: int = 200,
    ) -> list[LedgerEntry]:
        """查询总账/明细账行。"""
        where_sql, params = self._build_posted_where(period_name)
        if subject_code:
            where_sql = f"{where_sql} AND l.subject_code = ?"
            params.append(subject_code)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    v.id AS voucher_id,
                    v.voucher_number,
                    v.voucher_date,
                    v.period_name,
                    v.summary,
                    l.subject_code,
                    l.subject_name,
                    l.debit_amount,
                    l.credit_amount,
                    l.description
                FROM journal_line l
                JOIN journal_voucher v ON v.id = l.voucher_id
                {where_sql}
                ORDER BY v.voucher_date ASC, v.voucher_sequence ASC, l.line_no ASC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
        return [
            LedgerEntry(
                voucher_id=row["voucher_id"],
                voucher_number=row["voucher_number"],
                voucher_date=row["voucher_date"],
                period_name=row["period_name"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                debit_amount=float(row["debit_amount"]),
                credit_amount=float(row["credit_amount"]),
                summary=row["summary"],
                description=row["description"],
            )
            for row in rows
        ]

    def build_trial_balance(
        self,
        period_name: str | None = None,
    ) -> TrialBalanceReport:
        """生成试算平衡报告。"""
        rows = self.list_account_balances(period_name)
        debit_total = round(sum(row.debit_total for row in rows), 2)
        credit_total = round(sum(row.credit_total for row in rows), 2)
        difference = round(debit_total - credit_total, 2)
        return TrialBalanceReport(
            period_name=period_name,
            debit_total=debit_total,
            credit_total=credit_total,
            difference=difference,
            balanced=abs(difference) <= 0.01,
            rows=rows,
        )

    def run_integrity_check(self) -> list[str]:
        """执行账簿完整性检查。"""
        issues: list[str] = []
        issues.extend(self._check_voucher_balance())
        issues.extend(self._check_voucher_periods())
        issues.extend(self._check_period_statuses())
        issues.extend(self._check_voucher_statuses())
        issues.extend(self._check_bank_links())
        return issues

    def _fetch_vouchers(
        self,
        where_sql: str,
        params: list[object],
        limit: int,
    ) -> list[JournalVoucher]:
        """查询凭证及其分录。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            voucher_rows = connection.execute(
                f"{SELECT_VOUCHER_COLUMNS_SQL} {where_sql} ORDER BY v.id DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
            return [
                self._build_journal_voucher(connection, voucher_row)
                for voucher_row in voucher_rows
            ]

    def _build_journal_voucher(
        self,
        connection: sqlite3.Connection,
        voucher_row: sqlite3.Row,
    ) -> JournalVoucher:
        """构造凭证模型。"""
        lines = _load_voucher_lines(connection, int(voucher_row["id"]))
        return _build_journal_voucher(voucher_row, lines)

    def _get_period(self, period_name: str) -> AccountingPeriod | None:
        """读取会计期间。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT period_name, start_date, end_date, status, closed_at
                FROM accounting_period
                WHERE period_name = ?
                """,
                (period_name,),
            ).fetchone()
        if row is None:
            return None
        return _build_period(row)

    def _ensure_period_open(
        self,
        connection: sqlite3.Connection,
        period_name: str,
    ) -> None:
        """确保期间存在且未结账。"""
        start_date, end_date = _build_period_dates(period_name)
        connection.execute(
            """
            INSERT OR IGNORE INTO accounting_period (period_name, start_date, end_date, status)
            VALUES (?, ?, ?, 'open')
            """,
            (period_name, start_date, end_date),
        )
        row = connection.execute(
            "SELECT status FROM accounting_period WHERE period_name = ?",
            (period_name,),
        ).fetchone()
        if row is None or row[0] != OPEN_PERIOD_STATUS:
            raise AccountingError(f"会计期间 {period_name} 已结账，不能写入或修改凭证")

    def _require_period_open(self, period_name: str) -> None:
        """在独立连接中校验期间开启状态。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            self._ensure_period_open(connection, period_name)

    def _next_voucher_sequence(
        self,
        connection: sqlite3.Connection,
        period_name: str,
    ) -> int:
        """获取期间内下一凭证序号。"""
        row = connection.execute(
            """
            SELECT COALESCE(MAX(voucher_sequence), 0)
            FROM journal_voucher
            WHERE period_name = ?
            """,
            (period_name,),
        ).fetchone()
        return int(row[0] or 0) + 1

    def _build_posted_where(self, period_name: str | None) -> tuple[str, list[object]]:
        """构造报表查询条件。"""
        placeholders = ", ".join("?" for _ in POSTED_REPORT_STATUSES)
        clauses = [f"v.status IN ({placeholders})"]
        params: list[object] = list(POSTED_REPORT_STATUSES)
        if period_name:
            clauses.append("v.period_name = ?")
            params.append(period_name)
        return f"WHERE {' AND '.join(clauses)}", params

    def _build_account_balance(self, row: sqlite3.Row) -> AccountBalance:
        """从聚合行构造科目余额。"""
        debit_total = round(float(row["debit_total"] or 0), 2)
        credit_total = round(float(row["credit_total"] or 0), 2)
        normal_balance = row["normal_balance"] or "debit"
        raw_balance = (
            debit_total - credit_total
            if normal_balance == "debit"
            else credit_total - debit_total
        )
        balance_direction = normal_balance if raw_balance >= 0 else self._opposite(normal_balance)
        return AccountBalance(
            subject_code=row["subject_code"],
            subject_name=row["subject_name"],
            normal_balance=normal_balance,
            debit_total=debit_total,
            credit_total=credit_total,
            balance_direction=balance_direction,
            balance_amount=round(abs(raw_balance), 2),
        )

    def _opposite(self, direction: str) -> str:
        """返回相反余额方向。"""
        return "credit" if direction == "debit" else "debit"

    def _check_voucher_balance(self) -> list[str]:
        """检查凭证借贷平衡。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            rows = connection.execute(
                """
                SELECT
                    v.id,
                    ROUND(SUM(l.debit_amount), 2) AS debit_total,
                    ROUND(SUM(l.credit_amount), 2) AS credit_total
                FROM journal_voucher v
                JOIN journal_line l ON l.voucher_id = v.id
                GROUP BY v.id
                HAVING ABS(debit_total - credit_total) > 0.01
                """
            ).fetchall()
        return [
            f"凭证 {row[0]} 借贷不平：借方 {row[1]:.2f}，贷方 {row[2]:.2f}"
            for row in rows
        ]

    def _check_voucher_periods(self) -> list[str]:
        """检查凭证期间存在性和编号连续性。"""
        issues: list[str] = []
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            missing_rows = connection.execute(
                """
                SELECT v.id, v.period_name
                FROM journal_voucher v
                LEFT JOIN accounting_period p ON p.period_name = v.period_name
                WHERE p.period_name IS NULL
                """
            ).fetchall()
            period_rows = connection.execute(
                """
                SELECT period_name, voucher_sequence
                FROM journal_voucher
                ORDER BY period_name ASC, voucher_sequence ASC
                """
            ).fetchall()
            mismatch_rows = connection.execute(
                """
                SELECT id, voucher_date, period_name
                FROM journal_voucher
                WHERE period_name != substr(voucher_date, 1, 4) || substr(voucher_date, 6, 2)
                """
            ).fetchall()
        issues.extend(
            [f"凭证 {row[0]} 引用不存在的会计期间 {row[1]}" for row in missing_rows]
        )
        issues.extend(
            [
                f"凭证 {row[0]} 日期 {row[1]} 与会计期间 {row[2]} 不一致"
                for row in mismatch_rows
            ]
        )
        sequences_by_period: dict[str, list[int]] = {}
        for period_name, sequence in period_rows:
            sequences_by_period.setdefault(str(period_name), []).append(int(sequence or 0))
        for period_name, sequences in sequences_by_period.items():
            expected = list(range(1, len(sequences) + 1))
            if sequences != expected:
                issues.append(f"会计期间 {period_name} 凭证编号不连续")
        return issues

    def _check_period_statuses(self) -> list[str]:
        """检查会计期间状态是否在受控生命周期内。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            rows = connection.execute(
                """
                SELECT period_name, status
                FROM accounting_period
                """
            ).fetchall()
        return [
            f"会计期间 {row[0]} 状态非法：{row[1]}"
            for row in rows
            if row[1] not in VALID_PERIOD_STATUSES
        ]

    def _check_voucher_statuses(self) -> list[str]:
        """检查凭证状态是否在受控生命周期内。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            rows = connection.execute(
                """
                SELECT id, status
                FROM journal_voucher
                """
            ).fetchall()
        return [
            f"凭证 {row[0]} 状态非法：{row[1]}"
            for row in rows
            if row[1] not in VALID_VOUCHER_STATUSES
        ]

    def _check_bank_links(self) -> list[str]:
        """检查银行流水关联凭证是否存在。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            has_bank_table = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'bank_transaction'
                """
            ).fetchone()
            if has_bank_table is None:
                return []
            rows = connection.execute(
                """
                SELECT b.id, b.linked_voucher_id
                FROM bank_transaction b
                LEFT JOIN journal_voucher v ON v.id = b.linked_voucher_id
                WHERE b.linked_voucher_id IS NOT NULL AND v.id IS NULL
                """
            ).fetchall()
        return [f"银行流水 {row[0]} 关联不存在的凭证 {row[1]}" for row in rows]

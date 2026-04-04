"""SQLite 出纳仓储实现。"""

import sqlite3
from pathlib import Path

from cashier.cash_transaction import CashTransaction
from cashier.cashier_error import CashierError
from cashier.cashier_repository import CashierRepository
from cashier.query_cash_transactions_query import QueryCashTransactionsQuery
from cashier.record_cash_transaction_command import RecordCashTransactionCommand
from configuration.defaults import DEFAULT_DB


CREATE_CASH_TRANSACTION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cash_transaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount REAL NOT NULL,
    account_name TEXT NOT NULL,
    summary TEXT NOT NULL,
    counterparty TEXT DEFAULT '',
    status TEXT DEFAULT 'completed',
    related_voucher_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def _ensure_database_directory(database_path: str) -> None:
    """确保数据库目录存在。"""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def _build_cash_transaction(row: sqlite3.Row) -> CashTransaction:
    """把数据库行转换为资金收付模型。"""
    return CashTransaction(
        transaction_id=row["id"],
        transaction_date=row["transaction_date"],
        direction=row["direction"],
        amount=float(row["amount"]),
        account_name=row["account_name"],
        summary=row["summary"],
        counterparty=row["counterparty"],
        status=row["status"],
        related_voucher_id=row["related_voucher_id"],
        created_at=row["created_at"],
    )


class SQLiteCashierRepository(CashierRepository):
    """SQLite 出纳仓储实现。"""

    def __init__(self, database_path: str = DEFAULT_DB):
        self._database_path = database_path

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return self._database_path

    def initialize_storage(self) -> None:
        """初始化出纳存储。"""
        _ensure_database_directory(self._database_path)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(CREATE_CASH_TRANSACTION_TABLE_SQL)
            connection.commit()

    def create_transaction(self, command: RecordCashTransactionCommand) -> int:
        """新增资金收付记录。"""
        with sqlite3.connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO cash_transaction (
                    transaction_date, direction, amount, account_name,
                    summary, counterparty, status, related_voucher_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command.transaction_date,
                    command.direction,
                    command.amount,
                    command.account_name,
                    command.summary,
                    command.counterparty,
                    command.status,
                    command.related_voucher_id,
                ),
            )
            connection.commit()
            if not cursor.lastrowid:
                raise CashierError("资金收付记录写入失败")
            return int(cursor.lastrowid)

    def list_transactions(
        self, query: QueryCashTransactionsQuery
    ) -> list[CashTransaction]:
        """查询资金收付记录。"""
        clauses = []
        params: list[object] = []
        if query.date_prefix:
            clauses.append("transaction_date LIKE ?")
            params.append(f"{query.date_prefix}%")
        if query.direction:
            clauses.append("direction = ?")
            params.append(query.direction)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    transaction_date,
                    direction,
                    amount,
                    account_name,
                    summary,
                    counterparty,
                    status,
                    related_voucher_id,
                    created_at
                FROM cash_transaction
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                [*params, query.limit],
            ).fetchall()
        return [_build_cash_transaction(row) for row in rows]

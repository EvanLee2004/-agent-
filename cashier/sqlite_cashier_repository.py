"""SQLite 出纳/银行仓储。"""

import sqlite3
from pathlib import Path

from cashier.bank_transaction import BankTransaction
from cashier.cashier_error import CashierError
from cashier.cashier_repository import CashierRepository
from cashier.query_bank_transactions_query import QueryBankTransactionsQuery
from cashier.record_bank_transaction_command import RecordBankTransactionCommand
from configuration.defaults import DEFAULT_DB
from configuration.sqlite_database_runtime import prepare_sqlite_connection


CREATE_BANK_TRANSACTION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bank_transaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inflow', 'outflow')),
    amount REAL NOT NULL CHECK (amount > 0),
    account_name TEXT NOT NULL,
    counterparty TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unreconciled'
        CHECK (status IN ('unreconciled', 'reconciled')),
    linked_voucher_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def _build_transaction(row: sqlite3.Row) -> BankTransaction:
    """把数据库行转换为银行流水模型。"""
    return BankTransaction(
        transaction_id=row["id"],
        transaction_date=row["transaction_date"],
        direction=row["direction"],
        amount=float(row["amount"]),
        account_name=row["account_name"],
        counterparty=row["counterparty"],
        summary=row["summary"],
        status=row["status"],
        linked_voucher_id=row["linked_voucher_id"],
        created_at=row["created_at"],
    )


class SQLiteCashierRepository(CashierRepository):
    """SQLite 银行流水仓储实现。"""

    def __init__(self, database_path: str = DEFAULT_DB):
        self._database_path = database_path

    def initialize_storage(self) -> None:
        """初始化银行流水表。"""
        Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection, enable_wal=True)
            connection.execute(CREATE_BANK_TRANSACTION_TABLE_SQL)
            connection.commit()

    def create_transaction(self, command: RecordBankTransactionCommand) -> int:
        """创建银行流水。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            cursor = connection.execute(
                """
                INSERT INTO bank_transaction (
                    transaction_date, direction, amount, account_name,
                    counterparty, summary, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'unreconciled')
                """,
                (
                    command.transaction_date,
                    command.direction,
                    command.amount,
                    command.account_name,
                    command.counterparty,
                    command.summary,
                ),
            )
            if not cursor.lastrowid:
                raise CashierError("银行流水写入失败")
            connection.commit()
            return int(cursor.lastrowid)

    def list_transactions(
        self,
        query: QueryBankTransactionsQuery,
    ) -> list[BankTransaction]:
        """查询银行流水。"""
        clauses = []
        params: list[object] = []
        if query.date_prefix:
            clauses.append("transaction_date LIKE ?")
            params.append(f"{query.date_prefix}%")
        if query.status:
            clauses.append("status = ?")
            params.append(query.status)
        if query.direction:
            clauses.append("direction = ?")
            params.append(query.direction)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT id, transaction_date, direction, amount, account_name,
                       counterparty, summary, status, linked_voucher_id, created_at
                FROM bank_transaction
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                [*params, query.limit],
            ).fetchall()
        return [_build_transaction(row) for row in rows]

    def get_transaction_by_id(self, transaction_id: int) -> BankTransaction | None:
        """按主键查询银行流水。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, transaction_date, direction, amount, account_name,
                       counterparty, summary, status, linked_voucher_id, created_at
                FROM bank_transaction
                WHERE id = ?
                """,
                (transaction_id,),
            ).fetchone()
        if row is None:
            return None
        return _build_transaction(row)

    def mark_reconciled(
        self,
        transaction_id: int,
        linked_voucher_id: int | None,
    ) -> None:
        """标记银行流水已对账。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            cursor = connection.execute(
                """
                UPDATE bank_transaction
                SET status = 'reconciled', linked_voucher_id = ?
                WHERE id = ?
                """,
                (linked_voucher_id, transaction_id),
            )
            if cursor.rowcount == 0:
                raise CashierError(f"银行流水 {transaction_id} 不存在")
            connection.commit()

    def mark_unreconciled(self, transaction_id: int) -> None:
        """解除银行流水对账。"""
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection)
            cursor = connection.execute(
                """
                UPDATE bank_transaction
                SET status = 'unreconciled', linked_voucher_id = NULL
                WHERE id = ?
                """,
                (transaction_id,),
            )
            if cursor.rowcount == 0:
                raise CashierError(f"银行流水 {transaction_id} 不存在")
            connection.commit()

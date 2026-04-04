"""应用引导器。"""

import sqlite3

from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.journal_repository import JournalRepository
from accounting.sqlite_chart_of_accounts_repository import (
    CREATE_ACCOUNT_SUBJECT_TABLE_SQL,
)
from accounting.sqlite_journal_repository import (
    CREATE_LINE_TABLE_SQL,
    CREATE_VOUCHER_TABLE_SQL,
)
from cashier.cashier_repository import CashierRepository
from cashier.sqlite_cashier_repository import CREATE_CASH_TRANSACTION_TABLE_SQL


class ApplicationBootstrapper:
    """应用引导器。"""

    def __init__(
        self,
        chart_of_accounts_repository: ChartOfAccountsRepository,
        journal_repository: JournalRepository,
        chart_of_accounts_service: ChartOfAccountsService,
        cashier_repository: CashierRepository,
    ):
        self._chart_of_accounts_repository = chart_of_accounts_repository
        self._journal_repository = journal_repository
        self._chart_of_accounts_service = chart_of_accounts_service
        self._cashier_repository = cashier_repository

    def initialize(self) -> None:
        """初始化数据库和默认会计科目。

        使用单一连接执行所有建表语句，保证原子性。中间任何一步失败都会回滚，
        不会出现三库建表进度不一致的状态。
        """
        db_path = self._journal_repository.database_path
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(CREATE_ACCOUNT_SUBJECT_TABLE_SQL)
            connection.execute(CREATE_VOUCHER_TABLE_SQL)
            connection.execute(CREATE_LINE_TABLE_SQL)
            connection.execute(CREATE_CASH_TRANSACTION_TABLE_SQL)
            connection.commit()
        self._chart_of_accounts_service.initialize_default_subjects()

"""SQLite 科目仓储实现。"""

import sqlite3
from pathlib import Path
from typing import Optional

from accounting.account_subject import AccountSubject
from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from configuration.defaults import DEFAULT_DB

CREATE_ACCOUNT_SUBJECT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS account_subject (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    normal_balance TEXT NOT NULL,
    description TEXT DEFAULT ''
)
"""


def _build_subject_row(subject: AccountSubject) -> tuple[str, str, str, str, str]:
    """构造单条科目写入行。"""
    return (
        subject.code,
        subject.name,
        subject.category,
        subject.normal_balance,
        subject.description,
    )


class SQLiteChartOfAccountsRepository(ChartOfAccountsRepository):
    """SQLite 科目仓储实现。"""

    def __init__(self, database_path: str = DEFAULT_DB):
        self._database_path = database_path

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return self._database_path

    def initialize_storage(self) -> None:
        """初始化科目表。"""
        Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(CREATE_ACCOUNT_SUBJECT_TABLE_SQL)

    def save_subjects(self, subjects: list[AccountSubject]) -> None:
        """写入科目数据。"""
        if not subjects:
            return

        with sqlite3.connect(self._database_path) as connection:
            connection.executemany(
                """
                INSERT INTO account_subject (code, name, category, normal_balance, description)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    normal_balance = excluded.normal_balance,
                    description = excluded.description
                """,
                [_build_subject_row(subject) for subject in subjects],
            )
            connection.commit()

    def list_subjects(self) -> list[AccountSubject]:
        """列出全部科目。"""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT code, name, category, normal_balance, description
                FROM account_subject
                ORDER BY code
                """
            ).fetchall()
        return [self._build_account_subject(row) for row in rows]

    def get_subject_by_code(self, subject_code: str) -> Optional[AccountSubject]:
        """按编码读取科目。"""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT code, name, category, normal_balance, description
                FROM account_subject
                WHERE code = ?
                """,
                (subject_code,),
            ).fetchone()
        if row is None:
            return None
        return self._build_account_subject(row)

    def _build_account_subject(self, row: sqlite3.Row) -> AccountSubject:
        """构造科目模型。

        Args:
            row: SQLite 行对象。

        Returns:
            标准化的科目模型。
        """
        return AccountSubject(
            code=row["code"],
            name=row["name"],
            category=row["category"],
            normal_balance=row["normal_balance"],
            description=row["description"],
        )

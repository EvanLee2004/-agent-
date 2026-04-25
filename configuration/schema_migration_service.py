"""SQLite schema migration 服务。"""

import sqlite3

from configuration.sqlite_database_runtime import prepare_sqlite_connection


CURRENT_SCHEMA_VERSION = 2

CREATE_SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT DEFAULT (datetime('now', 'utc'))
)
"""

CREATE_ACCOUNTING_PERIOD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS accounting_period (
    period_name TEXT PRIMARY KEY,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    closed_at TEXT
)
"""

CREATE_JOURNAL_VOUCHER_PERIOD_SEQUENCE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_journal_voucher_period_sequence
ON journal_voucher(period_name, voucher_sequence)
WHERE period_name IS NOT NULL AND voucher_sequence IS NOT NULL
"""


class SchemaMigrationService:
    """集中管理本地 SQLite schema 迁移。

    早期版本把“缺列时 ALTER TABLE”的兼容逻辑放在具体 repository 里。
    进入生产化阶段后，schema 生命周期必须收口到一个服务，避免业务仓储混入
    启动迁移细节，也便于未来升级时判断当前数据库版本。
    """

    def __init__(self, database_path: str):
        self._database_path = database_path

    def migrate(self) -> None:
        """执行幂等迁移。

        迁移过程允许重复运行：新库会直接建成最新结构，旧库会补列、补期间、
        补期间内凭证序号，并记录当前 schema 版本。
        """
        with sqlite3.connect(self._database_path) as connection:
            prepare_sqlite_connection(connection, enable_wal=True)
            connection.execute(CREATE_SCHEMA_MIGRATIONS_SQL)
            connection.execute(CREATE_ACCOUNTING_PERIOD_TABLE_SQL)
            self._ensure_journal_voucher_columns(connection)
            self._backfill_periods(connection)
            self._ensure_indexes(connection)
            self._record_current_version(connection)
            connection.commit()

    def _ensure_journal_voucher_columns(self, connection: sqlite3.Connection) -> None:
        """为旧凭证表补齐生产级生命周期字段。"""
        columns = self._list_columns(connection, "journal_voucher")
        self._add_column_if_missing(connection, columns, "period_name", "TEXT")
        self._add_column_if_missing(connection, columns, "voucher_sequence", "INTEGER")
        self._add_column_if_missing(connection, columns, "source_voucher_id", "INTEGER")
        self._add_column_if_missing(
            connection,
            columns,
            "lifecycle_action",
            "TEXT DEFAULT 'normal'",
        )
        self._add_column_if_missing(connection, columns, "posted_at", "TEXT")
        self._add_column_if_missing(connection, columns, "voided_at", "TEXT")

    def _backfill_periods(self, connection: sqlite3.Connection) -> None:
        """把旧凭证映射到凭证日期所属期间，并补齐期间内连续号。

        旧库的凭证号形如 `JV-YYYYMMDD-00001`，不满足期间内连续编号要求。
        这里按同一期间内的自增 ID 顺序生成 `JV-YYYYMM-0001`，保证迁移后
        报表、查询和后续新增凭证都使用同一口径。
        """
        connection.execute(
            """
            UPDATE journal_voucher
            SET period_name = substr(voucher_date, 1, 4) || substr(voucher_date, 6, 2)
            WHERE period_name IS NULL OR period_name = ''
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO accounting_period (period_name, start_date, end_date, status)
            SELECT DISTINCT
                period_name,
                substr(period_name, 1, 4) || '-' || substr(period_name, 5, 2) || '-01',
                date(substr(period_name, 1, 4) || '-' || substr(period_name, 5, 2) || '-01',
                    '+1 month', '-1 day'),
                'open'
            FROM journal_voucher
            WHERE period_name IS NOT NULL AND period_name != ''
            """
        )
        period_rows = connection.execute(
            """
            SELECT DISTINCT period_name
            FROM journal_voucher
            WHERE period_name IS NOT NULL AND period_name != ''
            ORDER BY period_name
            """
        ).fetchall()
        for (period_name,) in period_rows:
            voucher_rows = connection.execute(
                """
                SELECT id
                FROM journal_voucher
                WHERE period_name = ?
                ORDER BY id ASC
                """,
                (period_name,),
            ).fetchall()
            for sequence, (voucher_id,) in enumerate(voucher_rows, start=1):
                connection.execute(
                    """
                    UPDATE journal_voucher
                    SET voucher_sequence = ?,
                        voucher_number = ?,
                        lifecycle_action = COALESCE(lifecycle_action, 'normal')
                    WHERE id = ?
                    """,
                    (sequence, f"JV-{period_name}-{sequence:04d}", voucher_id),
                )

    def _record_current_version(self, connection: sqlite3.Connection) -> None:
        """记录当前 schema 版本。"""
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, description)
            VALUES (?, ?)
            """,
            (CURRENT_SCHEMA_VERSION, "production finance backend core"),
        )

    def _ensure_indexes(self, connection: sqlite3.Connection) -> None:
        """建立生产约束索引。

        SQLite 无法通过 `ALTER TABLE` 直接补 `UNIQUE(period_name, sequence)`，
        所以迁移完成数据回填后创建唯一索引。这样旧库能平滑升级，新库也能在
        数据库层防止同一会计期间出现重复凭证序号。
        """
        connection.execute(CREATE_JOURNAL_VOUCHER_PERIOD_SEQUENCE_INDEX_SQL)

    def _list_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
    ) -> set[str]:
        """读取表字段集合。"""
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _add_column_if_missing(
        self,
        connection: sqlite3.Connection,
        columns: set[str],
        column_name: str,
        column_definition: str,
    ) -> None:
        """缺列时追加字段，并更新本地字段集合。"""
        if column_name in columns:
            return
        connection.execute(
            f"ALTER TABLE journal_voucher ADD COLUMN {column_name} {column_definition}"
        )
        columns.add(column_name)

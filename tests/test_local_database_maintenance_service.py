"""本地数据库维护服务测试。"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.local_database_maintenance_service import LocalDatabaseMaintenanceService


class LocalDatabaseMaintenanceServiceTest(unittest.TestCase):
    """验证 SQLite 备份与恢复能力。"""

    def test_backup_and_restore_database(self):
        """账簿数据库可以备份并从备份恢复。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ledger.db"
            backup_path = Path(tmpdir) / "backup.db"
            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
                connection.execute("INSERT INTO sample (name) VALUES ('before')")
                connection.commit()
            service = LocalDatabaseMaintenanceService(db_path)

            service.backup_to(backup_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute("DELETE FROM sample")
                connection.commit()
            service.restore_from(backup_path)

            with sqlite3.connect(db_path) as connection:
                rows = connection.execute("SELECT name FROM sample").fetchall()
            self.assertEqual(rows, [("before",)])


if __name__ == "__main__":
    unittest.main()

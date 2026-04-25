"""本地数据库维护服务。"""

from pathlib import Path

from configuration.sqlite_database_runtime import (
    backup_sqlite_database,
    restore_sqlite_database,
)


class LocalDatabaseMaintenanceService:
    """提供本地私有部署需要的数据库备份与恢复能力。

    当前项目 v1 面向单个小公司本地部署。备份/恢复不放进会计业务服务里，是因为它
    属于运维能力；也不放进 runtime/crewai，避免第三方 Agent 运行时和数据库生命周期
    耦合。
    """

    def __init__(self, database_path: str | Path):
        self._database_path = Path(database_path)

    def backup_to(self, destination_path: str | Path) -> None:
        """备份主账簿数据库。"""
        backup_sqlite_database(self._database_path, destination_path)

    def restore_from(self, backup_path: str | Path) -> None:
        """从备份恢复主账簿数据库。"""
        restore_sqlite_database(backup_path, self._database_path)

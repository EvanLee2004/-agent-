"""SQLite 本地部署运行参数。"""

import sqlite3
from pathlib import Path


def prepare_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    enable_wal: bool = False,
) -> None:
    """应用本地私有部署的 SQLite 连接参数。

    Args:
        connection: 已打开的 SQLite 连接。
        enable_wal: 是否尝试启用 WAL。建表/初始化阶段启用即可持久化到数据库文件。
    """
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if enable_wal:
        connection.execute("PRAGMA journal_mode = WAL")


def backup_sqlite_database(source_path: str | Path, destination_path: str | Path) -> None:
    """备份 SQLite 数据库。

    Args:
        source_path: 源数据库路径。
        destination_path: 备份文件路径。
    """
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"SQLite 源数据库不存在: {source}")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def restore_sqlite_database(backup_path: str | Path, destination_path: str | Path) -> None:
    """从备份恢复 SQLite 数据库。

    Args:
        backup_path: 备份文件路径。
        destination_path: 恢复目标路径。
    """
    backup = Path(backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"SQLite 备份文件不存在: {backup}")
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup) as backup_connection:
        with sqlite3.connect(destination) as destination_connection:
            backup_connection.backup(destination_connection)

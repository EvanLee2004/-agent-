"""会计工具调用持久化幂等跟踪器。"""

import hashlib
import json
import sqlite3
from pathlib import Path

from configuration.sqlite_database_runtime import prepare_sqlite_connection
from conversation.tool_router_response import ToolRouterResponse


DEFAULT_IDEMPOTENCY_DB = Path(".runtime/crewai/idempotency.db")
_IDEMPOTENCY_DB_PATH = DEFAULT_IDEMPOTENCY_DB

CREATE_IDEMPOTENCY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tool_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'utc'))
)
"""


def configure_idempotency_store(database_path: str | Path) -> None:
    """配置幂等存储路径。

    Args:
        database_path: SQLite 幂等数据库路径。
    """
    global _IDEMPOTENCY_DB_PATH
    _IDEMPOTENCY_DB_PATH = Path(database_path)
    _ensure_storage()


def compute_idempotency_key(
    thread_id: str,
    tool_name: str,
    arguments: dict,
) -> str:
    """计算持久化幂等 key。

    crewAI 可能在同一任务中重试工具调用，服务也可能在写账后重启。记账是有副作用
    的写操作，因此 key 必须同时包含 thread_id、工具名和规范化参数，确保同一请求
    重放时返回原结果，不重复落库。
    """
    normalized_arguments = json.dumps(arguments, sort_keys=True, ensure_ascii=True)
    args_hash = hashlib.sha256(normalized_arguments.encode()).hexdigest()[:32]
    return f"{thread_id}:{tool_name}:{args_hash}"


def check_idempotency(key: str) -> ToolRouterResponse | None:
    """读取幂等记录。"""
    _ensure_storage()
    with _connect() as connection:
        row = connection.execute(
            "SELECT response_json FROM tool_idempotency WHERE idempotency_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    return ToolRouterResponse.from_tool_message_content(str(row[0]))


def record_idempotency(key: str, response: ToolRouterResponse) -> None:
    """保存幂等记录。"""
    _ensure_storage()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO tool_idempotency (idempotency_key, response_json)
            VALUES (?, ?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
                response_json = excluded.response_json
            """,
            (key, response.to_tool_message_content()),
        )
        connection.commit()


def clear_idempotency() -> None:
    """清空幂等存储。

    生产路径不应主动清空幂等记录；该入口用于测试和 `clear_db.sh` 类本地重置场景。
    """
    if not _IDEMPOTENCY_DB_PATH.exists():
        return
    with _connect() as connection:
        connection.execute("DELETE FROM tool_idempotency")
        connection.commit()


def _ensure_storage() -> None:
    """确保幂等数据库存在。"""
    _IDEMPOTENCY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        prepare_sqlite_connection(connection, enable_wal=True)
        connection.execute(CREATE_IDEMPOTENCY_TABLE_SQL)
        connection.commit()


def _connect() -> sqlite3.Connection:
    """创建幂等数据库连接。"""
    connection = sqlite3.connect(str(_IDEMPOTENCY_DB_PATH))
    prepare_sqlite_connection(connection)
    return connection

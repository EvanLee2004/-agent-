"""Session 管理模块，使用 SQLite 存储对话历史"""

import sqlite3
from pathlib import Path
from datetime import datetime


class SessionManager:
    """会话管理器，负责对话历史的存储和读取"""

    def __init__(self, db_path: str = "sessions/sessions.db"):
        """初始化会话管理器

        Args:
            db_path: 数据库文件路径，默认保存在 sessions/sessions.db
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库，创建 sessions 和 messages 两张表"""
        conn = sqlite3.connect(self.db_path)

        # 创建 sessions 表：存储会话列表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,           -- 会话唯一标识符
                title TEXT NOT NULL,           -- 会话标题
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP   -- 更新时间
            )
        """)

        # 创建 messages 表：存储消息
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 消息唯一ID
                session_id TEXT NOT NULL,             -- 所属会话ID
                role TEXT NOT NULL,                    -- 消息角色：system/user/assistant
                content TEXT NOT NULL,                 -- 消息内容
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # 创建索引，加速按 session_id 查询
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)
        """)

        conn.commit()
        conn.close()

    def create(self, title: str) -> str:
        """创建新会话

        Args:
            title: 会话标题

        Returns:
            session_id: 新创建的会话ID，格式为 YYYYMMDD_HHMMSS
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)", (session_id, title)
        )
        conn.commit()
        conn.close()
        return session_id

    def add(self, session_id: str, role: str, content: str):
        """添加消息到指定会话

        Args:
            session_id: 会话ID
            role: 消息角色，"user" 或 "assistant"
            content: 消息内容
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()

    def get(self, session_id: str) -> list[dict]:
        """获取指定会话的所有消息

        Args:
            session_id: 会话ID

        Returns:
            消息列表，每条是 {"role": "...", "content": "..."}
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_all(self, limit: int = 10) -> list[dict]:
        """列出最近的会话

        Args:
            limit: 返回数量限制，默认10条

        Returns:
            会话列表，每条包含 id, title, created_at, updated_at
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

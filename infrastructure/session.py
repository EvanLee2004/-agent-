"""Session management module.

Manages conversation sessions with SQLite persistence.
Supports:
- Creating and listing sessions
- Adding messages to sessions
- Retrieving session history
- Token counting for compaction triggers
- Summary tracking (for compaction)

Each session has:
- id: Unique session identifier (YYYYMMDD_HHMMSS format)
- title: Session title
- messages: Conversation history (stored in messages table)
- token_count: Running token estimate for the session
- summary: Compressed summary when history is compacted
- summary_message_id: DB message ID of the summary
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from infrastructure.token_counter import TokenCounter


class ConversationSession:
    """内存中的会话对象。

    追踪消息、token 计数和会话状态。
    此对象存在于内存中，通过 SessionManager 持久化。

    Attributes:
        session_id: 唯一标识符。
        title: 会话标题。
        agent_name: 关联的 Agent 名称（用于记忆查询）。
        messages: 消息字典列表，包含 'role' 和 'content'。
        token_count: 估算的总 token 数量。
        summary: 压缩后的摘要文本。
        summary_message_id: 摘要在数据库中的消息 ID。
    """

    def __init__(
        self,
        session_id: str,
        title: str = "",
        agent_name: str = "manager",
        messages: Optional[list[dict]] = None,
        token_count: int = 0,
        summary: Optional[str] = None,
        summary_message_id: Optional[int] = None,
    ):
        """初始化会话。

        Args:
            session_id: 唯一标识符。
            title: 会话标题。
            agent_name: 关联的 Agent 名称（用于记忆查询）。
            messages: 初始消息列表（默认空）。
            token_count: 初始 token 计数（默认 0）。
            summary: 现有摘要文本（如果有）。
            summary_message_id: 摘要的消息 ID（如果有）。
        """
        self.session_id = session_id
        self.title = title
        self.agent_name = agent_name
        self.messages: list[dict] = messages or []
        self.token_count = token_count
        self.summary = summary
        self.summary_message_id = summary_message_id

    def add_message(self, role: str, content: str) -> None:
        """Add a message and update token count.

        Args:
            role: Message role ('user' or 'assistant').
            content: Message content.
        """
        self.messages.append({"role": role, "content": content})
        self.token_count += TokenCounter.estimate_from_text(content) + 4

    def get_messages(self) -> list[dict]:
        """Get all messages in the session.

        Returns:
            List of message dicts.
        """
        return self.messages

    def has_summary(self) -> bool:
        """Check if session has a summary (has been compacted).

        Returns:
            True if session has been compacted, False otherwise.
        """
        return self.summary is not None

    def compact_with_summary(self, summary: str, summary_message_id: int) -> None:
        """Replace session history with summary after compaction.

        Args:
            summary: The summary text.
            summary_message_id: DB message ID of the summary message.
        """
        self.messages = [
            {
                "role": "assistant",
                "content": f"[Previous conversation summary]\n{summary}",
            }
        ]
        self.summary = summary
        self.summary_message_id = summary_message_id
        self.token_count = TokenCounter.estimate_from_text(summary) + 10


class SessionManager:
    """Manages session persistence to SQLite database.

    Handles:
    - Creating new sessions
    - Adding messages to sessions
    - Retrieving session history
    - Tracking summaries for compaction

    Database schema:
    - sessions: id, title, created_at, updated_at, summary, summary_message_id
    - messages: id, session_id, role, content, created_at
    """

    def __init__(self, db_path: str = "sessions/sessions.db"):
        """Initialize the session manager.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """创建数据库表（如果不存在）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                summary_message_id INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)"
        )
        conn.commit()
        conn.close()

    def create(self, title: str = "") -> str:
        """Create a new session.

        Args:
            title: Session title.

        Returns:
            Session ID string in YYYYMMDD_HHMMSS format.
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)",
            (session_id, title or "New Session"),
        )
        conn.commit()
        conn.close()
        return session_id

    def add_message(self, session_id: str, role: str, content: str) -> Optional[int]:
        """Add a message to a session.

        Args:
            session_id: Session ID.
            role: Message role ('user' or 'assistant').
            content: Message content.

        Returns:
            Message ID if successful, None if session not found.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            msg_id = cursor.lastrowid
            conn.close()
            return msg_id
        except sqlite3.Error:
            conn.close()
            return None

    def get_messages(self, session_id: str) -> list[dict]:
        """Get all messages for a session.

        Args:
            session_id: Session ID.

        Returns:
            List of message dicts with 'role' and 'content'.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get session metadata.

        Args:
            session_id: Session ID.

        Returns:
            Dict with session info including summary and summary_message_id,
            or None if session not found.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_summary(
        self, session_id: str, summary: str, summary_message_id: int
    ) -> bool:
        """Update session with summary information after compaction.

        Args:
            session_id: Session ID.
            summary: Summary text.
            summary_message_id: Message ID of the summary in DB.

        Returns:
            True if update successful, False otherwise.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE sessions
                   SET summary = ?, summary_message_id = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (summary, summary_message_id, session_id),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error:
            conn.close()
            return False

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session dicts with id, title, created_at, updated_at.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, title, created_at, updated_at
               FROM sessions
               ORDER BY updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_or_create_session(
        self, session_id: Optional[str] = None
    ) -> tuple[str, list[dict]]:
        """Get existing session or create a new one.

        If session_id is provided and exists, returns that session.
        Otherwise creates a new session.

        Args:
            session_id: Optional session ID to retrieve.

        Returns:
            Tuple of (session_id, messages).
        """
        if session_id:
            info = self.get_session_info(session_id)
            if info:
                return session_id, self.get_messages(session_id)

        new_id = self.create()
        return new_id, []

    def load_session(self, session_id: str) -> Optional[ConversationSession]:
        """Load a session from database into a ConversationSession object.

        Args:
            session_id: Session ID to load.

        Returns:
            ConversationSession object, or None if not found.
        """
        info = self.get_session_info(session_id)
        if not info:
            return None

        messages = self.get_messages(session_id)
        token_count = TokenCounter.estimate_messages(messages)

        return ConversationSession(
            session_id=session_id,
            title=info.get("title", ""),
            messages=messages,
            token_count=token_count,
            summary=info.get("summary"),
            summary_message_id=info.get("summary_message_id"),
        )

"""OpenClaw 风格长期记忆基础设施。

当前实现参考 OpenClaw 的公开记忆形态：
- 工作区根目录 `MEMORY.md`：长期、稳定、可反复复用的记忆
- 工作区目录 `memory/YYYY-MM-DD.md`：每天的短期/上下文记忆

设计目标：
1. 让“长期偏好/稳定事实”和“短期上下文”分层存储。
2. 让 Agent 通过统一接口读写记忆，而不是直接拼文件路径。
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from domain.models import (
    MemoryDecision,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
)
from infrastructure.memory_index import IMemoryIndex, SQLiteMemoryIndex


DEFAULT_MEMORY_LIMIT = 10
LONG_TERM_MEMORY_FILE = Path("MEMORY.md")
DAILY_MEMORY_DIR = Path("memory")

class IAgentMemoryStore(ABC):
    """Agent 记忆存储接口。"""

    @abstractmethod
    def store_memory_decision(self, agent_name: str, decision: MemoryDecision) -> None:
        """根据记忆决策写入长期或每日记忆。"""
        pass

    @abstractmethod
    def get_memory_context(
        self,
        agent_name: str,
        query: Optional[str] = None,
        limit: int = DEFAULT_MEMORY_LIMIT,
    ) -> str:
        """获取适合注入 Prompt 的记忆上下文。"""
        pass

    @abstractmethod
    def search_memories(
        self,
        query: str,
        limit: int = DEFAULT_MEMORY_LIMIT,
    ) -> list[MemorySearchResult]:
        """根据查询搜索相关记忆片段。"""
        pass

    @abstractmethod
    def get_memory_file(
        self,
        scope: MemoryScope,
        target_date: Optional[str] = None,
    ) -> Optional[str]:
        """读取指定记忆文件的原始内容。"""
        pass

    @abstractmethod
    def clear_memory(self, agent_name: str) -> None:
        """清理长期记忆和每日记忆。"""
        pass


class OpenClawMemoryStore(IAgentMemoryStore):
    """OpenClaw 风格记忆存储实现。"""

    def __init__(
        self,
        long_term_memory_file: Optional[Path] = None,
        daily_memory_dir: Optional[Path] = None,
        memory_index: Optional[IMemoryIndex] = None,
    ):
        self._long_term_memory_file = long_term_memory_file or LONG_TERM_MEMORY_FILE
        self._daily_memory_dir = daily_memory_dir or DAILY_MEMORY_DIR
        self._memory_index = memory_index or SQLiteMemoryIndex()

    def store_memory_decision(self, agent_name: str, decision: MemoryDecision) -> None:
        """根据记忆决策写入记忆。"""
        if not decision.should_store:
            return

        self._ensure_layout()

        if decision.scope == MemoryScope.LONG_TERM:
            self._store_long_term_record(
                MemoryRecord(
                    scope=MemoryScope.LONG_TERM,
                    category=decision.category or "general",
                    content=(decision.content or "").strip(),
                    recorded_at=datetime.now().strftime("%Y-%m-%d"),
                )
            )
            self._rebuild_index()
            return

        self._store_daily_record(
            MemoryRecord(
                scope=MemoryScope.DAILY,
                category=decision.category or "general",
                content=(decision.content or "").strip(),
                recorded_at=datetime.now().strftime("%H:%M"),
            )
        )
        self._rebuild_index()

    def get_memory_context(
        self,
        agent_name: str,
        query: Optional[str] = None,
        limit: int = DEFAULT_MEMORY_LIMIT,
    ) -> str:
        """获取 Prompt 注入用记忆上下文。

        当前实现遵循“长期记忆 + 今日/昨日记忆”的思路：
        - 长期记忆始终注入，因为它代表稳定用户偏好和事实
        - 每日记忆只取最近两天，避免上下文无限膨胀
        """
        if query:
            relevant_records = self.search_memories(query=query, limit=limit)
            if relevant_records:
                sections = ["【相关记忆】"]
                for record in relevant_records:
                    label = "长期" if record.scope == MemoryScope.LONG_TERM else "每日"
                    sections.append(
                        f"- [{label}/{record.category}] {record.content}"
                    )
                return "\n\n" + "\n".join(sections)

        long_term_records = self._read_long_term_records()[:limit]
        daily_records = self._read_recent_daily_records(days=2)[:limit]

        sections = []
        if long_term_records:
            sections.append("【长期记忆】")
            for record in long_term_records:
                sections.append(
                    f"- [{record.category}] {record.content}"
                )

        if daily_records:
            sections.append("【近期记忆】")
            for record in daily_records:
                sections.append(
                    f"- [{record.recorded_at}] ({record.category}) {record.content}"
                )

        if sections:
            return "\n\n" + "\n".join(sections)
        return ""

    def clear_memory(self, agent_name: str) -> None:
        """清理长期和每日记忆。"""
        del agent_name

        if self._long_term_memory_file.exists():
            self._long_term_memory_file.unlink()

        if self._daily_memory_dir.exists():
            for path in self._daily_memory_dir.glob("*.md"):
                path.unlink()

    def _ensure_layout(self) -> None:
        """确保基础目录存在。"""
        self._daily_memory_dir.mkdir(parents=True, exist_ok=True)

    def _store_long_term_record(self, record: MemoryRecord) -> None:
        """写入长期记忆。

        文件格式采用纯 Markdown section + bullet list，便于人和模型直接阅读：

        # Long-Term Memory
        ## Preference
        - 2026-04-01 用户偏好 ...
        """
        existing = self._read_long_term_records()
        if self._is_duplicate(existing, record):
            return

        records = existing + [record]
        grouped = self._group_records_by_category(records)

        lines = [
            "# Long-Term Memory",
            "",
            "长期稳定的用户偏好、事实和决策。",
            "",
        ]
        for category in sorted(grouped.keys()):
            lines.append(f"## {category}")
            for item in grouped[category]:
                lines.append(f"- {item.recorded_at} {item.content}")
            lines.append("")

        self._long_term_memory_file.write_text("\n".join(lines), encoding="utf-8")

    def _store_daily_record(self, record: MemoryRecord) -> None:
        """写入每日记忆。"""
        self._daily_memory_dir.mkdir(parents=True, exist_ok=True)
        today_file = self._daily_memory_dir / f"{date.today().isoformat()}.md"
        existing = self._read_daily_records(today_file)
        if self._is_duplicate(existing, record):
            return

        if today_file.exists():
            content = today_file.read_text(encoding="utf-8").rstrip()
            content += f"\n- [{record.recorded_at}] ({record.category}) {record.content}\n"
        else:
            content = "\n".join(
                [
                    f"# Daily Memory - {date.today().isoformat()}",
                    "",
                    "当天的重要上下文、待办和短期约束。",
                    "",
                    f"- [{record.recorded_at}] ({record.category}) {record.content}",
                    "",
                ]
            )
        today_file.write_text(content, encoding="utf-8")

    def _read_long_term_records(self) -> list[MemoryRecord]:
        """读取长期记忆文件。"""
        if not self._long_term_memory_file.exists():
            return []

        lines = self._long_term_memory_file.read_text(encoding="utf-8").splitlines()
        records: list[MemoryRecord] = []
        current_category = "general"
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("## "):
                current_category = stripped_line[3:].strip().lower()
                continue

            if not stripped_line.startswith("- "):
                continue

            bullet_content = stripped_line[2:]
            parts = bullet_content.split(" ", 1)
            recorded_at = parts[0]
            content = parts[1].strip() if len(parts) > 1 else ""
            if content:
                records.append(
                    MemoryRecord(
                        scope=MemoryScope.LONG_TERM,
                        category=current_category,
                        content=content,
                        recorded_at=recorded_at,
                    )
                )
        return records

    def _read_recent_daily_records(self, days: int = 2) -> list[MemoryRecord]:
        """读取最近若干天的每日记忆。"""
        records: list[MemoryRecord] = []
        for offset in range(days):
            target_date = date.today() - timedelta(days=offset)
            file_path = self._daily_memory_dir / f"{target_date.isoformat()}.md"
            records.extend(self._read_daily_records(file_path))
        return records

    def _read_daily_records(self, file_path: Path) -> list[MemoryRecord]:
        """读取单个每日记忆文件。"""
        if not file_path.exists():
            return []

        records: list[MemoryRecord] = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped_line = line.strip()
            if not stripped_line.startswith("- ["):
                continue

            closing_bracket_index = stripped_line.find("]")
            if closing_bracket_index == -1:
                continue
            recorded_at = stripped_line[3:closing_bracket_index]

            remainder = stripped_line[closing_bracket_index + 1 :].strip()
            category = "general"
            content = remainder
            if remainder.startswith("(") and ")" in remainder:
                category_end_index = remainder.find(")")
                category = remainder[1:category_end_index].strip().lower()
                content = remainder[category_end_index + 1 :].strip()

            if content:
                records.append(
                    MemoryRecord(
                        scope=MemoryScope.DAILY,
                        category=category,
                        content=content,
                        recorded_at=recorded_at,
                    )
                )
        return records

    def search_memories(
        self,
        query: str,
        limit: int = DEFAULT_MEMORY_LIMIT,
    ) -> list[MemorySearchResult]:
        """搜索相关记忆。

        当前实现使用 SQLite FTS5 对 Markdown 记忆文件建立索引，
        更接近 OpenClaw 文档中 `memory_search` 的检索式使用方式。
        """
        self._rebuild_index()
        return self._memory_index.search(query=query, limit=limit)

    def get_memory_file(
        self,
        scope: MemoryScope,
        target_date: Optional[str] = None,
        start_line: Optional[int] = None,
        line_count: Optional[int] = None,
    ) -> Optional[str]:
        """读取记忆文件原文。

        Args:
            scope: 记忆范围，长期或每日。
            target_date: 当 scope 为 daily 时指定日期，格式 `YYYY-MM-DD`。
            start_line: 可选，起始行号（1-based）。
            line_count: 可选，读取的行数。

        Returns:
            文件内容；若文件不存在则返回 None。
        """
        if scope == MemoryScope.LONG_TERM:
            if not self._long_term_memory_file.exists():
                return None
            content = self._long_term_memory_file.read_text(encoding="utf-8")
            return self._slice_text_by_line(content, start_line, line_count)

        if not target_date:
            target_date = date.today().isoformat()

        daily_file = self._daily_memory_dir / f"{target_date}.md"
        if not daily_file.exists():
            return None
        content = daily_file.read_text(encoding="utf-8")
        return self._slice_text_by_line(content, start_line, line_count)

    @staticmethod
    def _is_duplicate(existing_records: list[MemoryRecord], new_record: MemoryRecord) -> bool:
        """判断是否与已有记忆重复。"""
        normalized_new_content = new_record.content.strip()
        for record in existing_records:
            if (
                record.category == new_record.category
                and record.content.strip() == normalized_new_content
            ):
                return True
        return False

    @staticmethod
    def _group_records_by_category(
        records: list[MemoryRecord],
    ) -> dict[str, list[MemoryRecord]]:
        """按分类对长期记忆分组。"""
        grouped_records: dict[str, list[MemoryRecord]] = {}
        for record in records:
            grouped_records.setdefault(record.category, []).append(record)
        return grouped_records

    def _rebuild_index(self) -> None:
        """根据当前记忆文件重建 SQLite 索引。"""
        self._memory_index.rebuild_index(
            long_term_file=self._long_term_memory_file,
            daily_memory_dir=self._daily_memory_dir,
        )

    @staticmethod
    def _slice_text_by_line(
        content: str,
        start_line: Optional[int],
        line_count: Optional[int],
    ) -> str:
        """按行裁剪文本，近似 OpenClaw `memory_get` 的片段读取。"""
        if start_line is None or line_count is None:
            return content

        all_lines = content.splitlines()
        start_index = max(start_line - 1, 0)
        end_index = start_index + max(line_count, 0)
        return "\n".join(all_lines[start_index:end_index])


_memory_store: Optional[OpenClawMemoryStore] = None


def get_memory_store() -> OpenClawMemoryStore:
    """获取默认记忆存储实例。"""
    global _memory_store
    if _memory_store is None:
        _memory_store = OpenClawMemoryStore()
    return _memory_store

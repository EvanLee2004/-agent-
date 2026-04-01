"""Markdown 记忆存储仓储实现。"""

from datetime import date, datetime, timedelta
from pathlib import Path

from memory.memory_decision import MemoryDecision
from memory.memory_record import MemoryRecord
from memory.memory_scope import MemoryScope
from memory.memory_store_repository import MemoryStoreRepository


LONG_TERM_MEMORY_FILE = Path("MEMORY.md")
DAILY_MEMORY_DIR = Path("memory")


def _build_memory_record(scope: MemoryScope, category: str, content: str) -> MemoryRecord:
    """构造标准化记忆记录。"""
    recorded_at = datetime.now().strftime("%Y-%m-%d")
    if scope == MemoryScope.DAILY:
        recorded_at = datetime.now().strftime("%H:%M")
    return MemoryRecord(
        scope=scope,
        category=(category or "general").strip(),
        content=(content or "").strip(),
        recorded_at=recorded_at,
    )


def _parse_long_term_records(long_term_memory_file: Path) -> list[MemoryRecord]:
    """解析长期记忆文件。"""
    if not long_term_memory_file.exists():
        return []
    records = []
    current_category = "general"
    for line in long_term_memory_file.read_text(encoding="utf-8").splitlines():
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
        if not content:
            continue
        records.append(
            MemoryRecord(
                scope=MemoryScope.LONG_TERM,
                category=current_category,
                content=content,
                recorded_at=recorded_at,
            )
        )
    return records


def _parse_daily_records(file_path: Path) -> list[MemoryRecord]:
    """解析单个每日记忆文件。"""
    if not file_path.exists():
        return []
    records = []
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
        if not content:
            continue
        records.append(
            MemoryRecord(
                scope=MemoryScope.DAILY,
                category=category,
                content=content,
                recorded_at=recorded_at,
            )
        )
    return records


def _is_duplicate_record(existing_records: list[MemoryRecord], new_record: MemoryRecord) -> bool:
    """判断是否存在重复记忆。"""
    return any(
        record.scope == new_record.scope
        and record.category == new_record.category
        and record.content == new_record.content
        for record in existing_records
    )


def _group_records_by_category(records: list[MemoryRecord]) -> dict[str, list[MemoryRecord]]:
    """按分类聚合长期记忆。"""
    grouped_records: dict[str, list[MemoryRecord]] = {}
    for record in records:
        grouped_records.setdefault(record.category, []).append(record)
    return grouped_records


def _render_long_term_memory(records: list[MemoryRecord]) -> str:
    """渲染长期记忆文档内容。"""
    grouped_records = _group_records_by_category(records)
    lines = ["# Long-Term Memory", "", "长期稳定的用户偏好、事实和决策。", ""]
    for category in sorted(grouped_records.keys()):
        lines.append(f"## {category}")
        lines.extend([f"- {item.recorded_at} {item.content}" for item in grouped_records[category]])
        lines.append("")
    return "\n".join(lines)


def _build_daily_record_line(memory_record: MemoryRecord) -> str:
    """渲染单条每日记忆记录。"""
    return f"- [{memory_record.recorded_at}] ({memory_record.category}) {memory_record.content}"


def _render_new_daily_memory(memory_record: MemoryRecord) -> str:
    """渲染新的每日记忆文件。"""
    return "\n".join(
        [
            f"# Daily Memory - {date.today().isoformat()}",
            "",
            "当天的重要上下文、待办和短期约束。",
            "",
            _build_daily_record_line(memory_record),
            "",
        ]
    )


class MarkdownMemoryStoreRepository(MemoryStoreRepository):
    """Markdown 记忆存储仓储实现。"""

    def __init__(
        self,
        long_term_memory_file: Path = LONG_TERM_MEMORY_FILE,
        daily_memory_dir: Path = DAILY_MEMORY_DIR,
    ):
        self._long_term_memory_file = long_term_memory_file
        self._daily_memory_dir = daily_memory_dir

    def store_memory_decision(self, agent_name: str, memory_decision: MemoryDecision) -> None:
        """根据决策写入记忆。"""
        del agent_name
        if not memory_decision.should_store():
            return
        self._ensure_layout()
        memory_record = _build_memory_record(
            memory_decision.scope,
            memory_decision.category or "general",
            memory_decision.content or "",
        )
        if memory_decision.scope == MemoryScope.LONG_TERM:
            self._store_long_term_record(memory_record)
            return
        self._store_daily_record(memory_record)

    def read_long_term_records(self) -> list[MemoryRecord]:
        """读取长期记忆。"""
        return _parse_long_term_records(self._long_term_memory_file)

    def read_recent_daily_records(self, days: int) -> list[MemoryRecord]:
        """读取近期每日记忆。"""
        records = []
        for offset in range(days):
            target_date = date.today() - timedelta(days=offset)
            records.extend(self._read_daily_records(self._daily_memory_dir / f"{target_date.isoformat()}.md"))
        return records

    def clear_memory(self, agent_name: str) -> None:
        """清理记忆。"""
        del agent_name
        if self._long_term_memory_file.exists():
            self._long_term_memory_file.unlink()
        if not self._daily_memory_dir.exists():
            return
        for memory_file in self._daily_memory_dir.glob("*.md"):
            memory_file.unlink()

    def get_long_term_memory_file(self) -> Path:
        """返回长期记忆文件路径。"""
        return self._long_term_memory_file

    def get_daily_memory_dir(self) -> Path:
        """返回每日记忆目录路径。"""
        return self._daily_memory_dir

    def _ensure_layout(self) -> None:
        """确保目录存在。"""
        self._daily_memory_dir.mkdir(parents=True, exist_ok=True)

    def _store_long_term_record(self, memory_record: MemoryRecord) -> None:
        """写入长期记忆。"""
        existing_records = self.read_long_term_records()
        if _is_duplicate_record(existing_records, memory_record):
            return
        content = _render_long_term_memory(existing_records + [memory_record])
        self._long_term_memory_file.write_text(content, encoding="utf-8")

    def _store_daily_record(self, memory_record: MemoryRecord) -> None:
        """写入每日记忆。"""
        today_file = self._daily_memory_dir / f"{date.today().isoformat()}.md"
        existing_records = _parse_daily_records(today_file)
        if _is_duplicate_record(existing_records, memory_record):
            return
        if today_file.exists():
            content = today_file.read_text(encoding="utf-8").rstrip()
            content += f"\n{_build_daily_record_line(memory_record)}\n"
            today_file.write_text(content, encoding="utf-8")
            return
        today_file.write_text(_render_new_daily_memory(memory_record), encoding="utf-8")

    def _read_daily_records(self, file_path: Path) -> list[MemoryRecord]:
        """读取单个每日记忆文件。"""
        return _parse_daily_records(file_path)

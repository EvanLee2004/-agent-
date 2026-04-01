"""SQLite 记忆索引。

该模块实现“Markdown 记忆文件是源数据，SQLite FTS5 是搜索索引”的架构。
这与 OpenClaw 文档里“文件是记忆载体，搜索是独立能力”的设计更接近。
"""

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from domain.models import MemoryScope, MemorySearchResult


@dataclass
class MemoryChunk:
    """待索引的记忆片段。"""

    path: str
    scope: MemoryScope
    category: str
    content: str
    start_line: int
    end_line: int
    search_text: str


class IMemoryIndex(ABC):
    """记忆索引抽象接口。"""

    @abstractmethod
    def rebuild_index(self, long_term_file: Path, daily_memory_dir: Path) -> None:
        """根据当前记忆文件重建索引。"""
        pass

    @abstractmethod
    def search(self, query: str, limit: int) -> list[MemorySearchResult]:
        """执行记忆搜索。"""
        pass


class SQLiteMemoryIndex(IMemoryIndex):
    """基于 SQLite FTS5 的记忆索引实现。"""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or Path(".opencode/cache/memory_search.sqlite")

    def rebuild_index(self, long_term_file: Path, daily_memory_dir: Path) -> None:
        """重建 FTS 索引。

        当前项目的记忆文件数量很小，因此采用全量重建策略。
        这样实现简单、确定性强，也更容易测试。
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        chunks = self._load_chunks(long_term_file, daily_memory_dir)
        with sqlite3.connect(self._db_path) as connection:
            self._ensure_tables(connection)
            connection.execute("DELETE FROM memory_chunks_fts")
            connection.executemany(
                """
                INSERT INTO memory_chunks_fts
                (path, scope, category, content, start_line, end_line, search_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.path,
                        chunk.scope.value,
                        chunk.category,
                        chunk.content,
                        str(chunk.start_line),
                        str(chunk.end_line),
                        chunk.search_text,
                    )
                    for chunk in chunks
                ],
            )
            connection.commit()

    def search(self, query: str, limit: int) -> list[MemorySearchResult]:
        """执行 FTS 搜索。"""
        search_terms = self._tokenize_query(query)
        if not search_terms:
            return []

        search_expression = " OR ".join(
            self._escape_fts_term(term) for term in search_terms[:12]
        )
        with sqlite3.connect(self._db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    path,
                    scope,
                    category,
                    content,
                    start_line,
                    end_line,
                    bm25(memory_chunks_fts) AS rank
                FROM memory_chunks_fts
                WHERE memory_chunks_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (search_expression, limit),
            ).fetchall()

        return [
            MemorySearchResult(
                path=str(row[0]),
                scope=MemoryScope(str(row[1])),
                category=str(row[2]),
                content=str(row[3]),
                start_line=int(row[4]),
                end_line=int(row[5]),
                score=float(-row[6]),
            )
            for row in rows
        ]

    def _ensure_tables(self, connection: sqlite3.Connection) -> None:
        """初始化 FTS 表。"""
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks_fts
            USING fts5(
                path UNINDEXED,
                scope UNINDEXED,
                category UNINDEXED,
                content UNINDEXED,
                start_line UNINDEXED,
                end_line UNINDEXED,
                search_text
            )
            """
        )

    def _load_chunks(self, long_term_file: Path, daily_memory_dir: Path) -> list[MemoryChunk]:
        """从长期记忆和每日记忆文件中提取索引片段。"""
        chunks = []
        chunks.extend(self._load_long_term_chunks(long_term_file))
        chunks.extend(self._load_daily_chunks(daily_memory_dir))
        return chunks

    def _load_long_term_chunks(self, long_term_file: Path) -> list[MemoryChunk]:
        """从 `MEMORY.md` 提取长期记忆片段。"""
        if not long_term_file.exists():
            return []

        lines = long_term_file.read_text(encoding="utf-8").splitlines()
        chunks: list[MemoryChunk] = []
        current_category = "general"

        for line_number, line in enumerate(lines, start=1):
            stripped_line = line.strip()
            if stripped_line.startswith("## "):
                current_category = stripped_line[3:].strip().lower()
                continue

            if not stripped_line.startswith("- "):
                continue

            bullet_content = stripped_line[2:]
            parts = bullet_content.split(" ", 1)
            content = parts[1].strip() if len(parts) > 1 else bullet_content.strip()
            if not content:
                continue

            chunks.append(
                MemoryChunk(
                    path=str(long_term_file),
                    scope=MemoryScope.LONG_TERM,
                    category=current_category,
                    content=content,
                    start_line=line_number,
                    end_line=line_number,
                    search_text=self._build_search_text(current_category, content),
                )
            )
        return chunks

    def _load_daily_chunks(self, daily_memory_dir: Path) -> list[MemoryChunk]:
        """从 `memory/YYYY-MM-DD.md` 提取每日记忆片段。"""
        if not daily_memory_dir.exists():
            return []

        chunks: list[MemoryChunk] = []
        for daily_file in sorted(daily_memory_dir.glob("*.md")):
            lines = daily_file.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                stripped_line = line.strip()
                if not stripped_line.startswith("- ["):
                    continue

                closing_bracket_index = stripped_line.find("]")
                if closing_bracket_index == -1:
                    continue

                remainder = stripped_line[closing_bracket_index + 1 :].strip()
                category = "general"
                content = remainder
                if remainder.startswith("(") and ")" in remainder:
                    category_end_index = remainder.find(")")
                    category = remainder[1:category_end_index].strip().lower()
                    content = remainder[category_end_index + 1 :].strip()

                if not content:
                    continue

                chunks.append(
                    MemoryChunk(
                        path=str(daily_file),
                        scope=MemoryScope.DAILY,
                        category=category,
                        content=content,
                        start_line=line_number,
                        end_line=line_number,
                        search_text=self._build_search_text(category, content),
                    )
                )
        return chunks

    @staticmethod
    def _build_search_text(category: str, content: str) -> str:
        """构造适合 FTS 的搜索文本。

        SQLite 默认 tokenizer 对中文分词有限，因此这里主动补充
        中文 n-gram 与原文本，提升中文检索效果。
        """
        combined_text = f"{category} {content}".strip()
        tokens = SQLiteMemoryIndex._tokenize_query(combined_text)
        return " ".join(tokens + [combined_text.lower()])

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        """把查询拆成可供 FTS 使用的关键词。"""
        normalized_query = query.lower()
        ascii_terms = [
            term
            for term in (
                normalized_query.replace("：", " ")
                .replace("，", " ")
                .replace("。", " ")
                .replace("、", " ")
                .split()
            )
            if term
        ]

        chinese_terms: list[str] = []
        current_chars: list[str] = []
        for char in normalized_query:
            if "\u4e00" <= char <= "\u9fff":
                current_chars.append(char)
                continue
            if current_chars:
                chinese_terms.extend(
                    SQLiteMemoryIndex._generate_chinese_ngrams("".join(current_chars))
                )
                current_chars = []
        if current_chars:
            chinese_terms.extend(
                SQLiteMemoryIndex._generate_chinese_ngrams("".join(current_chars))
            )

        result = []
        seen = set()
        for term in ascii_terms + chinese_terms:
            if term not in seen:
                seen.add(term)
                result.append(term)
        return result

    @staticmethod
    def _generate_chinese_ngrams(text: str) -> list[str]:
        """生成 2-6 字的中文 n-gram。"""
        if len(text) <= 2:
            return [text]

        ngrams: list[str] = [text]
        for size in range(2, min(6, len(text)) + 1):
            for start_index in range(0, len(text) - size + 1):
                ngrams.append(text[start_index : start_index + size])
        return ngrams

    @staticmethod
    def _escape_fts_term(term: str) -> str:
        """转义 FTS 查询词。"""
        sanitized = term.replace('"', " ").strip()
        return f'"{sanitized}"'

"""SQLite 记忆索引仓储实现。"""

import sqlite3
from pathlib import Path
from typing import Optional

from memory.memory_index_repository import MemoryIndexRepository
from memory.memory_chunk import MemoryChunk
from memory.memory_scope import MemoryScope
from memory.memory_search_result import MemorySearchResult


def _load_chunks(long_term_file: Path, daily_memory_dir: Path) -> list[MemoryChunk]:
    """汇总长期记忆与每日记忆片段。"""
    chunks = []
    chunks.extend(_load_long_term_chunks(long_term_file))
    chunks.extend(_load_daily_chunks(daily_memory_dir))
    return chunks


def _load_long_term_chunks(long_term_file: Path) -> list[MemoryChunk]:
    """提取长期记忆片段。"""
    if not long_term_file.exists():
        return []
    chunks = []
    current_category = "general"
    lines = long_term_file.read_text(encoding="utf-8").splitlines()
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
                search_text=_build_search_text(current_category, content),
            )
        )
    return chunks


def _load_daily_chunks(daily_memory_dir: Path) -> list[MemoryChunk]:
    """提取每日记忆片段。"""
    if not daily_memory_dir.exists():
        return []
    chunks = []
    for daily_file in sorted(daily_memory_dir.glob("*.md")):
        chunks.extend(_load_daily_file_chunks(daily_file))
    return chunks


def _load_daily_file_chunks(daily_file: Path) -> list[MemoryChunk]:
    """提取单个每日记忆文件中的片段。"""
    chunks = []
    lines = daily_file.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        memory_chunk = _parse_daily_chunk(daily_file, line_number, line)
        if memory_chunk is not None:
            chunks.append(memory_chunk)
    return chunks


def _parse_daily_chunk(
    daily_file: Path,
    line_number: int,
    line: str,
) -> Optional[MemoryChunk]:
    """解析单行每日记忆片段。"""
    stripped_line = line.strip()
    if not stripped_line.startswith("- ["):
        return None
    closing_bracket_index = stripped_line.find("]")
    if closing_bracket_index == -1:
        return None
    remainder = stripped_line[closing_bracket_index + 1 :].strip()
    category = "general"
    content = remainder
    if remainder.startswith("(") and ")" in remainder:
        category_end_index = remainder.find(")")
        category = remainder[1:category_end_index].strip().lower()
        content = remainder[category_end_index + 1 :].strip()
    if not content:
        return None
    return MemoryChunk(
        path=str(daily_file),
        scope=MemoryScope.DAILY,
        category=category,
        content=content,
        start_line=line_number,
        end_line=line_number,
        search_text=_build_search_text(category, content),
    )


def _build_search_text(category: str, content: str) -> str:
    """构造 FTS 搜索文本。"""
    combined_text = f"{category} {content}".strip()
    tokens = _tokenize_query(combined_text)
    return " ".join(tokens + [combined_text.lower()])


def _tokenize_query(query: str) -> list[str]:
    """拆分检索词。"""
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
    chinese_terms = _extract_chinese_terms(normalized_query)
    return _merge_unique_terms(ascii_terms + chinese_terms)


def _extract_chinese_terms(normalized_query: str) -> list[str]:
    """提取中文检索词。"""
    chinese_terms = []
    current_chars = []
    for char in normalized_query:
        if "\u4e00" <= char <= "\u9fff":
            current_chars.append(char)
            continue
        if current_chars:
            chinese_terms.extend(_generate_chinese_ngrams("".join(current_chars)))
            current_chars = []
    if current_chars:
        chinese_terms.extend(_generate_chinese_ngrams("".join(current_chars)))
    return chinese_terms


def _merge_unique_terms(terms: list[str]) -> list[str]:
    """按出现顺序去重检索词。"""
    merged_terms = []
    seen_terms = set()
    for term in terms:
        if term in seen_terms:
            continue
        seen_terms.add(term)
        merged_terms.append(term)
    return merged_terms


def _generate_chinese_ngrams(text: str) -> list[str]:
    """生成中文 n-gram。"""
    if len(text) <= 2:
        return [text]
    ngrams = [text]
    for size in range(2, min(6, len(text)) + 1):
        for start_index in range(0, len(text) - size + 1):
            ngrams.append(text[start_index : start_index + size])
    return ngrams


def _escape_fts_term(term: str) -> str:
    """转义 FTS 检索词。"""
    sanitized_term = term.replace('"', " ").strip()
    return f'"{sanitized_term}"'


def _build_search_results(rows: list[tuple]) -> list[MemorySearchResult]:
    """把 SQL 行转换为搜索结果模型。"""
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


class SQLiteMemoryIndexRepository(MemoryIndexRepository):
    """SQLite FTS5 记忆索引实现。"""

    def __init__(self, database_path: Optional[Path] = None):
        self._database_path = database_path or Path(".opencode/cache/memory_search.sqlite")

    def rebuild_index(self, long_term_file: Path, daily_memory_dir: Path) -> None:
        """重建索引。"""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        chunks = _load_chunks(long_term_file, daily_memory_dir)
        with sqlite3.connect(self._database_path) as connection:
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
        """执行记忆搜索。"""
        search_terms = _tokenize_query(query)
        if not search_terms:
            return []
        if not self._database_path.exists():
            return []
        search_expression = " OR ".join(_escape_fts_term(term) for term in search_terms[:12])
        with sqlite3.connect(self._database_path) as connection:
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
        return _build_search_results(rows)

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

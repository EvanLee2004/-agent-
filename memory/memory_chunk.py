"""记忆索引片段模型。"""

from dataclasses import dataclass

from memory.memory_scope import MemoryScope


@dataclass(frozen=True)
class MemoryChunk:
    """待索引的记忆片段。

    Attributes:
        path: 原始记忆文件路径。
        scope: 记忆范围。
        category: 记忆分类。
        content: 片段正文。
        start_line: 起始行号。
        end_line: 结束行号。
        search_text: 用于全文检索的展开文本。
    """

    path: str
    scope: MemoryScope
    category: str
    content: str
    start_line: int
    end_line: int
    search_text: str

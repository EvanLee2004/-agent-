"""记忆服务。"""

from memory.memory_context_query import MemoryContextQuery
from memory.memory_decision import MemoryDecision
from memory.memory_error import MemoryError
from memory.memory_index_repository import MemoryIndexRepository
from memory.memory_scope import MemoryScope
from memory.memory_search_result import MemorySearchResult
from memory.memory_store_repository import MemoryStoreRepository
from memory.search_memory_query import SearchMemoryQuery
from memory.store_memory_command import StoreMemoryCommand


DEFAULT_MEMORY_LIMIT = 10
RECENT_DAILY_MEMORY_DAYS = 2


class MemoryService:
    """记忆服务。"""

    def __init__(
        self,
        memory_store_repository: MemoryStoreRepository,
        memory_index_repository: MemoryIndexRepository,
        agent_name: str = "智能会计",
    ):
        self._memory_store_repository = memory_store_repository
        self._memory_index_repository = memory_index_repository
        self._agent_name = agent_name

    def store_memory(self, command: StoreMemoryCommand) -> None:
        """写入记忆。"""
        decision = MemoryDecision(
            action="store",
            scope=command.scope,
            category=command.category.strip(),
            content=command.content.strip(),
            reason="tool_call",
        )
        if not decision.should_store():
            raise MemoryError("记忆写入参数不完整")
        self._memory_store_repository.store_memory_decision(self._agent_name, decision)
        self._rebuild_index()

    def search_memory(self, query: SearchMemoryQuery) -> list[MemorySearchResult]:
        """搜索记忆。"""
        return self._memory_index_repository.search(query=query.query, limit=query.limit)

    def build_memory_context(self, query: MemoryContextQuery) -> str:
        """构造 prompt 注入用记忆上下文。"""
        relevant_context = self._build_relevant_memory_context(query)
        if relevant_context:
            return relevant_context
        return self._build_fallback_memory_context(query)

    def _build_relevant_memory_context(self, query: MemoryContextQuery) -> str:
        """优先构造与当前问题强相关的记忆上下文。"""
        if not query.query:
            return ""
        relevant_records = self.search_memory(
            SearchMemoryQuery(query=query.query, limit=query.limit)
        )
        if not relevant_records:
            return ""
        lines = ["【相关记忆】"]
        lines.extend(
            [
                f"- [{'长期' if record.scope == MemoryScope.LONG_TERM else '每日'}/{record.category}] {record.content}"
                for record in relevant_records
            ]
        )
        return "\n\n" + "\n".join(lines)

    def _build_fallback_memory_context(self, query: MemoryContextQuery) -> str:
        """构造没有明显检索命中时的回退记忆上下文。"""
        long_term_records = self._memory_store_repository.read_long_term_records()[: query.limit]
        daily_records = self._memory_store_repository.read_recent_daily_records(
            RECENT_DAILY_MEMORY_DAYS
        )[: query.limit]
        sections = self._build_fallback_sections(long_term_records, daily_records)
        if sections:
            return "\n\n" + "\n".join(sections)
        return ""

    def _build_fallback_sections(self, long_term_records: list, daily_records: list) -> list[str]:
        """构造长期记忆与近期记忆的文本片段。"""
        sections = []
        if long_term_records:
            sections.append("【长期记忆】")
            sections.extend([f"- [{record.category}] {record.content}" for record in long_term_records])
        if daily_records:
            sections.append("【近期记忆】")
            sections.extend(
                [f"- [{record.recorded_at}] ({record.category}) {record.content}" for record in daily_records]
            )
        return sections

    def _rebuild_index(self) -> None:
        """重建记忆索引。

        索引重建收在服务层，是为了把“文件是真相、索引是派生物”的规则固定在一个地方，
        避免调用方忘记同步索引。
        """
        self._memory_index_repository.rebuild_index(
            self._memory_store_repository.get_long_term_memory_file(),
            self._memory_store_repository.get_daily_memory_dir(),
        )

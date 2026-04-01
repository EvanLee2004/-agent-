"""记忆应用服务。

在 function calling 改造之后，记忆层的职责已经完全收敛为确定性能力：
1. 显式写入长期或每日记忆
2. 搜索相关记忆片段，近似 OpenClaw 的 `memory_search`
3. 读取指定记忆文件，近似 OpenClaw 的 `memory_get`

主流程不再通过“memory skill 输出 JSON，再由服务解释”的旧链路更新记忆，
而是由模型直接调用 `store_memory` / `search_memory` 两个原生工具。
"""

from domain.memory import MemoryDecision, MemoryScope, MemorySearchResult
from infrastructure.memory import IAgentMemoryStore


class MemoryService:
    """记忆应用服务。"""

    def __init__(
        self,
        memory_store: IAgentMemoryStore,
        agent_name: str = "智能会计",
    ):
        self._memory_store = memory_store
        self._agent_name = agent_name

    def store_memory(
        self,
        scope: MemoryScope,
        category: str,
        content: str,
    ) -> None:
        """显式写入记忆。

        Args:
            scope: 写入范围，长期或每日。
            category: 记忆分类。
            content: 记忆正文。
        """
        decision = MemoryDecision(
            action="store",
            scope=scope,
            category=category.strip(),
            content=content.strip(),
            reason="tool_call",
        )
        if not decision.should_store:
            raise ValueError("记忆写入参数不完整")
        self._memory_store.store_memory_decision(self._agent_name, decision)

    def search_memory(
        self,
        query: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """搜索相关记忆片段。"""
        return self._memory_store.search_memories(query=query, limit=limit)

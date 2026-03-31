"""Agent 基类。

职责：
- 定义 Agent 接口（NAME, SYSTEM_PROMPT）
- 提供公共工具方法（LLM调用、记忆管理）

注意：
- 各 Agent 用自然语言与 LLM 交互，不强制 JSON 输出
- Skill 系统会替换 SYSTEM_PROMPT 来改变 Agent 行为
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from core.llm import LLMClient
from core.schemas import AuditResult


def read_memory(agent_name: str) -> dict:
    """读取指定 Agent 的记忆文件。"""
    path = Path("memory") / f"{agent_name}.json"
    if path.exists():
        import json

        return json.loads(path.read_text())
    return {"agent": agent_name, "experiences": []}


def write_memory(agent_name: str, memory: dict) -> None:
    """写入指定 Agent 的记忆文件。"""
    import json

    Path("memory").mkdir(exist_ok=True)
    path = Path("memory") / f"{agent_name}.json"
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2))


class BaseAgent(ABC):
    """Agent 基类。

    所有 Agent 必须继承此类并实现 process() 方法。

    Attributes:
        NAME: Agent 名称标识
        SYSTEM_PROMPT: 系统提示词，决定 Agent 的行为方式
    """

    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> str:
        """调用 LLM。

        Args:
            messages: 对话消息列表
            temperature: 温度参数

        Returns:
            LLM 返回的文本
        """
        try:
            return LLMClient.get_instance().chat(messages, temperature)
        except Exception as e:
            return f"LLM 调用失败: {e}"

    def update_memory(self, experience: str) -> None:
        """追加新经验到记忆。

        Args:
            experience: 经验描述
        """
        memory = read_memory(self.NAME)
        memory["experiences"].append(
            {
                "context": experience,
                "learned_at": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        memory["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        write_memory(self.NAME, memory)

    def ask_llm(self, task: str, context: str = "") -> str:
        """构造消息并调用 LLM。

        将 SYSTEM_PROMPT 和记忆拼接到消息中，发给 LLM。

        Args:
            task: 用户任务或指令
            context: 额外上下文

        Returns:
            LLM 返回的文本
        """
        memory = read_memory(self.NAME)
        memory_context = ""
        if memory["experiences"]:
            lines = [f"- {e['context']}" for e in memory["experiences"][-5:]]
            memory_context = "\n你的经验：\n" + "\n".join(lines)

        system = self.SYSTEM_PROMPT
        if context or memory_context:
            system += f"\n\n{context}{memory_context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        return self.call_llm(messages)

    def handle(self, task: str) -> str:
        """处理任务的对外接口。

        内部调用 process() 方法。

        Args:
            task: 用户任务

        Returns:
            处理结果字符串
        """
        return self.process(task)

    @abstractmethod
    def process(self, task: str) -> str:
        """处理任务入口方法。

        每个子类必须实现此方法。

        Args:
            task: 用户任务

        Returns:
            处理结果字符串
        """
        pass

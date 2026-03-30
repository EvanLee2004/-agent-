"""Agent 基类，提供公共能力"""

from abc import ABC, abstractmethod
from datetime import datetime

from core.llm import LLMClient
from core.memory import read_memory, write_memory
from core.rules import read_rules


class BaseAgent(ABC):
    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    def read_memory(self) -> dict:
        return read_memory(self.NAME)

    def write_memory(self, memory: dict) -> None:
        write_memory(self.NAME, memory)

    def update_memory(self, experience: str) -> None:
        """追加新经验到记忆"""
        memory = self.read_memory()
        memory["experiences"].append(
            {
                "context": experience,
                "learned_at": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        memory["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        self.write_memory(memory)

    def read_rules(self, filename: str = "accounting_rules.md") -> str:
        return read_rules(filename)

    def call_llm(self, messages: list[dict], temperature: float = 0.3) -> str:
        try:
            return LLMClient.get_instance().chat(messages, temperature)
        except Exception as e:
            return f"LLM 调用失败: {e}"

    def build_messages(self, task: str, extra_context: str = "") -> list[dict]:
        memory = self.read_memory()
        context = ""
        if memory["experiences"]:
            context = "\n".join(
                [f"- {e['context']}" for e in memory["experiences"][-5:]]
            )
            context = f"\n你的经验总结：\n{context}\n"

        system = self.SYSTEM_PROMPT
        if extra_context or context:
            system += f"\n{extra_context}{context}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

    @abstractmethod
    def process(self, task: str) -> str:
        pass

    def handle(self, task: str) -> str:
        return self.process(task)

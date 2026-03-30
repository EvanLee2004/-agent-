"""Agent 基类，提供公共能力"""

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime

from core.llm import LLMClient
from core.memory import read_memory, write_memory
from core.rules import read_rules
from core.schemas import ThoughtResult


class BaseAgent(ABC):
    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    def read_memory(self) -> dict:
        return read_memory(self.NAME)

    def write_memory(self, memory: dict) -> None:
        write_memory(self.NAME, memory)

    def update_memory(self, experience: str) -> None:
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

    def think(self, task: str, hint: str = "") -> ThoughtResult:
        """让 LLM 先思考任务，返回结构化分析结果

        Args:
            task: 用户输入的任务
            hint: 额外的提示信息

        Returns:
            ThoughtResult: 包含意图、实体、推理过程的结构化结果
        """
        system_hint = hint or (
            "你是一个任务分析专家。请分析用户输入，返回 JSON 格式结果。"
            "\n\n返回格式："
            "\n{"
            '\n  "intent": "accounting|review|transfer|unknown",'
            '\n  "entities": {"key": "value", ...},'
            '\n  "reasoning": "你的分析推理过程",'
            '\n  "confidence": 0.0-1.0'
            "}"
        )

        messages = [
            {"role": "system", "content": f"{self.SYSTEM_PROMPT}\n\n{system_hint}"},
            {"role": "user", "content": f"任务：{task}\n\n请分析并返回 JSON。"},
        ]

        response = self.call_llm(messages)
        return self._parse_thought(response)

    def _parse_thought(self, raw: str) -> ThoughtResult:
        """解析 LLM 返回的原始文本为 ThoughtResult"""
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != 0:
                data = json.loads(raw[start:end])
                return ThoughtResult(
                    intent=data.get("intent", "unknown"),
                    entities=data.get("entities", {}),
                    reasoning=data.get("reasoning", ""),
                    confidence=data.get("confidence", 1.0),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return ThoughtResult(
            intent="unknown",
            entities={},
            reasoning=raw,
            confidence=0.0,
        )

    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """根据思考结果执行动作（子类实现）"""
        raise NotImplementedError

    def reflect(self, result: str, feedback: str) -> str:
        """反思执行结果，如有反馈则尝试修正"""
        if not feedback:
            return result

        memory = self.read_memory()
        memory["experiences"].append(
            {
                "context": f"根据反馈修正: {feedback[:100]}",
                "learned_at": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        self.write_memory(memory)
        return result

    @abstractmethod
    def process(self, task: str) -> str:
        pass

    def handle(self, task: str) -> str:
        return self.process(task)

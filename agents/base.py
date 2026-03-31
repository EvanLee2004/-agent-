"""Agent 基类。

职责：
- 定义 Agent 接口（NAME, SYSTEM_PROMPT, process）
- 提供公共工具方法（LLM调用、记忆管理、规则读取）

注意：
- ReAct 循环逻辑已抽离到 core/workflow.py
- 各 Agent 只实现业务逻辑
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from core.llm import LLMClient
from core.memory import read_memory, write_memory
from core.rules import read_rules
from core.schemas import ThoughtResult


class BaseAgent(ABC):
    """Agent 基类。

    所有 Agent 必须继承此类并实现 process() 方法。

    Attributes:
        NAME: Agent 名称标识
        SYSTEM_PROMPT: 系统提示词
    """

    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    def read_memory(self) -> dict:
        """读取当前 Agent 的记忆。

        Returns:
            记忆字典，包含 experiences 列表
        """
        return read_memory(self.NAME)

    def write_memory(self, memory: dict) -> None:
        """写入记忆。

        Args:
            memory: 要写入的记忆字典
        """
        write_memory(self.NAME, memory)

    def update_memory(self, experience: str) -> None:
        """追加新经验到记忆。

        Args:
            experience: 经验描述
        """
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
        """读取规则文件。

        Args:
            filename: 规则文件名

        Returns:
            规则文件内容字符串
        """
        return read_rules(filename)

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

    def build_messages(
        self,
        task: str,
        extra_context: str = "",
    ) -> list[dict[str, str]]:
        """构造发给 LLM 的消息。

        自动注入记忆中的经验作为上下文。

        Args:
            task: 用户任务
            extra_context: 额外的上下文信息

        Returns:
            消息列表
        """
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
        """让 LLM 先思考任务，返回结构化分析结果。

        Args:
            task: 用户输入的任务
            hint: 额外的提示信息，用于指导 LLM 分析

        Returns:
            ThoughtResult 结构化结果，包含意图、实体、推理过程
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
            {
                "role": "system",
                "content": f"{self.SYSTEM_PROMPT}\n\n{system_hint}",
            },
            {"role": "user", "content": f"任务：{task}\n\n请分析并返回 JSON。"},
        ]

        response = self.call_llm(messages)
        return self._parse_thought(response)

    def _parse_thought(self, raw: str) -> ThoughtResult:
        """解析 LLM 返回的原始文本为 ThoughtResult。

        尝试从返回内容中提取 JSON 并解析。

        Args:
            raw: LLM 返回的原始文本

        Returns:
            解析后的 ThoughtResult，解析失败时返回默认值
        """
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

    def reflect(self, result: str, feedback: str) -> str:
        """反思执行结果，如有反馈则尝试修正。

        将反馈记录到记忆中，供后续参考。

        Args:
            result: 之前的执行结果
            feedback: 反馈信息

        Returns:
            修正后的结果
        """
        if not feedback:
            return result

        self.update_memory(f"反馈: {feedback[:100]}")
        return result

    @abstractmethod
    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """根据思考结果执行动作。

        这是 ReAct 模式的执行步骤。

        Args:
            plan: think() 返回的结构化思考结果
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        pass

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

    def handle(self, task: str) -> str:
        """处理任务的对外接口。

        内部调用 process() 方法。

        Args:
            task: 用户任务

        Returns:
            处理结果字符串
        """
        return self.process(task)

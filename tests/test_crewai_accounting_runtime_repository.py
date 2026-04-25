"""crewAI 会计运行时仓储测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from configuration.crewai_runtime_configuration import CrewAIRuntimeConfiguration
from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_role_request import DepartmentRoleRequest
from department.department_runtime_context import DepartmentRuntimeContext
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.crewai_accounting_runtime_repository import (
    CrewAIAccountingRuntimeRepository,
)


class FakeCrew:
    """测试用 crewAI Crew 替身。"""

    def __init__(self, raw: str):
        self.raw = raw
        self.inputs = None

    def kickoff(self, inputs: dict):
        """记录 kickoff 输入并返回 crewAI 风格输出对象。"""
        self.inputs = inputs
        return SimpleNamespace(
            raw=self.raw,
            token_usage=SimpleNamespace(
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
            ),
        )


def _build_configuration() -> LlmConfiguration:
    """构造运行时仓储测试配置。"""
    return LlmConfiguration(
        models=(
            LlmModelProfile(
                name="minimax",
                provider_name="minimax",
                model_name="MiniMax-M1",
                base_url="https://api.minimax.chat/v1",
                api_key_env="MINIMAX_API_KEY",
                api_key="test-key",
            ),
        ),
        default_model_name="minimax",
        runtime_configuration=CrewAIRuntimeConfiguration(),
    )


class CrewAIAccountingRuntimeRepositoryTest(unittest.TestCase):
    """验证仓储把 crewAI 输出投影成部门响应。"""

    def test_reply_extracts_text_usage_and_task_events(self):
        """一轮回复应包含固定会计任务事件、最终回复和 token 使用量。"""
        fake_crew = FakeCrew("凭证已记录，凭证号为 1。")
        repository = CrewAIAccountingRuntimeRepository(
            configuration=_build_configuration(),
            runtime_context=DepartmentRuntimeContext(),
            reply_text_sanitizer=ReplyTextSanitizer(),
        )

        with patch.object(repository, "_build_crew", return_value=fake_crew):
            response = repository.reply(
                DepartmentRoleRequest(
                    role_name="accounting-manager",
                    user_input="记录一笔收入",
                    thread_id="thread-1",
                )
            )

        self.assertEqual(
            fake_crew.inputs,
            {
                "user_input": "记录一笔收入",
                "conversation_context": "无可用历史上下文。",
            },
        )
        self.assertEqual(response.reply_text, "凭证已记录，凭证号为 1。")
        self.assertEqual(response.usage.total_tokens, 18)
        self.assertEqual(
            [event.event_type for event in response.execution_events],
            [
                ExecutionEventType.TASK_CALL,
                ExecutionEventType.TASK_CALL,
                ExecutionEventType.TASK_CALL,
                ExecutionEventType.TASK_CALL,
                ExecutionEventType.FINAL_REPLY,
            ],
        )
        self.assertEqual(
            [event.tool_name for event in response.execution_events[:4]],
            [
                "accounting_intake",
                "accounting_execution",
                "cashier_execution",
                "accounting_review",
            ],
        )


if __name__ == "__main__":
    unittest.main()

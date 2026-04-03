"""规则问答 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class ReplyWithRulesTool(BaseTool):
    """读取项目规则与记忆参考，辅助说明性回复。"""

    class InputSchema(BaseModel):
        """规则问答工具入参。"""

        question: str = Field(..., description="用户当前的问题原文")

    name: str = "reply_with_rules"
    description: str = "获取项目当前的会计、报销、审核和记忆相关规则参考。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行规则工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = FinanceDepartmentToolContextRegistry.get_context().reply_with_rules_router
        response = router.route({"question": payload.question})
        return response.to_tool_message_content()


reply_with_rules_tool = ReplyWithRulesTool()

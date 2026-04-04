"""生成财务子代理专业化 prompt 的 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import (
    FinanceDepartmentToolContextRegistry,
)


class GenerateFiscalTaskPromptTool(BaseTool):
    """为 DeerFlow task 生成结构化财务专业化 prompt。

    用途：coordinator 在复杂财务任务中需要使用 DeerFlow 原生 task(..., subagent_type="general-purpose")
    时，先调用本工具获取由 FiscalRolePromptBuilder 生成的、包含身份/工具边界/权责约束/
    输出格式的结构化 prompt，再将其作为 DeerFlow task 的 prompt 参数传入。

    使用流程：
        1. 调用本工具，指定 fiscal_mode 和 user_task
        2. 获得结构化 prompt 字符串
        3. 在下一轮调用 DeerFlow task(description=..., prompt=<上一步结果>, subagent_type="general-purpose")

    注意：本工具只生成 prompt 字符串，不执行 DeerFlow task 本身。
    """

    class InputSchema(BaseModel):
        """生成 prompt 工具入参。"""

        fiscal_mode: str = Field(
            ...,
            description="财务专业模式，取值：bookkeeping / tax / audit / cashier / policy_research",
        )
        user_task: str = Field(..., description="用户原始任务描述")
        context: str = Field(
            default="",
            description="可选的已知上下文（如之前的对话历史、已确认的事实）",
        )

    name: str = "generate_fiscal_task_prompt"
    description: str = (
        "为 DeerFlow task(..., subagent_type='general-purpose') 生成结构化财务专业化 prompt。\n"
        "当需要委托复杂财务任务（跨多个步骤、需专业角色分工）给 DeerFlow task 时使用。\n"
        "流程：先用本工具生成 prompt，再将其作为 DeerFlow task 的 prompt 参数传入。\n"
        "支持的 fiscal_mode：bookkeeping（记账）、tax（税务）、audit（审核）、"
        "cashier（出纳）、policy_research（政策研究）。"
    )
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行 prompt 生成。

        返回纯 prompt 字符串，可直接作为 DeerFlow task 的 prompt 参数。
        失败时返回错误原因文本。
        """
        payload = self.InputSchema.model_validate(kwargs)
        router = (
            FinanceDepartmentToolContextRegistry.get_context()
            .generate_fiscal_task_prompt_router
        )
        response = router.route(payload.model_dump())
        if response.success:
            # 返回纯字符串，可直接作为 task(prompt=...) 参数，无需额外解析
            return response.payload["prompt"]
        return f"生成 prompt 失败: {response.error_message}"


generate_fiscal_task_prompt_tool = GenerateFiscalTaskPromptTool()

"""generate_fiscal_task_prompt 工具路由。"""

from department.subagent.fiscal_role_mode import FiscalRoleMode
from department.subagent.fiscal_role_prompt_builder import FiscalRolePromptBuilder
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class GenerateFiscalTaskPromptRouter(ToolRouter):
    """generate_fiscal_task_prompt 工具入口。

    该工具供 coordinator 在复杂财务任务中调用 DeerFlow task 前，
    先通过 FiscalRolePromptBuilder 生成结构化 prompt，再将生成的
    prompt 作为 DeerFlow task 的 prompt 参数传入。

    本路由为自包含组件，直接持有 FiscalRolePromptBuilder 实例，
    不依赖 DepartmentCollaborationService 等 legacy 协作层。
    """

    def __init__(self) -> None:
        self._prompt_builder = FiscalRolePromptBuilder()

    def route(self, arguments: dict) -> ToolRouterResponse:
        """生成财务专业化 task prompt。"""
        try:
            fiscal_mode = FiscalRoleMode(arguments["fiscal_mode"])
        except ValueError:
            return ToolRouterResponse(
                tool_name="generate_fiscal_task_prompt",
                success=False,
                error_message=(
                    f"不支持的专业模式：{arguments['fiscal_mode']}，"
                    f"支持：{[m.value for m in FiscalRoleMode]}"
                ),
            )

        context = arguments.get("context")
        if context:
            prompt = self._prompt_builder.build_with_context(
                mode=fiscal_mode,
                user_task=arguments["user_task"],
                context=context,
            )
        else:
            prompt = self._prompt_builder.build(
                mode=fiscal_mode,
                user_task=arguments["user_task"],
            )
        return ToolRouterResponse(
            tool_name="generate_fiscal_task_prompt",
            success=True,
            payload={"prompt": prompt},
        )

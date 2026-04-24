"""会计科目查询工具入口。"""

from accounting.chart_of_accounts_service import ChartOfAccountsService
from conversation.tool_router import ToolRouter
from conversation.tool_router_response import ToolRouterResponse


class QueryChartOfAccountsRouter(ToolRouter):
    """查询当前可用会计科目。"""

    def __init__(self, chart_of_accounts_service: ChartOfAccountsService):
        self._chart_of_accounts_service = chart_of_accounts_service

    def route(self, arguments: dict) -> ToolRouterResponse:
        """执行会计科目查询。

        Args:
            arguments: 当前未使用，保留统一工具路由签名。

        Returns:
            包含全部会计科目的结构化响应。
        """
        subjects = self._chart_of_accounts_service.list_subjects()
        return ToolRouterResponse(
            tool_name="query_chart_of_accounts",
            success=True,
            payload={
                "count": len(subjects),
                "items": [
                    {
                        "code": subject.code,
                        "name": subject.name,
                        "category": subject.category,
                        "normal_balance": subject.normal_balance,
                        "description": subject.description,
                    }
                    for subject in subjects
                ],
            },
        )

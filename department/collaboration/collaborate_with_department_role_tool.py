"""部门角色协作 LangChain 工具。"""

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry


class CollaborateWithDepartmentRoleTool(BaseTool):
    """请求其他财务角色协作。"""

    class InputSchema(BaseModel):
        """角色协作工具入参。"""

        target_role_name: str = Field(..., description="目标角色名，例如 finance-bookkeeping 或 finance-tax")
        goal: str = Field(..., description="希望目标角色完成的具体目标")
        context_note: str = Field(default="", description="补充上下文，可选")

    name: str = "collaborate_with_department_role"
    description: str = "向智能财务部门中的其他角色发起协作请求，并获取该角色的专业结果。"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, **kwargs) -> str:
        """执行角色协作工具。"""
        payload = self.InputSchema.model_validate(kwargs)
        router = (
            FinanceDepartmentToolContextRegistry.get_context()
            .collaborate_with_department_role_router
        )
        response = router.route(payload.model_dump())
        return response.to_tool_message_content()


collaborate_with_department_role_tool = CollaborateWithDepartmentRoleTool()

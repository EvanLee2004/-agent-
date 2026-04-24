"""会计部门编排工厂。"""

from pathlib import Path
from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.accounting_department_role_catalog import AccountingDepartmentRoleCatalog
from department.accounting_department_service import AccountingDepartmentService
from department.department_runtime_context import DepartmentRuntimeContext
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.sqlite_department_workbench_repository import (
    SQLiteDepartmentWorkbenchRepository,
)
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.final_reply_summary_builder import FinalReplySummaryBuilder
from runtime.crewai.crewai_accounting_runtime_repository import (
    CrewAIAccountingRuntimeRepository,
)

from app.department_orchestration_bundle import DepartmentOrchestrationBundle

CREWAI_RUNTIME_ROOT = Path(".runtime/crewai")


class DepartmentOrchestrationFactory:
    """负责装配会计部门协作层。

    角色目录、共享工作台、crewAI 运行时都属于“会计部门编排”问题域。
    会话入口只拿到 AccountingDepartmentService，不感知 crewAI 的 Agent/Task/Crew。
    """

    def __init__(
        self,
        role_catalog: AccountingDepartmentRoleCatalog,
        configuration: LlmConfiguration,
        runtime_root: Optional[Path] = None,
    ):
        """构造工厂。

        Args:
            role_catalog: 会计部门角色目录。
            configuration: LLM 配置。
            runtime_root: crewAI 运行时根目录。当前只用于工作台数据库路径隔离。
        """
        self._role_catalog = role_catalog
        self._configuration = configuration
        self._runtime_root = (
            runtime_root if runtime_root is not None else CREWAI_RUNTIME_ROOT
        )

    def build(self) -> DepartmentOrchestrationBundle:
        """构造部门协作层对象集合。

        Returns:
            对外暴露的会计部门入口服务。
        """
        runtime_context = DepartmentRuntimeContext()
        collaboration_step_factory = CollaborationStepFactory(FinalReplySummaryBuilder())
        role_runtime_repository = CrewAIAccountingRuntimeRepository(
            configuration=self._configuration,
            runtime_context=runtime_context,
            reply_text_sanitizer=ReplyTextSanitizer(),
        )
        workbench_db_path = self._runtime_root / "workbench.db"
        workbench_service = DepartmentWorkbenchService(
            SQLiteDepartmentWorkbenchRepository(workbench_db_path)
        )
        accounting_department_service = AccountingDepartmentService(
            role_catalog=self._role_catalog,
            role_runtime_repository=role_runtime_repository,
            workbench_service=workbench_service,
            collaboration_step_factory=collaboration_step_factory,
        )
        return DepartmentOrchestrationBundle(
            accounting_department_service=accounting_department_service,
            workbench_service=workbench_service,
        )

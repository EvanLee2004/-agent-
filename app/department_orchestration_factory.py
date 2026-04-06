"""部门编排工厂。"""

from pathlib import Path
from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_runtime_context import DepartmentRuntimeContext
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.sqlite_department_workbench_repository import (
    SQLiteDepartmentWorkbenchRepository,
)
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.final_reply_summary_builder import FinalReplySummaryBuilder
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_department_role_runtime_repository import (
    DeerFlowDepartmentRoleRuntimeRepository,
)
from runtime.deerflow.deerflow_invocation_runner import DeerFlowInvocationRunner
from runtime.deerflow.deerflow_runtime_assets_service import DEERFLOW_RUNTIME_ROOT
from runtime.deerflow.deerflow_runtime_assets_service import (
    DeerFlowRuntimeAssetsService,
)

from app.department_orchestration_bundle import DepartmentOrchestrationBundle


class DepartmentOrchestrationFactory:
    """负责装配财务部门协作层。

    角色目录、共享工作台、DeerFlow 角色运行时都属于"部门编排"问题域。
    把这些对象集中在一个工厂中，是为了让会话入口不再理解部门内部的中间部件。

    并发安全说明：
    DeerFlowInvocationRunner 通过全局串行锁（threading.Lock）确保同进程内所有
    DeerFlow 调用严格串行执行，防止 checkpoint/memory 文件被并发写入，也防止
    os.environ 快照被并发破坏。每个 build() 调用产生的独立 runtime_root
    仍用于资产路径隔离（config/checkpoint/home 文件不会冲突）。
    """

    def __init__(
        self,
        role_catalog: FinanceDepartmentRoleCatalog,
        configuration: LlmConfiguration,
        runtime_root: Optional[Path] = None,
    ):
        """构造工厂。

        Args:
            role_catalog: 财务部门角色目录。
            configuration: LLM 配置。
            runtime_root: DeerFlow 运行时根目录。默认使用 DEERFLOW_RUNTIME_ROOT（.runtime/deerflow）。
                API 并发场景下应传入独立目录以实现实例级隔离。
        """
        self._role_catalog = role_catalog
        self._configuration = configuration
        self._runtime_root = (
            runtime_root if runtime_root is not None else DEERFLOW_RUNTIME_ROOT
        )

    def build(self) -> DepartmentOrchestrationBundle:
        """构造部门协作层对象集合。

        Returns:
            对外暴露的部门入口服务（通过 DeerFlow 原生 task 实现多 agent 协作）。
        """
        runtime_assets_service = DeerFlowRuntimeAssetsService(
            self._role_catalog,
            runtime_root=self._runtime_root,
        )
        invocation_runner = DeerFlowInvocationRunner(
            client_factory=DeerFlowClientFactory(),
        )
        runtime_context = DepartmentRuntimeContext()
        collaboration_step_factory = CollaborationStepFactory(FinalReplySummaryBuilder())
        role_runtime_repository = DeerFlowDepartmentRoleRuntimeRepository(
            configuration=self._configuration,
            runtime_assets_service=runtime_assets_service,
            runtime_context=runtime_context,
            reply_text_sanitizer=ReplyTextSanitizer(),
            invocation_runner=invocation_runner,
        )
        workbench_db_path = self._runtime_root / "workbench.db"
        workbench_service = DepartmentWorkbenchService(
            SQLiteDepartmentWorkbenchRepository(workbench_db_path)
        )
        finance_department_service = FinanceDepartmentService(
            role_catalog=self._role_catalog,
            role_runtime_repository=role_runtime_repository,
            workbench_service=workbench_service,
            collaboration_step_factory=collaboration_step_factory,
        )
        return DepartmentOrchestrationBundle(
            finance_department_service=finance_department_service,
            workbench_service=workbench_service,
        )

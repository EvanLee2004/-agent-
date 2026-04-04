"""部门编排工厂。"""

from pathlib import Path
from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.collaboration.department_collaboration_service import DepartmentCollaborationService
from department.department_runtime_context import DepartmentRuntimeContext
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.in_memory_department_workbench_repository import InMemoryDepartmentWorkbenchRepository
from department.workbench.role_trace_factory import RoleTraceFactory
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_department_role_runtime_repository import DeerFlowDepartmentRoleRuntimeRepository
from runtime.deerflow.deerflow_runtime_assets_service import DEERFLOW_RUNTIME_ROOT
from runtime.deerflow.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService

from app.department_orchestration_bundle import DepartmentOrchestrationBundle


class DepartmentOrchestrationFactory:
    """负责装配财务部门协作层。

    角色目录、共享工作台、DeerFlow 角色运行时和协作服务都属于"部门编排"问题域。
    把这些对象集中在一个工厂中，是为了让会话入口不再理解部门内部的中间部件。

    并发安全说明：
    每个 build() 调用会产生独立的运行时资产集合（通过独立的 runtime_root）。
    在 CLI 单线程场景下，所有请求共享同一个 factory 实例和 runtime_root，无问题。
    在 API 并发场景下，应该为每个请求/用户会话创建独立的 factory 实例或
    在 build() 时传入不同的 runtime_root，以确保 config/checkpoint/home 不会冲突。
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
        self._runtime_root = runtime_root if runtime_root is not None else DEERFLOW_RUNTIME_ROOT

    def build(self) -> DepartmentOrchestrationBundle:
        """构造部门协作层对象集合。

        Returns:
            对外暴露的部门入口服务和角色协作服务。
        """
        runtime_context = DepartmentRuntimeContext()
        role_trace_factory = RoleTraceFactory(RoleTraceSummaryBuilder())
        role_runtime_repository = DeerFlowDepartmentRoleRuntimeRepository(
            configuration=self._configuration,
            runtime_assets_service=DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(self._role_catalog),
                runtime_root=self._runtime_root,
            ),
            client_factory=DeerFlowClientFactory(),
            runtime_context=runtime_context,
            reply_text_sanitizer=ReplyTextSanitizer(),
        )
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
        )
        collaboration_service = DepartmentCollaborationService(
            role_catalog=self._role_catalog,
            runtime_repository=role_runtime_repository,
            workbench_service=workbench_service,
            runtime_context=runtime_context,
            role_trace_factory=role_trace_factory,
        )
        finance_department_service = FinanceDepartmentService(
            role_catalog=self._role_catalog,
            role_runtime_repository=role_runtime_repository,
            workbench_service=workbench_service,
            role_trace_factory=role_trace_factory,
        )
        return DepartmentOrchestrationBundle(
            finance_department_service=finance_department_service,
            collaboration_service=collaboration_service,
        )

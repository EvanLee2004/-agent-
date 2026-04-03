"""角色轨迹工厂。"""

from typing import Optional

from department.workbench.role_trace import RoleTrace
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder


class RoleTraceFactory:
    """统一构造可展示的角色轨迹。

    入口角色和协作角色都会把自然语言回复转成工作台轨迹。把这层抽成工厂，可以避免
    轨迹字段、摘要策略和默认值在多个服务里各写一遍，降低后续扩角色时的重复改动。
    """

    def __init__(self, summary_builder: RoleTraceSummaryBuilder):
        self._summary_builder = summary_builder

    def build(
        self,
        role_name: str,
        display_name: str,
        goal: str,
        reply_text: str,
        depth: int,
        requested_by: Optional[str] = None,
    ) -> RoleTrace:
        """根据角色回复生成标准轨迹对象。

        Args:
            role_name: 角色稳定标识。
            display_name: 角色展示名。
            goal: 本次处理目标。
            reply_text: 角色自然语言回复。
            depth: 当前协作深度。
            requested_by: 发起当前协作的上游角色展示名；入口角色为 None。

        Returns:
            已完成摘要压缩的角色轨迹对象。
        """
        return RoleTrace(
            role_name=role_name,
            display_name=display_name,
            requested_by=requested_by,
            goal=goal,
            thinking_summary=self._summary_builder.build(reply_text),
            depth=depth,
        )

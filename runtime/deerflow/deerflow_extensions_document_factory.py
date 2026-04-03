"""DeerFlow 扩展配置文档工厂。"""

from typing import Any


class DeerFlowExtensionsDocumentFactory:
    """负责构造 DeerFlow 扩展配置文档。

    扩展配置目前只包含空 MCP 集合和启用的 skills，但未来如果要增加更多上游扩展，
    单独工厂会比继续堆在运行时资产服务里更容易演进和测试。
    """

    def build(self, available_skills: set[str]) -> dict[str, Any]:
        """构造 DeerFlow 扩展配置文档。

        Args:
            available_skills: 当前运行时需要启用的 skill 名称集合。

        Returns:
            可直接序列化为 `extensions_config.json` 的配置字典。
        """
        return {
            "mcpServers": {},
            "skills": {
                skill_name: {"enabled": True}
                for skill_name in sorted(available_skills)
            },
        }

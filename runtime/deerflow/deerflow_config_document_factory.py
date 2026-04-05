"""DeerFlow 主配置文档工厂。"""

from pathlib import Path
from typing import Any

from configuration.llm_configuration import LlmConfiguration
from runtime.deerflow.deerflow_model_document_factory import (
    DeerFlowModelDocumentFactory,
)
from runtime.deerflow.deerflow_tool_catalog import DeerFlowToolCatalog


def _build_tool_group_documents(
    tool_catalog: DeerFlowToolCatalog,
) -> list[dict[str, str]]:
    """根据工具目录生成 tool group 文档。

    DeerFlow 会先按 `tool_groups` 过滤 agent 可见的配置工具，再解析实际工具对象。
    如果这里仍然只写单个 `finance` 组，即使后面把 `ls` / `read_file` / `web_search`
    等基础工具加入了 `tools`，自定义角色也依然看不到它们。这里统一从工具目录反推
    tool group，可避免“工具注册了但角色永远不可见”的隐蔽错配。
    """
    group_names: list[str] = []
    for spec in tool_catalog.list_specs():
        if spec.group not in group_names:
            group_names.append(spec.group)
    return [{"name": group_name} for group_name in group_names]


class DeerFlowConfigDocumentFactory:
    """负责构造 DeerFlow `config.yaml` 文档。

    运行时主配置涉及模型、工具组、技能目录和 checkpoint 路径。把这些拼装逻辑收敛到
    专用工厂，可以避免 `DeerFlowRuntimeAssetsService` 同时承担目录准备和配置细节维护。
    """

    def __init__(
        self,
        model_document_factory: DeerFlowModelDocumentFactory,
        tool_catalog: DeerFlowToolCatalog,
    ):
        self._model_document_factory = model_document_factory
        self._tool_catalog = tool_catalog

    def build(
        self,
        configuration: LlmConfiguration,
        checkpoint_path: Path,
        skills_root: Path,
    ) -> dict[str, Any]:
        """构造 DeerFlow 主配置文档。

        Args:
            configuration: 当前模型配置。
            checkpoint_path: DeerFlow SQLite checkpoint 文件路径。
            skills_root: DeerFlow skills 根目录。

        Returns:
            可直接序列化为 `config.yaml` 的配置字典。
        """
        runtime_configuration = configuration.runtime_configuration
        return {
            "config_version": 5,
            "log_level": "info",
            "token_usage": {"enabled": False},
            "models": self._model_document_factory.build_documents(configuration),
            "tool_groups": _build_tool_group_documents(self._tool_catalog),
            "tools": self._build_tool_documents(),
            "tool_search": {"enabled": runtime_configuration.tool_search_enabled},
            "sandbox": {
                "use": runtime_configuration.sandbox_use_path,
                "allow_host_bash": runtime_configuration.sandbox_allow_host_bash,
                "bash_output_max_chars": runtime_configuration.sandbox_bash_output_max_chars,
                "read_file_output_max_chars": runtime_configuration.sandbox_read_file_output_max_chars,
            },
            "skills": {
                "path": str(skills_root.resolve()),
                "container_path": "/mnt/skills",
            },
            "title": {
                "enabled": False,
                "max_words": 6,
                "max_chars": 60,
                "model_name": None,
            },
            "summarization": {"enabled": False},
            "memory": {
                "enabled": True,
                "debounce_seconds": 30,
                "max_facts": 100,
                "fact_confidence_threshold": 0.7,
                "injection_enabled": True,
                "max_injection_tokens": 2000,
            },
            "checkpointer": {
                "type": "sqlite",
                "connection_string": str(checkpoint_path.resolve()),
            },
        }

    def _build_tool_documents(self) -> list[dict[str, str]]:
        """构造全部工具配置文档。"""
        return [
            {
                "name": spec.name,
                "group": spec.group,
                "use": spec.use_path,
            }
            for spec in self._tool_catalog.list_specs()
        ]

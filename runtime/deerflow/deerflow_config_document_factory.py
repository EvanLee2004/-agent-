"""DeerFlow 主配置文档工厂。"""

from pathlib import Path
from typing import Any

from configuration.llm_configuration import LlmConfiguration
from runtime.deerflow.deerflow_model_document_factory import DeerFlowModelDocumentFactory
from runtime.deerflow.deerflow_tool_catalog import DeerFlowToolCatalog
from runtime.deerflow.deerflow_tool_spec import DEERFLOW_TOOL_GROUP_NAME


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
        return {
            "config_version": 5,
            "log_level": "info",
            "token_usage": {"enabled": False},
            "models": [self._model_document_factory.build(configuration)],
            "tool_groups": [{"name": DEERFLOW_TOOL_GROUP_NAME}],
            "tools": self._build_tool_documents(),
            "tool_search": {"enabled": False},
            "sandbox": {
                "use": "deerflow.sandbox.local:LocalSandboxProvider",
                "allow_host_bash": False,
                "bash_output_max_chars": 20000,
                "read_file_output_max_chars": 50000,
            },
            "skills": {
                "path": str(skills_root.resolve()),
                "container_path": "/mnt/skills",
            },
            "title": {"enabled": False, "max_words": 6, "max_chars": 60, "model_name": None},
            "summarization": {"enabled": False},
            "memory": {
                # 启用 DeerFlow 原生记忆机制。
                # DeerFlow 会在每轮对话结束后用 LLM 自动提取对话事实，写入
                # `.runtime/deerflow/home/agents/{agent_name}/memory.json`，
                # 并在下一轮对话开始时自动注入 system prompt。
                # 不再需要 store_memory / search_memory 工具，也不再需要
                # 项目自维护的 Markdown + SQLite 记忆模块。
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
                "group": DEERFLOW_TOOL_GROUP_NAME,
                "use": spec.use_path,
            }
            for spec in self._tool_catalog.list_specs()
        ]

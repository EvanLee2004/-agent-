"""DeerFlow 运行时资产服务。"""

import json
from pathlib import Path
from typing import Any

import yaml

from configuration.llm_configuration import LlmConfiguration
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets


DEERFLOW_RUNTIME_ROOT = Path(".runtime/deerflow")
DEERFLOW_CONFIG_FILE_NAME = "config.yaml"
DEERFLOW_EXTENSIONS_FILE_NAME = "extensions_config.json"
DEERFLOW_CHECKPOINT_FILE_NAME = "checkpoints.sqlite"
DEERFLOW_HOME_DIRECTORY_NAME = "home"
DEERFLOW_SKILLS_ROOT = Path(".agent_assets/deerflow_skills")
DEERFLOW_TOOL_GROUP_NAME = "finance"


class DeerFlowRuntimeAssetsService:
    """负责准备 DeerFlow 运行时所需的本地资产。

    我们把 DeerFlow 当作外部底层引擎使用，因此配置文件、扩展文件和
    skills 路径都不应该散落在 CLI、依赖容器或业务代码里。把它们集中到
    一个服务，是为了保证运行时接入只有一个事实来源，后续切多 Agent 时
    也不需要在多个位置同步改配置结构。
    """

    def __init__(
        self,
        department_agent_assets_service: FinanceDepartmentAgentAssetsService,
        runtime_root: Path = DEERFLOW_RUNTIME_ROOT,
        skills_root: Path = DEERFLOW_SKILLS_ROOT,
    ):
        self._department_agent_assets_service = department_agent_assets_service
        self._runtime_root = runtime_root
        self._skills_root = skills_root
        self._available_skills = self._department_agent_assets_service.list_available_skill_names()

    def prepare_assets(self, configuration: LlmConfiguration) -> DeerFlowRuntimeAssets:
        """准备 DeerFlow 运行时资产。

        Args:
            configuration: 当前项目的 LLM 运行配置。

        Returns:
            DeerFlow 运行时需要的配置资产集合。
        """
        self._runtime_root.mkdir(parents=True, exist_ok=True)
        runtime_home = self._runtime_root / DEERFLOW_HOME_DIRECTORY_NAME
        runtime_home.mkdir(parents=True, exist_ok=True)
        self._department_agent_assets_service.prepare_agent_assets(runtime_home)
        config_path = self._runtime_root / DEERFLOW_CONFIG_FILE_NAME
        extensions_config_path = self._runtime_root / DEERFLOW_EXTENSIONS_FILE_NAME
        config_path.write_text(
            yaml.safe_dump(
                self._build_config_document(configuration),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        extensions_config_path.write_text(
            json.dumps(self._build_extensions_document(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return DeerFlowRuntimeAssets(
            config_path=config_path,
            extensions_config_path=extensions_config_path,
            runtime_home=runtime_home.resolve(),
            skills_path=self._skills_root.resolve(),
            available_skills=set(self._available_skills),
            api_key=configuration.api_key,
        )

    def _build_config_document(self, configuration: LlmConfiguration) -> dict[str, Any]:
        """构造 DeerFlow 主配置文档。

        这里故意把配置压到最小集合，只保留我们当前阶段真正需要的能力：
        OpenAI-compatible 模型、财务 tools、skills、SQLite checkpointer。
        这样做是为了避免把 DeerFlow 的通用 research/web/sandbox 生态一次性
        全量打开，导致项目在迈向最终目标前先被非财务能力拖复杂。
        """
        checkpoint_path = (self._runtime_root / DEERFLOW_CHECKPOINT_FILE_NAME).resolve()
        return {
            "config_version": 5,
            "log_level": "info",
            "token_usage": {"enabled": False},
            "models": [self._build_model_document(configuration)],
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
                "path": str(self._skills_root.resolve()),
                "container_path": "/mnt/skills",
            },
            "title": {"enabled": False, "max_words": 6, "max_chars": 60, "model_name": None},
            "summarization": {"enabled": False},
            "memory": {"enabled": False},
            "checkpointer": {
                "type": "sqlite",
                "connection_string": str(checkpoint_path),
            },
        }

    def _build_model_document(self, configuration: LlmConfiguration) -> dict[str, Any]:
        """构造单模型配置。

        当前项目主要使用 OpenAI-compatible 提供商，因此优先复用
        DeerFlow 官方示例里的 `langchain_openai:ChatOpenAI`，这样可以把
        provider 适配逻辑交给上游库，而不是继续维持我们自己的聊天协议层。
        """
        return {
            "name": configuration.model_name,
            "display_name": configuration.model_name,
            "use": "langchain_openai:ChatOpenAI",
            "model": configuration.model_name,
            "api_key": "$LLM_API_KEY",
            "base_url": configuration.base_url,
            "request_timeout": 600.0,
            "max_retries": 2,
            "max_tokens": 4096,
            "temperature": self._resolve_temperature(configuration),
            "supports_thinking": True,
            "supports_vision": False,
        }

    def _build_tool_documents(self) -> list[dict[str, str]]:
        """构造财务工具配置列表。"""
        return [
            self._build_tool_document(
                "collaborate_with_department_role",
                "department.collaboration.collaborate_with_department_role_tool:collaborate_with_department_role_tool",
            ),
            self._build_tool_document("record_voucher", "accounting.record_voucher_tool:record_voucher_tool"),
            self._build_tool_document("query_vouchers", "accounting.query_vouchers_tool:query_vouchers_tool"),
            self._build_tool_document(
                "record_cash_transaction",
                "cashier.record_cash_transaction_tool:record_cash_transaction_tool",
            ),
            self._build_tool_document(
                "query_cash_transactions",
                "cashier.query_cash_transactions_tool:query_cash_transactions_tool",
            ),
            self._build_tool_document("calculate_tax", "tax.calculate_tax_tool:calculate_tax_tool"),
            self._build_tool_document("audit_voucher", "audit.audit_voucher_tool:audit_voucher_tool"),
            self._build_tool_document("store_memory", "memory.store_memory_tool:store_memory_tool"),
            self._build_tool_document("search_memory", "memory.search_memory_tool:search_memory_tool"),
            self._build_tool_document("reply_with_rules", "rules.reply_with_rules_tool:reply_with_rules_tool"),
        ]

    def _build_tool_document(self, tool_name: str, use_path: str) -> dict[str, str]:
        """构造单个工具配置。"""
        return {
            "name": tool_name,
            "group": DEERFLOW_TOOL_GROUP_NAME,
            "use": use_path,
        }

    def _build_extensions_document(self) -> dict[str, Any]:
        """构造 DeerFlow 扩展配置文档。

        这里显式写出空 MCP 配置，是为了让 DeerFlow 在我们的项目目录中运行时
        拥有确定的扩展状态，而不是去继承用户其他 DeerFlow 项目的残留配置。
        """
        return {
            "mcpServers": {},
            "skills": {
                skill_name: {"enabled": True}
                for skill_name in sorted(self._available_skills)
            },
        }

    def _resolve_temperature(self, configuration: LlmConfiguration) -> float:
        """按 provider 决定默认温度。"""
        if configuration.provider_name == "minimax":
            # MiniMax 当前接口要求温度在 (0.0, 1.0] 内，不能给 0。
            return 1.0
        return 0.7

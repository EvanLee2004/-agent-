"""Skill Prompt 组装服务。

当前主流程已经切到原生 function calling，因此本服务的职责也收口为：
- 加载 `.opencode/skills/` 里的领域指令
- 注入相关记忆
- 注入会计科目目录
- 构造原生工具调用所需的总 system prompt

类名仍保留为 `SkillPromptService`，但它在语义上更接近 Skill Context Service。
"""

from datetime import datetime
from typing import Optional

from infrastructure.memory import IAgentMemoryStore
from infrastructure.skill_loader import SkillLoader
from services.chart_of_accounts_service import ChartOfAccountsService


BASE_TOOL_SYSTEM_PROMPT = """你是专业的智能会计助手，当前运行在原生 function calling 模式下。

【总原则】
- 你必须通过工具完成实际动作，不能伪造工具调用结果
- 不要手写 JSON 协议，不要输出代码块，不要把工具参数当最终回答直接展示给用户
- 第一轮必须调用至少一个工具；拿到工具结果后，再生成最终中文答复
- 如果工具返回失败，请基于失败原因向用户解释，不要编造成果

【工具使用规则】
- 用户要记账、做分录、做凭证时，调用 `record_voucher`
- 用户要查看账目、查询凭证、看最近记录时，调用 `query_vouchers`
- 用户要算税时，调用 `calculate_tax`
- 用户要审核凭证、查看异常时，调用 `audit_voucher`
- 用户明确要求记住某件事时，调用 `store_memory`
- 用户问“你还记得吗”“我之前说过什么”时，优先调用 `search_memory`
- 用户询问会计规则、报销规范、项目内部判断标准或普通说明性问题时，调用 `reply_with_rules`

【税务特别规则】
- `calculate_tax.includes_tax` 只能在用户明确出现“含税”“价税合计”“税已包含”等意思时设为 `true`
- 如果用户没有明确说明是否含税，默认必须设为 `false`
- 不要因为行业习惯或主观猜测把未说明金额自动当成含税价

【最终答复要求】
- 最终答复必须使用中文
- 风格简洁、专业、直接
- 可以引用工具结果，但不要把工具原始 JSON 整段贴给用户
"""


class SkillPromptService:
    """Skill Prompt 组装服务。"""

    def __init__(
        self,
        skill_loader: SkillLoader,
        memory_store: IAgentMemoryStore,
        chart_of_accounts_service: ChartOfAccountsService,
        agent_name: str = "智能会计",
    ):
        self._skill_loader = skill_loader
        self._memory_store = memory_store
        self._chart_of_accounts_service = chart_of_accounts_service
        self._agent_name = agent_name

    def build_agent_tool_prompt(
        self,
        user_input: Optional[str] = None,
    ) -> str:
        """构造原生工具调用主提示词。

        这里不再要求模型输出 JSON，而是把各类 skill 作为领域上下文统一注入，
        让模型在一个总 prompt 里学会：
        - 什么时候该调用哪个工具
        - 记账/税务/审核/记忆分别遵循什么专业规则
        - 最终回复该如何组织
        """
        memory_context = self._memory_store.get_memory_context(
            self._agent_name,
            query=user_input,
        )
        subject_catalog = self._chart_of_accounts_service.build_subject_catalog_prompt()
        today = datetime.now().strftime("%Y-%m-%d")
        prompt_parts = [
            BASE_TOOL_SYSTEM_PROMPT,
            "",
            f"今天日期：{today}",
        ]

        aggregated_skills = self._build_aggregated_skill_context(
            skill_names=["accounting", "tax", "audit", "memory", "rules"]
        )
        if aggregated_skills:
            prompt_parts.extend(["", "【领域 Skills】", aggregated_skills])

        if subject_catalog:
            prompt_parts.extend(["", subject_catalog])

        if memory_context:
            prompt_parts.extend(["", memory_context.strip()])

        return "\n".join(prompt_parts)

    def build_rules_tool_payload(self, user_input: str) -> dict:
        """构造 `reply_with_rules` 工具返回的参考内容。"""
        rules_prompt = self._safe_load_skill_prompt("rules") or "暂无规则说明"
        normalized_rules = "\n".join(
            line
            for line in rules_prompt.splitlines()
            if "reply_with_rules" not in line
        ).strip()
        memory_context = self._memory_store.get_memory_context(
            self._agent_name,
            query=user_input,
        )
        payload = {
            "question": user_input,
            "rules_reference": normalized_rules,
        }
        if memory_context:
            payload["memory_context"] = memory_context.strip()
        return payload

    def _safe_load_skill_prompt(self, skill_name: str) -> Optional[str]:
        """安全加载 Skill 提示词。"""
        try:
            return self._skill_loader.load_system_prompt(skill_name)
        except (FileNotFoundError, ValueError):
            return None

    def _build_aggregated_skill_context(self, skill_names: list[str]) -> str:
        """把多个 skill 合并为总领域上下文。"""
        sections = []
        for skill_name in skill_names:
            prompt = self._safe_load_skill_prompt(skill_name)
            if not prompt:
                continue
            sections.append(f"[{skill_name}]\n{prompt.strip()}")
        return "\n\n".join(sections)

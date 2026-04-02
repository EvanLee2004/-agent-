"""Prompt 上下文服务。"""

from datetime import datetime

from accounting.chart_of_accounts_service import ChartOfAccountsService
from conversation.prompt_skill_repository import PromptSkillRepository
from conversation.tool_use_policy import ToolUsePolicy
from memory.memory_context_query import MemoryContextQuery
from memory.memory_service import MemoryService


BASE_TOOL_SYSTEM_PROMPT = """你是专业的智能会计助手，当前运行在原生 function calling 模式下。

【总原则】
- 涉及真实动作、持久化数据或需要核对系统事实时，应优先使用工具
- 不能伪造工具调用结果
- 不要手写 JSON 协议，不要输出代码块，不要把工具参数当最终回答直接展示给用户
- 日常寒暄、自我介绍、一般性说明在不需要系统事实时，可以直接自然回答
- 拿到工具结果后，再生成最终中文答复
- 如果工具返回失败，请基于失败原因向用户解释，不要编造成果

【工具使用规则】
- 用户要记账、做分录、做凭证时，应调用 `record_voucher`
- 用户要查看账目、查询凭证、看最近记录时，应调用 `query_vouchers`
- 用户要算税时，应调用 `calculate_tax`
- 用户要审核凭证、查看异常时，应调用 `audit_voucher`
- 用户明确要求记住某件事时，应调用 `store_memory`
- 用户问“你还记得吗”“我之前说过什么”时，优先调用 `search_memory`
- 用户询问会计规则、报销规范、项目内部判断标准时，优先调用 `reply_with_rules`
- 如果只是普通闲聊，不必为了调用工具而调用工具

【税务特别规则】
- `calculate_tax.includes_tax` 只能在用户明确出现“含税”“价税合计”“税已包含”等意思时设为 `true`
- 如果用户没有明确说明是否含税，默认必须设为 `false`
- 不要因为行业习惯或主观猜测把未说明金额自动当成含税价

【最终答复要求】
- 最终答复必须使用中文
- 风格简洁、专业、直接
- 可以引用工具结果，但不要把工具原始 JSON 整段贴给用户
"""

SKILL_NAMES = ["accounting", "tax", "audit", "memory", "rules"]


class PromptContextService:
    """Prompt 上下文服务。"""

    def __init__(
        self,
        prompt_skill_repository: PromptSkillRepository,
        memory_service: MemoryService,
        chart_of_accounts_service: ChartOfAccountsService,
        tool_use_policy: ToolUsePolicy,
        agent_name: str = "智能会计",
    ):
        self._prompt_skill_repository = prompt_skill_repository
        self._memory_service = memory_service
        self._chart_of_accounts_service = chart_of_accounts_service
        self._tool_use_policy = tool_use_policy
        self._agent_name = agent_name

    def build_system_prompt(self, user_input: str) -> str:
        """构造会话系统提示词。"""
        prompt_parts = self._build_base_prompt_parts()
        self._append_skill_context(prompt_parts)
        self._append_subject_catalog(prompt_parts)
        if self._tool_use_policy.is_memory_recall_request(user_input):
            self._append_memory_recall_constraint(prompt_parts)
            return "\n".join(prompt_parts)
        self._append_memory_context(prompt_parts, user_input)
        return "\n".join(prompt_parts)

    def _build_base_prompt_parts(self) -> list[str]:
        """构造所有会话都共享的提示前缀。"""
        return [
            BASE_TOOL_SYSTEM_PROMPT,
            "",
            f"今天日期：{datetime.now().strftime('%Y-%m-%d')}",
        ]

    def _append_skill_context(self, prompt_parts: list[str]) -> None:
        """追加聚合后的领域 skill 内容。"""
        aggregated_skill_context = self._build_aggregated_skill_context()
        if aggregated_skill_context:
            prompt_parts.extend(["", "【领域 Skills】", aggregated_skill_context])

    def _append_subject_catalog(self, prompt_parts: list[str]) -> None:
        """追加科目目录提示。"""
        subject_catalog = self._chart_of_accounts_service.build_subject_catalog_prompt()
        if subject_catalog:
            prompt_parts.extend(["", subject_catalog])

    def _append_memory_recall_constraint(self, prompt_parts: list[str]) -> None:
        """追加记忆召回约束。

        记忆召回场景不预注入具体记忆内容，是为了减少模型把上下文误当事实源，
        从而提升其主动查询记忆工具的概率。
        """
        prompt_parts.extend(
            [
                "",
                "【记忆召回约束】",
                "当前用户问题属于记忆召回场景。请优先调用 `search_memory` 再回答，不要仅凭印象判断是否记住了什么。",
            ]
        )

    def _append_memory_context(self, prompt_parts: list[str], user_input: str) -> None:
        """追加与当前问题相关的记忆上下文。"""
        memory_context = self._memory_service.build_memory_context(
            MemoryContextQuery(agent_name=self._agent_name, query=user_input)
        )
        if memory_context:
            prompt_parts.extend(["", memory_context.strip()])

    def _build_aggregated_skill_context(self) -> str:
        """聚合领域 skill。"""
        sections = []
        for skill_name in SKILL_NAMES:
            prompt_text = self._prompt_skill_repository.load_system_prompt(skill_name)
            if not prompt_text:
                continue
            sections.append(f"[{skill_name}]\n{prompt_text.strip()}")
        return "\n\n".join(sections)

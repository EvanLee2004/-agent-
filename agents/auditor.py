"""审核 Agent，负责审查记账结果"""

from agents.base import BaseAgent


class Auditor(BaseAgent):
    NAME = "auditor"
    SYSTEM_PROMPT = "你是财务审核，负责审查会计的记账结果是否符合规则。发现问题只在context中标注，让会计主动修改，不要直接打回。"

    def process(self, task: str) -> str:
        rules = self.read_rules()
        messages = self.build_messages(
            f"审查以下记账结果是否符合规则：\n{task}\n\n规则：\n{rules}",
            extra_context="""审查要求：
1. 逐条检查是否符合规则
2. 如发现问题，在结果末尾添加【标注】说明问题
3. 如无问题，返回【审核通过】
4. 不要直接说"打回"，而是标注问题让对方主动修改""",
        )
        return self.call_llm(messages)

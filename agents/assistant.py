"""AI 角色基类"""

from core.llm import chat


class Assistant:
    """财务角色基类，所有具体助手都继承此类"""

    SYSTEM_PROMPT: str = "你是智能财务助手"

    def handle(self, task: str) -> str:
        """处理用户任务"""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        return chat(messages)

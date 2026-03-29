"""AI 角色基类"""

from core.llm import chat


class Assistant:
    """财务助手基类，所有具体助手都继承此类"""

    SYSTEM_PROMPT: str = "你是智能财务助手"

    def handle(self, task: str) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        return chat(messages)

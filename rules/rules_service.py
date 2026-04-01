"""规则服务。"""

from rules.rules_reference import RulesReference
from rules.rules_repository import RulesRepository


class RulesService:
    """规则服务。"""

    def __init__(self, rules_repository: RulesRepository):
        self._rules_repository = rules_repository

    def build_rules_reference(self, question: str) -> RulesReference:
        """构造规则参考。

        Args:
            question: 用户问题。

        Returns:
            规则参考对象。
        """
        rules_text = self._rules_repository.load_rules_text()
        normalized_rules = "\n".join(
            line for line in rules_text.splitlines() if "reply_with_rules" not in line
        ).strip()
        return RulesReference(question=question, rules_text=normalized_rules)

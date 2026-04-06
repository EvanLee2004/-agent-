"""最终回复摘要构造器。

把 DeerFlow 最终回复文本压缩为可展示的协作摘要。
"""

from typing import Optional


MAX_SUMMARY_CHARS = 180
MIN_SENTENCE_SUMMARY_CHARS = 24
SENTENCE_ENDINGS = ("。", "！", "？", "!", "?", "\n")


class FinalReplySummaryBuilder:
    """把 DeerFlow 最终回复文本压缩为可展示的协作摘要。

    DeerFlow 对外回复面向最终用户，长度和语气都可能更完整；而协作摘要需要的是
    "本轮系统得出什么结论"的简短文本。独立构造器可避免在 CollaborationStepFactory
    和展示层各自重复裁剪逻辑。
    """

    def build(self, reply_text: str) -> str:
        """根据 DeerFlow 回复生成摘要文本。

        Args:
            reply_text: DeerFlow 原始最终回复文本。

        Returns:
            适合作为协作摘要的单段文本。
        """
        normalized_text = self._normalize_whitespace(reply_text)
        first_sentence = self._extract_first_sentence(normalized_text)
        if self._is_preferred_summary(first_sentence):
            return self._truncate(first_sentence)
        return self._truncate(normalized_text)

    def _normalize_whitespace(self, reply_text: str) -> str:
        """归一化空白字符。

        回复里常包含 Markdown 换行、列表或空行。摘要不需要保留这些排版；
        统一压成单段文本后，能避免工作台里混入终端展示细节，保持摘要语义稳定。
        """
        return " ".join(reply_text.split()).strip()

    def _extract_first_sentence(self, normalized_text: str) -> str:
        """提取首句作为优先摘要候选。"""
        for sentence_ending in SENTENCE_ENDINGS:
            ending_index = normalized_text.find(sentence_ending)
            if ending_index == -1:
                continue
            return normalized_text[: ending_index + 1].strip()
        return normalized_text

    def _is_preferred_summary(self, first_sentence: str) -> bool:
        """判断首句是否足以表达本轮结论。"""
        return len(first_sentence) >= MIN_SENTENCE_SUMMARY_CHARS

    def _truncate(self, text: str) -> str:
        """控制摘要上限，避免工作台保存过长文本。"""
        if len(text) <= MAX_SUMMARY_CHARS:
            return text
        return text[: MAX_SUMMARY_CHARS - 1] + "…"

"""本地确定性 embedding 函数。"""

import hashlib
from typing import Any

import numpy as np


EMBEDDING_DIMENSION = 128


class LocalHashEmbeddingFunction:
    """为 crewAI Memory 提供本地 embedding。

    生产级本地私有部署不能在用户未显式配置时偷偷调用默认 OpenAI embedding。
    当前函数使用稳定哈希生成轻量向量，只服务“会话上下文/偏好”这类低风险记忆；
    财务事实仍必须通过 SQLite 账簿工具确认，因此这里不追求语义检索的最高精度。
    """

    def __call__(self, input: Any) -> list[np.ndarray]:
        """把文本列表转换为向量列表。"""
        texts = input if isinstance(input, list) else [input]
        return [self._embed_text(str(text)) for text in texts]

    def embed_query(self, input: Any) -> list[np.ndarray]:
        """查询向量入口，兼容 crewAI embedding protocol。"""
        return self.__call__(input)

    def _embed_text(self, text: str) -> np.ndarray:
        """生成确定性哈希向量。"""
        vector = np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMENSION
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign
        norm = np.linalg.norm(vector)
        if norm == 0:
            vector[0] = 1.0
            return vector
        return vector / norm

"""模型配置模块。

集中管理模型配置，支持切换不同模型。
每个模型条目包含 context_window、max_tokens 等元数据。

换模型只需在此文件添加/修改配置，LLMClient 自动读取。
"""

from typing import Optional, TypedDict


class ModelConfig(TypedDict):
    """模型配置结构"""

    context_window: int
    max_tokens: int
    supports_usage: bool


MODELS: dict[str, ModelConfig] = {
    "MiniMax-M2.7": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "MiniMax-M2.7-highspeed": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "MiniMax-M2.5": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "MiniMax-M2.5-highspeed": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "MiniMax-M2.1": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "MiniMax-M2": {
        "context_window": 204800,
        "max_tokens": 8192,
        "supports_usage": True,
    },
    "gpt-4": {
        "context_window": 8192,
        "max_tokens": 2048,
        "supports_usage": True,
    },
    "gpt-4-32k": {
        "context_window": 32768,
        "max_tokens": 4096,
        "supports_usage": True,
    },
    "gpt-3.5-turbo": {
        "context_window": 16385,
        "max_tokens": 4096,
        "supports_usage": True,
    },
}


def get_default_model() -> str:
    """Get the default model name from environment variable.

    Returns:
        Model name string from LLM_MODEL env var, defaults to "MiniMax-M2.7".
    """
    import os

    return os.getenv("LLM_MODEL", "MiniMax-M2.7") or "MiniMax-M2.7"


def get_model_config(model: Optional[str] = None) -> ModelConfig:
    """Get model configuration by name.

    Args:
        model: Model name. If None, uses default model from env.

    Returns:
        ModelConfig dictionary with context_window, max_tokens, supports_usage.

    Raises:
        KeyError: If model not found in MODELS.
    """
    if model is None:
        model = get_default_model()
    return MODELS[model]


def get_context_window(model: Optional[str] = None) -> int:
    """Get model's context window size.

    Args:
        model: Model name. If None, uses default model.

    Returns:
        Context window in tokens.
    """
    return get_model_config(model)["context_window"]


def get_max_tokens(model: Optional[str] = None) -> int:
    """Get model's maximum output tokens.

    Args:
        model: Model name. If None, uses default model.

    Returns:
        Maximum tokens model can generate.
    """
    return get_model_config(model)["max_tokens"]

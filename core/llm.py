"""LLM 调用模块，支持多种模型提供商"""

import os
from enum import Enum
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ModelProvider(Enum):
    """模型提供商枚举，定义支持的 LLM 提供商"""

    MINIMAX = "minimax"


# 提供商配置：api_key（API密钥）、base_url（API地址）、default_model（默认模型）
PROVIDER_CONFIG: dict[ModelProvider, dict] = {
    ModelProvider.MINIMAX: {
        "api_key": os.getenv("MINIMAX_API_KEY"),  # API 密钥
        "base_url": "https://api.minimax.chat/v1",  # API 地址
        "default_model": "MiniMax-M2.7",  # 默认模型
    },
}


def chat(
    messages: list[dict],
    provider: ModelProvider = ModelProvider.MINIMAX,
    model: str | None = None,
    temperature: float = 0.3,
) -> str:
    """调用 LLM 模型进行对话

    Args:
        messages: 对话消息列表，格式为 [{"role": "user", "content": "..."}]
        provider: 模型提供商，默认为 MiniMax
        model: 可选的模型名称，不传则使用提供商默认模型
        temperature: 温度参数，控制输出随机性，0-1 之间，越低越确定

    Returns:
        模型返回的文本内容
    """
    config = PROVIDER_CONFIG[provider]
    model = model or config["default_model"]

    # MiniMax/DeepSeek 等都兼容 OpenAI 格式
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
    )
    return response.choices[0].message.content or ""

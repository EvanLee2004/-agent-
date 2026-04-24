"""单个 LLM 模型配置。"""

from dataclasses import dataclass
from typing import Optional


DEFAULT_MODEL_USE_PATH = "crewai:LLM"
DEFAULT_REQUEST_TIMEOUT = 600.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_TOKENS = 4096


@dataclass(frozen=True)
class LlmModelProfile:
    """描述一个可供 crewAI 运行时使用的模型条目。

    这里不把“当前系统只有一个活跃模型”的假设写死在配置层，而是把每个模型
    的运行参数、环境变量名和能力标记显式建模。这样做有三个目的：

    1. 让 crewAI 运行时可以稳定拿到默认模型和未来的模型池；
    2. 为后续按角色或按任务切换模型预留稳定数据结构；
    3. 避免 provider 目录、运行时工厂和环境变量注入层各自重复拼接模型信息。

    Attributes:
        name: 当前配置内的稳定模型名，用于默认模型选择和未来按名称切换。
        provider_name: 提供商标识，例如 `openai`、`deepseek`、`minimax`。
        model_name: 发给上游网关的真实模型名。
        base_url: 模型 API 基础地址。
        api_key_env: crewAI 运行时应读取的环境变量名。
        api_key: 当前进程内解析出的真实密钥，用于在运行前写入环境变量。
        display_name: 用户可见展示名；为空时退化为 `model_name`。
        use_path: crewAI 解析模型类时使用的导入路径。
        supports_thinking: 是否支持扩展思考。
        supports_vision: 是否支持视觉输入。
        request_timeout: 请求超时秒数。
        max_retries: 最大重试次数。
        max_tokens: 单次请求的 token 上限。
        temperature: 可选采样温度；为空时由运行时工厂按 provider 决定默认值。
    """

    name: str
    provider_name: str
    model_name: str
    base_url: str
    api_key_env: str
    api_key: str
    display_name: Optional[str] = None
    use_path: str = DEFAULT_MODEL_USE_PATH
    supports_thinking: bool = True
    supports_vision: bool = False
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: Optional[float] = None

    def get_display_name(self) -> str:
        """返回用于 UI 与 crewAI 配置的展示名。"""
        if self.display_name:
            return self.display_name
        return self.model_name

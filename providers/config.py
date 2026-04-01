"""配置管理 - 管理模型选择和配置"""

import json
from pathlib import Path

from providers import PROVIDERS, get_provider, list_providers


CONFIG_FILE = Path("config.json")


def load_config() -> dict | None:
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        return None

    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def save_config(config: dict) -> None:
    """保存配置"""
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))


def select_provider() -> str:
    """让用户选择 provider"""
    providers = list_providers()
    print("请选择模型提供商：")
    for i, p in enumerate(providers, 1):
        cfg = get_provider(p)
        print(f"  {i}. {cfg.name} ({p})")

    while True:
        choice = input("选择 (1): ").strip() or "1"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                return providers[idx]
        except ValueError:
            pass
        print("无效选择，请重试")


def select_model(provider: str) -> str:
    """让用户选择 model"""
    cfg = get_provider(provider)
    print(f"\n请为 {cfg.name} 选择模型：")
    for i, m in enumerate(cfg.models, 1):
        marker = " (默认)" if m == cfg.default_model else ""
        print(f"  {i}. {m}{marker}")

    while True:
        choice = input("选择: ").strip()
        if not choice:
            return cfg.default_model
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(cfg.models):
                return cfg.models[idx]
        except ValueError:
            pass
        print("无效选择，请重试")


def input_api_key(provider: str) -> str:
    """输入 API key"""
    cfg = get_provider(provider)
    print(f"\n请输入 {cfg.name} 的 API Key：")
    key = input("API Key: ").strip()
    return key


def setup_config() -> dict:
    """引导用户配置"""
    print("=" * 50)
    print("首次使用，需要配置模型")
    print("=" * 50)

    # 选择 provider
    provider = select_provider()

    # 选择 model
    model = select_model(provider)

    # 输入 API key
    api_key = input_api_key(provider)

    config = {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }

    save_config(config)
    print(f"\n配置已保存到 {CONFIG_FILE}")
    return config


def ensure_config() -> dict:
    """确保配置存在，必要时引导用户配置"""
    config = load_config()

    if config and config.get("provider") and config.get("model") and config.get("api_key"):
        return config

    return setup_config()


def print_current_config() -> None:
    """打印当前配置"""
    config = load_config()
    if not config:
        print("未配置")
        return

    provider = get_provider(config.get("provider", ""))
    if provider:
        print(f"当前: {provider.name} - {config.get('model')}")
    else:
        print(f"当前: {config.get('provider')} - {config.get('model')}")

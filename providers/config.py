"""配置管理 - 管理模型选择和配置"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from providers import PROVIDERS, get_provider, list_providers


load_dotenv()

CONFIG_FILE = Path("config.json")
ENV_FILE = Path(".env")


def load_config() -> Optional[dict]:
    """加载配置文件（不含密钥）"""
    if not CONFIG_FILE.exists():
        return None
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def save_config(config: dict) -> None:
    """保存配置（不含密钥）"""
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))


def get_api_key() -> str:
    """从 .env 获取 API 密钥"""
    key = os.getenv("LLM_API_KEY", "").strip()
    if key:
        return key

    # 如果 .env 没有，提示用户输入
    print("未在 .env 中找到 LLM_API_KEY，请输入：")
    key = input("API Key: ").strip()
    # 保存到 .env
    _save_env_key(key)
    return key


def _save_env_key(key: str) -> None:
    """保存密钥到 .env"""
    content = f"LLM_API_KEY={key}\n"
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("LLM_API_KEY="):
                new_lines.append(f"LLM_API_KEY={key}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(content)
        content = "\n".join(new_lines)
    ENV_FILE.write_text(content + "\n")


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


def setup_config() -> dict:
    """引导用户配置"""
    print("=" * 50)
    print("首次使用，需要配置模型")
    print("=" * 50)

    # 选择 provider
    provider = select_provider()

    # 选择 model
    model = select_model(provider)

    # 输入 API key（保存到 .env）
    api_key = get_api_key()

    # 获取 base_url
    provider_cfg = get_provider(provider)
    base_url = provider_cfg.base_url_template

    config = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
    }

    save_config(config)
    print(f"\n配置已保存到 {CONFIG_FILE}，密钥已保存到 .env")
    return config


def ensure_config() -> dict:
    """确保配置存在，必要时引导用户配置"""
    config = load_config()

    if config and config.get("provider") and config.get("model"):
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

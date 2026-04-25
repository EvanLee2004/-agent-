"""智能财务部门 CLI 入口。"""

import sys

from app.cli_router import CliRouter
from app.dependency_container import AppServiceFactory
from configuration.configuration_error import ConfigurationError


def main() -> None:
    """启动 CLI。"""
    try:
        cli_router = CliRouter(AppServiceFactory.create_configuration_service())
        cli_router.run()
    except ConfigurationError as error:
        # CLI 属于用户直接面对的入口，配置错误应当给出明确提示并干净退出，
        # 而不是抛出 Python 栈信息破坏产品体验。
        print(f"启动失败：{str(error)}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()

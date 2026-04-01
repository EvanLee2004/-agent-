"""智能会计 CLI 入口。"""

from app.cli_router import CliRouter
from app.dependency_container import DependencyContainer
from configuration.configuration_error import ConfigurationError


def main() -> None:
    """启动 CLI。"""
    try:
        cli_router = CliRouter(DependencyContainer.create_configuration_service())
        cli_router.run()
    except ConfigurationError as error:
        raise RuntimeError(str(error)) from error


if __name__ == "__main__":
    main()

"""DeerFlow 运行时配置。"""

from dataclasses import dataclass


DEFAULT_SANDBOX_USE_PATH = "deerflow.sandbox.local:LocalSandboxProvider"
DEFAULT_BASH_OUTPUT_MAX_CHARS = 20000
DEFAULT_READ_FILE_OUTPUT_MAX_CHARS = 50000


@dataclass(frozen=True)
class DeerFlowRuntimeConfiguration:
    """描述项目当前采用的 DeerFlow runtime 运行参数。

    这里单独抽出 DeerFlow runtime 配置，而不是继续把这些开关硬编码在
    `DeerFlowClientFactory` 或 `config.yaml` 工厂里，主要有三个原因：

    1. DeerFlow public client 本身就支持 `thinking_enabled`、`subagent_enabled`
       和 `plan_mode` 这些运行时参数；如果我们把它们写死，项目表面上“接了 DeerFlow”，
       实际上仍然是自定义运行时策略。
    2. DeerFlow 主配置里的 `tool_search` 与 `sandbox` 也是底层能力的一部分。
       把它们留在配置对象里，才能做到“项目只定制财务领域，底层能力按 DeerFlow 方式装配”。
    3. 后续如果要按环境或角色切换这些开关，只需要在配置层扩展，不需要再修改多处 runtime 代码。

    Attributes:
        thinking_enabled: 是否启用模型扩展思考能力。
        subagent_enabled: 是否启用 DeerFlow 原生子代理委派。
        plan_mode: 是否启用 DeerFlow plan mode。
        tool_search_enabled: 是否启用 DeerFlow 的工具搜索能力。
        sandbox_use_path: DeerFlow sandbox provider 的导入路径。
        sandbox_allow_host_bash: 是否允许本机 bash 直接执行。
        sandbox_bash_output_max_chars: bash 输出最大字符数。
        sandbox_read_file_output_max_chars: 读文件工具最大输出字符数。
    """

    thinking_enabled: bool = True
    subagent_enabled: bool = False
    plan_mode: bool = False
    tool_search_enabled: bool = False
    sandbox_use_path: str = DEFAULT_SANDBOX_USE_PATH
    sandbox_allow_host_bash: bool = False
    sandbox_bash_output_max_chars: int = DEFAULT_BASH_OUTPUT_MAX_CHARS
    sandbox_read_file_output_max_chars: int = DEFAULT_READ_FILE_OUTPUT_MAX_CHARS

"""领域层包。

默认继续通过 `domain.models` 暴露统一兼容出口；
新代码可以按业务边界直接从子模块导入。
"""

from domain.models import *  # noqa: F401,F403

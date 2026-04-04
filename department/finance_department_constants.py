"""财务部门共享常量。"""


DEPARTMENT_DISPLAY_NAME = "智能财务部门"
SHARED_SKILL_NAMES = ("finance-core",)

# DeerFlow 官方默认 agent 在运行时会基于 tool group 过滤“配置文件里声明的工具”。
# 这里把我们希望所有财务角色共享的基础能力统一收口成常量，避免每个角色定义文件
# 各自复制一份字符串列表，后续如果要继续向 DeerFlow 官方默认配置靠拢，只改这一处。
DEERFLOW_BASE_TOOL_GROUP_NAMES = (
    "web",
    "file:read",
    "file:write",
    "bash",
    "finance",
)

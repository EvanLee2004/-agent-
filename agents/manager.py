"""经理角色，负责分配任务给不同的财务助手"""

from agents.assistant import Assistant

SYSTEM_PROMPT = "你是智能财务部门的财务经理，负责把用户任务按职能分配给不同的AI财务助手"


class Manager(Assistant):
    """经理角色，继承自 Assistant"""

    SYSTEM_PROMPT = SYSTEM_PROMPT


manager = Manager()

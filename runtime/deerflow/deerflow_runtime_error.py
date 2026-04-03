"""DeerFlow 运行时异常。"""

from conversation.conversation_error import ConversationError


class DeerFlowRuntimeError(ConversationError):
    """描述 DeerFlow 底层接入失败。

    该异常专门用于包裹 DeerFlow public client 初始化、配置解析和会话执行阶段的
    可预期失败。把它从通用 `ConversationError` 中单独拆出来，是为了让调用方
    能够明确区分“会话层自身错误”和“第三方 runtime 接入错误”。
    """

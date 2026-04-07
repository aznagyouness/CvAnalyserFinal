from enum import Enum

class LLMModelEnums(Enum):
    # DeepSeek models
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"

    # Qwen models   
    QWEN_MAX = "qwen-max"
    QWEN_PLUS = "qwen-plus"

    # Minimax models
    MINIMAX_CHAT = "minimax-chat"

class LLMProviderEnums(Enum):
    DEEPSEEK = "deepseek"
    QWEN = "qwen"   
    MINIMAX = "minimax"

class LLMRoleEnums(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

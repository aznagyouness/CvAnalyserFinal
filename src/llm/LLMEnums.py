from enum import Enum

class LLMModelEnums(Enum):
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"

class LLMRoleEnums(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

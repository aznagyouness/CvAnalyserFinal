import os
from typing import Optional
from src.llm.LLMEnums import LLMProviderEnums
from src.llm.providers.deepseek_model import DeepSeekModel
from src.llm.providers.qwen_model import QwenModel
from src.llm.providers.minimax_model import MinimaxModel
from src.helpers.config import get_settings

settings = get_settings()

class LLMFactory:
    """
    Factory class to instantiate different LLM providers.
    """

    @staticmethod
    def get_llm(
        provider: str, 
        api_key: Optional[str] = None, 
        api_url: Optional[str] = None,
        **kwargs
    ):
        """
        Returns an instance of the requested LLM provider.
        
        Args:
            provider (str): The provider name (e.g., 'deepseek', 'qwen').
            api_key (str, optional): API key for the provider.
            api_url (str, optional): Base URL for the API.
            **kwargs: Additional parameters for the model constructor.
            
        Returns:
            LLMInterface: An instance of a concrete LLM provider class.
        """
        provider = provider.lower()

        if provider == LLMProviderEnums.DEEPSEEK.value:
            return DeepSeekModel(
                api_key=api_key if api_key else settings.DEEPSEEK_API_KEY,
                api_url=api_url if api_url else settings.DEEPSEEK_API_URL,
                **kwargs
            )
        
        elif provider == LLMProviderEnums.QWEN.value:
            return QwenModel(
                api_key=api_key if api_key else settings.QWEN_API_KEY,
                api_url=api_url if api_url else settings.QWEN_API_URL,
                **kwargs
            )
        
        elif provider == LLMProviderEnums.MINIMAX.value:
            return MinimaxModel(
                api_key=api_key if api_key else settings.MINIMAX_API_KEY,
                api_url=api_url if api_url else settings.MINIMAX_API_URL,
                **kwargs
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

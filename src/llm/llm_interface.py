from abc import ABC, abstractmethod
from typing import List, Optional, Union

class LLMInterface(ABC):
    """
    Abstract interface for LLM providers (e.g., DeepSeek, OpenAI).
    Ensures unified methods for text generation and embedding.
    """

    @abstractmethod
    def set_generation_model(self, model_id: str):
        """Sets the model to be used for text generation."""
        pass

    @abstractmethod
    def set_embedding_model(self, model_id: str, embedding_size: int):
        """Sets the model to be used for generating embeddings."""
        pass

    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        chat_history: List[dict] = [], 
        documents: Optional[List[dict]] = None,
        lang: str = "en",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Asynchronously generates text based on a prompt, optional chat history and RAG documents."""
        pass



    @abstractmethod
    async def embed_text(self, text: Union[str, List[str]], **kwargs) -> Union[List[float], List[List[float]]]:
        """Asynchronously creates embeddings for the given text(s)."""
        pass

    @abstractmethod
    def construct_prompt(self, prompt: str, role: str) -> dict:
        """Constructs a message object for the specific provider's format."""
        pass



import os
import logging
from typing import List, Union, Optional, Dict, Any
import asyncio
from openai import AsyncOpenAI
from src.llm.llm_interface import LLMInterface
from src.llm.LLMEnums import LLMRoleEnums
from src.llm.templates.rag_prompt import RAGPromptManager

from src.helpers.config import get_settings

settings = get_settings()

class DeepSeekModel(LLMInterface):
    """
    Asynchronous implementation of the DeepSeek model using AsyncOpenAI client.
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_url: str = None,
        default_input_max_characters: int = 4000,
        default_generation_max_output_tokens: int = 2000,
        default_generation_temperature: float = 0.7
    ):
        """
        Initializes the DeepSeek model with an asynchronous client.
        """
        self.api_key = api_key if api_key else settings.DEEPSEEK_API_KEY
        self.api_url = api_url if api_url else settings.DEEPSEEK_API_URL

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY must be provided or set as an environment variable.")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_url
        )

        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def _process_text(self, text: str) -> str:
        """Truncates and cleans the input text."""
        return text[:self.default_input_max_characters].strip()

    async def generate_text(
        self, 
        prompt: str, 
        chat_history: List[dict] = [], 
        documents: Optional[List[Dict[str, Any]]] = None,
        lang: str = "en",
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Asynchronously generates a response from DeepSeek.
        If documents are provided, it builds a RAG-optimized prompt.
        """
        if not self.generation_model_id:
            self.logger.error("Generation model ID was not set.")
            return ""

        max_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temp = temperature or self.default_generation_temperature

        # Prepare messages
        if documents:
            # RAG flow: Use RAGPromptManager to build messages
            prompt_manager = RAGPromptManager(lang=lang)
            # We assume the context window for DeepSeek is large, 
            # but we limit the prompt part to around 8k tokens for safety
            messages = prompt_manager.build_messages(
                query=prompt, 
                documents=documents,
                max_input_tokens=8000 
            )
            # If there's existing chat history, we can prepend it (before system prompt or between system/user)
            # For simplicity in RAG, we'll append the built RAG messages to history if provided
            if chat_history:
                # Merge: [history...] + [RAG system] + [RAG user]
                # Note: DeepSeek usually prefers one system message at the start.
                messages = chat_history + messages
        else:
            # Standard flow
            messages = list(chat_history)
            messages.append(self.construct_prompt(prompt=prompt, role=LLMRoleEnums.USER.value))

        try:
            response = await self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temp,
                stream=False,
                **kwargs
            )

            if response and response.choices:
                return response.choices[0].message.content or ""
            
            return ""
        except Exception as e:
            self.logger.error(f"Error during DeepSeek text generation: {str(e)}")
            return ""



    async def embed_text(self, text: Union[str, List[str]], **kwargs) -> Union[List[float], List[List[float]]]:
        """
        Asynchronously generates embeddings using DeepSeek (if supported) or compatible endpoint.
        """
        if not self.embedding_model_id:
            self.logger.error("Embedding model ID was not set.")
            return []

        input_text = [text] if isinstance(text, str) else text

        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model_id,
                input=input_text,
                **kwargs
            )

            if not response or not response.data:
                self.logger.error("DeepSeek embedding API returned empty data.")
                return []

            embeddings = [item.embedding for item in response.data]
            
            # If the original input was a string, return a single list.
            # Otherwise, return the list of lists.
            return embeddings[0] if isinstance(text, str) else embeddings
        except Exception as e:
            self.logger.error(f"Error during DeepSeek embedding generation: {str(e)}")
            raise e # Raise to let the caller handle it or for debugging

    def construct_prompt(self, prompt: str, role: str) -> dict:
        """
        Constructs a message dictionary for the OpenAI-compatible API.
        """
        return {
            "role": role,
            "content": prompt
        }



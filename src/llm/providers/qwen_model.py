import os
import logging
import asyncio
from typing import List, Union, Optional, Dict, Any
from aiolimiter import AsyncLimiter
from openai import AsyncOpenAI
from src.llm.llm_interface import LLMInterface
from src.llm.LLMEnums import LLMRoleEnums
from src.llm.templates.rag_prompt import RAGPromptManager

from src.helpers.config import get_settings

settings = get_settings()

class QwenModel(LLMInterface):
    """
    Asynchronous implementation of the qwen model using AsyncOpenAI client.
    qwen API from DashScope is OpenAI-compatible.
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_url: Optional[str] = None,
        default_input_max_characters: int = 4000,
        default_generation_max_output_tokens: int = 2000,
        default_generation_temperature: float = 0.7,
        max_requests_per_minute: int = 60,
        max_concurrent_requests: int = 10
    ):
        """
        Initializes the qwen model with an asynchronous client.
        """
        self.api_key = api_key if api_key else settings.QWEN_API_KEY
        self.api_url = api_url if api_url else settings.QWEN_API_URL

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        # Rate limiting and concurrency control
        self.rpm_limiter = AsyncLimiter(max_requests_per_minute, 60)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        if not self.api_key:
            raise ValueError("qwen_API_KEY must be provided or set as an environment variable.")

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
        Asynchronously generates a response from qwen.
        If documents are provided, it builds a RAG-optimized prompt.
        """
        if not self.generation_model_id:
            self.logger.error("Generation model ID was not set.")
            return ""

        max_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temp = temperature if temperature else self.default_generation_temperature

        

        # Prepare messages
        if documents:

            import time 
            start = time.time()
            prompt_manager = RAGPromptManager(lang=lang)
            messages = prompt_manager.build_messages(
                query=prompt, 
                documents=documents,
                max_input_tokens=8000 
            )
            if chat_history:
                messages = chat_history + messages

            end_time = time.time()
            print(f"build messages with documents in {end_time - start} seconds")
            
    
        else:
            messages = list(chat_history)
            messages.append(self.construct_prompt(prompt=prompt, role=LLMRoleEnums.USER.value))

        try:
            start = time.time()
            response = await self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temp,
                stream=False,
                **kwargs
            )
            end_time = time.time()
            print(f"generate text in {end_time - start} seconds")

            if response and response.choices:
                return response.choices[0].message.content or ""
            
            return ""
        except Exception as e:
            self.logger.error(f"Error during qwen text generation: {str(e)}")
            raise e

    

    async def embed_text(self, text: Union[str, List[str]], **kwargs) -> Union[List[float], List[List[float]]]:
        """
        Asynchronously generates embeddings using qwen with advanced batching,
        rate limiting, concurrency control, and retries.
        """
        if not self.embedding_model_id:
            self.logger.error("Embedding model ID was not set.")
            return []

        # Convert single string to list for unified processing
        is_single_input = isinstance(text, str)
        input_texts = [text] if is_single_input else text
        
        # Qwen has a strict limit of 10 items per batch
        batch_size = 10
        batches = [input_texts[i : i + batch_size] for i in range(0, len(input_texts), batch_size)]
        
        async def process_batch(batch: List[str], batch_idx: int) -> tuple:
            """Processes a single batch with retries and rate limiting."""
            async with self.semaphore:
                for attempt in range(3):  # Max 3 retries
                    try:
                        async with self.rpm_limiter:
                            response = await self.client.embeddings.create(
                                model=self.embedding_model_id,
                                input=batch,
                                **kwargs
                            )
                            
                            if not response or not response.data:
                                raise ValueError(f"Empty response for batch {batch_idx}")
                                
                            return batch_idx, [item.embedding for item in response.data]
                            
                    except Exception as e:
                        if attempt == 2:
                            self.logger.error(f"Failed to process embedding batch {batch_idx} after 3 attempts: {str(e)}")
                            raise e
                        
                        wait_time = (2 ** attempt) + 0.1  # Exponential backoff
                        self.logger.warning(
                            f"Retry {attempt + 1}/3 for batch {batch_idx} in {wait_time:.1f}s due to: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
            
            return batch_idx, []

        try:
            # Run all batches concurrently (controlled by semaphore)
            tasks = [process_batch(batch, i) for i, batch in enumerate(batches)]
            results = await asyncio.gather(*tasks)
            
            # Sort results by batch_idx to maintain original order
            results.sort(key=lambda x: x[0])
            
            all_embeddings = []
            for _, batch_embeddings in results:
                all_embeddings.extend(batch_embeddings)

            if not all_embeddings:
                return []

            return all_embeddings[0] if is_single_input else all_embeddings
            
        except Exception as e:
            self.logger.error(f"Error during qwen concurrent embedding generation: {str(e)}")
            raise e

    def construct_prompt(self, prompt: str, role: str) -> dict:
        """
        Constructs a message dictionary for the OpenAI-compatible API.
        """
        return {
            "role": role,
            "content": prompt
        }

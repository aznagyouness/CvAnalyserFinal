import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.helpers.config import get_settings

settings = get_settings()

class QwenReranker:
    """
    Asynchronous implementation of the Qwen Reranker using AsyncOpenAI client.
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_url: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        """
        Initializes the Qwen Reranker with an asynchronous client.
        """
        self.api_key = api_key if api_key else settings.QWEN_RERANK_API_KEY
        self.api_url = api_url if api_url else settings.QWEN_RERANK_API_URL
        self.model_id = model_id if model_id else settings.QWEN_RERANK_MODEL_ID

        if not self.api_key:
            raise ValueError("QWEN_RERANK_API_KEY must be provided or set as an environment variable.")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_url
        )

        self.logger = logging.getLogger(__name__)

    async def rerank(
        self, 
        query: str, 
        documents: List[str], 
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously reranks documents based on a query.
        Returns a list of dictionaries containing document index and relevance score.
        """
        if not documents:
            return []

        try:
            # Using the custom endpoint for reranking as per Qwen documentation
            response = await self.client.post(
                "/reranks",
                body={
                    "model": self.model_id,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n
                },
                cast_to=object
            )

            # The response format usually includes a list of results with index and relevance_score
            if hasattr(response, "results"):
                return response.results
            elif isinstance(response, dict) and "results" in response:
                return response["results"]
            
            return []
        except Exception as e:
            self.logger.error(f"Error during Qwen reranking: {str(e)}")
            raise e

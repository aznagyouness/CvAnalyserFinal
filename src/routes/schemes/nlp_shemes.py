from pydantic import BaseModel
from typing import Optional, List

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0
    provider: Optional[str] = "deepseek"

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    provider: Optional[str] = "deepseek"

class RAGRequest(BaseModel):
    query: str
    vector_db_limit: Optional[int] = 50
    provider: Optional[str] = "qwen"
    lang: Optional[str] = "en"
    chat_history: Optional[List[dict]] = []
    use_reranker: Optional[bool] = False
    reranker_top_n: Optional[int] = 5

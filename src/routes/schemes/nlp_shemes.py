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
    limit: Optional[int] = 5
    provider: Optional[str] = "deepseek"
    lang: Optional[str] = "en"
    chat_history: Optional[List[dict]] = []

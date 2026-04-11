from typing import Optional
from pydantic import BaseModel

class RetrievedDocumentEnum(BaseModel):
    text: str
    score: float
    metadata: Optional[dict] = None
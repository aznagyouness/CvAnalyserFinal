from pydantic import BaseModel

class RetrievedDocumentEnum(BaseModel):
    text: str
    score: float
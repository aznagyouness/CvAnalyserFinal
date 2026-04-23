from typing import Optional
from pydantic import BaseModel

from src.helpers.config import get_settings
settings = get_settings()
class ProcessRequest(BaseModel):
    file_name: Optional[str] = None
    chunk_size: Optional[int] = settings.CHUNK_SIZE
    overlap_size: Optional[int] = settings.CHUNK_OVERLAP
    do_reset: Optional[int] = 0
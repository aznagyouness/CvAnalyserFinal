from typing import Optional
from pydantic import BaseModel

class ProcessRequest(BaseModel):
    file_name: Optional[str] = None
    chunk_size: Optional[int] = 1000 
    overlap_size: Optional[int] = 200
    do_reset: Optional[int] = 0
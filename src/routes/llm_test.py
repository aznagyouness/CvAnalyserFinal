from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from src.llm.providers.deepseek_model import DeepSeekModel
from src.llm.templates.rag_prompt import RAGPromptManager
from src.helpers.config import get_settings

router = APIRouter(prefix="/test/llm", tags=["LLM Testing"])
settings = get_settings()

# Initialize DeepSeek model
deepseek_model = DeepSeekModel(
    api_key=settings.DEEPSEEK_API_KEY,
    api_url=settings.DEEPSEEK_API_URL
)
deepseek_model.set_generation_model(settings.GENERATION_MODEL_ID)
deepseek_model.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

class GenerateRequest(BaseModel):
    prompt: str
    chat_history: Optional[List[dict]] = []
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None

class RAGGenerateRequest(BaseModel):
    prompt: str
    documents: List[Dict[str, Any]]
    chat_history: Optional[List[dict]] = []
    lang: str = "en"
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None

class EmbedRequest(BaseModel):
    text: str # Can be single string or list of strings

@router.post("/generate")
async def test_generate(req: GenerateRequest):
    """Test basic text generation."""
    try:
        # Replicate message building for debugging
        debug_messages = list(req.chat_history)
        debug_messages.append(deepseek_model.construct_prompt(prompt=req.prompt, role="user"))

        response = await deepseek_model.generate_text(
            prompt=req.prompt,
            chat_history=req.chat_history,
            max_output_tokens=req.max_output_tokens,
            temperature=req.temperature,
            
        )
        return {
            "status": "success", 
            "prompt": req.prompt, 
            "debug_messages": debug_messages,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rag-generate")
async def test_rag_generate(req: RAGGenerateRequest):
    """Test RAG-based text generation with documents."""
    try:
        # Replicate message building logic for debugging
        prompt_manager = RAGPromptManager(lang=req.lang)
        debug_messages = prompt_manager.build_messages(
            query=req.prompt, 
            documents=req.documents,
            max_input_tokens=8000 
        )
        if req.chat_history:
            debug_messages = req.chat_history + debug_messages

        response = await deepseek_model.generate_text(
            prompt=req.prompt,
            documents=req.documents,
            chat_history=req.chat_history,
            lang=req.lang,
            max_output_tokens=req.max_output_tokens,
            temperature=req.temperature
        )
        return {
            "status": "success", 
            "prompt": req.prompt, 
            "debug_messages": debug_messages,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embed")
async def test_embed(req: EmbedRequest):
    """Test text embedding generation."""
    try:
        embedding = await deepseek_model.embed_text(text=req.text)
        return {"status": "success", "embedding_size": len(embedding) if isinstance(embedding, list) and not isinstance(embedding[0], list) else "multiple", "embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

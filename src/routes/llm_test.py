from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from src.llm.LLMFactory import LLMFactory
from src.llm.LLMEnums import LLMModelEnums,LLMProviderEnums,LLMRoleEnums

from src.llm.templates.rag_prompt import RAGPromptManager
from src.helpers.config import get_settings

router = APIRouter(prefix="/test/llm", tags=["LLM Testing"])
settings = get_settings()

class GenerateRequest(BaseModel):
    provider: str = "qwen"
    prompt: str
    chat_history: Optional[List[dict]] = []
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None

class RAGGenerateRequest(BaseModel):
    provider: str = "qwen"
    prompt: str
    documents: List[Dict[str, Any]]
    chat_history: Optional[List[dict]] = []
    lang: str = "en"
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None

class EmbedRequest(BaseModel):
    provider: str = "qwen"  
    text: str # Can be single string or list of strings

class ConnectRequest(BaseModel):
    provider: str = "qwen"

@router.post("/connect")
async def test_connect(req: ConnectRequest):
    """Test connection to the LLM client."""
    try:
        llm = LLMFactory.get_llm(provider=req.provider)
        # Check if API key is present
        if not llm.api_key:
            return {
                "status": "failed",
                "provider": req.provider,
                "message": f"API Key for {req.provider} is missing."
            }
        
        # Simple verification: try to access the client
        # For OpenAI-compatible clients, we can't easily "ping" without making a request,
        # but we can at least verify the client is initialized.
        return {
            "status": "success",
            "provider": req.provider,
            "message": f"Successfully initialized {req.provider} client.",
            "api_url": llm.api_url
        }
    except Exception as e:
        return {
            "status": "failed",
            "provider": req.provider,
            "message": str(e)
        }

@router.post("/generate")
async def test_generate(req: GenerateRequest):
    """Test basic text generation."""
    try:
        llm = LLMFactory.get_llm(provider=req.provider)
        # Use defaults from settings if deepseek, otherwise user might need to specify model_id
        if req.provider == "deepseek":
            llm.set_generation_model(settings.GENERATION_MODEL_ID)
        elif req.provider == "minimax":
            llm.set_generation_model(LLMModelEnums.MINIMAX_CHAT.value)
        else:
            llm.set_generation_model(LLMModelEnums.QWEN_MAX.value)

        # Replicate message building for debugging
        debug_messages = list(req.chat_history)
        debug_messages.append(llm.construct_prompt(prompt=req.prompt, role="user"))

        response = await llm.generate_text(
            prompt=req.prompt,
            chat_history=req.chat_history,
            max_output_tokens=req.max_output_tokens,
            temperature=req.temperature,
        )
        
        return {
            "status": "success", 
            "provider": req.provider,
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
        llm = LLMFactory.get_llm(provider=req.provider)
        if req.provider == "deepseek":
            llm.set_generation_model(settings.GENERATION_MODEL_ID)
        elif req.provider == "minimax":
            llm.set_generation_model(LLMModelEnums.MINIMAX_CHAT.value)
        else:
            llm.set_generation_model(LLMModelEnums.QWEN_MAX.value)

        # Replicate message building logic for debugging
        prompt_manager = RAGPromptManager(lang=req.lang)
        debug_messages = prompt_manager.build_messages(
            query=req.prompt, 
            documents=req.documents,
            max_input_tokens=8000 
        )
        if req.chat_history:
            debug_messages = req.chat_history + debug_messages

        response = await llm.generate_text(
            prompt=req.prompt,
            documents=req.documents,
            chat_history=req.chat_history,
            lang=req.lang,
            max_output_tokens=req.max_output_tokens,
            temperature=req.temperature
        )
        return {
            "status": "success", 
            "provider": req.provider,
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
        llm = LLMFactory.get_llm(provider=req.provider)
        if req.provider == "deepseek":
            llm.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
        else:
            # qwen embedding model placeholder
            llm.set_embedding_model("text-embedding-v3", 1024)

        embedding = await llm.embed_text(text=req.text)
        
        # Check if we got a list of floats (single embedding) or list of lists (multiple)
        is_multiple = isinstance(embedding, list) and len(embedding) > 0 and isinstance(embedding[0], list)
        
        return {
            "status": "success", 
            "provider": req.provider,
            "embedding_size": len(embedding) if not is_multiple else f"{len(embedding)} x {len(embedding[0])}", 
            "embedding": embedding
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

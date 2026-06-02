from fastapi import APIRouter, Depends, status, Request, HTTPException
from fastapi.responses import StreamingResponse
from src.routes.schemes.nlp_shemes import RAGRequest
from src.llm.LLMFactory import LLMFactory
from src.helpers.config import get_settings, Settings
from src.database import get_utils
from src.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.controllers.NLPController import NLPController
from src.llm.providers.qwen_rerank import QwenReranker
import logging
from typing import AsyncGenerator
import json

logger = logging.getLogger('uvicorn.error')

stream_router = APIRouter(
    prefix="/api/v1/stream",
    tags=["api_v1", "stream"],
)

@stream_router.post("/answer/{project_id}")
async def answer_question_stream(
    project_id: int, 
    rag_request: RAGRequest, 
    request: Request,
    settings: Settings = Depends(get_settings)
):
    """
    Streaming version of the RAG answer endpoint for high-performance production use.
    Provides real-time token generation for better UX.
    """
    # Optimized: Use sessionmaker from app.state initialized in main.py
    db_client_sessionmaker = request.app.state.db_session_factory
    
    # Initialize VectorDB
    vdb_factory = VectorDBProviderFactory(config=settings, db_client=db_client_sessionmaker)
    vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vdb_client.connect()
    
    # Initialize LLM
    llm = LLMFactory.get_llm(provider=rag_request.provider)
    nlp_controller = NLPController(vectordb_client=vdb_client, llm_client=llm)
    nlp_controller.set_project_id(project_id=str(project_id))
    
    nlp_controller.llm_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
    nlp_controller.llm_client.set_generation_model(settings.GENERATION_MODEL_ID)

    async def stream_generator() -> AsyncGenerator[str, None]:
        try:
            # 0. Initial Heartbeat (Prevents Timeouts)
            yield 'event: info\ndata: {"message": "Connected. Searching knowledge base..."}\n\n'

            # 1. Retrieval
            retrieval_limit = rag_request.vector_db_limit if not rag_request.use_reranker else max(rag_request.vector_db_limit, 20)
            
            retrieved_documents = await nlp_controller.search_vector_db_collection(
                project_id=project_id,
                text=rag_request.query,
                limit=retrieval_limit,
                provider=rag_request.provider
            )

            if not retrieved_documents:
                yield 'event: error\ndata: {"message": "I couldn\'t find any relevant information to answer your question."}\n\n'
                return

            # 1.5 Reranking (if enabled)
            if rag_request.use_reranker:
                yield 'event: info\ndata: {"message": "Reranking results for better accuracy..."}\n\n'
                reranker = QwenReranker()
                doc_texts = [doc.text for doc in retrieved_documents]
                try:
                    rerank_results = await reranker.rerank(
                        query=rag_request.query,
                        documents=doc_texts,
                        top_n=rag_request.reranker_top_n
                    )
                    reranked_docs = []
                    for res in rerank_results:
                        idx = res.index if hasattr(res, 'index') else res.get('index')
                        if idx < len(retrieved_documents):
                            reranked_docs.append(retrieved_documents[idx])
                    retrieved_documents = reranked_docs
                except Exception as e:
                    logger.error(f"Reranking failed in stream: {str(e)}")
                    # Fallback to original top-k
                    retrieved_documents = retrieved_documents[:rag_request.vector_db_limit]

            # 2. Prepare documents for RAG
            documents = [{"text": doc.text, "source": doc.metadata.get("source", "Unknown")} for doc in retrieved_documents]
            
            yield 'event: info\ndata: {"message": "Generating answer..."}\n\n'

            # 3. Streaming Generation (SSE Format)
            async for chunk in nlp_controller.llm_client.generate_text_stream(
                prompt=rag_request.query,
                documents=documents,
                chat_history=rag_request.chat_history,
                lang=rag_request.lang
            ):
                # We wrap the chunk in SSE data format
                yield f"data: {chunk}\n\n"

            yield 'event: done\ndata: {"message": "Generation complete"}\n\n'

        except Exception as e:
            logger.error(f"Error in stream_generator for project {project_id}: {str(e)}")
            error_msg = str(e).replace('"', '\\"')
            yield f"event: error\ndata: {{\"message\": \"{error_msg}\"}}\n\n"
        finally:
            # Ensure resources are cleaned up after stream ends or client disconnects
            if vdb_client:
                await vdb_client.disconnect()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Critical for Nginx proxying
        }
    )

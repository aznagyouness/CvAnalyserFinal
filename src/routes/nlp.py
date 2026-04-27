from fastapi import APIRouter, status, Request, Depends
from fastapi.responses import JSONResponse
from src.routes.schemes.nlp_shemes import PushRequest, SearchRequest, RAGRequest
from src.models.crud.ProjectCrud import ProjectCrud
from src.models.crud.DataChunkCrud import DataChunkCrud
from src.controllers.NLPController import NLPController
from src.models.enums.ResponseEnums import ResponseSignal
from src.helpers.config import get_settings, Settings
from src.database import get_utils
from src.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from tqdm.auto import tqdm
import logging
import time
from src.llm.LLMFactory import LLMFactory

logger = logging.getLogger('uvicorn.error')

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest, settings: Settings = Depends(get_settings)):
    db_engine = None
    vdb_client = None
    try:
        (db_engine, db_client_sessionmaker) = await get_utils()
        project_crud = ProjectCrud(db_client=db_client_sessionmaker)
        chunk_crud = DataChunkCrud(db_client=db_client_sessionmaker)

        project = await project_crud.get_project_or_create_one(project_id=project_id)
        if not project:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
            )

        # Initialize VectorDB
        vdb_factory = VectorDBProviderFactory(config=settings, db_client=db_client_sessionmaker)
        vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
        await vdb_client.connect()
        
        llm = LLMFactory.get_llm(provider=push_request.provider)
        nlp_controller = NLPController(vectordb_client=vdb_client,llm_client=llm)
        nlp_controller.set_project_id(project_id=str(project_id))

        has_records = True
        page_no = 1
        inserted_items_count = 0

        while has_records:
            # Note: We need a paginated fetch for chunks. 
            # I'll assume get_project_chunks exists or I'll fetch all for now if small, 
            # but better to use the asset-based retrieval or implement pagination in DataChunkCrud
            # For now, let's fetch all chunks for the project
            chunks = await chunk_crud.get_chunks_by_project(project_id=project_id)
            if not chunks:
                has_records = False
                break
            
            is_inserted = await nlp_controller.index_into_vector_db(
                project_id=project_id,
                chunks=chunks,
                do_reset=bool(push_request.do_reset),
                provider=push_request.provider
            )

            if not is_inserted:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value}
                )

            inserted_items_count += len(chunks)
            has_records = False # For now, processing all at once as get_chunks_by_project is not paginated
            
        return JSONResponse(
            content={
                "signal": ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
                "inserted_items_count": inserted_items_count
            }
        )
    except Exception as e:
        logger.error(f"Error indexing project {project_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value, "detail": str(e)}
        )
    
    finally:
        if vdb_client : 
            await vdb_client.disconnect()
        if db_engine : 
            await db_engine.dispose()


@nlp_router.post("/search/{project_id}")
async def search_project(request: Request, project_id: int, search_request: SearchRequest, settings: Settings = Depends(get_settings)):
    db_engine = None
    vdb_client = None
    try:
        (db_engine, db_client_sessionmaker) = await get_utils()
        vdb_factory = VectorDBProviderFactory(config=settings, db_client=db_client_sessionmaker)
        vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
        await vdb_client.connect()

        
        llm = LLMFactory.get_llm(provider=search_request.provider)
        nlp_controller = NLPController(vectordb_client=vdb_client,llm_client=llm)
        nlp_controller.set_project_id(project_id=str(project_id))

        # Initialize the embedding model before searching
        nlp_controller.llm_client.set_embedding_model(
            settings.EMBEDDING_MODEL_ID, 
            settings.EMBEDDING_MODEL_SIZE
        )

        results = await nlp_controller.search_vector_db_collection(
            project_id=project_id,
            text=search_request.text,
            limit=search_request.limit,
            provider=search_request.provider
        )

        if results is False:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value}
            )

        return JSONResponse(
            content={
                "signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
                "results": [
                    {
                        "text": res.text,
                        "score": res.score,
                        "metadata": res.metadata
                    } for res in results
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error searching project {project_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value, "detail": str(e)}
        )
    
    finally:
        if vdb_client : 
            await vdb_client.disconnect()
        if db_engine : 
            await db_engine.dispose()




@nlp_router.post("/answer/{project_id}")
async def answer_question(request: Request, project_id: int, rag_request: RAGRequest, settings: Settings = Depends(get_settings)):

    start_endpoint = time.time()

    db_engine = None
    vdb_client = None
    try:
        start = time.time()
        (db_engine, db_client_sessionmaker) = await get_utils()
        vdb_factory = VectorDBProviderFactory(config=settings, db_client=db_client_sessionmaker)
        vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
        await vdb_client.connect()
        end_time = time.time()
        logger.info(f"Connected to VectorDB in {end_time - start} seconds")
        
        start = time.time()
        
        llm = LLMFactory.get_llm(provider=rag_request.provider)

        nlp_controller = NLPController(vectordb_client=vdb_client,llm_client=llm)
        nlp_controller.set_project_id(project_id=str(project_id))
        
        nlp_controller.llm_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
        
        end_time = time.time()
        logger.info(f"Set embedding model in {end_time - start} seconds")

        start = time.time()
        nlp_controller.llm_client.set_generation_model(settings.GENERATION_MODEL_ID)
        end_time = time.time()
        logger.info(f"Set generation model in {end_time - start} seconds")
        
        start = time.time()

        answer, full_history, retrieved_documents = await nlp_controller.answer_rag_question(
            project_id=project_id,
            query=rag_request.query,
            limit=rag_request.limit,
            provider=rag_request.provider,
            lang=rag_request.lang,
            chat_history=rag_request.chat_history
        )
        end_time = time.time()
        logger.info(f"Answered question with answer_rag_question in {end_time - start} seconds")

        return JSONResponse(
            content={
                "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
                "answer": answer,
                "retrieved_documents": [
                    {
                        "text": doc.text,
                        "score": doc.score,
                        "metadata": doc.metadata
                    } for doc in retrieved_documents
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error answering question for project {project_id}: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value, "detail": str(e)}
        )
    finally:
        if vdb_client : 
            await vdb_client.disconnect()
        if db_engine : 
            await db_engine.dispose()
    
        end_endpoint = time.time()
        logger.info(f"Endpoint processed in {end_endpoint - start_endpoint} seconds")






@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )

@nlp_router.post("/index/search/{project_id}")
async def search_index(request: Request, project_id: int, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value
                }
            )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
            "results": [ result.dict()  for result in results ]
        }
    )

""" @nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: int, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    answer, full_prompt, chat_history = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=search_request.limit,
    )

    if not answer:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.RAG_ANSWER_ERROR.value
                }
        )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )
 """

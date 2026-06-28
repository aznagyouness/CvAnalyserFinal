from src.tk_broker import broker
from src.controllers.NLPController import NLPController
from src.controllers.ProcessController import ProcessController
from src.models.crud.DataChunkCrud import DataChunkCrud
from src.database import get_utils
from src.llm import LLMFactory
from src.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.helpers.config import get_settings
from taskiq import TaskiqDepends
import logging
import asyncio

logger = logging.getLogger(__name__)
settings = get_settings()

@broker.task(
    task_name="indexing.process_file", 
    max_retry=3,
    retry_on_error=True
)
async def process_file_task(
    project_id: int,
    file_name: str,
    asset_id: int,
    chunk_size: int,
    overlap_size: int,
    db_utils = TaskiqDepends(get_utils)
):
    """
    Step 1: Load file, split into chunks, and save to Relational DB.
    """
    _, sessionmaker = db_utils
    process_controller = ProcessController(project_id=str(project_id))
    chunk_crud = DataChunkCrud(db_client=sessionmaker)
    
    try:
        # Load and split
        file_content = process_controller.load_documents(file_name)
        if not file_content:
            return f"No content found for {file_name}"
            
        file_chunks = process_controller.split_documents(file_content, chunk_size, overlap_size)
        if not file_chunks:
            return f"No chunks generated for {file_name}"

        # Prepare batch insertion for Relational DB
        chunks_to_insert = [
            {
                "text": chunk.page_content,
                "order": i + 1,
                "metadata": chunk.metadata
            }
            for i, chunk in enumerate(file_chunks)
        ]

        # Insert chunks in batch
        await chunk_crud.create_chunks_batch(
            project_id=project_id,
            asset_id=asset_id,
            chunks_data=chunks_to_insert
        )
        
        # Trigger Step 2: Orchestrate Indexing
        await index_project_task.kiq(project_id=project_id, asset_id=asset_id)
        
        return f"File {file_name} processed into {len(chunks_to_insert)} chunks and queued for indexing."
    except Exception as e:
        logger.error(f"Failed to process file {file_name}: {e}")
        # SimpleRetryMiddleware will catch this and retry because retry_on_error=True
        raise e

@broker.task(task_name="indexing.index_project", retry_on_error=True)
async def index_project_task(
    project_id: int,
    asset_id: int = None,
    db_utils = TaskiqDepends(get_utils)
):
    """
    Step 2: Fetch chunks from DB and decompose into parallel batches for indexing.
    """
    _, sessionmaker = db_utils
    chunk_crud = DataChunkCrud(db_client=sessionmaker)
    
    # Fetch all chunks for the project or asset
    if asset_id:
        chunks = await chunk_crud.get_chunks_by_asset(asset_id=asset_id)
    else:
        chunks = await chunk_crud.get_chunks_by_project(project_id=project_id)
        
    if not chunks:
        return f"No chunks found to index for project {project_id}"

    # Decompose into batches (e.g., 50 chunks per batch to optimize RPM)
    batch_size = 50
    chunk_ids = [c.chunk_id for c in chunks]
    
    batches = [chunk_ids[i:i + batch_size] for i in range(0, len(chunk_ids), batch_size)]
    
    # Dispatch batch tasks
    for batch in batches:
        await index_batch_task.kiq(project_id=project_id, chunk_ids=batch)
        
    return f"Project {project_id} indexing decomposed into {len(batches)} batches."

@broker.task(
    task_name="indexing.index_batch",
    max_retry=5,
    retry_on_error=True
)
async def index_batch_task(
    project_id: int,
    chunk_ids: list[int],
    db_utils = TaskiqDepends(get_utils)
):
    """
    Step 3: The "Worker Bee" - Embeds a batch and inserts into VectorDB.
    Strictly follows the "Hybrid Strategy" using the explicit REDIS_URL_QUOTA.
    """
    _, sessionmaker = db_utils
    chunk_crud = DataChunkCrud(db_client=sessionmaker)
    
    # 1. Fetch the actual chunks
    chunks = await chunk_crud.get_chunks_by_ids(chunk_ids=chunk_ids)
    if not chunks:
        return "Batch empty or chunks already deleted"

    # 2. Initialize Clients (Lazy loading in task)
    vdb_factory = VectorDBProviderFactory(config=settings, db_client=sessionmaker)
    vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vdb_client.connect()
    
    llm = LLMFactory.get_llm(provider=settings.EMBEDDING_BACKEND)
    nlp = NLPController(vectordb_client=vdb_client, llm_client=llm)
    
    try:
        # 3. Apply the Shield (Hybrid Strategy)
        from src.helpers.quota import GlobalLLMQuota
        quota_manager = GlobalLLMQuota(
            redis_url=settings.REDIS_URL_QUOTA,
            max_rpm=settings.MAX_RPM_EMBEDDING,
            key_prefix="quota:llm_embedding"
        )
        
        # Wait for a slot before embedding
        await quota_manager.wait_for_slot()
        
        # 4. Perform Indexing
        success = await nlp.index_into_vector_db(
            project_id=project_id,
            chunks=chunks,
            do_reset=False,
            provider=settings.EMBEDDING_BACKEND
        )
        
        await quota_manager.close()
        await vdb_client.disconnect()
        
        if not success:
            raise Exception("Batch indexing failed")
            
        return f"Successfully indexed batch of {len(chunks)} chunks"
        
    except Exception as e:
        logger.error(f"Error in index_batch_task: {e}")
        await vdb_client.disconnect()
        # SimpleRetryMiddleware will catch this and retry because retry_on_error=True
        raise e

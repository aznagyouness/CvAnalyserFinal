import datetime
from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from src.helpers.config import get_settings
from src.tasks.test_task import test_sum

settings = get_settings()

data_router = APIRouter(
    prefix="/api/v1/welcome",
    tags=["api_v1", "welcome"],
)


@data_router.get("/welcome_fastapi")
def test_fastapi():
    return {
        "message ": "Welcome to the Data API v1!"
        }


@data_router.get("/welcome_postgres")
async def test_postgres(request: Request):    
    db_engine = request.app.state.db_engine
    db_client_sessionmaker = request.app.state.db_session_factory
    return {
        "message ": "Postgres Docker connection successful!",
        "db_engine": str(db_engine),
        "db_client_sessionmaker": str(db_client_sessionmaker),
        "settings.POSTGRES_DATABASE_URL": settings.POSTGRES_DATABASE_URL,
        }


# ------------- VectorDBProvider -------------
import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

@data_router.get("/welcome_vectordb")
async def test_vector_db():
    # 1. Initialize Async Client pointing to Docker
    # url: Points to the REST port (6333) for discovery
    # prefer_grpc: Forces search/upsert to use gRPC port (6334)
    url = settings.VECTOR_DB_URL
    client = AsyncQdrantClient(
        url=url, 
        prefer_grpc=True,
        timeout=30
    )
    
    try:
        # 2. Health Check (Ping)
        # Using a metadata call is faster than listing all collections
        try:
            # We check connectivity by asking for a small piece of metadata
            # await client.get_collections() is very fast in Qdrant (metadata lookup)
            # In Qdrant, there isn't a dedicated "ping" method in the client, but await client.get_collections() is used as the standard way to verify a connection.
            await client.get_collections()
            print("✅ Connected to Qdrant Docker")
            return {
                "message ": " Connected to Qdrant Docker successful!",
                "url" : url
            }
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return {
                "message ": " Connection failed!",
                "url" : url
            }


    finally:
        # AsyncQdrantClient doesn't strictly require closing in older versions, 
        # but it's good practice to close the underlying session if available.
        # In newer versions, it might have a .close() method.
        if hasattr(client, 'close'):
            await client.close()



""" from qdrant_client import QdrantClient
vectordb_client = QdrantClient(
    url=settings.VECTOR_DB_PATH,
    collection_name=settings.VECTOR_DB_COLLECTION_NAME,
) """

@data_router.get("/welcome_vectordb_db_check")
async def test_vector_db_db_check(request: Request):    
    db_engine = request.app.state.db_engine
    db_client_sessionmaker = request.app.state.db_session_factory
    return {
        "message ": "VectorDBProvider connection successful!",
        "db_engine": str(db_engine),
        "db_client_sessionmaker": str(db_client_sessionmaker),
        "settings.POSTGRES_DATABASE_URL": settings.POSTGRES_DATABASE_URL,
        }


# This endpoint tests the Celery integration by calling a simple task that sums two numbers.
# define a celery task in tasks folder and let celery knows it by including it in the celery_app.py file. remeber to start worker (celery -A src.celery_app.celery_app worker --loglevel=info) before calling this endpoint.
#a Celery task will NOT execute unless a worker is running.

@data_router.get("/welcome_celery")
def test_celery():
    result = test_sum.delay(4, 4)
    return {
        "message ": "Welcome to celery : you are connected with redis & RabbitMQ!",
        "test_task_id": result.id
        }


from src.tasks.test_taskiq import my_task
from taskiq.exceptions import SendTaskError 
import traceback

@data_router.get("/welcome_taskiq")
async def test_taskiq():
    try:
        await my_task.kiq()
        return JSONResponse(content={"message": "Task queued!"})
    except SendTaskError as e:
        # Print the full chain of exceptions
        print("SendTaskError caught!")
        print(f"Message: {e}")
        print(f"Cause: {e.__cause__}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "cause": str(e.__cause__)}
        )
from pydantic import BaseModel
from src.tasks.test_taskiq import my_task2
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from taskiq.exceptions import SendTaskError
import traceback


class WelcomeRequest(BaseModel):
    name: str

@data_router.post("/welcome_taskiq2")
async def test_taskiq2(request: WelcomeRequest):
    task = await my_task2.kiq(request.name)
    return {"task_id": task.task_id, "status": "queued"}

@data_router.get("/task-result/{task_id}")
async def get_task_result(task_id: str):
    """Check the result of a queued task."""
    from src.tk_broker import broker
    
    result = await broker.result_backend.get_result(task_id)
    
    if result is None:
        return {"status": "pending", "task_id": task_id}
    
    if result.is_err:
        return {
            "status": "error",
            "task_id": task_id,
            "error": str(result.error)
        }
    
    return {
        "status": "success",
        "task_id": task_id,
        "result": result.return_value,
        "execution_time": result.execution_time
    }



import datetime
from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from src.database import get_utils
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


@data_router.get("/welcome_postres")
def test_postgres():    
    (db_engine, db_client_sessionmaker) = get_utils()   
    return {
        "message ": "Postgres connection successful!",
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

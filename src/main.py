from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.helpers.config import get_settings
from src.routes import data, welcome, qdrant_test, llm_test


from src.utils.metrics import setup_metrics
from src.database import get_utils

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print("✅ Loaded settings:", settings.model_dump())
    (db_engine, db_client_sessionmaker) = get_utils()

    print("✅ Application started successfully")

    # Yield control to the application

    yield

    await db_engine.dispose()
    
    # Shutdown  
    print("👋 Shutting down...")
    print("❌ postgres connection closed")


app = FastAPI(lifespan=lifespan)

# Setup Prometheus metrics
setup_metrics(app)

# Include routes
app.include_router(data.data_router)
app.include_router(welcome.data_router)
app.include_router(qdrant_test.router)
app.include_router(llm_test.router)

from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.helpers.config import get_settings
from src.routes import data, welcome, qdrant_test, llm_test, nlp, stream


from src.utils.metrics import setup_metrics
from src.database import get_utils
import src.database as db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print("✅ all variable in settings using get_settings() with pydantic are loaded.")
    
    # 1. Initialize Global Database Engine and Session Factory
    db.db_engine = create_async_engine(settings.POSTGRES_DATABASE_URL, echo=False)
    db.db_session_factory = async_sessionmaker(
        bind=db.db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    
    # 2. Store in app.state as requested (Optional but good for access via Request)
    app.state.db_engine = db.db_engine
    app.state.db_session_factory = db.db_session_factory

    print("✅ Database Engine and Session Factory initialized in app.state.")
    print("✅ Application started successfully")

    # Yield control to the application
    yield

    # Shutdown  
    print("👋 Shutting down...")
    if db.db_engine:
        await db.db_engine.dispose()
        print("❌ postgres connection closed")


app = FastAPI(lifespan=lifespan)

# Setup Prometheus metrics
setup_metrics(app)

# Include routes
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(welcome.data_router)
app.include_router(qdrant_test.router)
app.include_router(llm_test.router)
app.include_router(stream.stream_router)

"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.helpers.config import get_settings
from src.helpers.quota import GlobalLLMQuota
from src.routes import data, welcome, qdrant_test, llm_test, nlp, stream


from src.utils.metrics import setup_metrics
from src.database import get_utils
import src.database as db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import taskiq_fastapi
from src.tk_broker import broker

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

    # 3. Initialize Global Quota Managers (Multi-Lane Highway)
    # Each lane uses the explicit Quota Redis URL (DB 0)
    
    # Lane 1: Embedding Quota
    app.state.embedding_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_EMBEDDING,
        key_prefix="quota:llm_embedding"
    )

    # Lane 2: Generation Quota
    app.state.generation_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_GENERATION,
        key_prefix="quota:llm_generation"
    )

    print("✅ Database Engine and Session Factory initialized in app.state.")
    print("✅ Global Quota Managers (Embedding & Generation) initialized in app.state.")
    print("✅ Application started successfully")

    # 🔥 START TASKIQ BROKER (add this line)
    await broker.startup()
    print("✅ Taskiq broker started")
    # Yield control to the application
    yield

    # Shutdown  
    print("👋 Shutting down...")

    await broker.shutdown()   # add this as well
    print("❌ Taskiq broker shut down")
    
    # Close Quota Manager Redis connections
    if hasattr(app.state, "embedding_quota"):
        await app.state.embedding_quota.close()
    if hasattr(app.state, "generation_quota"):
        await app.state.generation_quota.close()
    print("❌ Quota Managers Redis connections closed")

    if db.db_engine:
        await db.db_engine.dispose()
        print("❌ postgres connection closed")


app = FastAPI(lifespan=lifespan)

# Initialize Taskiq with FastAPI
taskiq_fastapi.init(broker, app)

# Setup Prometheus metrics
setup_metrics(app)

# Include routes
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(welcome.data_router)
app.include_router(qdrant_test.router)
app.include_router(llm_test.router)
app.include_router(stream.stream_router)
"""

# main.py
# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.helpers.config import get_settings
from src.helpers.quota import GlobalLLMQuota
from src.routes import data, welcome, qdrant_test, llm_test, nlp, stream, test_taskiq_router,task_result_router


from src.utils.metrics import setup_metrics
import src.database as db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import taskiq_fastapi
from src.tk_broker import broker

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print("✅ settings loaded.")
    
    # 1. Initialize Global Database Engine and Session Factory
    # We init it here so FastAPI endpoints can use it immediately.
    if db.db_engine is None:
        db.db_engine = create_async_engine(
            settings.POSTGRES_DATABASE_URL, 
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        db.db_session_factory = async_sessionmaker(
            bind=db.db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    
    app.state.db_engine = db.db_engine
    app.state.db_session_factory = db.db_session_factory

    # 2. Initialize Global Quota Managers
    app.state.embedding_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_EMBEDDING,
        key_prefix="quota:llm_embedding"
    )
    app.state.generation_quota = GlobalLLMQuota(
        redis_url=settings.REDIS_URL_QUOTA,
        max_rpm=settings.MAX_RPM_GENERATION,
        key_prefix="quota:llm_generation"
    )

    print("✅ Database Engine and Session Factory initialized.")
    print("✅ Global Quota Managers initialized.")

    # 3. START TASKIQ BROKER
    # This will start all middlewares (including Idempotency Redis connection).
    # Since db.db_engine is already set, AppAioPikaBroker will skip DB initialization.
    await broker.startup()
    print("✅ Taskiq broker started")
    
    yield

    # Shutdown  
    print("👋 Shutting down...")

    # This will shutdown middlewares (closing Idempotency Redis) AND dispose the DB engine.
    await broker.shutdown()
    print("❌ Taskiq broker shut down and resources disposed")
    
    # Close Quota Manager Redis connections
    if hasattr(app.state, "embedding_quota"):
        await app.state.embedding_quota.close()
    if hasattr(app.state, "generation_quota"):
        await app.state.generation_quota.close()
    print("❌ Quota Managers Redis connections closed")

app = FastAPI(lifespan=lifespan)

# Initialize Taskiq with FastAPI
taskiq_fastapi.init(broker, app)

# Setup Prometheus metrics
setup_metrics(app)

# Include routes
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(welcome.data_router)
app.include_router(qdrant_test.router)
app.include_router(llm_test.router)
app.include_router(stream.stream_router)
app.include_router(test_taskiq_router.test_taskiq_router)
app.include_router(task_result_router.task_result_router)
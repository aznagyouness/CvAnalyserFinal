# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.helpers.config import get_settings
from src.helpers.quota import GlobalLLMQuota
from src.routes import data, welcome, qdrant_test, llm_test, nlp, stream, test_taskiq_router,task_result_router


from src.utils.metrics import setup_metrics
from src.observability.logging import configure_logging
from src.observability.middleware import RequestContextMiddleware

import src.database as db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import taskiq_fastapi
from src.tk_broker import broker

# 1. Configure logging FIRST — before anything else logs
configure_logging()

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



# 2. Build app
app = FastAPI(lifespan=lifespan)

# Initialize Taskiq with FastAPI
taskiq_fastapi.init(broker, app)

# Setup Prometheus metrics
setup_metrics(app)


# 3. Add middleware (executed in REVERSE order of registration,
#    but `RequestContextMiddleware` should be the OUTERMOST, so add it LAST
#    OR use `add_middleware` correctly)
app.add_middleware(RequestContextMiddleware)

# Include routes
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(welcome.data_router)
app.include_router(qdrant_test.router)
app.include_router(llm_test.router)
app.include_router(stream.stream_router)
app.include_router(test_taskiq_router.test_taskiq_router)
app.include_router(task_result_router.task_result_router)
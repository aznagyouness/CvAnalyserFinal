from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.helpers.config import get_settings
from typing import AsyncGenerator

settings = get_settings()

# We define these as None initially and initialize them in the lifespan of main.py
db_engine = None
db_session_factory = None

async def get_utils():
    """
    DEPRECATED: Use Dependency Injection or app.state instead.
    Kept for backward compatibility but creates a new engine every time.
    """
    engine = create_async_engine(settings.POSTGRES_DATABASE_URL, echo=False)
    sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return (engine, sessionmaker)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency to provide a database session.
    Usage: db: AsyncSession = Depends(get_db)
    """
    if db_session_factory is None:
        raise Exception("Database session factory not initialized. Call init_db first.")
    
    async with db_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

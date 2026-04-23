from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.helpers.config import get_settings

settings = get_settings()

async def get_utils():
        
    db_engine = create_async_engine(settings.POSTGRES_DATABASE_URL, echo=False)
    db_client_sessionmaker = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    return (db_engine, db_client_sessionmaker)

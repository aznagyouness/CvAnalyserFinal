import logging
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.db_schemes.cv_analysis_db.db_tables import DataChunk

logger = logging.getLogger(__name__)

"""
You need chunk_order because when you split a document into multiple pieces (chunks), you lose the original sequence unless you store it. Without an order field:

You cannot reliably reconstruct the original text from its chunks. If you retrieve a set of chunks (e.g., via vector search), you have no way to sort them back into the order they appeared in the source document.

Providing context to an LLM becomes messy – the model may see relevant chunks in random order, reducing coherence.

Displaying source material to users (like showing the original document snippet) would be impossible without knowing which chunk came first.

Pagination or listing chunks for a given asset would default to an unpredictable order (e.g., by insertion time), which is rarely what you want.
"""

class DataChunkCrud:
    def __init__(self, db_client: async_sessionmaker):
        self.session_factory = db_client

    async def create_chunk(
        self,
        project_id: int,
        asset_id: int,
        text: str,
        order: int,
        metadata: Optional[dict] = None,
    ) -> DataChunk:
        """
        Creates a new data chunk.
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    new_chunk = DataChunk(
                        chunk_uuid=uuid.uuid4(),
                        chunk_project_id=project_id,
                        chunk_asset_id=asset_id,
                        chunk_text=text,
                        chunk_order=order,
                        chunk_metadata=metadata,
                    )
                    session.add(new_chunk)
                
                await session.refresh(new_chunk)
                logger.info(f"Created chunk {new_chunk.chunk_id} for asset {asset_id}")
                return new_chunk
        except SQLAlchemyError as e:
            logger.error(f"Error creating chunk for asset {asset_id}: {e}")
            raise

    async def create_chunks_batch(
        self,
        project_id: int,
        asset_id: int,
        chunks_data: List[dict]
    ) -> List[DataChunk]:
        """
        Creates multiple data chunks in a single transaction.
        chunks_data: List of dicts with {"text": str, "order": int, "metadata": dict}
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    new_chunks = [
                        DataChunk(
                            chunk_uuid=uuid.uuid4(),
                            chunk_project_id=project_id,
                            chunk_asset_id=asset_id,
                            chunk_text=chunk["text"],
                            chunk_order=chunk["order"],
                            chunk_metadata=chunk["metadata"],
                        )
                        for chunk in chunks_data
                    ]
                    session.add_all(new_chunks)
                
                logger.info(f"Created {len(new_chunks)} chunks for asset {asset_id}")
                return new_chunks
        except SQLAlchemyError as e:
            logger.error(f"Error creating batch chunks for asset {asset_id}: {e}")
            raise

    async def get_chunks_by_asset(self, asset_id: int) -> List[DataChunk]:
        """
        Retrieves all chunks for a specific asset, ordered by chunk_order.
        """
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(DataChunk)
                    .where(DataChunk.chunk_asset_id == asset_id)
                    .order_by(DataChunk.chunk_order)
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chunks for asset {asset_id}: {e}")
            raise

    async def get_chunks_by_project(self, project_id: int) -> List[DataChunk]:
        """
        Retrieves all chunks for a specific project.
        """
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(DataChunk).where(DataChunk.chunk_project_id == project_id)
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chunks for project {project_id}: {e}")
            raise

    async def delete_chunks_by_project(self, project_id: int) -> int:
        """
        Deletes all chunks associated with a project.
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(DataChunk).where(DataChunk.chunk_project_id == project_id)
                    )
                    chunks = result.scalars().all()
                    count = 0
                    for chunk in chunks:
                        await session.delete(chunk)
                        count += 1
                    logger.info(f"Deleted {count} chunks for project {project_id}")
                    return count
        except SQLAlchemyError as e:
            logger.error(f"Error deleting chunks for project {project_id}: {e}")
            raise

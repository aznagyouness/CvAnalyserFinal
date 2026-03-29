import logging
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.models.db_schemes.cv_analysis_db.db_tables import Asset

logger = logging.getLogger(__name__)


class AssetCrud:
    def __init__(self, db_client: async_sessionmaker[AsyncSession]):
        self.session_factory = db_client

    async def create_asset(
        self,
        project_id: int,
        asset_type: str,
        asset_name: str,
        asset_size: int,
        asset_config: Optional[dict] = None,
    ) -> Asset:
        """
        Creates a new asset for a project.
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    new_asset = Asset(
                        asset_uuid=uuid.uuid4(),
                        asset_project_id=project_id,
                        asset_type=asset_type,
                        asset_name=asset_name,
                        asset_size=asset_size,
                        asset_config=asset_config,
                    )
                    session.add(new_asset)
                
                await session.refresh(new_asset)
                logger.info(f"Created asset {new_asset.asset_id} for project {project_id}")
                return new_asset
        except SQLAlchemyError as e:
            logger.error(f"Error creating asset for project {project_id}: {e}")
            raise


    """
    - Enhanced Security (Scoping) : Even though asset_id is a unique primary key, adding project_id ensures that a user cannot access an asset belonging to Project A by simply guessing its ID while they are authorized for Project B. It acts as an essential security layer for multi-project isolation.
    - Data Integrity : It guarantees that the asset you are retrieving actually belongs to the project context you are currently working in, preventing accidental cross-project data leaks or modifications.
    """
    async def get_asset_by_name(self, asset_name: str, project_id: int) -> Optional[Asset]:
        """
        Retrieves an asset by its name and project ID.
        """
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Asset).where(
                        Asset.asset_name == asset_name,
                        Asset.asset_project_id == project_id
                    )
                )
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving asset {asset_name}: {e}")
            raise

    async def get_assets_by_project(self, project_id: int) -> List[Asset]:
        """
        Retrieves all assets for a project.
        """
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Asset).where(Asset.asset_project_id == project_id)
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving assets for project {project_id}: {e}")
            raise

    async def delete_asset(self, asset_id: int) -> bool:
        """
        Deletes an asset.
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    asset = await session.get(Asset, asset_id)
                    if asset:
                        await session.delete(asset)
                        logger.info(f"Deleted asset {asset_id}")
                        return True
                    return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting asset {asset_id}: {e}")
            raise

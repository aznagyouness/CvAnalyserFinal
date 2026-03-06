import logging
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from src.models.db_schemes.cv_analysis_db.db_tables import Project

# Configure a module-level logger
logger = logging.getLogger(__name__)

class ProjectCrud:
    """
    Production-ready CRUD model for Projects.
    Includes:
    - Safe transaction management
    - Cursor-based pagination
    - Race-condition handling
    - Logging and Error Handling
    """

    def __init__(self, db_client: async_sessionmaker[AsyncSession]):
        self.session_factory = db_client




    async def get_project_or_create_one(self, project_id: int) -> Project:
        """
        Gets a project or creates it atomically using ON CONFLICT (Upsert-like) logic.
        """
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    # 1. Try to fetch first (Optimization for common case)
                    query = select(Project).where(Project.project_id == project_id)
                    result = await session.execute(query)
                    existing_project = result.scalar_one_or_none()

                    if existing_project:
                        return existing_project

                    # 2. Insert safely with ON CONFLICT DO NOTHING
                    logger.debug(f"Project {project_id} not found, attempting safe insert.")
                    stmt = insert(Project).values(project_id=project_id).on_conflict_do_nothing()
                    await session.execute(stmt)
                
                # 3. Fetch final result (guaranteed to exist now)
                # We use a fresh query in a new transaction context implicitly
                query = select(Project).where(Project.project_id == project_id)
                result = await session.execute(query)
                final_project = result.scalar_one()
                
                logger.info(f"Retrieved/Created project: {project_id}")
                return final_project

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_project_or_create_one for {project_id}: {e}")
            raise

    async def get_all_projects(
        self, 
        limit: int = 10, 
        cursor_id: Optional[int] = None
    ) -> Tuple[List[Project], Optional[int]]:
        """
        Production-ready Cursor Pagination.
        """
        # Safety: Enforce maximum limit to prevent huge queries
        safe_limit = min(limit, 100)
        
        try:
            async with self.session_factory() as session:
                query = select(Project).limit(safe_limit).order_by(Project.project_id.asc())

                if cursor_id is not None:
                    query = query.where(Project.project_id > cursor_id)

                result = await session.execute(query)
                projects = result.scalars().all()

                next_cursor = projects[-1].project_id if projects else None
                return projects, next_cursor
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch projects: {e}")
            raise

from src.celery_app import celery_app


from src.models.crud.ProjectCrud import ProjectCrud
from src.models.crud.AssetCrud import AssetCrud

from src.models.db_schemes.cv_analysis_db.db_tables import Project, Asset
from src.database import get_utils

from sqlalchemy.exc import SQLAlchemyError
import asyncio
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task(
                 bind=True, name="src.tasks.creating_tables.fct_table_creation",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60}
                ) 
def fct_table_creation(self, project_id,):
    return asyncio.run(_fct_table_creation(self, project_id))

# don't use celery's async support, it's broken
# use asyncio inside a normal celery task instead
# don't use await inside a celery task directly


async def _fct_table_creation(instance, project_id, ):

    start = time.time()
    # Your task logic here
    # simultanous tasks example
    
    (db_engine, db_client_sessionmaker) = await get_utils()

    user_crud = UserCrud(db_client_sessionmaker)
    project_crud = ProjectCrud(db_client_sessionmaker)
    asset_crud = AssetCrud(db_client_sessionmaker)
    try: 
        await asyncio.sleep(20)  # Simulate a long-running task
        # user = await user_crud.create_user(User(username="testuser", email="testuser@example.com"))
        project = await project_crud.get_project_or_create_one(project_id)
        # asset = await asset_crud.create_asset(Asset(name="test_asset", project_id=project.project_id))
        
        return {
            "message": f"Created tables for project {project_id}",
            "duration": time.time() - start,
            "task_id": instance.request.id,
            "project_id": project.project_id, 
        }
    
    except SQLAlchemyError as e:
        logger.error(f"Database Operation Failed: {e}")
        return {
            "message": f"Failed to create tables: {str(e)}",
            "duration": time.time() - start,
            "task_id": instance.request.id,
        }
    
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {
            "message": f"An unexpected error occurred: {str(e)}",
            "duration": time.time() - start,
            "task_id": instance.request.id,
        }
    



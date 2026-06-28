from src.tk_broker import broker
from src.models.crud.AssetCrud import AssetCrud
from src.database import get_utils
from taskiq import TaskiqDepends
import logging

logger = logging.getLogger(__name__)

@broker.task(task_name="maintenance.cleanup_old_assets")
async def cleanup_old_assets_task(
    days_old: int = 30,
    db_utils = TaskiqDepends(get_utils)
):
    """
    Periodic cleanup of old assets and their temporary files.
    """
    _, sessionmaker = db_utils
    asset_crud = AssetCrud(db_client=sessionmaker)
    
    # Assuming delete_old_assets is implemented in AssetCrud
    try:
        deleted_count = await asset_crud.delete_old_assets(days=days_old)
        logger.info(f"Cleanup complete: {deleted_count} assets removed.")
        return {"status": "success", "deleted": deleted_count}
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"status": "error", "message": str(e)}

@broker.task(task_name="maintenance.optimize_qdrant")
async def optimize_qdrant_task(
    project_id: int,
):
    """
    Trigger Qdrant collection optimization (compaction/indexing).
    Useful after large batch imports.
    """
    # Placeholder for actual optimization logic
    # In Qdrant, this usually happens automatically, but can be triggered via API
    return f"Optimization triggered for project {project_id}"

# src/tasks/maintenance.py
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Annotated

from sqlalchemy import delete
from taskiq import Context, TaskiqDepends

from src.tk_broker import broker
import src.database as db
from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution

logger = logging.getLogger(__name__)


@broker.task(
    task_name="src.tasks.maintenance:archive_old_task_executions",
    timeout=300.0,  # 5 minutes max
    labels={"queue": "maintenance"},
)
async def archive_old_task_executions(
    older_than_days: int = 90,
    context: Annotated[Context, TaskiqDepends()] = None,
):
    """
    Deletes task execution audit records older than N days.
    Should be scheduled via cron (e.g., daily at 2 AM) to prevent 
    the audit table from growing infinitely.
    """
    # 1. Check idempotency skip flag
    if context and context.message.labels.get("should_skip") == "true":
        return {"status": "skipped_by_idempotency"}

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    logger.info(f"Archiving taskiq_task_executions older than {cutoff_date}")

    # 2. Ensure DB is initialized (Worker context)
    if db.db_session_factory is None:
        logger.error("Database session factory is not initialized!")
        return {"status": "error", "message": "DB not initialized"}

    # 3. Execute the deletion using a short-lived session
    try:
        async with db.db_session_factory() as session:
            stmt = delete(TaskiqTaskExecution).where(
                TaskiqTaskExecution.completed_at < cutoff_date
            )
            result = await session.execute(stmt)
            await session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Successfully archived {deleted_count} old task execution records.")
            return {"status": "success", "deleted_count": deleted_count}
            
    except Exception as e:
        logger.exception("Failed to archive old task executions")
        return {"status": "error", "message": str(e)}
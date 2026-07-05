# src/services/task_result_service.py
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.models.db_schemes.cv_analysis_db.db_tables import TaskiqTaskExecution
from src.tk_broker import broker

logger = logging.getLogger(__name__)


class TaskResultService:
    """
    Production-grade result retrieval with Redis fast path + PG fallback.
    
    Uses SHORT-LIVED sessions: sessions are opened only during actual
    DB operations (milliseconds), not for the entire request.
    """
    
    def __init__(self, db_client: async_sessionmaker[AsyncSession]):
        self.session_factory = db_client
    
    async def get_result_by_task_id(self, task_id: str) -> Dict[str, Any]:
        """
        Get result by task_id using HYBRID strategy:
        1. Try Redis first (fast, for tasks completed < 1 hour ago)
        2. Fall back to PostgreSQL (permanent, for older tasks)
        
        Session is only opened for the PostgreSQL fallback (~2ms).
        """
        # ─── FAST PATH: Redis (no session needed!) ─────────────────────────
        try:
            redis_result = await broker.result_backend.get_result(task_id)
        except Exception as e:
            logger.warning("Redis result backend error, falling back to PG: %s", e)
            redis_result = None
        
        if redis_result is not None:
            return {
                "task_id": task_id,
                "status": "SUCCESS" if not redis_result.is_err else "FAILED",
                "result": redis_result.return_value if not redis_result.is_err else None,
                "error": str(redis_result.error) if redis_result.is_err else None,
                "source": "redis",
            }
        
        # ─── FALLBACK: PostgreSQL (session opened HERE, for ~2ms only) ────
        try:
            async with self.session_factory() as session:
                stmt = select(TaskiqTaskExecution).where(
                    TaskiqTaskExecution.taskiq_task_id == task_id
                )
                result = await session.execute(stmt)
                record = result.scalar_one_or_none()
            
            # Session is CLOSED here — outside the `async with` block
            
            if record is None:
                return {"task_id": task_id, "status": "PENDING"}
            
            return {
                "task_id": record.taskiq_task_id,
                "task_name": record.task_name,
                "status": record.status,
                "result": record.result if record.status == "SUCCESS" else None,
                "error": record.error if record.status == "FAILED" else None,
                "enqueued_at": record.enqueued_at.isoformat() if record.enqueued_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "source": "postgres",
            }
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed for task_id %s: %s", task_id, e)
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": "Database query failed",
                "source": "postgres",
            }
    
    async def get_result_by_input(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get result by EXACT input (guaranteed linkage).
        ALWAYS uses PostgreSQL — Redis doesn't store task_name/args.
        
        Session opened for ~2ms only.
        """
        # Generate the same hash the middleware uses
        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        task_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(TaskiqTaskExecution)
                    .where(
                        and_(
                            TaskiqTaskExecution.task_args_hash == task_hash,
                            TaskiqTaskExecution.status == "SUCCESS",
                        )
                    )
                    .order_by(TaskiqTaskExecution.completed_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                record = result.scalar_one_or_none()
            
            # Session is CLOSED here
            
            if record is None:
                return None
            
            return {
                "task_id": record.taskiq_task_id,
                "task_name": record.task_name,
                "task_hash": record.task_args_hash,
                "input": {
                    "args": record.task_args.get("args", []),
                    "kwargs": record.task_args.get("kwargs", {}),
                },
                "status": record.status,
                "result": record.result,
                "enqueued_at": record.enqueued_at.isoformat() if record.enqueued_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "linkage_verified": True,
            }
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed for input hash %s: %s", task_hash[:12], e)
            return None
    
    async def get_all_executions_by_input(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
    ) -> list[Dict[str, Any]]:
        """Get ALL executions of the same task signature (for debugging).
        [
           {"task_id": "...", "status": "SUCCESS", "result": "...", ...},
           {"task_id": "...", "status": "FAILED", "error": "...", ...},
           {"task_id": "...", "status": "SUCCESS", "result": "...", ...}
        ]
        if no executions found, return [] if 1 success you get 1 success
        if 1 failed you get 1 failed
        """
        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        task_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(TaskiqTaskExecution)
                    .where(TaskiqTaskExecution.task_args_hash == task_hash)
                    .order_by(TaskiqTaskExecution.enqueued_at.desc())
                )
                result = await session.execute(stmt)
                records = result.scalars().all()
            
            # Session closed here
            
            return [
                {
                    "task_id": r.taskiq_task_id,
                    "task_name": r.task_name,
                    "status": r.status,
                    "result": r.result if r.status == "SUCCESS" else None,
                    "error": r.error if r.status == "FAILED" else None,
                    "enqueued_at": r.enqueued_at.isoformat() if r.enqueued_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in records
            ]
        except SQLAlchemyError as e:
            logger.error("PostgreSQL query failed: %s", e)
            return []
from __future__ import annotations
from src.models.db_schemes.cv_analysis_db.base import BaseTable

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


#------- Full Relationships : -------------------------------------------------------------------
"""
Full Relationships :
- Project ↔ Asset (One-to-Many)
- Project ↔ DataChunk (One-to-Many)
- Asset ↔ DataChunk (One-to-Many)

"""
#-------- idempotency table --------------------------------------------------------------------
# src/models/db_schemes/minirag/schemes/taskiq_task_execution.py


from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB



class TaskiqTaskExecution(BaseTable):
    __tablename__ = "taskiq_task_executions"

    # Modern SQLAlchemy 2.0 syntax using Mapped and mapped_column
    execution_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    taskiq_task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # For JSON columns, we use dict/Any for type hinting
    task_args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    # ✅ FIX: Changed from dict[str, Any] to Any
    # Tasks can return dicts, lists, strings, numbers, etc.
    result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tte_hash_status", "task_args_hash", "status"),
        Index("ix_tte_name_enqueued", "task_name", "enqueued_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaskiqTaskExecution id={self.execution_id} "
            f"task={self.task_name} status={self.status}>"
        )

#---------------- project table -----------------------------------------------------------------

class Project(BaseTable):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    assets_r: Mapped[List["Asset"]] = relationship(back_populates="project_r")
    chunks_r: Mapped[List["DataChunk"]] = relationship(back_populates="project_r")

    def __repr__(self):
        return f"<Project(project_id={self.project_id}, project_uuid={self.project_uuid}, created_at={self.created_at}, updated_at={self.updated_at})>"

"""
Control over name

- index=True :
  - SQLAlchemy lets the database choose the index name (or auto‑generates one).
  - You don’t control the exact index name.
- Index("project_id_index_1", "project_id", unique=True) :
  - You explicitly set the name project_id_index_1 .
  - This matches your original MongoDB name and is easier to recognize in DB tools and logs.
"""

# ---------------- asset table -----------------------------------------------------------------


class Asset(BaseTable):
    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )

    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    asset_size: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    asset_project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    project_r: Mapped["Project"] = relationship(back_populates="assets_r")
    chunks_r: Mapped[List["DataChunk"]] = relationship(back_populates="asset_r")

    __table_args__ = (
        Index("ix_asset_project_id", "asset_project_id"),
        Index("ix_asset_type", "asset_type"),
    )

    def __repr__(self):
        return f"<Asset(asset_id={self.asset_id}, asset_uuid={self.asset_uuid}, asset_type={self.asset_type}, asset_name={self.asset_name}, asset_size={self.asset_size}, created_at={self.created_at}, updated_at={self.updated_at}, asset_project_id={self.asset_project_id})>"


#---------------- data chunk table -----------------------------------------------------------------

class DataChunk(BaseTable):
    __tablename__ = "chunks"

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )

    chunk_text: Mapped[str] = mapped_column(String, nullable=False)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk_project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False
    )
    chunk_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.asset_id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    project_r: Mapped["Project"] = relationship(back_populates="chunks_r")
    asset_r: Mapped["Asset"] = relationship(back_populates="chunks_r")

    __table_args__ = (
        Index("ix_chunk_project_id", "chunk_project_id"),
        Index("ix_chunk_asset_id", "chunk_asset_id"),
    )

    def __repr__(self):
        return f"<DataChunk(chunk_id={self.chunk_id}, chunk_uuid={self.chunk_uuid}, chunk_text={self.chunk_text}, chunk_order={self.chunk_order}, created_at={self.created_at}, updated_at={self.updated_at}, chunk_project_id={self.chunk_project_id}, chunk_asset_id={self.chunk_asset_id})>"


class RetrievedDocument(BaseModel):
    text: str
    score: float

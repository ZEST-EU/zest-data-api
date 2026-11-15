"""Response schemas for MinIO-backed datasets."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size_bytes: int
    etag: str | None = None
    created_at: datetime | None = None


class DatasetOut(BaseModel):
    """One row in the dataset catalogue (GET /datasets)."""

    dataset_id: str
    name: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    file_count: int = 0
    total_size: int = 0


class DatasetDetail(DatasetOut):
    """Full dataset view (GET /datasets/{dataset_id})."""

    files: list[DatasetFileOut] = []

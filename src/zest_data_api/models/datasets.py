"""Dataset metadata (the bytes live in object storage, keyed by ``object_key``).

A dataset is a named bundle of one or more uploaded files. Postgres holds the
metadata for listing/browsing; MinIO holds the file contents under
``<dataset_id>/<filename>``.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .base import PKMixin, TimestampMixin


class Dataset(PKMixin, TimestampMixin, Base):
    __tablename__ = "dataset"

    dataset_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    files: Mapped[list[DatasetFile]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )


class DatasetFile(PKMixin, TimestampMixin, Base):
    __tablename__ = "dataset_file"

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("dataset.dataset_id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    object_key: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(String(128))

    dataset: Mapped[Dataset] = relationship(back_populates="files")

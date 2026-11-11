"""Shared ORM building blocks: PK/timestamp mixins and an enum-column helper."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ..db import BigIntPK


class PKMixin:
    """Surrogate ``BIGINT`` primary key (``INTEGER`` on SQLite)."""

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)


class TimestampMixin:
    """Server-managed ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def enum_column(enum_cls: type[Enum], **kwargs):
    """A VARCHAR column constrained to an enum's *values* (portable, no native DB enum)."""
    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=32,
            values_callable=lambda e: [member.value for member in e],
        ),
        **kwargs,
    )

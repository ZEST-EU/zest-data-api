"""Pagination envelope and helpers to derive Pydantic models from ORM tables.

The 12 reference/core/result entities share the same CRUD shape, so rather than
hand-writing ~36 schema classes we build read/create/update models by reflecting
each SQLAlchemy table's columns. Dataset/measurement responses are hand-written
(see schemas/datasets.py) because they are the user-facing surface.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, create_model

T = TypeVar("T")

_AUTO_COLUMNS = {"id", "created_at", "updated_at"}


class Page(BaseModel, Generic[T]):
    """A paginated list response."""

    items: list[T]
    total: int
    limit: int
    offset: int


def _python_type(column) -> Any:
    try:
        return column.type.python_type
    except (NotImplementedError, AttributeError):
        return Any


def build_read_model(model, name: str, exclude: tuple[str, ...] = ()):
    """All columns (incl. id/timestamps) as an optional, ORM-friendly read model."""
    fields: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.name in exclude:
            continue
        fields[col.name] = (_python_type(col) | None, None)
    return create_model(name, __config__=ConfigDict(from_attributes=True), **fields)


def _is_required(col) -> bool:
    """A column must be supplied on create iff it is NOT NULL with no default."""
    return (
        not col.nullable
        and not col.primary_key
        and col.default is None
        and col.server_default is None
    )


def build_create_model(model, name: str, exclude: tuple[str, ...] = ()):
    """Writable columns; NOT-NULL-without-default columns are required."""
    fields: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.name in _AUTO_COLUMNS or col.name in exclude:
            continue
        py = _python_type(col)
        if _is_required(col):
            fields[col.name] = (py, ...)
        else:
            fields[col.name] = (py | None, None)
    return create_model(name, __config__=ConfigDict(extra="forbid"), **fields)


def build_update_model(
    model, name: str, key_field: str, exclude: tuple[str, ...] = ()
):
    """Every writable non-key column, all optional (partial update / PATCH-like)."""
    fields: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.name in _AUTO_COLUMNS or col.name == key_field or col.name in exclude:
            continue
        fields[col.name] = (_python_type(col) | None, None)
    return create_model(name, __config__=ConfigDict(extra="forbid"), **fields)

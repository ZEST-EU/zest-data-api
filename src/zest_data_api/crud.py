"""Generic CRUD operations keyed by a natural business key (e.g. ``run_id``)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .errors import ConflictError, NotFoundError


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Database integrity error (duplicate key or missing foreign-key target).",
            detail=str(getattr(exc, "orig", exc)),
        ) from exc


def list_rows(
    db: Session,
    model,
    *,
    limit: int,
    offset: int,
    filters: dict[str, Any] | None = None,
) -> tuple[list[Any], int]:
    stmt = select(model)
    for field, value in (filters or {}).items():
        if value is not None:
            stmt = stmt.where(getattr(model, field) == value)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(model.id).limit(limit).offset(offset)).all()
    return list(rows), total


def get_row(db: Session, model, key_field: str, key_value: Any):
    row = db.scalar(select(model).where(getattr(model, key_field) == key_value))
    if row is None:
        raise NotFoundError(f"{model.__tablename__} '{key_value}' not found.")
    return row


def create_row(db: Session, model, data: dict[str, Any], key_field: str | None = None):
    # Friendly duplicate check only when the client supplies a natural key.
    if key_field and key_field != "id" and data.get(key_field) is not None:
        key_value = data[key_field]
        existing = db.scalar(select(model).where(getattr(model, key_field) == key_value))
        if existing is not None:
            raise ConflictError(f"{model.__tablename__} '{key_value}' already exists.")
    obj = model(**data)
    db.add(obj)
    _commit(db)
    db.refresh(obj)
    return obj


def update_row(db: Session, model, key_field: str, key_value: Any, data: dict[str, Any]):
    obj = get_row(db, model, key_field, key_value)
    for field, value in data.items():
        setattr(obj, field, value)
    _commit(db)
    db.refresh(obj)
    return obj


def delete_row(db: Session, model, key_field: str, key_value: Any) -> None:
    obj = get_row(db, model, key_field, key_value)
    db.delete(obj)
    _commit(db)

"""Dataset endpoints: generic multi-file upload/list/detail/download/delete.

A dataset is a named bundle of one or more arbitrary files. File bytes live in
object storage (MinIO) under the key ``<dataset_id>/<filename>``; Postgres holds
the metadata. Endpoints are sync so the blocking MinIO SDK runs in the threadpool.
"""

from __future__ import annotations

import io
import os
import secrets
import zipfile

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..models import Dataset, DatasetFile
from ..schemas.common import Page
from ..schemas.datasets import DatasetDetail, DatasetFileOut, DatasetOut
from ..storage import get_store

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _new_dataset_id() -> str:
    return "ds_" + secrets.token_hex(5)


def _get_dataset(db: Session, dataset_id: str) -> Dataset:
    ds = db.scalar(select(Dataset).where(Dataset.dataset_id == dataset_id))
    if ds is None:
        raise NotFoundError(f"Dataset '{dataset_id}' not found.")
    return ds


def _detail(ds: Dataset) -> DatasetDetail:
    files = sorted(ds.files, key=lambda f: f.filename)
    return DatasetDetail(
        dataset_id=ds.dataset_id,
        name=ds.name,
        description=ds.description,
        created_at=ds.created_at,
        file_count=len(files),
        total_size=sum(f.size_bytes for f in files),
        files=[DatasetFileOut.model_validate(f) for f in files],
    )


@router.post("", response_model=DatasetDetail, status_code=201, summary="Upload a dataset")
def upload_dataset(
    files: list[UploadFile] = File(..., description="One or more files to store as a dataset"),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DatasetDetail:
    """Store the uploaded files in object storage as a single named dataset."""
    if not files:
        raise ValidationError("At least one file is required.")

    settings = get_settings()
    store = get_store()
    dataset_id = _new_dataset_id()

    ds = Dataset(
        dataset_id=dataset_id,
        name=name or (os.path.basename(files[0].filename or "") or dataset_id),
        description=description,
    )
    db.add(ds)
    db.flush()

    seen: set[str] = set()
    for upload in files:
        filename = os.path.basename(upload.filename or "") or "file"
        if filename in seen:
            raise ValidationError(f"Duplicate filename in upload: '{filename}'.")
        seen.add(filename)

        data = upload.file.read()
        if len(data) > settings.max_upload_bytes:
            raise ValidationError(
                f"File '{filename}' exceeds the {settings.max_upload_bytes}-byte upload limit."
            )
        key = f"{dataset_id}/{filename}"
        stored = store.put(key, data, upload.content_type or "application/octet-stream")
        db.add(
            DatasetFile(
                dataset_id=dataset_id,
                filename=filename,
                object_key=key,
                content_type=upload.content_type or "application/octet-stream",
                size_bytes=stored.size,
                etag=stored.etag,
            )
        )

    db.commit()
    db.refresh(ds)
    return _detail(ds)


@router.get("", response_model=Page[DatasetOut], summary="List datasets")
def list_datasets(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Page[DatasetOut]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    total = db.scalar(select(func.count()).select_from(Dataset)) or 0
    datasets = db.scalars(
        select(Dataset).order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
    ).all()

    ids = [d.dataset_id for d in datasets]
    agg = {
        row[0]: (row[1], int(row[2] or 0))
        for row in db.execute(
            select(
                DatasetFile.dataset_id,
                func.count(),
                func.coalesce(func.sum(DatasetFile.size_bytes), 0),
            )
            .where(DatasetFile.dataset_id.in_(ids))
            .group_by(DatasetFile.dataset_id)
        ).all()
    }
    items = [
        DatasetOut(
            dataset_id=d.dataset_id,
            name=d.name,
            description=d.description,
            created_at=d.created_at,
            file_count=agg.get(d.dataset_id, (0, 0))[0],
            total_size=agg.get(d.dataset_id, (0, 0))[1],
        )
        for d in datasets
    ]
    return Page[DatasetOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{dataset_id}", response_model=DatasetDetail, summary="Dataset detail")
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetDetail:
    return _detail(_get_dataset(db, dataset_id))


@router.get("/{dataset_id}/download", summary="Download all files (zip)")
def download_dataset(dataset_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    ds = _get_dataset(db, dataset_id)
    if not ds.files:
        raise NotFoundError(f"Dataset '{dataset_id}' has no files.")
    store = get_store()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ds.files:
            zf.writestr(f.filename, store.get(f.object_key))
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{dataset_id}.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


@router.get("/{dataset_id}/files/{file_id}", summary="Download one file")
def download_file(dataset_id: str, file_id: int, db: Session = Depends(get_db)) -> Response:
    f = db.scalar(
        select(DatasetFile).where(
            DatasetFile.id == file_id, DatasetFile.dataset_id == dataset_id
        )
    )
    if f is None:
        raise NotFoundError(f"File {file_id} not found in dataset '{dataset_id}'.")
    try:
        content = get_store().get(f.object_key)
    except FileNotFoundError as exc:
        raise NotFoundError(f"Object for file {file_id} is missing from storage.") from exc
    headers = {"Content-Disposition": f'attachment; filename="{f.filename}"'}
    return Response(content=content, media_type=f.content_type, headers=headers)


@router.delete("/{dataset_id}", summary="Delete a dataset and its objects")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    ds = _get_dataset(db, dataset_id)
    get_store().delete_prefix(f"{dataset_id}/")
    db.delete(ds)  # cascade removes dataset_file rows
    db.commit()
    return {"deleted": dataset_id}

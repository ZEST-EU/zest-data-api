"""Dataset endpoints: ingest, browse, detail, and download.

A "dataset" here is a fermentation run plus its attached raw files. This is the
surface the dashboard will consume to browse and download experimental data.
"""

from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..ingest import ingest_dataset
from ..models import FermentationProcessRun, ProcessMeasurementRecord, RawFile, SyntheticRunSpec
from ..schemas.common import Page
from ..schemas.datasets import (
    DatasetDetail,
    DatasetSummary,
    IngestResult,
    PropertySummary,
    RawFileInfo,
    SyntheticSpecOut,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


async def _read_upload(upload: UploadFile | None) -> bytes | None:
    if upload is None:
        return None
    data = await upload.read()
    limit = get_settings().max_upload_bytes
    if len(data) > limit:
        raise ValidationError(f"File '{upload.filename}' exceeds the {limit}-byte upload limit.")
    return data or None


@router.post("", response_model=IngestResult, status_code=201, summary="Upload a dataset")
async def upload_dataset(
    log: UploadFile | None = File(default=None, description="<run>_log.csv (dense time series)"),
    labels: UploadFile | None = File(default=None, description="<run>_labels.csv (optional)"),
    truth: UploadFile | None = File(default=None, description="<run>_truth.json (optional)"),
    replace: bool = Query(False, description="Overwrite an existing run with the same run_id."),
    db: Session = Depends(get_db),
) -> IngestResult:
    """Ingest a SIM-01-format dataset (log + optional labels + optional truth)."""
    return ingest_dataset(
        db,
        log_bytes=await _read_upload(log),
        log_filename=(log.filename if log else "log.csv"),
        labels_bytes=await _read_upload(labels),
        labels_filename=(labels.filename if labels else "labels.csv"),
        truth_bytes=await _read_upload(truth),
        truth_filename=(truth.filename if truth else "truth.json"),
        replace=replace,
    )


def _summary_from_run(run: FermentationProcessRun, n_meas: int, n_files: int, has_spec: bool):
    return DatasetSummary(
        run_id=run.run_id,
        run_name=run.run_name,
        is_synthetic=run.is_synthetic,
        process_mode=run.process_mode,
        run_scale=run.run_scale,
        process_status=run.process_status,
        duration=run.duration,
        duration_unit=run.duration_unit,
        working_volume=run.working_volume,
        working_volume_unit=run.working_volume_unit,
        created_at=run.created_at,
        n_measurements=n_meas,
        n_files=n_files,
        has_spec=has_spec,
    )


@router.get("", response_model=Page[DatasetSummary], summary="List datasets")
def list_datasets(
    is_synthetic: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[DatasetSummary]:
    stmt = select(FermentationProcessRun)
    if is_synthetic is not None:
        stmt = stmt.where(FermentationProcessRun.is_synthetic == is_synthetic)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    runs = db.scalars(
        stmt.order_by(FermentationProcessRun.created_at.desc()).limit(limit).offset(offset)
    ).all()

    run_ids = [r.run_id for r in runs]
    meas_counts = dict(
        db.execute(
            select(ProcessMeasurementRecord.run_id, func.count())
            .where(ProcessMeasurementRecord.run_id.in_(run_ids))
            .group_by(ProcessMeasurementRecord.run_id)
        ).all()
    )
    file_counts = dict(
        db.execute(
            select(RawFile.run_id, func.count())
            .where(RawFile.run_id.in_(run_ids))
            .group_by(RawFile.run_id)
        ).all()
    )
    specs = set(
        db.scalars(
            select(SyntheticRunSpec.run_id).where(SyntheticRunSpec.run_id.in_(run_ids))
        ).all()
    )

    items = [
        _summary_from_run(
            r, meas_counts.get(r.run_id, 0), file_counts.get(r.run_id, 0), r.run_id in specs
        )
        for r in runs
    ]
    return Page[DatasetSummary](items=items, total=total, limit=limit, offset=offset)


def _get_run(db: Session, run_id: str) -> FermentationProcessRun:
    run = db.scalar(
        select(FermentationProcessRun).where(FermentationProcessRun.run_id == run_id)
    )
    if run is None:
        raise NotFoundError(f"Dataset '{run_id}' not found.")
    return run


@router.get("/{run_id}", response_model=DatasetDetail, summary="Dataset detail")
def get_dataset(run_id: str, db: Session = Depends(get_db)) -> DatasetDetail:
    run = _get_run(db, run_id)

    prop_rows = db.execute(
        select(
            ProcessMeasurementRecord.measured_property,
            ProcessMeasurementRecord.property_category,
            ProcessMeasurementRecord.unit,
            ProcessMeasurementRecord.is_ground_truth,
            func.count(),
            func.min(ProcessMeasurementRecord.time_h),
            func.max(ProcessMeasurementRecord.time_h),
        )
        .where(ProcessMeasurementRecord.run_id == run_id)
        .group_by(
            ProcessMeasurementRecord.measured_property,
            ProcessMeasurementRecord.property_category,
            ProcessMeasurementRecord.unit,
            ProcessMeasurementRecord.is_ground_truth,
        )
        .order_by(ProcessMeasurementRecord.measured_property)
    ).all()
    properties = [
        PropertySummary(
            measured_property=p[0],
            property_category=p[1],
            unit=p[2],
            is_ground_truth=p[3],
            count=p[4],
            time_min_h=p[5],
            time_max_h=p[6],
        )
        for p in prop_rows
    ]

    files = db.scalars(
        select(RawFile).where(RawFile.run_id == run_id).order_by(RawFile.kind)
    ).all()
    spec = db.scalar(select(SyntheticRunSpec).where(SyntheticRunSpec.run_id == run_id))
    n_meas = sum(p.count for p in properties)

    detail = DatasetDetail(
        **_summary_from_run(run, n_meas, len(files), spec is not None).model_dump()
    )
    detail.generator = run.generator
    detail.seed = run.seed
    detail.notes = run.notes
    detail.raw_data_reference = run.raw_data_reference
    detail.files = [RawFileInfo.model_validate(f) for f in files]
    detail.properties = properties
    detail.synthetic_spec = SyntheticSpecOut.model_validate(spec) if spec else None
    return detail


@router.get("/{run_id}/download", summary="Download all raw files (zip)")
def download_dataset(run_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    _get_run(db, run_id)
    files = db.scalars(select(RawFile).where(RawFile.run_id == run_id)).all()
    if not files:
        raise NotFoundError(f"Dataset '{run_id}' has no stored raw files.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f.filename, f.content)
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{run_id}.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


@router.get("/{run_id}/files/{kind}", summary="Download one raw file")
def download_file(run_id: str, kind: str, db: Session = Depends(get_db)) -> Response:
    _get_run(db, run_id)
    f = db.scalar(
        select(RawFile).where(RawFile.run_id == run_id, RawFile.kind == kind)
    )
    if f is None:
        raise NotFoundError(f"Dataset '{run_id}' has no '{kind}' file.")
    headers = {"Content-Disposition": f'attachment; filename="{f.filename}"'}
    return Response(content=f.content, media_type=f.content_type, headers=headers)


@router.delete("/{run_id}", summary="Delete a dataset and all its data")
def delete_dataset(run_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete the run and everything owned by it (measurements, files, spec, …) via cascade."""
    run = _get_run(db, run_id)
    db.delete(run)
    db.commit()
    return {"deleted": run_id}

"""Per-run measurement access: filtered JSON series and a re-pivoted wide CSV."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import NotFoundError
from ..models import FermentationProcessRun, ProcessMeasurementRecord
from ..schemas.common import Page
from ..schemas.datasets import MeasurementOut

router = APIRouter(prefix="/runs", tags=["measurements"])


def _ensure_run(db: Session, run_id: str) -> None:
    exists = db.scalar(
        select(FermentationProcessRun.id).where(FermentationProcessRun.run_id == run_id)
    )
    if exists is None:
        raise NotFoundError(f"Run '{run_id}' not found.")


@router.get(
    "/{run_id}/measurements",
    response_model=Page[MeasurementOut],
    summary="Query a run's measurements",
)
def list_measurements(
    run_id: str,
    measured_property: str | None = Query(None, alias="property"),
    is_ground_truth: bool | None = Query(None),
    from_h: float | None = Query(None, description="Inclusive lower bound on time_h"),
    to_h: float | None = Query(None, description="Inclusive upper bound on time_h"),
    limit: int = Query(1000, ge=1, le=100_000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[MeasurementOut]:
    _ensure_run(db, run_id)
    stmt = select(ProcessMeasurementRecord).where(ProcessMeasurementRecord.run_id == run_id)
    if measured_property is not None:
        stmt = stmt.where(ProcessMeasurementRecord.measured_property == measured_property)
    if is_ground_truth is not None:
        stmt = stmt.where(ProcessMeasurementRecord.is_ground_truth == is_ground_truth)
    if from_h is not None:
        stmt = stmt.where(ProcessMeasurementRecord.time_h >= from_h)
    if to_h is not None:
        stmt = stmt.where(ProcessMeasurementRecord.time_h <= to_h)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            ProcessMeasurementRecord.time_h, ProcessMeasurementRecord.measured_property
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[MeasurementOut](
        items=[MeasurementOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}/measurements.csv", summary="Export measurements as a wide CSV")
def export_measurements_csv(
    run_id: str,
    include_ground_truth: bool = Query(True),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Re-pivot the long measurement store back to wide form (one column per channel).

    Column names are reconstructed as ``<property>`` for observed channels and
    ``truth_<property>`` for ground-truth channels. For a byte-exact copy of the
    uploaded file, use ``GET /datasets/{run_id}/files/log`` instead.
    """
    _ensure_run(db, run_id)
    stmt = select(
        ProcessMeasurementRecord.time_h,
        ProcessMeasurementRecord.measured_property,
        ProcessMeasurementRecord.is_ground_truth,
        ProcessMeasurementRecord.value_num,
    ).where(ProcessMeasurementRecord.run_id == run_id)
    if not include_ground_truth:
        stmt = stmt.where(ProcessMeasurementRecord.is_ground_truth.is_(False))
    stmt = stmt.order_by(ProcessMeasurementRecord.time_h)

    by_time: dict[float | None, dict[str, float | None]] = {}
    columns: set[str] = set()
    for time_h, prop, is_truth, value in db.execute(stmt).all():
        col = f"truth_{prop}" if is_truth else prop
        columns.add(col)
        by_time.setdefault(time_h, {})[col] = value

    ordered_cols = sorted(columns)
    header = ["run_id", "time_h", *ordered_cols]

    def rows() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()
        for time_h in sorted(by_time, key=lambda t: (t is None, t)):
            buf.seek(0)
            buf.truncate(0)
            record = by_time[time_h]
            writer.writerow(
                [run_id, time_h, *(record.get(c) for c in ordered_cols)]
            )
            yield buf.getvalue()

    headers = {"Content-Disposition": f'attachment; filename="{run_id}_measurements.csv"'}
    return StreamingResponse(rows(), media_type="text/csv", headers=headers)

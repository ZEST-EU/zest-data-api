"""User-facing response/request schemas for datasets, measurements, and ingest."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RawFileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime | None = None


class PropertySummary(BaseModel):
    """Aggregate of one measured property within a run."""

    measured_property: str
    property_category: str | None = None
    unit: str | None = None
    is_ground_truth: bool
    count: int
    time_min_h: float | None = None
    time_max_h: float | None = None


class SyntheticSpecOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    note: str | None = None
    spec: dict | None = None
    kinetics: dict | None = None


class DatasetSummary(BaseModel):
    """One row in the dataset catalogue (GET /datasets)."""

    run_id: str
    run_name: str | None = None
    is_synthetic: bool = False
    process_mode: str | None = None
    run_scale: str | None = None
    process_status: str | None = None
    duration: float | None = None
    duration_unit: str | None = None
    working_volume: float | None = None
    working_volume_unit: str | None = None
    created_at: datetime | None = None
    n_measurements: int = 0
    n_files: int = 0
    has_spec: bool = False


class DatasetDetail(DatasetSummary):
    """Full dataset view (GET /datasets/{run_id})."""

    generator: str | None = None
    seed: int | None = None
    notes: str | None = None
    raw_data_reference: str | None = None
    files: list[RawFileInfo] = []
    properties: list[PropertySummary] = []
    synthetic_spec: SyntheticSpecOut | None = None


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    measured_property: str
    property_category: str | None = None
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    time_h: float | None = None
    timepoint: datetime | None = None
    measurement_basis: str | None = None
    value_status: str | None = None
    method_or_sensor: str | None = None
    data_source: str | None = None
    is_ground_truth: bool = False
    qudt_unit: str | None = None
    fiware_model: str | None = None
    notes: str | None = None


class IngestResult(BaseModel):
    """Outcome of POST /datasets."""

    run_id: str
    created: bool
    replaced: bool
    n_measurements: int
    n_labels: int
    n_files: int
    files: list[str]
    message: str

"""Ingest the ``zest-model-service`` SIM-01 dataset format into the data model.

A dataset is up to three files per run, all keyed by ``run_id``:

* ``<run_id>_log.csv``    — dense time series; one row per timestep, one column per
  channel. Melted into ``process_measurement_record`` (one row per channel per step).
  ``truth_*`` columns are the simulation ground truth and are flagged accordingly.
* ``<run_id>_labels.csv`` — sparse biomass "anchor" measurements.
* ``<run_id>_truth.json`` — ``{run_id, note, spec, kinetics, labels}`` for synthetic
  runs; stored in ``synthetic_run_spec``.

All three originals are also kept verbatim in ``raw_file`` for byte-exact download.
Column names/units follow ``zest_model.synthetic`` (the format's authority).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..errors import ConflictError, ValidationError
from ..models import (
    FermentationProcessRun,
    ProcessMeasurementRecord,
    RawFile,
    SyntheticRunSpec,
)
from ..models.enums import ProcessMode, ProcessStatus, RawFileKind, RunScale, ValueStatus
from ..schemas.datasets import IngestResult

# Canonical channel -> (property_category, human unit). Keyed by the *base* name
# (the ``truth_`` prefix is stripped before lookup). Unknown channels still ingest,
# with category/unit left null.
CHANNELS: dict[str, tuple[str, str]] = {
    "do_pct": ("environment", "%"),
    "temp_C": ("environment", "Cel"),
    "rpm": ("operation", "rpm"),
    "airflow_L_min": ("operation", "L/min"),
    "pressure_gauge_bar": ("environment", "bar"),
    "offgas_o2_pct": ("offgas", "%"),
    "offgas_co2_pct": ("offgas", "%"),
    "feed_total_L": ("operation", "L"),
    "volume_L": ("operation", "L"),
    "o2_flow_L_min": ("operation", "L/min"),
    "conductivity_us_cm": ("environment", "uS/cm"),
    "ph": ("environment", "pH"),
    "biomass_g_L": ("biomass", "g/L"),
    "substrate_g_L": ("biomass", "g/L"),
    "do_g_L": ("biomass", "g/L"),
    "our_g_L_h": ("rate", "g/L/h"),
}

# Columns in the log/labels CSVs that are axes/metadata, not measured channels.
_NON_CHANNEL = {"run_id", "time_h", "method"}
_TRUTH_PREFIX = "truth_"


@dataclass
class _ParsedFile:
    kind: RawFileKind
    filename: str
    content: bytes
    content_type: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _channel_meta(column: str) -> tuple[str, str | None, str | None, bool]:
    """Return (measured_property, category, unit, is_ground_truth) for a column."""
    is_truth = column.startswith(_TRUTH_PREFIX)
    base = column[len(_TRUTH_PREFIX):] if is_truth else column
    category, unit = CHANNELS.get(base, (None, None))
    return base, category, unit, is_truth


def _to_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _read_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    return list(fieldnames), list(reader)


def ingest_dataset(
    db: Session,
    *,
    log_bytes: bytes | None = None,
    log_filename: str = "log.csv",
    labels_bytes: bytes | None = None,
    labels_filename: str = "labels.csv",
    truth_bytes: bytes | None = None,
    truth_filename: str = "truth.json",
    replace: bool = False,
) -> IngestResult:
    """Parse a SIM-01 dataset and persist it. Idempotent per ``run_id`` with ``replace``."""
    if not log_bytes and not truth_bytes:
        raise ValidationError("Provide at least a log CSV or a truth JSON file.")

    truth: dict | None = None
    if truth_bytes:
        try:
            truth = json.loads(truth_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationError("truth file is not valid JSON.", detail=str(exc)) from exc

    log_fields: list[str] = []
    log_rows: list[dict[str, str]] = []
    if log_bytes:
        log_fields, log_rows = _read_csv(log_bytes)

    # --- resolve run_id -----------------------------------------------------
    run_id: str | None = None
    if truth and truth.get("run_id"):
        run_id = str(truth["run_id"])
    elif log_rows and log_rows[0].get("run_id"):
        run_id = str(log_rows[0]["run_id"])
    if not run_id:
        raise ValidationError("Could not determine run_id (missing in truth and log).")

    # --- idempotency --------------------------------------------------------
    existing = db.scalar(
        select(FermentationProcessRun).where(FermentationProcessRun.run_id == run_id)
    )
    if existing is not None:
        if not replace:
            raise ConflictError(
                f"Dataset '{run_id}' already exists. Re-upload with replace=true to overwrite."
            )
        db.delete(existing)  # cascades to measurements / raw_file / synthetic_spec
        db.flush()

    spec = (truth or {}).get("spec") or {}
    kinetics = (truth or {}).get("kinetics")
    note = (truth or {}).get("note")
    has_truth_cols = any(c.startswith(_TRUTH_PREFIX) for c in log_fields)
    is_synthetic = truth is not None or has_truth_cols

    # --- the run row --------------------------------------------------------
    duration = spec.get("duration_h")
    if duration is None and log_rows:
        times = [t for t in (_to_float(r.get("time_h")) for r in log_rows) if t is not None]
        duration = max(times) if times else None

    run = FermentationProcessRun(
        run_id=run_id,
        run_name=f"Synthetic run {run_id}" if is_synthetic else run_id,
        run_scale=RunScale.SIMULATION if is_synthetic else None,
        process_mode=ProcessMode.FED_BATCH if spec.get("feed_rate_L_h") else None,
        duration=duration,
        duration_unit="h" if duration is not None else None,
        working_volume=spec.get("volume_0_L"),
        working_volume_unit="L" if spec.get("volume_0_L") is not None else None,
        process_status=ProcessStatus.COMPLETED,
        raw_data_reference=f"{run_id}_log.csv" if log_bytes else None,
        notes=note,
        is_synthetic=is_synthetic,
        generator="zest_model.synthetic" if is_synthetic else None,
        seed=spec.get("seed"),
    )
    db.add(run)
    db.flush()

    # --- synthetic spec -----------------------------------------------------
    if truth is not None:
        db.add(SyntheticRunSpec(run_id=run_id, note=note, spec=spec or None, kinetics=kinetics))

    # --- melt log.csv -> measurements --------------------------------------
    measurement_rows: list[dict] = []
    n_log = 0
    for row in log_rows:
        time_h = _to_float(row.get("time_h"))
        for column in log_fields:
            if column in _NON_CHANNEL:
                continue
            value = _to_float(row.get(column))
            if value is None:
                continue
            prop, category, unit, is_truth = _channel_meta(column)
            measurement_rows.append(
                {
                    "run_id": run_id,
                    "measured_property": prop,
                    "property_category": category,
                    "value_num": value,
                    "unit": unit,
                    "time_h": time_h,
                    "value_status": (
                        ValueStatus.GROUND_TRUTH if is_truth else ValueStatus.MEASURED
                    ),
                    "is_ground_truth": is_truth,
                    "data_source": "synthetic_log" if is_synthetic else "log",
                    "measurement_basis": "online_sensor",
                }
            )
            n_log += 1

    # --- labels.csv -> biomass anchor measurements -------------------------
    n_labels = 0
    if labels_bytes:
        label_fields, label_rows = _read_csv(labels_bytes)
        for row in label_rows:
            time_h = _to_float(row.get("time_h"))
            method = row.get("method") or None
            for column in label_fields:
                if column in _NON_CHANNEL:
                    continue
                value = _to_float(row.get(column))
                if value is None:
                    continue
                prop, category, unit, is_truth = _channel_meta(column)
                measurement_rows.append(
                    {
                        "run_id": run_id,
                        "measured_property": prop,
                        "property_category": category or "biomass",
                        "value_num": value,
                        "unit": unit or "g/L",
                        "time_h": time_h,
                        "value_status": (
                            ValueStatus.GROUND_TRUTH if is_truth else ValueStatus.MEASURED
                        ),
                        "is_ground_truth": is_truth,
                        "data_source": "synthetic_label" if is_synthetic else "label",
                        "measurement_basis": "offline_lab",
                        "method_or_sensor": method,
                    }
                )
                n_labels += 1

    if measurement_rows:
        db.execute(insert(ProcessMeasurementRecord), measurement_rows)

    # --- raw files (verbatim) ----------------------------------------------
    files: list[_ParsedFile] = []
    if log_bytes:
        files.append(_ParsedFile(RawFileKind.LOG, log_filename, log_bytes, "text/csv"))
    if labels_bytes:
        files.append(
            _ParsedFile(RawFileKind.LABELS, labels_filename, labels_bytes, "text/csv")
        )
    if truth_bytes:
        files.append(
            _ParsedFile(RawFileKind.TRUTH, truth_filename, truth_bytes, "application/json")
        )
    for f in files:
        db.add(
            RawFile(
                run_id=run_id,
                kind=f.kind,
                filename=f.filename,
                content_type=f.content_type,
                content=f.content,
                size_bytes=len(f.content),
                sha256=f.sha256,
            )
        )

    db.commit()

    return IngestResult(
        run_id=run_id,
        created=existing is None,
        replaced=existing is not None,
        n_measurements=n_log,
        n_labels=n_labels,
        n_files=len(files),
        files=[f.kind.value for f in files],
        message=(
            f"Ingested run '{run_id}': {n_log} log + {n_labels} label measurements, "
            f"{len(files)} raw file(s)."
        ),
    )

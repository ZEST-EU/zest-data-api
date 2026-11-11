"""Core linkage + execution entities (blue/central band) plus storage additions.

feedstock-fungi combination, fermentation run, measurement records (EAV time
series), and the non-diagram additions needed for this data: raw_file (lossless
originals) and synthetic_run_spec (the truth.json spec/kinetics).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, BinaryType, JSONBType
from .base import PKMixin, TimestampMixin, enum_column
from .enums import ProcessMode, ProcessStatus, RawFileKind, RunScale, ValueStatus

if TYPE_CHECKING:
    from .results import ProcessBiomassOutcome, ProcessObservation


class FeedstockFungiCombination(PKMixin, TimestampMixin, Base):
    """The central link: a feedstock + fungus (+ media) considered for fermentation."""

    __tablename__ = "feedstock_fungi_combination"

    combination_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    feedstock_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedstock.feedstock_id", ondelete="SET NULL"), index=True
    )
    fungi_id: Mapped[str | None] = mapped_column(
        ForeignKey("fungal_species_strain.fungi_id", ondelete="SET NULL"), index=True
    )
    media_recipe_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_recipe.media_recipe_id", ondelete="SET NULL"), index=True
    )
    process_mode = enum_column(ProcessMode, nullable=True)
    co_culture_flag: Mapped[bool | None] = mapped_column(Boolean)
    co_culture_species_id: Mapped[str | None] = mapped_column(
        ForeignKey("fungal_species_strain.fungi_id", ondelete="SET NULL")
    )
    intended_product: Mapped[str | None] = mapped_column(String(255))
    suitability_status: Mapped[str | None] = mapped_column(String(255))
    recommendation_note: Mapped[str | None] = mapped_column(Text)
    evidence_level: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    runs: Mapped[list[FermentationProcessRun]] = relationship(back_populates="combination")


class FermentationProcessRun(PKMixin, TimestampMixin, Base):
    __tablename__ = "fermentation_process_run"

    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    combination_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedstock_fungi_combination.combination_id", ondelete="SET NULL"), index=True
    )
    equipment_setup_id: Mapped[str | None] = mapped_column(
        ForeignKey("bioreactor_equipment_setup.equipment_setup_id", ondelete="SET NULL"),
        index=True,
    )
    run_name: Mapped[str | None] = mapped_column(String(255))
    run_scale = enum_column(RunScale, nullable=True)
    process_mode = enum_column(ProcessMode, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration: Mapped[float | None] = mapped_column(Float)
    duration_unit: Mapped[str | None] = mapped_column(String(32))
    working_volume: Mapped[float | None] = mapped_column(Float)
    working_volume_unit: Mapped[str | None] = mapped_column(String(32))
    process_status = enum_column(ProcessStatus, nullable=True)
    operator_or_partner: Mapped[str | None] = mapped_column(String(255))
    raw_data_reference: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)

    # Provenance for synthetic/simulated runs (addition).
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generator: Mapped[str | None] = mapped_column(String(255))
    seed: Mapped[int | None] = mapped_column(Integer)

    # Owned children: deleting a run removes all of its data. passive_deletes lets
    # the DB's ON DELETE CASCADE do the work instead of loading rows into the session.
    combination: Mapped[FeedstockFungiCombination | None] = relationship(back_populates="runs")
    measurements: Mapped[list[ProcessMeasurementRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    raw_files: Mapped[list[RawFile]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    synthetic_spec: Mapped[SyntheticRunSpec | None] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    outcomes: Mapped[list[ProcessBiomassOutcome]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    observations: Mapped[list[ProcessObservation]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ProcessMeasurementRecord(PKMixin, TimestampMixin, Base):
    """One measured value at one timepoint for a run (long/EAV time series)."""

    __tablename__ = "process_measurement_record"
    __table_args__ = (
        Index("ix_measurement_run_prop_time", "run_id", "measured_property", "time_h"),
    )

    measurement_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("fermentation_process_run.run_id", ondelete="CASCADE"), index=True
    )
    measured_property: Mapped[str] = mapped_column(String(128), index=True)
    property_category: Mapped[str | None] = mapped_column(String(64))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(64))
    time_h: Mapped[float | None] = mapped_column(Float)
    timepoint: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    measurement_basis: Mapped[str | None] = mapped_column(String(255))
    value_status = enum_column(ValueStatus, nullable=True)
    method_or_sensor: Mapped[str | None] = mapped_column(String(255))
    data_source: Mapped[str | None] = mapped_column(String(255))
    is_ground_truth: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qudt_unit: Mapped[str | None] = mapped_column(String(128))
    fiware_model: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    run: Mapped[FermentationProcessRun] = relationship(back_populates="measurements")


class RawFile(PKMixin, TimestampMixin, Base):
    """A verbatim uploaded source file, kept for byte-exact re-download (addition)."""

    __tablename__ = "raw_file"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("fermentation_process_run.run_id", ondelete="CASCADE"), index=True
    )
    kind = enum_column(RawFileKind, nullable=False)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    content: Mapped[bytes] = mapped_column(BinaryType)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)

    run: Mapped[FermentationProcessRun] = relationship(back_populates="raw_files")


class SyntheticRunSpec(PKMixin, TimestampMixin, Base):
    """The simulation spec + kinetics for a synthetic run (from truth.json; addition)."""

    __tablename__ = "synthetic_run_spec"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("fermentation_process_run.run_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text)
    spec: Mapped[dict | None] = mapped_column(JSONBType)
    kinetics: Mapped[dict | None] = mapped_column(JSONBType)

    run: Mapped[FermentationProcessRun] = relationship(back_populates="synthetic_spec")

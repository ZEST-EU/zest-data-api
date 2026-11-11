"""Results + downstream-use entities (red band of the ZEST diagram)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .base import PKMixin, TimestampMixin, enum_column
from .enums import Severity

if TYPE_CHECKING:
    from .core import FermentationProcessRun


class ProcessBiomassOutcome(PKMixin, TimestampMixin, Base):
    """Per-run curated biomass summary (one row per run; all fields optional)."""

    __tablename__ = "process_biomass_outcome"

    outcome_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("fermentation_process_run.run_id", ondelete="CASCADE"), index=True
    )
    wet_biomass_mass: Mapped[float | None] = mapped_column(Float)
    wet_biomass_mass_unit: Mapped[str | None] = mapped_column(String(32))
    dry_biomass_mass: Mapped[float | None] = mapped_column(Float)
    dry_biomass_mass_unit: Mapped[str | None] = mapped_column(String(32))
    moisture_content_percent: Mapped[float | None] = mapped_column(Float)
    dry_matter_percent: Mapped[float | None] = mapped_column(Float)
    dcw_concentration: Mapped[float | None] = mapped_column(Float)
    dcw_concentration_unit: Mapped[str | None] = mapped_column(String(32))
    dcw_basis: Mapped[str | None] = mapped_column(String(255))
    biomass_yield: Mapped[float | None] = mapped_column(Float)
    biomass_yield_unit: Mapped[str | None] = mapped_column(String(32))
    yxs: Mapped[float | None] = mapped_column(Float)
    residual_feedstock_level: Mapped[float | None] = mapped_column(Float)
    separation_method: Mapped[str | None] = mapped_column(String(255))
    separation_efficiency_note: Mapped[str | None] = mapped_column(Text)
    product_quality_note: Mapped[str | None] = mapped_column(Text)
    analytical_result_reference: Mapped[str | None] = mapped_column(String(512))
    interpretation: Mapped[str | None] = mapped_column(Text)

    run: Mapped[FermentationProcessRun] = relationship(back_populates="outcomes")
    downstream_relevances: Mapped[list[DownstreamRelevance]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan", passive_deletes=True
    )


class ProcessObservation(PKMixin, TimestampMixin, Base):
    __tablename__ = "process_observation"

    observation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("fermentation_process_run.run_id", ondelete="CASCADE"), index=True
    )
    observation_type: Mapped[str | None] = mapped_column(String(255))
    severity = enum_column(Severity, nullable=True)
    timepoint: Mapped[float | None] = mapped_column(Float)
    observation_text: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    impact_on_result: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    observation_date: Mapped[date | None] = mapped_column(Date)

    run: Mapped[FermentationProcessRun] = relationship(back_populates="observations")


class DownstreamRelevance(PKMixin, TimestampMixin, Base):
    __tablename__ = "downstream_relevance"

    cascading_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("process_biomass_outcome.outcome_id", ondelete="CASCADE"), index=True
    )
    residue_type: Mapped[str | None] = mapped_column(String(255))
    potential_use: Mapped[str | None] = mapped_column(String(255))
    downstream_relevance: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    outcome: Mapped[ProcessBiomassOutcome] = relationship(back_populates="downstream_relevances")

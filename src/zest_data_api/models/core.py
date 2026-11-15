"""Core linkage + execution entities (blue/central band of the ZEST diagram).

feedstock-fungi combination and the fermentation run. (Raw dataset files now live
in object storage via the separate `dataset`/`dataset_file` tables — see
``models/datasets.py`` — not inline in Postgres.)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .base import PKMixin, TimestampMixin, enum_column
from .enums import ProcessMode, ProcessStatus, RunScale

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

    # Provenance for synthetic/simulated runs.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generator: Mapped[str | None] = mapped_column(String(255))
    seed: Mapped[int | None] = mapped_column(Integer)

    combination: Mapped[FeedstockFungiCombination | None] = relationship(back_populates="runs")
    outcomes: Mapped[list[ProcessBiomassOutcome]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    observations: Mapped[list[ProcessObservation]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

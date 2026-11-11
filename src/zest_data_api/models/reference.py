"""Reference / input entities (green band of the ZEST diagram).

Feedstock + composition, fungal strain + inoculum prep, media recipe (normalized
into header + components), and bioreactor equipment setup.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .base import PKMixin, TimestampMixin, enum_column
from .enums import ValueStatus


class Feedstock(PKMixin, TimestampMixin, Base):
    __tablename__ = "feedstock"

    feedstock_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    feedstock_name: Mapped[str | None] = mapped_column(String(255))
    source_material: Mapped[str | None] = mapped_column(String(255))
    side_stream_category: Mapped[str | None] = mapped_column(String(255))
    fraction: Mapped[str | None] = mapped_column(String(255))
    physical_form: Mapped[str | None] = mapped_column(String(255))
    processing_status: Mapped[str | None] = mapped_column(String(255))
    source_location: Mapped[str | None] = mapped_column(String(255))
    supplier_or_source: Mapped[str | None] = mapped_column(String(255))
    availability: Mapped[str | None] = mapped_column(String(255))
    handling_feasibility: Mapped[str | None] = mapped_column(String(255))
    foodon_mapping: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    compositions: Mapped[list[FeedstockComposition]] = relationship(
        back_populates="feedstock", cascade="all, delete-orphan", passive_deletes=True
    )


class FeedstockComposition(PKMixin, TimestampMixin, Base):
    """One measured compositional property of a feedstock."""

    __tablename__ = "feedstock_composition"

    composition_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    feedstock_id: Mapped[str] = mapped_column(
        ForeignKey("feedstock.feedstock_id", ondelete="CASCADE"), index=True
    )
    measured_property: Mapped[str | None] = mapped_column(String(255))
    property_category: Mapped[str | None] = mapped_column(String(255))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(64))
    measurement_basis: Mapped[str | None] = mapped_column(String(255))
    value_status = enum_column(ValueStatus, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(255))
    method: Mapped[str | None] = mapped_column(String(255))
    measurement_date: Mapped[date | None] = mapped_column(Date)
    confidence_level: Mapped[str | None] = mapped_column(String(64))
    chebi_qudt_mapping: Mapped[str | None] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(Text)

    feedstock: Mapped[Feedstock] = relationship(back_populates="compositions")


class FungalSpeciesStrain(PKMixin, TimestampMixin, Base):
    __tablename__ = "fungal_species_strain"

    fungi_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scientific_name: Mapped[str | None] = mapped_column(String(255))
    strain_identifier: Mapped[str | None] = mapped_column(String(255))
    source_collection: Mapped[str | None] = mapped_column(String(255))
    biological_group: Mapped[str | None] = mapped_column(String(255))
    safety_note: Mapped[str | None] = mapped_column(Text)
    growth_performance_class: Mapped[str | None] = mapped_column(String(255))
    sensory_note: Mapped[str | None] = mapped_column(Text)
    co_culture_relevance: Mapped[str | None] = mapped_column(String(255))
    ncbi_mapping: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    inoculum_preparations: Mapped[list[InoculumPreparation]] = relationship(
        back_populates="fungus", cascade="all, delete-orphan", passive_deletes=True
    )


class InoculumPreparation(PKMixin, TimestampMixin, Base):
    __tablename__ = "inoculum_preparation"

    inoculum_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fungi_id: Mapped[str] = mapped_column(
        ForeignKey("fungal_species_strain.fungi_id", ondelete="CASCADE"), index=True
    )
    source_culture_type: Mapped[str | None] = mapped_column(String(255))
    source_culture_age: Mapped[str | None] = mapped_column(String(255))
    pre_culture_medium: Mapped[str | None] = mapped_column(String(255))
    pre_culture_volume: Mapped[float | None] = mapped_column(Float)
    pre_culture_volume_unit: Mapped[str | None] = mapped_column(String(64))
    incubation_temperature: Mapped[float | None] = mapped_column(Float)
    incubation_temperature_unit: Mapped[str | None] = mapped_column(String(64))
    incubation_conditions: Mapped[str | None] = mapped_column(Text)
    agitation_profile: Mapped[str | None] = mapped_column(String(255))
    homogenisation_step: Mapped[str | None] = mapped_column(String(255))
    inoculum_volume: Mapped[float | None] = mapped_column(Float)
    inoculum_volume_unit: Mapped[str | None] = mapped_column(String(64))
    washing_applied: Mapped[str | None] = mapped_column(String(255))

    fungus: Mapped[FungalSpeciesStrain] = relationship(back_populates="inoculum_preparations")


class MediaRecipe(PKMixin, TimestampMixin, Base):
    """Media recipe header. Components live in ``media_recipe_component`` (normalized
    from the diagram's one-row-per-component layout)."""

    __tablename__ = "media_recipe"

    media_recipe_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    recipe_name: Mapped[str | None] = mapped_column(String(255))
    recipe_type: Mapped[str | None] = mapped_column(String(255))
    preparation_method: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    components: Mapped[list[MediaRecipeComponent]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", passive_deletes=True
    )


class MediaRecipeComponent(PKMixin, TimestampMixin, Base):
    __tablename__ = "media_recipe_component"

    media_recipe_id: Mapped[str] = mapped_column(
        ForeignKey("media_recipe.media_recipe_id", ondelete="CASCADE"), index=True
    )
    component_name: Mapped[str | None] = mapped_column(String(255))
    component_role: Mapped[str | None] = mapped_column(String(255))
    concentration: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(64))
    used_in_phase: Mapped[str | None] = mapped_column(String(255))
    chebi_qudt_mapping: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    recipe: Mapped[MediaRecipe] = relationship(back_populates="components")


class BioreactorEquipmentSetup(PKMixin, TimestampMixin, Base):
    __tablename__ = "bioreactor_equipment_setup"

    equipment_setup_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reactor_type: Mapped[str | None] = mapped_column(String(255))
    total_volume: Mapped[float | None] = mapped_column(Float)
    total_volume_unit: Mapped[str | None] = mapped_column(String(64))
    working_volume_range: Mapped[str | None] = mapped_column(String(255))
    vessel_type: Mapped[str | None] = mapped_column(String(255))
    drive_type: Mapped[str | None] = mapped_column(String(255))
    stirrer_type: Mapped[str | None] = mapped_column(String(255))
    rotation_speed_range: Mapped[str | None] = mapped_column(String(255))  # diagram typo fixed
    sparger_type: Mapped[str | None] = mapped_column(String(255))
    gas_supply: Mapped[str | None] = mapped_column(String(255))
    temperature_pressure_control: Mapped[str | None] = mapped_column(String(255))
    sensors: Mapped[str | None] = mapped_column(Text)
    fiware_model_mapping: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

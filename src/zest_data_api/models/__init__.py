"""SQLAlchemy ORM models for the ZEST fermentation data model.

Importing this package registers every table on ``Base.metadata`` (used by
Alembic autogenerate and by the test suite's ``create_all``).
"""

from __future__ import annotations

from .core import (
    FeedstockFungiCombination,
    FermentationProcessRun,
    ProcessMeasurementRecord,
    RawFile,
    SyntheticRunSpec,
)
from .enums import (
    ProcessMode,
    ProcessStatus,
    RawFileKind,
    RunScale,
    Severity,
    ValueStatus,
)
from .reference import (
    BioreactorEquipmentSetup,
    Feedstock,
    FeedstockComposition,
    FungalSpeciesStrain,
    InoculumPreparation,
    MediaRecipe,
    MediaRecipeComponent,
)
from .results import (
    DownstreamRelevance,
    ProcessBiomassOutcome,
    ProcessObservation,
)

__all__ = [
    # reference
    "Feedstock",
    "FeedstockComposition",
    "FungalSpeciesStrain",
    "InoculumPreparation",
    "MediaRecipe",
    "MediaRecipeComponent",
    "BioreactorEquipmentSetup",
    # core
    "FeedstockFungiCombination",
    "FermentationProcessRun",
    "ProcessMeasurementRecord",
    "RawFile",
    "SyntheticRunSpec",
    # results
    "ProcessBiomassOutcome",
    "ProcessObservation",
    "DownstreamRelevance",
    # enums
    "ProcessMode",
    "ProcessStatus",
    "RunScale",
    "ValueStatus",
    "Severity",
    "RawFileKind",
]

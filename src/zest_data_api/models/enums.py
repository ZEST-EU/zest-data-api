"""Controlled vocabularies for the few strictly categorical fields.

Kept deliberately small — most descriptive fields stay free-text. Every enum
includes a catch-all member so ingest never has to reject unexpected input.
"""

from __future__ import annotations

from enum import StrEnum


class ProcessMode(StrEnum):
    BATCH = "batch"
    FED_BATCH = "fed-batch"
    CONTINUOUS = "continuous"
    CO_CULTURE = "co-culture"
    UNKNOWN = "unknown"


class ProcessStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RunScale(StrEnum):
    LAB = "lab"
    BENCH = "bench"
    PILOT = "pilot"
    PRODUCTION = "production"
    SIMULATION = "simulation"
    UNKNOWN = "unknown"


class ValueStatus(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    DERIVED = "derived"
    GROUND_TRUTH = "ground_truth"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

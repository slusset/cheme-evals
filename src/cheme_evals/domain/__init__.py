"""Domain layer for the ChemE eval harness."""

from .records import (
    ArchiveRecord,
    ArtifactRecord,
    ArtifactStatus,
    ScoreBundle,
    ScoreDimension,
    TraceEvent,
    RunRecord,
)

__all__ = [
    "ArchiveRecord",
    "ArtifactRecord",
    "ArtifactStatus",
    "ScoreBundle",
    "ScoreDimension",
    "TraceEvent",
    "RunRecord",
]
"""Domain types for the eval harness."""

from .config import HarnessPaths

__all__ = ["HarnessPaths"]

"""Domain record schemas for the eval harness.

These records model the stable data shapes that move through the system.
They are intentionally serialization-friendly so they can back JSON/JSONL
storage now and cleaner message contracts later.
"""

from typing import Any, Literal, TypedDict


ArtifactStatus = Literal["proposed", "validated", "rejected", "promoted", "retired"]


class ScoreDimension(TypedDict, total=False):
    """One score dimension persisted in run results."""

    numeric_score: int
    numeric_possible: int
    numeric_pct: float
    reasoning_score_pct: float
    proposal_score: int
    proposal_possible: int
    proposal_score_pct: float
    judge_method: str
    score_reliability: str
    notes: str


class ScoreBundle(TypedDict):
    """Complete score block for one run."""

    numeric: dict[str, Any]
    reasoning: dict[str, Any]
    tool_proposals: dict[str, Any]
    overall_pct: float


class TraceEvent(TypedDict):
    """Append-only trace event for one run."""

    event_id: str
    run_id: str
    sequence: int
    timestamp: str
    type: str
    payload: dict[str, Any]


class ArtifactRecord(TypedDict, total=False):
    """Persisted artifact created from a proposal."""

    artifact_id: str
    artifact_type: str
    status: ArtifactStatus
    summary: str
    source_run_id: str
    source_fixture_id: str
    source_fixture_version: str
    timestamp: str
    git_sha: str
    proposal: dict[str, Any]
    validation: dict[str, Any]
    lifecycle: list[dict[str, Any]]
    artifact_path: str


class ArchiveRecord(TypedDict):
    """Append-only archive ledger record."""

    record_type: str
    record_id: str
    timestamp: str
    payload: dict[str, Any]


class RunRecord(TypedDict, total=False):
    """Completed run result record."""

    run_id: str
    eval_id: str
    fixture_id: str
    fixture_version: str
    layer: int
    timestamp: str
    git_sha: str
    agent_meta: dict[str, Any]
    scores: ScoreBundle
    agent_response: dict[str, Any]
    tool_proposals: list[dict[str, Any]]
    artifacts: list[ArtifactRecord]


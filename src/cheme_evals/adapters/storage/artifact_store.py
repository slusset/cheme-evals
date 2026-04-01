"""File-backed artifact registry storage."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cheme_evals.adapters.storage.archive_store import append_archive_record
from cheme_evals.domain.records import ArtifactRecord


def get_artifact_path(artifacts_dir: Path, artifact_id: str) -> Path:
    """Return the file path for a stored artifact."""
    return artifacts_dir / f"{artifact_id}.json"


def load_artifact(artifacts_dir: Path, artifact_id: str) -> ArtifactRecord:
    """Load one artifact record by ID."""
    artifact_path = get_artifact_path(artifacts_dir, artifact_id)
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact does not exist: {artifact_id}")
    with open(artifact_path) as f:
        artifact: ArtifactRecord = json.load(f)
    artifact["artifact_path"] = str(artifact_path)
    return artifact


def save_artifact(artifacts_dir: Path, artifact: ArtifactRecord) -> ArtifactRecord:
    """Persist one artifact record to disk."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = get_artifact_path(artifacts_dir, artifact["artifact_id"])
    artifact_to_write = dict(artifact)
    artifact_to_write.pop("artifact_path", None)
    with open(artifact_path, "w") as f:
        json.dump(artifact_to_write, f, indent=2)
    artifact["artifact_path"] = str(artifact_path)
    return artifact


def list_artifacts(
    artifacts_dir: Path,
    status: str = None,
    artifact_type: str = None,
) -> list[ArtifactRecord]:
    """List artifact records from the local registry with optional filters."""
    if not artifacts_dir.exists():
        return []

    artifacts: list[ArtifactRecord] = []
    for path in sorted(artifacts_dir.glob("*.json")):
        with open(path) as f:
            artifact: ArtifactRecord = json.load(f)
        artifact["artifact_path"] = str(path)
        if status and artifact.get("status") != status:
            continue
        if artifact_type and artifact.get("artifact_type") != artifact_type:
            continue
        artifacts.append(artifact)
    return artifacts


def record_artifact(
    *,
    artifacts_dir: Path,
    archive_log: Path,
    run_id: str,
    fixture: dict,
    artifact_type: str,
    proposal: dict,
    git_sha: str,
) -> ArtifactRecord:
    """Persist a first-class artifact record and return it."""
    artifact_id = str(uuid.uuid4())
    artifact: ArtifactRecord = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "status": "proposed",
        "summary": proposal.get("reason", ""),
        "source_run_id": run_id,
        "source_fixture_id": fixture["id"],
        "source_fixture_version": fixture.get("version", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "proposal": proposal,
        "validation": {
            "status": "not_validated",
            "tests_passed": False,
            "reviewed_by": None,
        },
    }
    save_artifact(artifacts_dir, artifact)
    append_archive_record(
        archive_log,
        "artifact",
        artifact_id,
        {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "status": artifact["status"],
            "source_run_id": run_id,
            "fixture_id": fixture["id"],
            "path": artifact["artifact_path"],
        },
    )
    return artifact

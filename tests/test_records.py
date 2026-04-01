"""
Tests for extracted domain record schemas.
"""
import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from cheme_evals.domain.records import (
    ArchiveRecord,
    ArtifactRecord,
    ArtifactStatus,
    RunRecord,
    ScoreBundle,
    TraceEvent,
)
from cheme_evals.domain.config import HarnessPaths


class TestDomainRecords:

    def test_run_record_shape_is_available(self):
        record: RunRecord = {
            "run_id": "run-123",
            "fixture_id": "fixture-1",
            "fixture_version": "1.0.0",
            "layer": 3,
            "timestamp": "2026-04-01T12:00:00Z",
            "git_sha": "deadbee",
            "agent_meta": {},
            "scores": {
                "numeric": {},
                "reasoning": {},
                "tool_proposals": {},
                "overall_pct": 100.0,
            },
            "agent_response": {},
            "tool_proposals": [],
            "artifacts": [],
        }
        assert record["run_id"] == "run-123"
        assert record["scores"]["overall_pct"] == 100.0

    def test_artifact_status_literal_is_usable(self):
        status: ArtifactStatus = "proposed"
        artifact: ArtifactRecord = {
            "artifact_id": "artifact-1",
            "artifact_type": "tool",
            "status": status,
        }
        assert artifact["status"] == "proposed"

    def test_trace_and_archive_record_shapes_are_available(self):
        trace_event: TraceEvent = {
            "event_id": "event-1",
            "run_id": "run-123",
            "sequence": 1,
            "timestamp": "2026-04-01T12:00:00Z",
            "type": "run_started",
            "payload": {},
        }
        archive_record: ArchiveRecord = {
            "record_type": "run",
            "record_id": "run-123",
            "timestamp": "2026-04-01T12:00:00Z",
            "payload": {"run_id": "run-123"},
        }
        assert trace_event["type"] == "run_started"
        assert archive_record["record_type"] == "run"

    def test_score_bundle_shape_is_available(self):
        scores: ScoreBundle = {
            "numeric": {"numeric_pct": 100.0},
            "reasoning": {"reasoning_score_pct": 80.0},
            "tool_proposals": {"proposal_score_pct": 100.0},
            "overall_pct": 91.0,
        }
        assert scores["overall_pct"] == 91.0

    def test_harness_paths_from_root_builds_repo_layout(self):
        root = Path("/tmp/cheme-evals")
        paths = HarnessPaths.from_root(root)

        assert paths.harness_root == root
        assert paths.fixtures_dir == root / "fixtures"
        assert paths.mocks_dir == root / "mocks"
        assert paths.results_dir == root / "results"
        assert paths.traces_dir == root / "results" / "traces"
        assert paths.artifacts_dir == root / "results" / "artifacts"
        assert paths.archive_log == root / "results" / "archive.jsonl"
        assert paths.experiment_log == root / "results" / "experiments.jsonl"
        assert paths.skills_dir == root / "agent" / "skills"

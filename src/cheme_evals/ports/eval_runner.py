"""Ports used by the eval runner application service."""

from pathlib import Path
from typing import Protocol


class RuntimeInfoPort(Protocol):
    """Runtime metadata required during an eval run."""

    judge_default_model: str

    def new_run_id(self) -> str:
        """Create a stable run identifier."""

    def get_git_sha(self) -> str:
        """Return the current git sha."""


class FixturePort(Protocol):
    """Fixture loading and prompt assembly."""

    def load_fixture(self, path: str) -> dict:
        """Load one fixture."""

    def build_system_prompt(self, fixture: dict, layer: int = 1) -> str:
        """Build the system prompt."""

    def build_user_prompt(self, fixture: dict, layer: int = 1) -> str:
        """Build the user prompt."""


class AgentPort(Protocol):
    """Agent invocation and replay behaviors."""

    def call_agent(
        self,
        system_prompt: str,
        user_prompt: str,
        mock_path: str = None,
        provider_name: str = None,
        model: str = None,
        layer: int = 1,
    ) -> dict:
        """Call the agent or replay from mock."""

    def save_mock(self, response: dict, fixture_id: str) -> None:
        """Persist one agent response for replay."""


class ScoringPort(Protocol):
    """Scoring and result-assembly operations."""

    def score_outputs(self, actual: dict, expected: dict, tolerances: dict) -> dict:
        """Score numeric outputs."""

    def score_reasoning(
        self,
        response: dict,
        fixture: dict,
        use_judge: bool = True,
        judge_provider: str = "anthropic",
        judge_model: str = None,
    ) -> dict:
        """Score reasoning quality."""

    def score_tool_proposals(self, response: dict, fixture: dict) -> dict:
        """Score tool proposal quality."""

    def assemble_result(
        self,
        fixture: dict,
        response: dict,
        output_scores: dict,
        reasoning_scores: dict,
        proposal_scores: dict = None,
        layer: int = 1,
    ) -> dict:
        """Assemble the final run record."""


class TracePort(Protocol):
    """Trace storage and lookup."""

    def append_trace_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
        sequence: int,
    ) -> int:
        """Append one event to a run trace."""

    def get_trace_path(self, run_id: str) -> Path:
        """Return the path to a run trace."""


class ArtifactPort(Protocol):
    """Artifact registration."""

    def record_artifact(
        self,
        *,
        run_id: str,
        fixture: dict,
        artifact_type: str,
        proposal: dict,
        git_sha: str,
    ) -> dict:
        """Persist one artifact created during a run."""


class ArchivePort(Protocol):
    """Append-only archive ledger."""

    def append_archive_record(self, record_type: str, record_id: str, payload: dict) -> dict:
        """Append one archive record."""


class ResultStorePort(Protocol):
    """Result and experiment storage."""

    def write_result(self, results_dir: Path, filename: str, result: dict) -> Path:
        """Write one result file."""

    def append_jsonl_record(self, log_path: Path, entry: dict) -> dict:
        """Append one JSONL record."""

    def read_jsonl_records(self, log_path: Path) -> list[dict]:
        """Read all JSONL records."""


class PresenterPort(Protocol):
    """Human-readable rendering."""

    def print_results(self, result: dict) -> None:
        """Print a completed run summary."""

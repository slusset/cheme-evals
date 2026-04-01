"""Runtime configuration value objects for the eval harness."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarnessPaths:
    """Filesystem locations used by one harness runtime."""

    harness_root: Path
    fixtures_dir: Path
    mocks_dir: Path
    results_dir: Path
    traces_dir: Path
    artifacts_dir: Path
    archive_log: Path
    experiment_log: Path
    skills_dir: Path

    @classmethod
    def from_root(cls, harness_root: Path) -> "HarnessPaths":
        """Construct the default repo-local path layout."""
        results_dir = harness_root / "results"
        return cls(
            harness_root=harness_root,
            fixtures_dir=harness_root / "fixtures",
            mocks_dir=harness_root / "mocks",
            results_dir=results_dir,
            traces_dir=results_dir / "traces",
            artifacts_dir=results_dir / "artifacts",
            archive_log=results_dir / "archive.jsonl",
            experiment_log=results_dir / "experiments.jsonl",
            skills_dir=harness_root / "agent" / "skills",
        )

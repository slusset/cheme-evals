"""File-backed result and experiment storage."""

import json
from pathlib import Path


def write_result(results_dir: Path, filename: str, result: dict) -> Path:
    """Persist one completed run result."""
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / filename
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    return result_path


def append_jsonl_record(log_path: Path, entry: dict) -> dict:
    """Append one JSON object to a JSONL file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_jsonl_records(log_path: Path) -> list[dict]:
    """Read all JSON objects from a JSONL file."""
    if not log_path.exists():
        return []

    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries

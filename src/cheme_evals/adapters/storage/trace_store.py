"""Append-only per-run trace storage."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cheme_evals.domain.records import TraceEvent


def get_trace_path(traces_dir: Path, run_id: str) -> Path:
    """Return the JSONL trace path for a run."""
    return traces_dir / f"{run_id}.jsonl"


def append_trace_event(
    traces_dir: Path,
    run_id: str,
    event_type: str,
    payload: dict,
    sequence: int,
) -> int:
    """Append one event to the run's trace log and return the next sequence number."""
    traces_dir.mkdir(parents=True, exist_ok=True)
    event: TraceEvent = {
        "event_id": str(uuid.uuid4()),
        "run_id": run_id,
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload,
    }
    with open(get_trace_path(traces_dir, run_id), "a") as f:
        f.write(json.dumps(event) + "\n")
    return sequence + 1

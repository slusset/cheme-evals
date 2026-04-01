"""Append-only archive storage."""

import json
from datetime import datetime, timezone
from pathlib import Path

from cheme_evals.domain.records import ArchiveRecord


def append_archive_record(
    archive_log: Path,
    record_type: str,
    record_id: str,
    payload: dict,
) -> ArchiveRecord:
    """Append one record to the central archive ledger."""
    archive_log.parent.mkdir(parents=True, exist_ok=True)
    record: ArchiveRecord = {
        "record_type": record_type,
        "record_id": record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with open(archive_log, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record

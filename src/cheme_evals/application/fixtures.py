"""Fixture loading service."""

import json


def load_fixture(path: str) -> dict:
    """Load and validate a fixture file."""
    with open(path) as f:
        fixture = json.load(f)

    required = ["id", "problem", "inputs", "expected_outputs", "acceptance_criteria"]
    missing = [key for key in required if key not in fixture]
    if missing:
        raise ValueError(f"Fixture missing required fields: {missing}")

    return fixture

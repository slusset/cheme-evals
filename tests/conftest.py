"""
Shared fixtures for cheme-evals tests.

These provide realistic fixture data matching the production schema
so tests exercise the same code paths as real evals.
"""
import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def flash_fixture():
    """The production flash-distillation-01 fixture."""
    with open(FIXTURES_DIR / "flash-distillation-01.json") as f:
        return json.load(f)


@pytest.fixture
def multistage_fixture():
    """The production multistage-flash-01 fixture."""
    with open(FIXTURES_DIR / "multistage-flash-01.json") as f:
        return json.load(f)


@pytest.fixture
def minimal_fixture():
    """Minimal valid fixture for unit tests — no file dependency."""
    return {
        "id": "test-fixture-01",
        "version": "1.0.0",
        "problem": {
            "statement": "Calculate the boiling point of water at 1 atm.",
            "task": "Report the temperature in K.",
            "difficulty": "introductory",
            "topics": ["thermodynamics"],
        },
        "inputs": {
            "pressure": {
                "value": 101.325,
                "unit": "kPa",
                "description": "System pressure",
            },
            "antoine_water": {
                "value": [8.07131, 1730.63, 233.426],
                "unit": "log10_mmHg_degC",
                "description": "Antoine coefficients for water",
                "input_class": "reference_data",
            },
        },
        "expected_outputs": {
            "boiling_point": {
                "value": 373.15,
                "unit": "K",
                "description": "Boiling point of water",
            },
        },
        "acceptance_criteria": {
            "tolerances": {
                "boiling_point": {
                    "type": "absolute",
                    "value": 1.0,
                },
            },
            "must_include": [
                "Use Antoine equation for vapor pressure",
            ],
            "must_not_include": [
                "Assume boiling point is exactly 100 C without calculation",
            ],
        },
        "domain_context": {
            "recommended_tools": ["manual_calculation"],
            "recommended_thermo_model": "Antoine equation",
            "key_assumptions": ["Ideal gas vapor phase"],
            "common_mistakes": ["Wrong Antoine units"],
        },
        "agent_evaluation": {
            "reasoning_checkpoints": [
                {
                    "checkpoint": "Uses Antoine equation to calculate vapor pressure",
                    "weight": 0.5,
                },
                {
                    "checkpoint": "Converts units correctly between mmHg and kPa",
                    "weight": 0.3,
                },
                {
                    "checkpoint": "States assumptions about ideal behavior",
                    "weight": 0.2,
                },
            ],
            "skill_document_expected": False,
        },
    }


@pytest.fixture
def perfect_response():
    """An agent response that should score perfectly against minimal_fixture."""
    return {
        "reasoning": "I used the Antoine equation to calculate the vapor pressure of water. "
                     "The Antoine equation gives log10(P/mmHg) = A - B/(C + T). "
                     "Setting P = 760 mmHg (= 101.325 kPa) and solving for T gives 100 C = 373.15 K.",
        "assumptions": [
            "Ideal gas behavior in vapor phase",
            "Antoine equation valid at this temperature",
        ],
        "method": "Antoine equation with unit conversion from mmHg to kPa",
        "calculations": {
            "P_mmHg": 760,
            "T_C": 100.0,
        },
        "outputs": {
            "boiling_point": {"value": 373.15, "unit": "K"},
        },
        "confidence": 0.95,
        "skill_notes": "Antoine equation is straightforward for pure component boiling points.",
    }

"""
Tests for the scoring engine: numeric scoring, unit normalization,
and keyword-based reasoning scoring.

These are the most critical pure functions in the harness — a bug here
silently corrupts every eval result.
"""
import sys
from pathlib import Path

import pytest

# Add project root to path so we can import run_eval
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_eval import normalize_unit, score_outputs, score_reasoning_keyword, score_tool_proposals


# ═══════════════════════════════════════════════════════════════════════════
# normalize_unit
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeUnit:
    """Unit conversion is the first thing that touches agent output.
    If it's wrong, every downstream score is wrong."""

    # --- identity (same unit, no conversion needed) ---

    def test_same_unit_returns_unchanged(self):
        val, note = normalize_unit(373.15, "K", "K")
        assert val == 373.15
        assert note is None

    def test_same_unit_mol_fraction(self):
        val, note = normalize_unit(0.5, "mol_fraction", "mol_fraction")
        assert val == 0.5
        assert note is None

    # --- temperature conversions ---

    def test_celsius_to_kelvin(self):
        val, note = normalize_unit(100.0, "°C", "K")
        assert abs(val - 373.15) < 0.01
        assert note is not None  # should describe conversion

    def test_degC_alias_to_kelvin(self):
        """The 'degC' variant (no special char) should also work."""
        val, note = normalize_unit(0.0, "degC", "K")
        assert abs(val - 273.15) < 0.01

    def test_bare_C_to_kelvin(self):
        val, note = normalize_unit(25.0, "C", "K")
        assert abs(val - 298.15) < 0.01

    def test_kelvin_to_celsius(self):
        val, note = normalize_unit(373.15, "K", "°C")
        assert abs(val - 100.0) < 0.01

    def test_fahrenheit_to_kelvin(self):
        val, note = normalize_unit(212.0, "°F", "K")
        assert abs(val - 373.15) < 0.5  # F→K via (F-32)*5/9+273.15

    def test_fahrenheit_to_celsius(self):
        val, note = normalize_unit(32.0, "°F", "°C")
        assert abs(val - 0.0) < 0.01

    # --- pressure conversions ---

    def test_atm_to_kpa(self):
        val, note = normalize_unit(1.0, "atm", "kPa")
        assert abs(val - 101.325) < 0.01

    def test_bar_to_kpa(self):
        val, note = normalize_unit(1.0, "bar", "kPa")
        assert abs(val - 100.0) < 0.01

    def test_mmhg_to_kpa(self):
        val, note = normalize_unit(760.0, "mmHg", "kPa")
        assert abs(val - 101.325) < 0.1

    def test_torr_to_kpa(self):
        """Torr and mmHg should give same result."""
        val_mmhg, _ = normalize_unit(760.0, "mmHg", "kPa")
        val_torr, _ = normalize_unit(760.0, "Torr", "kPa")
        assert abs(val_mmhg - val_torr) < 0.001

    def test_kpa_to_atm(self):
        val, note = normalize_unit(101.325, "kPa", "atm")
        assert abs(val - 1.0) < 0.001

    def test_pa_to_bar(self):
        val, note = normalize_unit(100000.0, "Pa", "bar")
        assert abs(val - 1.0) < 0.001

    # --- no conversion available ---

    def test_unknown_units_passthrough(self):
        """If no conversion exists, return value unchanged with no note."""
        val, note = normalize_unit(42.0, "furlongs", "cubits")
        assert val == 42.0
        assert note is None

    def test_incompatible_units_passthrough(self):
        """Temperature to pressure — no conversion should exist."""
        val, note = normalize_unit(300.0, "K", "kPa")
        assert val == 300.0
        assert note is None

    # --- roundtrip consistency ---

    def test_celsius_kelvin_roundtrip(self):
        original = 100.0
        to_k, _ = normalize_unit(original, "°C", "K")
        back, _ = normalize_unit(to_k, "K", "°C")
        assert abs(back - original) < 0.001

    def test_atm_kpa_roundtrip(self):
        original = 2.5
        to_kpa, _ = normalize_unit(original, "atm", "kPa")
        back, _ = normalize_unit(to_kpa, "kPa", "atm")
        assert abs(back - original) < 0.001


# ═══════════════════════════════════════════════════════════════════════════
# score_outputs
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreOutputs:
    """The numeric grading engine. Every eval runs through this."""

    def test_perfect_score_absolute(self):
        actual = {"temp": {"value": 373.15, "unit": "K"}}
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["numeric_score"] == 1
        assert result["numeric_possible"] == 1
        assert result["numeric_pct"] == 100.0
        assert result["output_scores"]["temp"]["status"] == "PASS"

    def test_perfect_score_relative(self):
        actual = {"flow": {"value": 100.0, "unit": "kmol/h"}}
        expected = {"flow": {"value": 100.0, "unit": "kmol/h"}}
        tolerances = {"flow": {"type": "relative_percent", "value": 2.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["numeric_pct"] == 100.0

    def test_within_absolute_tolerance(self):
        actual = {"temp": {"value": 374.0, "unit": "K"}}
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["temp"]["status"] == "PASS"

    def test_outside_absolute_tolerance(self):
        actual = {"temp": {"value": 380.0, "unit": "K"}}
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["temp"]["status"] == "FAIL"
        assert result["numeric_score"] == 0

    def test_within_relative_tolerance(self):
        actual = {"flow": {"value": 101.5, "unit": "kmol/h"}}
        expected = {"flow": {"value": 100.0, "unit": "kmol/h"}}
        tolerances = {"flow": {"type": "relative_percent", "value": 2.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["flow"]["status"] == "PASS"

    def test_outside_relative_tolerance(self):
        actual = {"flow": {"value": 105.0, "unit": "kmol/h"}}
        expected = {"flow": {"value": 100.0, "unit": "kmol/h"}}
        tolerances = {"flow": {"type": "relative_percent", "value": 2.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["flow"]["status"] == "FAIL"

    def test_missing_output(self):
        """Agent didn't produce an expected output."""
        actual = {}
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["temp"]["status"] == "MISSING"
        assert result["numeric_score"] == 0

    def test_missing_value_field(self):
        """Agent produced the key but no value inside it."""
        actual = {"temp": {"unit": "K"}}  # no "value"
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["temp"]["status"] == "MISSING"

    def test_multiple_outputs_mixed(self):
        """Some pass, some fail — verify aggregate scoring."""
        actual = {
            "x_benzene": {"value": 0.45, "unit": "mol_fraction"},
            "temp": {"value": 400.0, "unit": "K"},  # way off
        }
        expected = {
            "x_benzene": {"value": 0.445, "unit": "mol_fraction"},
            "temp": {"value": 366.9, "unit": "K"},
        }
        tolerances = {
            "x_benzene": {"type": "absolute", "value": 0.02},
            "temp": {"type": "absolute", "value": 3.0},
        }

        result = score_outputs(actual, expected, tolerances)
        assert result["numeric_score"] == 1  # x_benzene passes, temp fails
        assert result["numeric_possible"] == 2
        assert result["numeric_pct"] == 50.0

    def test_unit_conversion_in_scoring(self):
        """Agent returns °C, expected is K — should auto-convert and pass."""
        actual = {"temp": {"value": 100.0, "unit": "°C"}}
        expected = {"temp": {"value": 373.15, "unit": "K"}}
        tolerances = {"temp": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["temp"]["status"] == "PASS"

    def test_unit_conversion_atm_to_kpa(self):
        """Agent returns atm, expected is kPa."""
        actual = {"P": {"value": 1.0, "unit": "atm"}}
        expected = {"P": {"value": 101.325, "unit": "kPa"}}
        tolerances = {"P": {"type": "absolute", "value": 0.5}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["P"]["status"] == "PASS"

    def test_default_tolerance_when_missing(self):
        """If no tolerance is specified, falls back to 5% relative."""
        actual = {"x": {"value": 1.04, "unit": "m"}}
        expected = {"x": {"value": 1.0, "unit": "m"}}
        tolerances = {}  # no tolerance defined

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["x"]["status"] == "PASS"  # 4% < 5% default

    def test_relative_tolerance_expected_zero(self):
        """Edge case: expected value is zero with relative tolerance."""
        actual = {"x": {"value": 0.0, "unit": "m"}}
        expected = {"x": {"value": 0, "unit": "m"}}
        tolerances = {"x": {"type": "relative_percent", "value": 5.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["x"]["status"] == "PASS"

    def test_boundary_absolute_exact(self):
        """Error exactly equals tolerance — should pass (<=)."""
        actual = {"x": {"value": 11.0, "unit": "m"}}
        expected = {"x": {"value": 10.0, "unit": "m"}}
        tolerances = {"x": {"type": "absolute", "value": 1.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["x"]["status"] == "PASS"

    def test_boundary_relative_exact(self):
        """Error exactly equals relative tolerance — should pass (<=)."""
        actual = {"x": {"value": 102.0, "unit": "m"}}
        expected = {"x": {"value": 100.0, "unit": "m"}}
        tolerances = {"x": {"type": "relative_percent", "value": 2.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["x"]["status"] == "PASS"

    def test_flash_distillation_fixture(self, flash_fixture):
        """Score a perfect response against the real flash-distillation-01 fixture."""
        expected = flash_fixture["expected_outputs"]
        tolerances = flash_fixture["acceptance_criteria"]["tolerances"]

        # Simulate a perfect agent response
        actual = {
            key: {"value": spec["value"], "unit": spec["unit"]}
            for key, spec in expected.items()
        }

        result = score_outputs(actual, expected, tolerances)
        assert result["numeric_pct"] == 100.0, (
            f"Perfect response should score 100%, got {result['numeric_pct']}%"
        )

    def test_multistage_fixture_all_outputs(self, multistage_fixture):
        """Score a perfect response against multistage-flash-01 (11 outputs)."""
        expected = multistage_fixture["expected_outputs"]
        tolerances = multistage_fixture["acceptance_criteria"]["tolerances"]

        actual = {
            key: {"value": spec["value"], "unit": spec["unit"]}
            for key, spec in expected.items()
        }

        result = score_outputs(actual, expected, tolerances)
        assert result["numeric_score"] == 11
        assert result["numeric_possible"] == 11


# ═══════════════════════════════════════════════════════════════════════════
# score_reasoning_keyword
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreReasoningKeyword:
    """The heuristic reasoning scorer — coarse baseline only."""

    def test_perfect_response_scores_well(self, minimal_fixture, perfect_response):
        result = score_reasoning_keyword(perfect_response, minimal_fixture)

        # must_include: "Use Antoine equation for vapor pressure"
        assert result["must_include"][0]["found"] is True

        # must_not_include: "Assume boiling point is exactly 100 C without calculation"
        assert result["must_not_include"][0]["violated"] is False

        # Overall should be > 0
        assert result["reasoning_score_pct"] > 0

    def test_empty_response_scores_low(self, minimal_fixture):
        empty_response = {
            "reasoning": "",
            "assumptions": [],
            "method": "",
            "outputs": {},
        }
        result = score_reasoning_keyword(empty_response, minimal_fixture)
        assert result["reasoning_score_pct"] == 0

    def test_must_not_include_violation(self, minimal_fixture):
        """Response that commits the must_not_include error."""
        bad_response = {
            "reasoning": "I assume the boiling point is exactly 100 C without any calculation needed.",
            "assumptions": ["Boiling point is exactly 100 C"],
            "method": "Assumed standard value",
            "outputs": {"boiling_point": {"value": 373.15, "unit": "K"}},
        }
        result = score_reasoning_keyword(bad_response, minimal_fixture)
        # The keyword matcher should flag this
        assert result["must_not_include"][0]["violated"] is True

    def test_checkpoint_weights_sum(self, minimal_fixture, perfect_response):
        """Verify that checkpoint weights in results match fixture."""
        result = score_reasoning_keyword(perfect_response, minimal_fixture)
        fixture_weights = [
            cp["weight"]
            for cp in minimal_fixture["agent_evaluation"]["reasoning_checkpoints"]
        ]
        result_weights = [cp["weight"] for cp in result["reasoning_checkpoints"]]
        assert result_weights == fixture_weights

    def test_reasoning_score_is_percentage(self, minimal_fixture, perfect_response):
        result = score_reasoning_keyword(perfect_response, minimal_fixture)
        assert 0 <= result["reasoning_score_pct"] <= 100

    def test_result_is_explicitly_marked_as_heuristic(self, minimal_fixture, perfect_response):
        result = score_reasoning_keyword(perfect_response, minimal_fixture)
        assert result["judge_method"] == "heuristic"
        assert result["score_reliability"] == "rough_heuristic"
        assert "rough heuristic" in result["score_notes"].lower()

    def test_no_checkpoints_returns_zero(self):
        """Fixture with no reasoning_checkpoints should score 0."""
        fixture = {
            "acceptance_criteria": {"must_include": [], "must_not_include": []},
            "agent_evaluation": {"reasoning_checkpoints": []},
        }
        response = {"reasoning": "anything"}
        result = score_reasoning_keyword(response, fixture)
        assert result["reasoning_score_pct"] == 0

    def test_searches_entire_response_not_just_reasoning(self, minimal_fixture):
        """Heuristic search currently covers the full structured response."""
        response = {
            "reasoning": "I did some calculation.",
            "assumptions": ["ideal gas behavior"],
            "method": "Antoine equation with unit conversion from mmHg to kPa",
            "outputs": {},
        }
        result = score_reasoning_keyword(response, minimal_fixture)
        # "Antoine" appears in method field — must_include should find it
        assert result["must_include"][0]["found"] is True


class TestScoreToolProposals:

    def test_required_proposal_passes_when_expected_tool_is_proposed(self):
        fixture = {
            "agent_evaluation": {
                "tool_proposal_expectation": {
                    "mode": "required",
                    "allowed_tool_names": ["steam_table_lookup"],
                    "allowed_priorities": ["blocking"],
                }
            }
        }
        response = {
            "_meta": {
                "tool_proposals": [
                    {"tool_name": "steam_table_lookup", "priority": "blocking"}
                ]
            }
        }
        result = score_tool_proposals(response, fixture)
        assert result["proposal_score_pct"] == 100.0
        assert result["matched_tool_name"] == "steam_table_lookup"

    def test_required_proposal_fails_when_missing(self):
        fixture = {
            "agent_evaluation": {
                "tool_proposal_expectation": {
                    "mode": "required",
                    "allowed_tool_names": ["steam_table_lookup"],
                }
            }
        }
        result = score_tool_proposals({"_meta": {"tool_proposals": []}}, fixture)
        assert result["proposal_score_pct"] == 0.0

    def test_unnecessary_proposal_fails_when_agent_proposes_any_tool(self):
        fixture = {
            "agent_evaluation": {
                "tool_proposal_expectation": {
                    "mode": "unnecessary",
                }
            }
        }
        response = {
            "_meta": {
                "tool_proposals": [
                    {"tool_name": "steam_table_lookup", "priority": "blocking"}
                ]
            }
        }
        result = score_tool_proposals(response, fixture)
        assert result["proposal_score_pct"] == 0.0

    def test_optional_proposal_accepts_no_proposal(self):
        fixture = {
            "agent_evaluation": {
                "tool_proposal_expectation": {
                    "mode": "optional",
                    "allowed_tool_names": ["steam_table_lookup"],
                }
            }
        }
        result = score_tool_proposals({"_meta": {"tool_proposals": []}}, fixture)
        assert result["proposal_score_pct"] == 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Integration: score_outputs with real fixtures
# ═══════════════════════════════════════════════════════════════════════════

class TestScoringEdgeCases:
    """Edge cases and regression tests."""

    def test_negative_values(self):
        """Negative numbers should work correctly."""
        actual = {"delta_h": {"value": -45.2, "unit": "kJ/mol"}}
        expected = {"delta_h": {"value": -44.0, "unit": "kJ/mol"}}
        tolerances = {"delta_h": {"type": "absolute", "value": 2.0}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["delta_h"]["status"] == "PASS"

    def test_very_small_values(self):
        """Small mole fractions near zero."""
        actual = {"x_trace": {"value": 0.001, "unit": "mol_fraction"}}
        expected = {"x_trace": {"value": 0.0012, "unit": "mol_fraction"}}
        tolerances = {"x_trace": {"type": "absolute", "value": 0.001}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["x_trace"]["status"] == "PASS"

    def test_large_values_relative(self):
        """Large flow rates with relative tolerance."""
        actual = {"Q": {"value": 1_000_500, "unit": "kJ/h"}}
        expected = {"Q": {"value": 1_000_000, "unit": "kJ/h"}}
        tolerances = {"Q": {"type": "relative_percent", "value": 0.1}}

        result = score_outputs(actual, expected, tolerances)
        assert result["output_scores"]["Q"]["status"] == "PASS"  # 0.05% < 0.1%

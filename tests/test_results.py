"""
Tests for result assembly and the propose_tool schema.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_eval import assemble_result


class TestAssembleResult:
    """assemble_result builds the final output record. It should faithfully
    propagate all scores and metadata without mangling them."""

    def test_required_fields_present(self, minimal_fixture, perfect_response):
        output_scores = {
            "output_scores": {},
            "numeric_score": 1,
            "numeric_possible": 1,
            "numeric_pct": 100.0,
        }
        reasoning_scores = {
            "reasoning_checkpoints": [],
            "reasoning_score_pct": 100.0,
        }
        result = assemble_result(
            minimal_fixture, perfect_response, output_scores, reasoning_scores, layer=1
        )

        assert "run_id" in result
        assert "eval_id" in result
        assert "fixture_id" in result
        assert "fixture_version" in result
        assert "layer" in result
        assert "timestamp" in result
        assert "git_sha" in result
        assert "agent_meta" in result
        assert "scores" in result
        assert "agent_response" in result
        assert "tool_proposals" in result
        assert "artifacts" in result

    def test_fixture_id_propagated(self, minimal_fixture, perfect_response):
        perfect_response["_meta"] = {"run_id": "run-123"}
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
        )
        assert result["run_id"] == "run-123"
        assert result["fixture_id"] == "test-fixture-01"
        assert result["fixture_version"] == "1.0.0"

    def test_layer_propagated(self, minimal_fixture, perfect_response):
        for layer in [1, 2, 3]:
            result = assemble_result(
                minimal_fixture, perfect_response,
                {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
                {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
                layer=layer,
            )
            assert result["layer"] == layer

    def test_overall_pct_weighted(self, minimal_fixture, perfect_response):
        """Overall = 60% numeric + 40% reasoning."""
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 1, "numeric_possible": 1, "numeric_pct": 100.0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 50.0},
        )
        # 100 * 0.6 + 50 * 0.4 = 60 + 20 = 80
        assert result["scores"]["overall_pct"] == 80.0

    def test_overall_pct_all_zero(self, minimal_fixture, perfect_response):
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 1, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
        )
        assert result["scores"]["overall_pct"] == 0

    def test_overall_pct_includes_tool_proposal_quality_when_scored(self, minimal_fixture, perfect_response):
        proposal_scores = {
            "proposal_score": 1,
            "proposal_possible": 1,
            "proposal_score_pct": 100.0,
        }
        result = assemble_result(
            minimal_fixture,
            perfect_response,
            {"output_scores": {}, "numeric_score": 1, "numeric_possible": 1, "numeric_pct": 100.0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 50.0},
            proposal_scores,
        )
        assert result["scores"]["tool_proposals"]["proposal_score_pct"] == 100.0
        assert result["scores"]["overall_pct"] == 82.5

    def test_agent_response_fields(self, minimal_fixture, perfect_response):
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
        )
        ar = result["agent_response"]
        assert "reasoning" in ar
        assert "assumptions" in ar
        assert "method" in ar
        assert "outputs" in ar
        assert "confidence" in ar
        assert "skill_notes" in ar
        assert ar["confidence"] == 0.95

    def test_tool_proposals_empty_by_default(self, minimal_fixture, perfect_response):
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
        )
        assert result["tool_proposals"] == []
        assert result["artifacts"] == []

    def test_tool_proposals_propagated(self, minimal_fixture):
        """If the response has tool proposals in _meta, they should appear in result."""
        response = {
            "reasoning": "needed a tool",
            "assumptions": [],
            "method": "",
            "outputs": {},
            "confidence": 0.5,
            "skill_notes": "",
            "_meta": {
                "tool_proposals": [
                    {
                        "tool_name": "steam_table_lookup",
                        "reason": "Need steam properties",
                        "priority": "blocking",
                        "_turn": 1,
                    }
                ],
                "artifacts": [
                    {
                        "artifact_id": "artifact-123",
                        "artifact_type": "tool",
                        "status": "proposed",
                    }
                ],
            },
        }
        result = assemble_result(
            minimal_fixture, response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
        )
        assert len(result["tool_proposals"]) == 1
        assert result["tool_proposals"][0]["tool_name"] == "steam_table_lookup"
        assert result["tool_proposals"][0]["priority"] == "blocking"
        assert result["artifacts"][0]["artifact_id"] == "artifact-123"

    def test_eval_id_contains_fixture_and_layer(self, minimal_fixture, perfect_response):
        result = assemble_result(
            minimal_fixture, perfect_response,
            {"output_scores": {}, "numeric_score": 0, "numeric_possible": 0, "numeric_pct": 0},
            {"reasoning_checkpoints": [], "reasoning_score_pct": 0},
            layer=3,
        )
        assert "test-fixture-01" in result["eval_id"]
        assert "L3" in result["eval_id"]


class TestProposeToolSchema:
    """Verify the propose_tool tool definition is well-formed."""

    def test_schema_structure(self):
        from providers import PROPOSE_TOOL_TOOL

        assert PROPOSE_TOOL_TOOL["name"] == "propose_tool"
        schema = PROPOSE_TOOL_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert set(schema["required"]) == {"tool_name", "reason", "priority"}

    def test_priority_enum(self):
        from providers import PROPOSE_TOOL_TOOL

        priority = PROPOSE_TOOL_TOOL["input_schema"]["properties"]["priority"]
        assert set(priority["enum"]) == {"blocking", "would_improve", "nice_to_have"}

    def test_interface_has_inputs_and_outputs(self):
        from providers import PROPOSE_TOOL_TOOL

        iface = PROPOSE_TOOL_TOOL["input_schema"]["properties"]["interface"]
        assert "inputs" in iface["properties"]
        assert "outputs" in iface["properties"]

    def test_tool_present_in_loop(self):
        """propose_tool should be one of the tools in the L3 tool loop."""
        from providers import PYTHON_EXECUTE_TOOL, PROPOSE_TOOL_TOOL

        # Both tools should be importable and have distinct names
        assert PYTHON_EXECUTE_TOOL["name"] != PROPOSE_TOOL_TOOL["name"]
        assert PYTHON_EXECUTE_TOOL["name"] == "python_execute"
        assert PROPOSE_TOOL_TOOL["name"] == "propose_tool"

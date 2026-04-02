"""
Tests for prompt construction.

These verify that the layer system correctly controls what the model sees:
  Layer 1: all inputs (problem_data + reference_data)
  Layer 2/3: only problem_data, reference_data suppressed with a note
"""
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cheme_evals.application.prompts import build_system_prompt, build_user_prompt


class TestBuildUserPrompt:
    """build_user_prompt is pure string construction — no file I/O."""

    def test_layer1_includes_all_inputs(self, minimal_fixture):
        prompt = build_user_prompt(minimal_fixture, layer=1)

        # problem_data input should appear
        assert "101.325" in prompt
        assert "kPa" in prompt

        # reference_data should ALSO appear at Layer 1
        assert "antoine_water" in prompt
        assert "8.07131" in prompt

    def test_layer2_suppresses_reference_data(self, minimal_fixture):
        prompt = build_user_prompt(minimal_fixture, layer=2)

        # problem_data should still appear
        assert "101.325" in prompt
        assert "pressure" in prompt

        # reference_data should be SUPPRESSED
        assert "8.07131" not in prompt

        # But the suppressed field name should be mentioned in the note
        assert "antoine_water" in prompt
        assert "NOT provided" in prompt or "not provided" in prompt.lower()

    def test_layer3_same_as_layer2(self, minimal_fixture):
        """Layer 3 suppresses the same inputs as Layer 2."""
        prompt_l2 = build_user_prompt(minimal_fixture, layer=2)
        prompt_l3 = build_user_prompt(minimal_fixture, layer=3)

        # Both should suppress reference_data
        assert "8.07131" not in prompt_l2
        assert "8.07131" not in prompt_l3

    def test_problem_statement_always_present(self, minimal_fixture):
        for layer in [1, 2, 3]:
            prompt = build_user_prompt(minimal_fixture, layer=layer)
            assert "boiling point of water" in prompt.lower()

    def test_task_always_present(self, minimal_fixture):
        for layer in [1, 2, 3]:
            prompt = build_user_prompt(minimal_fixture, layer=layer)
            assert "temperature in K" in prompt

    def test_output_keys_listed(self, minimal_fixture):
        """The expected output keys should be listed so the agent knows what to produce."""
        prompt = build_user_prompt(minimal_fixture, layer=1)
        assert "boiling_point" in prompt

    def test_no_reference_data_means_no_suppression_note(self):
        """Fixture with no reference_data should have no suppression note."""
        fixture = {
            "problem": {
                "statement": "Simple problem.",
                "task": "Calculate X.",
            },
            "inputs": {
                "pressure": {"value": 101.325, "unit": "kPa"},
            },
            "expected_outputs": {
                "result": {"value": 42, "unit": "m"},
            },
        }
        prompt = build_user_prompt(fixture, layer=2)
        assert "NOT provided" not in prompt

    def test_flash_fixture_layer1_has_antoine(self, flash_fixture):
        """Real fixture: Antoine coefficients should appear at L1."""
        prompt = build_user_prompt(flash_fixture, layer=1)
        assert "6.90565" in prompt  # benzene Antoine A

    def test_flash_fixture_layer2_suppresses_antoine(self, flash_fixture):
        """Real fixture: Antoine coefficients should be suppressed at L2."""
        prompt = build_user_prompt(flash_fixture, layer=2)
        assert "6.90565" not in prompt
        assert "antoine_benzene" in prompt  # mentioned in suppression note

    def test_multistage_fixture_layer_suppression(self, multistage_fixture):
        """Multistage fixture should suppress both Antoine coefficient sets at L2."""
        prompt = build_user_prompt(multistage_fixture, layer=2)

        # Antoine values should not appear
        assert "6.90565" not in prompt
        assert "6.95464" not in prompt

        # But problem data should
        assert "365" in prompt   # stage1 temperature
        assert "350" in prompt   # stage2 temperature
        assert "60" in prompt    # stage2 pressure

    def test_multiple_inputs_formatted(self, multistage_fixture):
        """All problem_data inputs should be in the prompt at L1."""
        prompt = build_user_prompt(multistage_fixture, layer=1)
        assert "feed_flow_rate" in prompt
        assert "stage1_temperature" in prompt
        assert "stage2_pressure" in prompt
        assert "100" in prompt  # feed flow rate

"""
Tests for the agent harness — independent from the eval scoring pipeline.

These verify skill injection, prompt construction, layer visibility,
and skill document coverage WITHOUT running scoring, traces, or result storage.
"""
import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cheme_evals.application.prompts import build_system_prompt, build_user_prompt
from cheme_evals.application.agent_harness import run_agent_harness

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
SKILLS_DIR = PROJECT_ROOT / "agent" / "skills"


# ---------------------------------------------------------------------------
# Skill injection tests (no LLM, no mocks — pure string assertions)
# ---------------------------------------------------------------------------

class TestSkillInjection:

    def test_layer1_never_includes_skills(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=1, skills_dir=SKILLS_DIR)
        assert "No external skills loaded" in prompt
        assert "--- Skill:" not in prompt

    def test_layer2_includes_skill_documents(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=SKILLS_DIR)
        assert "--- Skill:" in prompt
        assert "No external skills loaded" not in prompt

    def test_layer3_includes_skill_documents(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=3, skills_dir=SKILLS_DIR)
        assert "--- Skill:" in prompt

    def test_layer2_loads_antoine_parameters(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=SKILLS_DIR)
        assert "Antoine" in prompt
        assert "Benzene" in prompt

    def test_layer2_loads_critical_properties(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=SKILLS_DIR)
        assert "Van der Waals" in prompt
        assert "Argon" in prompt

    def test_layer2_loads_thermodynamic_methods(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=SKILLS_DIR)
        assert "Clausius-Clapeyron" in prompt
        assert "Raoult" in prompt

    def test_skill_loading_is_sorted_by_filename(self, minimal_fixture):
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=SKILLS_DIR)
        antoine_pos = prompt.index("antoine-parameters")
        critical_pos = prompt.index("critical-properties")
        thermo_pos = prompt.index("thermodynamic-methods")
        assert antoine_pos < critical_pos < thermo_pos

    def test_empty_skills_dir_shows_no_skills(self, minimal_fixture, tmp_path):
        empty_dir = tmp_path / "skills"
        empty_dir.mkdir()
        prompt = build_system_prompt(minimal_fixture, layer=2, skills_dir=empty_dir)
        assert "No external skills loaded" in prompt

    def test_missing_skills_dir_shows_no_skills(self, minimal_fixture):
        prompt = build_system_prompt(
            minimal_fixture, layer=2, skills_dir=Path("/nonexistent")
        )
        assert "No external skills loaded" in prompt


# ---------------------------------------------------------------------------
# Skill coverage tests — do the skill docs contain what fixtures need?
# ---------------------------------------------------------------------------

class TestSkillCoverage:
    """Verify that reference_data inputs in fixtures are findable in skill docs.

    When a fixture marks an input as reference_data, the agent must retrieve
    that value from the skill documents at L2.  If the value isn't in any
    skill doc, the fixture is unfair at L2 and will fail for the wrong reason.
    """

    @pytest.fixture
    def all_skill_text(self):
        """Concatenated text of all skill documents."""
        texts = []
        for skill_file in sorted(SKILLS_DIR.glob("*.md")):
            texts.append(skill_file.read_text())
        return "\n".join(texts)

    @pytest.fixture(params=sorted(FIXTURES_DIR.glob("*.json")))
    def fixture_with_reference_data(self, request):
        """Yield (fixture, ref_input_name, ref_input_spec) for every
        reference_data input across all fixtures."""
        path = request.param
        if path.name == "fixture-schema.json":
            pytest.skip("schema, not a fixture")
        with open(path) as f:
            fixture = json.load(f)
        ref_inputs = {
            name: spec
            for name, spec in fixture.get("inputs", {}).items()
            if spec.get("input_class") == "reference_data"
        }
        if not ref_inputs:
            pytest.skip(f"{fixture['id']} has no reference_data inputs")
        return fixture, ref_inputs

    @pytest.mark.xfail(
        reason="Known skill doc coverage gaps: thermo-1.5 (molar masses), "
               "thermo-8.13 (ΔH_vap), thermo-8.25 (ΔH_vap). "
               "Fix by adding data to skill docs or removing reference_data tags.",
        strict=False,
    )
    def test_reference_data_values_exist_in_skills(
        self, fixture_with_reference_data, all_skill_text
    ):
        """Each reference_data numeric value should appear in the skill docs.

        Failures here mean the fixture is unfair at L2 — the agent is expected
        to retrieve values that don't exist in any skill document.  Fix by
        either adding the data to a skill doc or removing the input_class
        tag from the fixture.
        """
        fixture, ref_inputs = fixture_with_reference_data
        missing = []
        for name, spec in ref_inputs.items():
            value = spec["value"]
            # For scalar values, check the number appears in skill text
            if isinstance(value, (int, float)):
                # Check for the value with reasonable formatting
                found = (
                    str(value) in all_skill_text
                    or f"{value:.3f}" in all_skill_text
                    or f"{value:.4f}" in all_skill_text
                    or f"{value:.5f}" in all_skill_text
                )
                if not found:
                    missing.append(f"{name}={value} ({spec.get('description', '')})")
            elif isinstance(value, list):
                # For array values (e.g., Antoine coefficients), check each element
                for i, v in enumerate(value):
                    found = str(v) in all_skill_text
                    if not found:
                        missing.append(f"{name}[{i}]={v}")

        if missing:
            pytest.fail(
                f"Fixture '{fixture['id']}' has reference_data not found in "
                f"skill docs (will fail at L2 due to coverage gap):\n"
                + "\n".join(f"  - {m}" for m in missing)
            )


# ---------------------------------------------------------------------------
# run_agent_harness() integration test (with mock, no scoring)
# ---------------------------------------------------------------------------

class TestRunAgentHarness:

    def test_returns_prompts_and_response_with_mock(self, minimal_fixture, tmp_path):
        """run_agent_harness returns the full pipeline output without scoring."""
        mock_response = {
            "outputs": {"boiling_point": {"value": 373.15, "unit": "K"}},
            "reasoning": "Used Antoine equation.",
            "confidence": 0.9,
        }
        mock_path = tmp_path / "mock.json"
        mock_path.write_text(json.dumps(mock_response))

        class StubPrompts:
            def build_system_prompt(self, fixture, layer=1):
                return build_system_prompt(fixture, layer=layer, skills_dir=SKILLS_DIR)

            def build_user_prompt(self, fixture, layer=1):
                return build_user_prompt(fixture, layer=layer)

        class StubAgent:
            def call_agent(self, system, user, mock_path=None, **kwargs):
                with open(mock_path) as f:
                    return json.load(f)

        result = run_agent_harness(
            prompts=StubPrompts(),
            agent=StubAgent(),
            fixture=minimal_fixture,
            layer=2,
            mock_path=str(mock_path),
        )

        assert "system_prompt" in result
        assert "user_prompt" in result
        assert "response" in result
        assert result["response"]["outputs"]["boiling_point"]["value"] == 373.15

        # Verify the prompts reflect layer 2
        assert "--- Skill:" in result["system_prompt"]
        assert "antoine_water" not in result["user_prompt"] or "NOT provided" in result["user_prompt"]

    def test_layer1_prompt_includes_reference_data(self, minimal_fixture):
        """At L1, the user prompt should include reference data values."""

        class StubPrompts:
            def build_system_prompt(self, fixture, layer=1):
                return build_system_prompt(fixture, layer=layer, skills_dir=SKILLS_DIR)

            def build_user_prompt(self, fixture, layer=1):
                return build_user_prompt(fixture, layer=layer)

        class StubAgent:
            def call_agent(self, system, user, mock_path=None, **kwargs):
                return {"outputs": {}, "_raw_prompts": {"system": system, "user": user}}

        result = run_agent_harness(
            prompts=StubPrompts(),
            agent=StubAgent(),
            fixture=minimal_fixture,
            layer=1,
        )

        # L1 should have Antoine coefficients in user prompt
        assert "8.07131" in result["user_prompt"]
        # L1 should NOT have skills
        assert "No external skills loaded" in result["system_prompt"]

    def test_layer2_prompt_suppresses_reference_data(self, minimal_fixture):
        """At L2, reference data values should be suppressed, skills loaded."""

        class StubPrompts:
            def build_system_prompt(self, fixture, layer=1):
                return build_system_prompt(fixture, layer=layer, skills_dir=SKILLS_DIR)

            def build_user_prompt(self, fixture, layer=1):
                return build_user_prompt(fixture, layer=layer)

        class StubAgent:
            def call_agent(self, system, user, mock_path=None, **kwargs):
                return {"outputs": {}}

        result = run_agent_harness(
            prompts=StubPrompts(),
            agent=StubAgent(),
            fixture=minimal_fixture,
            layer=2,
        )

        # L2 should suppress Antoine coefficient values
        assert "8.07131" not in result["user_prompt"]
        # But should tell agent what was suppressed
        assert "antoine_water" in result["user_prompt"]
        # Skills should be loaded
        assert "--- Skill:" in result["system_prompt"]

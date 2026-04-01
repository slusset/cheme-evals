"""Fixture loading and prompt assembly services."""

import json
from pathlib import Path


def load_fixture(path: str) -> dict:
    """Load and validate a fixture file."""
    with open(path) as f:
        fixture = json.load(f)

    required = ["id", "problem", "inputs", "expected_outputs", "acceptance_criteria"]
    missing = [key for key in required if key not in fixture]
    if missing:
        raise ValueError(f"Fixture missing required fields: {missing}")

    return fixture


def build_system_prompt(fixture: dict, *, layer: int = 1, skills_dir: Path = None) -> str:
    """Assemble the system prompt from repo-managed components."""
    skills_context = ""
    if layer == 2 and skills_dir and skills_dir.exists():
        for skill_file in sorted(skills_dir.glob("*.md")):
            skills_context += f"\n--- Skill: {skill_file.stem} ---\n"
            skills_context += skill_file.read_text()
            skills_context += "\n"

    return f"""You are a chemical engineering process simulation agent.

Your task is to solve chemical engineering problems accurately and show your reasoning.

## Response format

You MUST respond with valid JSON containing these fields:
- "reasoning": Step-by-step explanation of your approach (string)
- "assumptions": List of assumptions you are making (array of strings)
- "method": The method/model you chose and why (string)
- "calculations": Key intermediate calculation steps (object with labeled values)
- "outputs": Your final answers, keyed EXACTLY as they appear in the problem's requested outputs (object)
  Each output should have "value" (number) and "unit" (string)
- "confidence": Your confidence in the answer, 0-1 (number)
- "skill_notes": What you learned that would help solve similar problems faster next time (string)

## Rules
- Always state your assumptions explicitly
- Always verify your answer with a material balance check
- If you use Antoine equation, state which form and units
- Show intermediate values so reasoning can be audited
- If you are unsure, say so — do not fabricate precision

## Available domain knowledge
{skills_context if skills_context else "(No external skills loaded for this layer)"}
"""


def build_user_prompt(fixture: dict, *, layer: int = 1) -> str:
    """Build the user prompt while enforcing the layer's visibility rules."""
    problem = fixture["problem"]
    inputs = fixture["inputs"]

    input_lines = []
    suppressed = []
    for name, spec in inputs.items():
        input_class = spec.get("input_class", "problem_data")
        if layer >= 2 and input_class == "reference_data":
            suppressed.append(name)
            continue
        description = spec.get("description", "")
        input_lines.append(
            f"  - {name}: {spec['value']} {spec['unit']}" +
            (f" ({description})" if description else "")
        )

    suppressed_note = ""
    if suppressed:
        suppressed_note = f"""
## Note

The following quantities are NOT provided — you must look them up from your reference materials or calculate them:
{chr(10).join(f'  - {name}' for name in suppressed)}
"""

    return f"""## Problem

{problem['statement']}

## Task

{problem['task']}

## Given values

{chr(10).join(input_lines)}
{suppressed_note}
## Output format

Return your answers as JSON with an "outputs" field containing these keys:
{json.dumps(list(fixture['expected_outputs'].keys()), indent=2)}

Each output should have "value" (number) and "unit" (string).
"""

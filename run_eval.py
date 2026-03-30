#!/usr/bin/env python3
"""
ChemE Agent Eval Runner

Takes a fixture (frozen test case), sends the problem to an agent,
captures the response, extracts answers, and scores against expected outputs.

Usage:
    python run_eval.py --fixture fixtures/flash-distillation-01.json
    python run_eval.py --fixture fixtures/flash-distillation-01.json --mock
    python run_eval.py --all
"""

import json
import os
import sys
import time
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HARNESS_ROOT = Path(__file__).resolve().parent
FIXTURES_DIR = HARNESS_ROOT / "fixtures"
MOCKS_DIR = HARNESS_ROOT / "mocks"
RESULTS_DIR = HARNESS_ROOT / "results"
SKILLS_DIR = HARNESS_ROOT / "agent" / "skills"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_git_sha() -> str:
    """Get current git commit SHA for traceability."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=HARNESS_ROOT
        )
        return result.stdout.strip() or "no-git"
    except Exception:
        return "no-git"


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

def load_fixture(path: str) -> dict:
    """Load and validate a fixture file."""
    with open(path) as f:
        fixture = json.load(f)

    required = ["id", "problem", "inputs", "expected_outputs", "acceptance_criteria"]
    missing = [k for k in required if k not in fixture]
    if missing:
        raise ValueError(f"Fixture missing required fields: {missing}")

    return fixture


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_system_prompt(fixture: dict) -> str:
    """
    Assemble the system prompt from version-controlled components.
    This is the agent's 'starting state' — everything it knows.
    """
    # Load skill documents if they exist
    skills_context = ""
    if SKILLS_DIR.exists():
        for skill_file in sorted(SKILLS_DIR.glob("*.md")):
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

{skills_context}

Respond ONLY with the JSON object. No markdown fences, no preamble."""


def build_user_prompt(fixture: dict) -> str:
    """Build the user message from the fixture's problem and inputs."""
    problem = fixture["problem"]
    inputs = fixture["inputs"]

    input_lines = []
    for name, spec in inputs.items():
        desc = spec.get("description", "")
        input_lines.append(f"  - {name}: {spec['value']} {spec['unit']}" +
                           (f" ({desc})" if desc else ""))

    return f"""## Problem

{problem['statement']}

## Task

{problem['task']}

## Given values

{chr(10).join(input_lines)}

## Output format

Return your answers as JSON with an "outputs" field containing these keys:
{json.dumps(list(fixture['expected_outputs'].keys()), indent=2)}

Each output should have "value" (number) and "unit" (string).
"""


# ---------------------------------------------------------------------------
# Agent execution
# ---------------------------------------------------------------------------

from providers import PROVIDERS, resolve_provider, get_api_key


def call_agent(system_prompt: str, user_prompt: str, mock_path: str = None,
               provider_name: str = None, model: str = None) -> dict:
    """
    Send the problem to the agent and get a response.
    If mock_path is provided, return the recorded response instead.
    """
    if mock_path and os.path.exists(mock_path):
        print(f"  [mock] Loading from {mock_path}")
        with open(mock_path) as f:
            return json.load(f)

    # Resolve provider + model
    provider_name = resolve_provider(provider_name)
    provider = PROVIDERS[provider_name]
    model = model or provider["default_model"]
    api_key = get_api_key(provider_name)

    print(f"  [live] Calling {provider_name} ({model})...")
    start_time = time.time()

    raw = provider["call"](
        system=system_prompt,
        user=user_prompt,
        model=model,
        temperature=0,
        max_tokens=4096,
        api_key=api_key,
    )

    elapsed = time.time() - start_time

    # Parse the JSON response
    # Strip markdown fences if present
    cleaned = raw["text"].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        response = json.loads(cleaned)
    except json.JSONDecodeError as e:
        response = {
            "parse_error": str(e),
            "raw_text": raw["text"],
            "outputs": {}
        }

    response["_meta"] = {
        "provider": provider_name,
        "model": raw["model"],
        "temperature": 0,
        "elapsed_seconds": round(elapsed, 2),
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
    }

    return response


def save_mock(response: dict, fixture_id: str):
    """Save a response as a mock for future deterministic replay."""
    mock_dir = MOCKS_DIR / "agent-responses"
    mock_dir.mkdir(parents=True, exist_ok=True)
    mock_path = mock_dir / f"{fixture_id}.json"
    with open(mock_path, "w") as f:
        json.dump(response, f, indent=2)
    print(f"  [mock] Saved to {mock_path}")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_outputs(actual: dict, expected: dict, tolerances: dict) -> dict:
    """
    Compare agent outputs against expected values.
    Returns a detailed score report.
    """
    results = {}
    total_score = 0
    total_possible = 0

    for key, expected_spec in expected.items():
        total_possible += 1
        expected_val = expected_spec["value"]
        expected_unit = expected_spec["unit"]

        # Find the agent's answer
        actual_spec = actual.get(key, {})
        if not actual_spec:
            results[key] = {
                "status": "MISSING",
                "expected": expected_val,
                "actual": None,
                "score": 0,
                "note": "Agent did not produce this output"
            }
            continue

        actual_val = actual_spec.get("value")
        if actual_val is None:
            results[key] = {
                "status": "MISSING",
                "expected": expected_val,
                "actual": None,
                "score": 0,
                "note": "Agent output has no 'value' field"
            }
            continue

        # Get tolerance for this output
        tol = tolerances.get(key, {"type": "relative_percent", "value": 5.0})
        tol_type = tol["type"]
        tol_val = tol["value"]

        # Calculate error
        if tol_type == "absolute":
            error = abs(actual_val - expected_val)
            within_tolerance = error <= tol_val
            error_display = f"{error:.4f} (tolerance: ±{tol_val})"
        elif tol_type == "relative_percent":
            if expected_val == 0:
                error = abs(actual_val)
                within_tolerance = error < 1e-6
                error_display = f"expected 0, got {actual_val}"
            else:
                error = abs((actual_val - expected_val) / expected_val) * 100
                within_tolerance = error <= tol_val
                error_display = f"{error:.2f}% (tolerance: ±{tol_val}%)"
        else:
            within_tolerance = False
            error_display = f"Unknown tolerance type: {tol_type}"

        score = 1 if within_tolerance else 0
        total_score += score

        results[key] = {
            "status": "PASS" if within_tolerance else "FAIL",
            "expected": expected_val,
            "actual": actual_val,
            "unit": expected_unit,
            "error": error_display,
            "score": score,
        }

    return {
        "output_scores": results,
        "numeric_score": total_score,
        "numeric_possible": total_possible,
        "numeric_pct": round(total_score / total_possible * 100, 1) if total_possible > 0 else 0,
    }


def score_reasoning(response: dict, fixture: dict) -> dict:
    """
    Score the agent's reasoning process (not just the final answer).
    This checks the 'must_include' and 'must_not_include' criteria,
    and the reasoning checkpoints.

    Note: This is a simple keyword/heuristic check. A more sophisticated
    version would use an LLM-as-judge pattern.
    """
    criteria = fixture.get("acceptance_criteria", {})
    reasoning_text = json.dumps(response).lower()

    # Check must_include (simple keyword presence)
    must_include_results = []
    for item in criteria.get("must_include", []):
        # Check for key phrases from the requirement
        keywords = item.lower().split()
        # Require at least half the significant words to appear
        significant = [w for w in keywords if len(w) > 3]
        found = sum(1 for w in significant if w in reasoning_text)
        passed = found >= len(significant) * 0.5 if significant else True
        must_include_results.append({
            "requirement": item,
            "found": passed,
        })

    # Check must_not_include
    must_not_results = []
    for item in criteria.get("must_not_include", []):
        keywords = item.lower().split()
        significant = [w for w in keywords if len(w) > 3]
        found = sum(1 for w in significant if w in reasoning_text)
        violated = found >= len(significant) * 0.7 if significant else False
        must_not_results.append({
            "requirement": item,
            "violated": violated,
        })

    # Reasoning checkpoints (from agent_evaluation)
    checkpoints = fixture.get("agent_evaluation", {}).get("reasoning_checkpoints", [])
    checkpoint_results = []
    weighted_score = 0
    total_weight = 0
    for cp in checkpoints:
        # Simple heuristic — check if key terms appear in reasoning
        terms = cp["checkpoint"].lower().split()
        significant = [w for w in terms if len(w) > 4]
        found = sum(1 for w in significant if w in reasoning_text)
        passed = found >= len(significant) * 0.4 if significant else True
        weight = cp.get("weight", 0.1)
        total_weight += weight
        if passed:
            weighted_score += weight
        checkpoint_results.append({
            "checkpoint": cp["checkpoint"],
            "weight": weight,
            "found": passed,
        })

    return {
        "must_include": must_include_results,
        "must_not_include": must_not_results,
        "reasoning_checkpoints": checkpoint_results,
        "reasoning_score_pct": round(weighted_score / total_weight * 100, 1) if total_weight > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------

def assemble_result(fixture: dict, response: dict, output_scores: dict, reasoning_scores: dict) -> dict:
    """Assemble the full eval result with traceability metadata."""
    return {
        "eval_id": f"{fixture['id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "fixture_id": fixture["id"],
        "fixture_version": fixture.get("version", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": get_git_sha(),
        "agent_meta": response.get("_meta", {}),
        "scores": {
            "numeric": output_scores,
            "reasoning": reasoning_scores,
            "overall_pct": round(
                (output_scores["numeric_pct"] * 0.6 + reasoning_scores["reasoning_score_pct"] * 0.4),
                1
            ),
        },
        "agent_response": {
            "reasoning": response.get("reasoning", ""),
            "assumptions": response.get("assumptions", []),
            "method": response.get("method", ""),
            "outputs": response.get("outputs", {}),
            "confidence": response.get("confidence", None),
            "skill_notes": response.get("skill_notes", ""),
        },
    }


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def print_results(result: dict):
    """Print a human-readable summary of the eval results."""
    scores = result["scores"]
    numeric = scores["numeric"]
    reasoning = scores["reasoning"]

    print("\n" + "=" * 60)
    print(f"  EVAL: {result['fixture_id']} v{result['fixture_version']}")
    print(f"  Time: {result['timestamp']}")
    print(f"  Git:  {result['git_sha']}")
    print("=" * 60)

    # Numeric outputs
    print(f"\n  NUMERIC ACCURACY: {numeric['numeric_score']}/{numeric['numeric_possible']} "
          f"({numeric['numeric_pct']}%)")
    print("  " + "-" * 40)
    for key, r in numeric["output_scores"].items():
        status = "PASS" if r["status"] == "PASS" else "FAIL"
        icon = "  ✓" if status == "PASS" else "  ✗"
        print(f"  {icon} {key}")
        print(f"      expected: {r['expected']}, actual: {r.get('actual', 'MISSING')}")
        if "error" in r:
            print(f"      error: {r['error']}")

    # Reasoning
    print(f"\n  REASONING: {reasoning['reasoning_score_pct']}%")
    print("  " + "-" * 40)
    for cp in reasoning.get("reasoning_checkpoints", []):
        icon = "  ✓" if cp["found"] else "  ✗"
        print(f"  {icon} {cp['checkpoint']} (weight: {cp['weight']})")

    # Must include
    for mi in reasoning.get("must_include", []):
        icon = "  ✓" if mi["found"] else "  ✗"
        print(f"  {icon} Must include: {mi['requirement']}")

    # Must not include
    for mn in reasoning.get("must_not_include", []):
        icon = "  ✓" if not mn["violated"] else "  ✗"
        print(f"  {icon} Must NOT: {mn['requirement']}" +
              (" [VIOLATED]" if mn["violated"] else ""))

    # Overall
    print(f"\n  OVERALL SCORE: {scores['overall_pct']}%")
    print(f"    (60% numeric accuracy + 40% reasoning quality)")

    # Agent confidence
    confidence = result["agent_response"].get("confidence")
    if confidence is not None:
        print(f"\n  AGENT SELF-ASSESSED CONFIDENCE: {confidence}")
        calibration = abs(confidence * 100 - scores["overall_pct"])
        print(f"  CALIBRATION ERROR: {calibration:.1f} points")

    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_fixture(fixture_path: str, use_mock: bool = False, save_mock_flag: bool = False,
                provider_name: str = None, model: str = None):
    """Run a single fixture evaluation."""
    print(f"\nLoading fixture: {fixture_path}")
    fixture = load_fixture(fixture_path)
    print(f"  ID: {fixture['id']}")
    print(f"  Problem: {fixture['problem']['statement'][:80]}...")

    # Build prompts
    system_prompt = build_system_prompt(fixture)
    user_prompt = build_user_prompt(fixture)

    # Determine mock path
    mock_path = None
    if use_mock:
        mock_path = str(MOCKS_DIR / "agent-responses" / f"{fixture['id']}.json")

    # Call agent
    response = call_agent(system_prompt, user_prompt, mock_path,
                          provider_name=provider_name, model=model)

    # Save mock if requested
    if save_mock_flag and not use_mock:
        save_mock(response, fixture["id"])

    # Score
    agent_outputs = response.get("outputs", {})
    tolerances = fixture.get("acceptance_criteria", {}).get("tolerances", {})

    output_scores = score_outputs(agent_outputs, fixture["expected_outputs"], tolerances)
    reasoning_scores = score_reasoning(response, fixture)

    # Assemble and save result
    result = assemble_result(fixture, response, output_scores, reasoning_scores)

    result_filename = f"{fixture['id']}-{get_git_sha()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    result_path = RESULTS_DIR / result_filename
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    # Display
    print_results(result)
    print(f"\n  Result saved: {result_path}")

    return result


def main():
    import argparse
    available_providers = ", ".join(sorted(PROVIDERS))
    parser = argparse.ArgumentParser(description="ChemE Agent Eval Runner")
    parser.add_argument("--fixture", type=str, help="Path to a single fixture JSON file")
    parser.add_argument("--all", action="store_true", help="Run all fixtures in fixtures/")
    parser.add_argument("--mock", action="store_true", help="Use mocked responses instead of live API")
    parser.add_argument("--save-mock", action="store_true", help="Save live responses as mocks for future replay")
    parser.add_argument("--provider", type=str, default=None,
                        help=f"LLM provider ({available_providers}). Default: anthropic")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name override (default: provider's default model)")
    args = parser.parse_args()

    if not args.fixture and not args.all:
        parser.error("one of --fixture or --all is required")

    run_kwargs = dict(
        use_mock=args.mock,
        save_mock_flag=args.save_mock,
        provider_name=args.provider,
        model=args.model,
    )

    if args.fixture:
        run_fixture(args.fixture, **run_kwargs)
    else:
        fixtures = sorted(FIXTURES_DIR.glob("*.json"))
        if not fixtures:
            print("No fixtures found in fixtures/")
            sys.exit(1)
        print(f"Running {len(fixtures)} fixtures...")
        results = []
        for fp in fixtures:
            r = run_fixture(str(fp), **run_kwargs)
            results.append(r)
        # Summary
        print("\n\n" + "=" * 60)
        print("  SUITE SUMMARY")
        print("=" * 60)
        for r in results:
            print(f"  {r['fixture_id']}: {r['scores']['overall_pct']}%")
        avg = sum(r["scores"]["overall_pct"] for r in results) / len(results)
        print(f"\n  Average: {avg:.1f}%")


if __name__ == "__main__":
    main()

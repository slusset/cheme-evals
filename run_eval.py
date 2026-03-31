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
EXPERIMENT_LOG = RESULTS_DIR / "experiments.jsonl"


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

def build_system_prompt(fixture: dict, layer: int = 1) -> str:
    """
    Assemble the system prompt from version-controlled components.
    This is the agent's 'starting state' — everything it knows.

    Layer controls what the agent has access to:
      Layer 1: No skills — pure reasoning with all constants embedded in inputs
      Layer 2: Skills loaded — agent retrieves reference data from domain docs
      Layer 3: No skills — agent must use tools to find data (future)
    """
    # Load skill documents at Layer 2 only
    skills_context = ""
    if layer == 2 and SKILLS_DIR.exists():
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


def build_user_prompt(fixture: dict, layer: int = 1) -> str:
    """
    Build the user message from the fixture's problem and inputs.

    Layer controls which inputs are provided:
      Layer 1: All inputs (problem_data + reference_data)
      Layer 2: Only problem_data — reference_data must come from skills
      Layer 3: Only problem_data — reference_data must come from tools
    """
    problem = fixture["problem"]
    inputs = fixture["inputs"]

    input_lines = []
    suppressed = []
    for name, spec in inputs.items():
        input_class = spec.get("input_class", "problem_data")
        if layer >= 2 and input_class == "reference_data":
            suppressed.append(name)
            continue
        desc = spec.get("description", "")
        input_lines.append(f"  - {name}: {spec['value']} {spec['unit']}" +
                           (f" ({desc})" if desc else ""))

    # Build the suppressed data note for Layer 2/3
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


# ---------------------------------------------------------------------------
# Agent execution
# ---------------------------------------------------------------------------

from providers import PROVIDERS, resolve_provider, get_api_key, call_anthropic_tool_loop


def call_agent(system_prompt: str, user_prompt: str, mock_path: str = None,
               provider_name: str = None, model: str = None,
               layer: int = 1) -> dict:
    """
    Send the problem to the agent and get a response.
    If mock_path is provided, return the recorded response instead.
    Layer 3 uses the multi-turn tool loop (python_execute).
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

    # Layer 3: use tool loop for Anthropic provider
    if layer == 3 and provider_name == "anthropic":
        print(f"  [live] Calling {provider_name} ({model}) with tool loop...")
        start_time = time.time()
        raw = call_anthropic_tool_loop(
            system=system_prompt,
            user=user_prompt,
            model=model,
            temperature=0,
            max_tokens=4096,
            api_key=api_key,
        )
    else:
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

    meta = {
        "provider": provider_name,
        "model": raw["model"],
        "temperature": 0,
        "elapsed_seconds": round(elapsed, 2),
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
    }
    if "tool_turns" in raw:
        meta["tool_turns"] = raw["tool_turns"]
    response["_meta"] = meta

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
# Unit normalization
# ---------------------------------------------------------------------------

# Known equivalent unit groups — when expected and actual units are both in
# the same group, we convert actual → expected before comparing values.
UNIT_CONVERSIONS = {
    # Temperature: normalize to expected unit
    "K": {
        "°C": lambda v: v + 273.15,
        "degC": lambda v: v + 273.15,
        "C": lambda v: v + 273.15,
        "°F": lambda v: (v - 32) * 5/9 + 273.15,
    },
    "°C": {
        "K": lambda v: v - 273.15,
        "°F": lambda v: (v - 32) * 5/9,
    },
    # Pressure
    "kPa": {
        "atm": lambda v: v * 101.325,
        "bar": lambda v: v * 100,
        "mmHg": lambda v: v * 0.133322,
        "Torr": lambda v: v * 0.133322,
        "psi": lambda v: v * 6.89476,
    },
    "atm": {
        "kPa": lambda v: v / 101.325,
        "bar": lambda v: v / 1.01325,
        "mmHg": lambda v: v / 760,
        "Torr": lambda v: v / 760,
    },
    "bar": {
        "atm": lambda v: v * 1.01325,
        "kPa": lambda v: v / 100,
        "Pa": lambda v: v / 1e5,
    },
}


def normalize_unit(actual_val: float, actual_unit: str, expected_unit: str) -> tuple:
    """
    If the agent returned a value in a different but compatible unit,
    convert it to the expected unit. Returns (converted_val, note_or_None).
    """
    if actual_unit == expected_unit:
        return actual_val, None

    # Strip whitespace and normalize common variations
    a = actual_unit.strip()
    e = expected_unit.strip()
    if a == e:
        return actual_val, None

    converters = UNIT_CONVERSIONS.get(e, {})
    if a in converters:
        converted = converters[a](actual_val)
        return converted, f"unit converted: {actual_val} {a} → {converted:.4f} {e}"

    # No conversion available — return as-is
    return actual_val, None


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

        # Normalize units if the agent used a different but compatible unit
        actual_unit = actual_spec.get("unit", "")
        actual_val, unit_note = normalize_unit(actual_val, actual_unit, expected_unit)
        if unit_note:
            print(f"    [{key}] {unit_note}")

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

        result_entry = {
            "status": "PASS" if within_tolerance else "FAIL",
            "expected": expected_val,
            "actual": actual_val,
            "unit": expected_unit,
            "error": error_display,
            "score": score,
        }
        if unit_note:
            result_entry["unit_conversion"] = unit_note
        results[key] = result_entry

    return {
        "output_scores": results,
        "numeric_score": total_score,
        "numeric_possible": total_possible,
        "numeric_pct": round(total_score / total_possible * 100, 1) if total_possible > 0 else 0,
    }


def score_reasoning_keyword(response: dict, fixture: dict) -> dict:
    """
    Score reasoning via keyword/heuristic matching (fast, free, deterministic).
    Used as the default when --judge is not specified, and as a baseline
    comparison when --judge IS specified.
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
# LLM-as-judge reasoning scorer
# ---------------------------------------------------------------------------

JUDGE_DEFAULT_MODEL = "claude-opus-4-20250514"

def _build_judge_prompt(fixture: dict, response: dict) -> tuple[str, str]:
    """
    Build the system and user prompts for the LLM judge.
    Returns (system_prompt, user_prompt).
    """
    criteria = fixture.get("acceptance_criteria", {})
    checkpoints = fixture.get("agent_evaluation", {}).get("reasoning_checkpoints", [])
    domain = fixture.get("domain_context", {})

    # Build the rubric from fixture data
    checkpoint_rubric = "\n".join(
        f"  {i+1}. (weight {cp['weight']:.2f}) {cp['checkpoint']}"
        for i, cp in enumerate(checkpoints)
    )

    must_include_rubric = "\n".join(
        f"  - {item}" for item in criteria.get("must_include", [])
    ) or "  (none specified)"

    must_not_rubric = "\n".join(
        f"  - {item}" for item in criteria.get("must_not_include", [])
    ) or "  (none specified)"

    common_mistakes = "\n".join(
        f"  - {m}" for m in domain.get("common_mistakes", [])
    ) or "  (none specified)"

    system = """You are an expert chemical engineering evaluator. Your job is to assess
whether a student/agent's solution demonstrates correct reasoning for a chemical
engineering problem.

You will be given:
1. The problem statement
2. A rubric with weighted reasoning checkpoints
3. Must-include and must-not-include criteria
4. The agent's full response

## Evaluation rules

- Judge reasoning quality, not just whether the final answer is correct.
- A checkpoint is MET if the agent demonstrates that reasoning step, even if they
  use different terminology (e.g., "Rachford-Rice" vs "flash objective function").
- A checkpoint is NOT MET only if the agent clearly skipped or incorrectly performed
  that reasoning step.
- For must-not-include items: flag as VIOLATED only if the agent actually commits
  the error described, not merely if they mention the topic.
- Be fair but rigorous. Partial credit is not available — each checkpoint is met or not.

## Response format

Respond with valid JSON only. No markdown fences, no preamble.

{
  "reasoning_checkpoints": [
    {
      "checkpoint": "the checkpoint text",
      "weight": 0.15,
      "met": true,
      "evidence": "brief quote or paraphrase from agent response supporting your verdict",
      "confidence": 0.95
    }
  ],
  "must_include": [
    {
      "requirement": "the requirement text",
      "found": true,
      "evidence": "brief supporting quote"
    }
  ],
  "must_not_include": [
    {
      "requirement": "the requirement text",
      "violated": false,
      "evidence": "why it was or was not violated"
    }
  ],
  "overall_reasoning_notes": "1-2 sentence summary of reasoning quality",
  "reasoning_score_pct": 72.5
}

The reasoning_score_pct should be: sum(weight for met checkpoints) / sum(all weights) * 100,
rounded to 1 decimal place. Compute this exactly from your checkpoint verdicts."""

    # Serialize the agent response (excluding internal metadata)
    agent_text = json.dumps({
        k: v for k, v in response.items() if not k.startswith("_")
    }, indent=2)

    user = f"""## Problem

{fixture['problem']['statement']}

## Task

{fixture['problem']['task']}

## Evaluation rubric

### Reasoning checkpoints (weighted):
{checkpoint_rubric}

### Must include:
{must_include_rubric}

### Must not include:
{must_not_rubric}

### Known common mistakes for this problem type:
{common_mistakes}

## Agent response to evaluate

{agent_text}

## Instructions

Evaluate each checkpoint and criterion. Return your verdict as JSON."""

    return system, user


def score_reasoning_llm_judge(response: dict, fixture: dict,
                              judge_provider: str = "anthropic",
                              judge_model: str = None) -> dict:
    """
    Score reasoning using an LLM-as-judge pattern.
    Sends the fixture rubric + agent response to a (typically stronger) model
    and parses its structured verdict.

    Returns the same shape as score_reasoning_keyword() for drop-in compatibility,
    plus additional judge-specific fields (evidence, confidence, notes).
    """
    judge_model = judge_model or JUDGE_DEFAULT_MODEL

    system_prompt, user_prompt = _build_judge_prompt(fixture, response)

    # Resolve provider and call
    provider_name = resolve_provider(judge_provider)
    provider = PROVIDERS[provider_name]
    api_key = get_api_key(provider_name)

    print(f"  [judge] Calling {provider_name} ({judge_model})...")
    start = time.time()

    raw = provider["call"](
        system=system_prompt,
        user=user_prompt,
        model=judge_model,
        temperature=0,
        max_tokens=4096,
        api_key=api_key,
    )

    elapsed = time.time() - start
    print(f"  [judge] Done in {elapsed:.1f}s ({raw.get('input_tokens', '?')} in / {raw.get('output_tokens', '?')} out)")

    # Parse the judge response
    cleaned = raw["text"].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        verdict = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  [judge] WARNING: Failed to parse judge response: {e}")
        print(f"  [judge] Falling back to keyword scoring")
        fallback = score_reasoning_keyword(response, fixture)
        fallback["judge_error"] = str(e)
        fallback["judge_raw"] = raw["text"][:500]
        return fallback

    # Normalize into the standard score shape
    # Checkpoint results
    checkpoint_results = []
    weighted_score = 0
    total_weight = 0
    for cp in verdict.get("reasoning_checkpoints", []):
        weight = cp.get("weight", 0.1)
        met = cp.get("met", False)
        total_weight += weight
        if met:
            weighted_score += weight
        checkpoint_results.append({
            "checkpoint": cp.get("checkpoint", ""),
            "weight": weight,
            "found": met,  # "found" for compatibility with keyword scorer
            "evidence": cp.get("evidence", ""),
            "confidence": cp.get("confidence", None),
        })

    # Must-include results
    must_include_results = []
    for mi in verdict.get("must_include", []):
        must_include_results.append({
            "requirement": mi.get("requirement", ""),
            "found": mi.get("found", False),
            "evidence": mi.get("evidence", ""),
        })

    # Must-not-include results
    must_not_results = []
    for mn in verdict.get("must_not_include", []):
        must_not_results.append({
            "requirement": mn.get("requirement", ""),
            "violated": mn.get("violated", False),
            "evidence": mn.get("evidence", ""),
        })

    # Compute score from verdicts (don't trust the model's arithmetic)
    computed_pct = round(weighted_score / total_weight * 100, 1) if total_weight > 0 else 0

    return {
        "must_include": must_include_results,
        "must_not_include": must_not_results,
        "reasoning_checkpoints": checkpoint_results,
        "reasoning_score_pct": computed_pct,
        "judge_method": "llm",
        "judge_model": judge_model,
        "judge_provider": judge_provider,
        "judge_notes": verdict.get("overall_reasoning_notes", ""),
        "judge_elapsed_seconds": round(elapsed, 2),
        "judge_tokens": {
            "input": raw.get("input_tokens", 0),
            "output": raw.get("output_tokens", 0),
        },
    }


def score_reasoning(response: dict, fixture: dict, use_judge: bool = False,
                    judge_provider: str = "anthropic", judge_model: str = None) -> dict:
    """
    Score reasoning — dispatches to keyword or LLM judge based on use_judge flag.
    When using judge, also runs keyword scorer and includes both for comparison.
    """
    if not use_judge:
        result = score_reasoning_keyword(response, fixture)
        result["judge_method"] = "keyword"
        return result

    # Run both scorers when judge is enabled
    keyword_result = score_reasoning_keyword(response, fixture)
    judge_result = score_reasoning_llm_judge(
        response, fixture,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )

    # The judge result is authoritative; include keyword as baseline comparison
    judge_result["keyword_baseline"] = {
        "reasoning_score_pct": keyword_result["reasoning_score_pct"],
        "checkpoints": keyword_result["reasoning_checkpoints"],
    }

    delta = judge_result["reasoning_score_pct"] - keyword_result["reasoning_score_pct"]
    print(f"  [judge] Score: {judge_result['reasoning_score_pct']}% "
          f"(keyword baseline: {keyword_result['reasoning_score_pct']}%, "
          f"delta: {'+' if delta >= 0 else ''}{delta:.1f}%)")

    return judge_result


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------

def assemble_result(fixture: dict, response: dict, output_scores: dict, reasoning_scores: dict,
                    layer: int = 1) -> dict:
    """Assemble the full eval result with traceability metadata."""
    return {
        "eval_id": f"{fixture['id']}-L{layer}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "fixture_id": fixture["id"],
        "fixture_version": fixture.get("version", "unknown"),
        "layer": layer,
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

    layer_labels = {1: "Layer 1 (base model)", 2: "Layer 2 (model + skills)", 3: "Layer 3 (model + tools)"}
    layer = result.get("layer", 1)

    print("\n" + "=" * 60)
    print(f"  EVAL: {result['fixture_id']} v{result['fixture_version']}")
    print(f"  {layer_labels.get(layer, f'Layer {layer}')}")
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
    judge_method = reasoning.get("judge_method", "keyword")
    method_label = "LLM JUDGE" if judge_method == "llm" else "KEYWORD"
    print(f"\n  REASONING ({method_label}): {reasoning['reasoning_score_pct']}%")
    if judge_method == "llm":
        print(f"  Judge: {reasoning.get('judge_provider', '?')}/{reasoning.get('judge_model', '?')}")
        baseline = reasoning.get("keyword_baseline", {})
        if baseline:
            print(f"  Keyword baseline: {baseline.get('reasoning_score_pct', '?')}%")
    print("  " + "-" * 40)
    for cp in reasoning.get("reasoning_checkpoints", []):
        icon = "  ✓" if cp["found"] else "  ✗"
        evidence = cp.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(f"  {icon} {cp['checkpoint']} (weight: {cp['weight']}){evidence_str}")

    # Must include
    for mi in reasoning.get("must_include", []):
        icon = "  ✓" if mi["found"] else "  ✗"
        evidence = mi.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(f"  {icon} Must include: {mi['requirement']}{evidence_str}")

    # Must not include
    for mn in reasoning.get("must_not_include", []):
        icon = "  ✓" if not mn["violated"] else "  ✗"
        evidence = mn.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(f"  {icon} Must NOT: {mn['requirement']}" +
              (" [VIOLATED]" if mn["violated"] else "") + evidence_str)

    # Judge notes
    if reasoning.get("judge_notes"):
        print(f"\n  JUDGE NOTES: {reasoning['judge_notes']}")

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
                provider_name: str = None, model: str = None, layer: int = 1,
                use_judge: bool = False, judge_provider: str = "anthropic",
                judge_model: str = None):
    """Run a single fixture evaluation."""
    print(f"\nLoading fixture: {fixture_path}")
    fixture = load_fixture(fixture_path)
    print(f"  ID: {fixture['id']}")
    print(f"  Layer: {layer}")
    if use_judge:
        print(f"  Judge: {judge_provider}/{judge_model or JUDGE_DEFAULT_MODEL}")
    print(f"  Problem: {fixture['problem']['statement'][:80]}...")

    # Build prompts (layer controls what gets included)
    system_prompt = build_system_prompt(fixture, layer=layer)
    user_prompt = build_user_prompt(fixture, layer=layer)

    # Determine mock path
    mock_path = None
    if use_mock:
        mock_path = str(MOCKS_DIR / "agent-responses" / f"{fixture['id']}.json")

    # Call agent (layer 3 uses tool loop)
    response = call_agent(system_prompt, user_prompt, mock_path,
                          provider_name=provider_name, model=model,
                          layer=layer)

    # Save mock if requested
    if save_mock_flag and not use_mock:
        save_mock(response, fixture["id"])

    # Score
    agent_outputs = response.get("outputs", {})
    tolerances = fixture.get("acceptance_criteria", {}).get("tolerances", {})

    output_scores = score_outputs(agent_outputs, fixture["expected_outputs"], tolerances)
    reasoning_scores = score_reasoning(response, fixture, use_judge=use_judge,
                                       judge_provider=judge_provider,
                                       judge_model=judge_model)

    # Assemble and save result
    result = assemble_result(fixture, response, output_scores, reasoning_scores, layer=layer)

    result_filename = f"{fixture['id']}-L{layer}-{get_git_sha()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    result_path = RESULTS_DIR / result_filename
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    # Display
    print_results(result)
    print(f"\n  Result saved: {result_path}")

    return result


def log_experiment(results: list, tag: str, layer: int, provider_name: str, model: str):
    """
    Append a single line to experiments.jsonl for this run.
    Each line is one experiment (one invocation of the harness).
    This is the 'lab notebook' — append-only, never edited.
    """
    # Summarize per-fixture scores
    fixture_scores = {}
    for r in results:
        fid = r["fixture_id"]
        s = r["scores"]
        fixture_scores[fid] = {
            "numeric_pct": s["numeric"]["numeric_pct"],
            "reasoning_pct": s["reasoning"]["reasoning_score_pct"],
            "overall_pct": s["overall_pct"],
            "confidence": r["agent_response"].get("confidence"),
        }

    avg_overall = sum(fs["overall_pct"] for fs in fixture_scores.values()) / len(fixture_scores) if fixture_scores else 0
    avg_numeric = sum(fs["numeric_pct"] for fs in fixture_scores.values()) / len(fixture_scores) if fixture_scores else 0
    avg_reasoning = sum(fs["reasoning_pct"] for fs in fixture_scores.values()) / len(fixture_scores) if fixture_scores else 0

    # Detect judge usage from first result
    judge_info = {}
    if results:
        reasoning_meta = results[0].get("scores", {}).get("reasoning", {})
        if reasoning_meta.get("judge_method") == "llm":
            judge_info = {
                "judge_method": "llm",
                "judge_model": reasoning_meta.get("judge_model", "unknown"),
                "judge_provider": reasoning_meta.get("judge_provider", "unknown"),
            }
        else:
            judge_info = {"judge_method": "keyword"}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "git_sha": get_git_sha(),
        "layer": layer,
        "provider": provider_name or "anthropic",
        "model": model or results[0].get("agent_meta", {}).get("model", "unknown") if results else "unknown",
        **judge_info,
        "n_fixtures": len(results),
        "avg_overall_pct": round(avg_overall, 1),
        "avg_numeric_pct": round(avg_numeric, 1),
        "avg_reasoning_pct": round(avg_reasoning, 1),
        "fixtures": fixture_scores,
    }

    with open(EXPERIMENT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def compare_experiments(last_n: int = 10):
    """
    Print a comparison table of recent experiments from the JSONL log.
    This is the 'did it get better?' view.
    """
    if not EXPERIMENT_LOG.exists():
        print("No experiments logged yet. Run some evals first!")
        return

    entries = []
    with open(EXPERIMENT_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if not entries:
        print("No experiments logged yet.")
        return

    entries = entries[-last_n:]

    # Header
    print("\n" + "=" * 100)
    print("  EXPERIMENT COMPARISON (last {})".format(len(entries)))
    print("=" * 100)
    print(f"  {'Tag':<20} {'Layer':>5} {'Model':<30} {'#Fix':>4} {'Num%':>6} {'Reas%':>6} {'Over%':>6}  {'Time'}")
    print("  " + "-" * 95)

    for e in entries:
        tag = (e.get("tag") or "—")[:20]
        model = (e.get("model") or "?")[:30]
        ts = e["timestamp"][:16].replace("T", " ")
        print(f"  {tag:<20} {e['layer']:>5} {model:<30} {e['n_fixtures']:>4} "
              f"{e['avg_numeric_pct']:>5.1f}% {e['avg_reasoning_pct']:>5.1f}% "
              f"{e['avg_overall_pct']:>5.1f}%  {ts}")

    # Show per-fixture breakdown for the latest two (for diffing)
    if len(entries) >= 2:
        prev, curr = entries[-2], entries[-1]
        all_fixtures = sorted(set(list(prev.get("fixtures", {}).keys()) + list(curr.get("fixtures", {}).keys())))
        if all_fixtures:
            print(f"\n  DIFF: '{prev.get('tag', '?')}' → '{curr.get('tag', '?')}'")
            print(f"  {'Fixture':<30} {'Before':>8} {'After':>8} {'Delta':>8}")
            print("  " + "-" * 56)
            for fid in all_fixtures:
                before = prev.get("fixtures", {}).get(fid, {}).get("overall_pct")
                after = curr.get("fixtures", {}).get(fid, {}).get("overall_pct")
                b_str = f"{before:.1f}%" if before is not None else "—"
                a_str = f"{after:.1f}%" if after is not None else "—"
                if before is not None and after is not None:
                    delta = after - before
                    d_str = f"{'+' if delta >= 0 else ''}{delta:.1f}%"
                else:
                    d_str = "—"
                print(f"  {fid:<30} {b_str:>8} {a_str:>8} {d_str:>8}")

    print("=" * 100)


def main():
    import argparse
    available_providers = ", ".join(sorted(PROVIDERS))
    parser = argparse.ArgumentParser(description="ChemE Agent Eval Runner")

    # Modes (default: run all curated fixtures)
    parser.add_argument("--fixture", type=str, help="Path to a single fixture JSON file")
    parser.add_argument("--compare", action="store_true", help="Compare recent experiment runs (no eval executed)")

    # Run options
    parser.add_argument("--mock", action="store_true", help="Use mocked responses instead of live API")
    parser.add_argument("--save-mock", action="store_true", help="Save live responses as mocks for future replay")
    parser.add_argument("--provider", type=str, default=None,
                        help=f"LLM provider ({available_providers}). Default: anthropic")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name override (default: provider's default model)")
    parser.add_argument("--layer", type=int, default=1, choices=[1, 2, 3],
                        help="Eval layer: 1=all inputs/no skills, 2=problem inputs+skills, 3=problem inputs+tools (default: 1)")
    parser.add_argument("--tag", type=str, default=None,
                        help="Label for this experiment run (e.g. 'baseline', 'added-skills', 'sonnet-vs-opus')")
    parser.add_argument("--include-drafts", action="store_true",
                        help="Include draft fixtures (version < 1.0.0). Default: curated only")

    # LLM judge options
    parser.add_argument("--judge", action="store_true",
                        help="Use LLM-as-judge for reasoning scoring (semantic, not keyword)")
    parser.add_argument("--judge-provider", type=str, default="anthropic",
                        help=f"Provider for the judge model ({available_providers}). Default: anthropic")
    parser.add_argument("--judge-model", type=str, default=None,
                        help=f"Judge model override. Default: {JUDGE_DEFAULT_MODEL}")
    args = parser.parse_args()

    # Compare mode — just print the table and exit
    if args.compare:
        compare_experiments()
        return

    # Default: run all curated fixtures (no flags needed)

    run_kwargs = dict(
        use_mock=args.mock,
        save_mock_flag=args.save_mock,
        provider_name=args.provider,
        model=args.model,
        layer=args.layer,
        use_judge=args.judge,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
    )

    results = []
    if args.fixture:
        r = run_fixture(args.fixture, **run_kwargs)
        results.append(r)
    else:
        fixtures = sorted(FIXTURES_DIR.glob("*.json"))
        # Skip non-fixture files
        fixtures = [f for f in fixtures if f.name != "fixture-schema.json"]

        # Default: curated only (version >= 1.0.0). Use --include-drafts to run all.
        if not args.include_drafts:
            curated = []
            for f in fixtures:
                with open(f) as fh:
                    ver = json.load(fh).get("version", "0.0.0")
                if not ver.startswith("0."):
                    curated.append(f)
                else:
                    print(f"  [skip] {f.name} (draft v{ver})")
            fixtures = curated
        if not fixtures:
            print("No fixtures found in fixtures/")
            sys.exit(1)
        print(f"Running {len(fixtures)} fixtures...")
        for fp in fixtures:
            try:
                r = run_fixture(str(fp), **run_kwargs)
                results.append(r)
            except Exception as e:
                print(f"  ERROR on {fp.name}: {e}")

        # Summary
        print("\n\n" + "=" * 60)
        print("  SUITE SUMMARY")
        print("=" * 60)
        for r in results:
            print(f"  {r['fixture_id']}: {r['scores']['overall_pct']}%")
        avg = sum(r["scores"]["overall_pct"] for r in results) / len(results)
        print(f"\n  Average: {avg:.1f}%")

    # Log the experiment
    if results:
        entry = log_experiment(results, tag=args.tag, layer=args.layer,
                               provider_name=args.provider, model=args.model)
        print(f"\n  Experiment logged: tag='{entry['tag']}' avg={entry['avg_overall_pct']}%")
        print(f"  View history: python run_eval.py --compare")


if __name__ == "__main__":
    main()

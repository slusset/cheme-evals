"""Scoring and result assembly services."""

import json
from datetime import datetime, timezone
from typing import Callable


UNIT_CONVERSIONS = {
    "K": {
        "°C": lambda v: v + 273.15,
        "degC": lambda v: v + 273.15,
        "C": lambda v: v + 273.15,
        "°F": lambda v: (v - 32) * 5 / 9 + 273.15,
    },
    "°C": {
        "K": lambda v: v - 273.15,
        "°F": lambda v: (v - 32) * 5 / 9,
    },
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
    """Convert a compatible actual unit into the expected unit when possible."""
    if actual_unit == expected_unit:
        return actual_val, None

    actual = actual_unit.strip()
    expected = expected_unit.strip()
    if actual == expected:
        return actual_val, None

    converters = UNIT_CONVERSIONS.get(expected, {})
    if actual in converters:
        converted = converters[actual](actual_val)
        return converted, f"unit converted: {actual_val} {actual} → {converted:.4f} {expected}"

    return actual_val, None


def score_outputs(actual: dict, expected: dict, tolerances: dict) -> dict:
    """Compare agent outputs against expected values."""
    results = {}
    total_score = 0
    total_possible = 0

    for key, expected_spec in expected.items():
        total_possible += 1
        expected_val = expected_spec["value"]
        expected_unit = expected_spec["unit"]
        actual_spec = actual.get(key, {})

        if not actual_spec:
            results[key] = {
                "status": "MISSING",
                "expected": expected_val,
                "actual": None,
                "score": 0,
                "note": "Agent did not produce this output",
            }
            continue

        actual_val = actual_spec.get("value")
        if actual_val is None:
            results[key] = {
                "status": "MISSING",
                "expected": expected_val,
                "actual": None,
                "score": 0,
                "note": "Agent output has no 'value' field",
            }
            continue

        actual_unit = actual_spec.get("unit", "")
        actual_val, unit_note = normalize_unit(actual_val, actual_unit, expected_unit)
        if unit_note:
            print(f"    [{key}] {unit_note}")

        tolerance = tolerances.get(key, {"type": "relative_percent", "value": 5.0})
        tolerance_type = tolerance["type"]
        tolerance_value = tolerance["value"]

        if tolerance_type == "absolute":
            error = abs(actual_val - expected_val)
            within_tolerance = error <= tolerance_value
            error_display = f"{error:.4f} (tolerance: ±{tolerance_value})"
        elif tolerance_type == "relative_percent":
            if expected_val == 0:
                error = abs(actual_val)
                within_tolerance = error < 1e-6
                error_display = f"expected 0, got {actual_val}"
            else:
                error = abs((actual_val - expected_val) / expected_val) * 100
                within_tolerance = error <= tolerance_value
                error_display = f"{error:.2f}% (tolerance: ±{tolerance_value}%)"
        else:
            within_tolerance = False
            error_display = f"Unknown tolerance type: {tolerance_type}"

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
    """Cheap but explicit heuristic reasoning scorer."""
    criteria = fixture.get("acceptance_criteria", {})
    reasoning_text = json.dumps(response).lower()

    must_include_results = []
    for item in criteria.get("must_include", []):
        keywords = item.lower().split()
        significant = [word for word in keywords if len(word) > 3]
        found = sum(1 for word in significant if word in reasoning_text)
        passed = found >= len(significant) * 0.5 if significant else True
        must_include_results.append({
            "requirement": item,
            "found": passed,
        })

    must_not_results = []
    for item in criteria.get("must_not_include", []):
        keywords = item.lower().split()
        significant = [word for word in keywords if len(word) > 3]
        found = sum(1 for word in significant if word in reasoning_text)
        violated = found >= len(significant) * 0.7 if significant else False
        must_not_results.append({
            "requirement": item,
            "violated": violated,
        })

    checkpoints = fixture.get("agent_evaluation", {}).get("reasoning_checkpoints", [])
    checkpoint_results = []
    weighted_score = 0
    total_weight = 0
    for checkpoint in checkpoints:
        terms = checkpoint["checkpoint"].lower().split()
        significant = [word for word in terms if len(word) > 4]
        found = sum(1 for word in significant if word in reasoning_text)
        passed = found >= len(significant) * 0.4 if significant else True
        weight = checkpoint.get("weight", 0.1)
        total_weight += weight
        if passed:
            weighted_score += weight
        checkpoint_results.append({
            "checkpoint": checkpoint["checkpoint"],
            "weight": weight,
            "found": passed,
        })

    return {
        "must_include": must_include_results,
        "must_not_include": must_not_results,
        "reasoning_checkpoints": checkpoint_results,
        "reasoning_score_pct": round(weighted_score / total_weight * 100, 1) if total_weight > 0 else 0,
        "judge_method": "heuristic",
        "score_reliability": "rough_heuristic",
        "score_notes": (
            "Keyword matching across the response is a rough heuristic only. "
            "Use LLM judge scoring for higher-confidence reasoning evaluation."
        ),
    }


def score_reasoning(
    response: dict,
    fixture: dict,
    *,
    use_judge: bool = True,
    judge_provider: str = "anthropic",
    judge_model: str = None,
    llm_judge_fn: Callable[..., dict] = None,
) -> dict:
    """Score reasoning with either the heuristic or an injected judge."""
    if not use_judge:
        return score_reasoning_keyword(response, fixture)

    if llm_judge_fn is None:
        raise ValueError("llm_judge_fn is required when use_judge=True")

    heuristic_result = score_reasoning_keyword(response, fixture)
    judge_result = llm_judge_fn(
        response,
        fixture,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )
    judge_result["heuristic_baseline"] = {
        "reasoning_score_pct": heuristic_result["reasoning_score_pct"],
        "checkpoints": heuristic_result["reasoning_checkpoints"],
        "score_notes": heuristic_result.get("score_notes", ""),
    }
    judge_result["score_reliability"] = "judge_scored"

    delta = judge_result["reasoning_score_pct"] - heuristic_result["reasoning_score_pct"]
    print(
        f"  [judge] Score: {judge_result['reasoning_score_pct']}% "
        f"(heuristic baseline: {heuristic_result['reasoning_score_pct']}%, "
        f"delta: {'+' if delta >= 0 else ''}{delta:.1f}%)"
    )
    return judge_result


def score_tool_proposals(response: dict, fixture: dict) -> dict:
    """Score whether tool proposals were appropriate for the fixture."""
    expectation = fixture.get("agent_evaluation", {}).get("tool_proposal_expectation")
    if not expectation:
        return {
            "proposal_score": 0,
            "proposal_possible": 0,
            "proposal_score_pct": 0,
            "mode": "not_scored",
            "notes": "No tool proposal expectation defined for this fixture.",
        }

    proposals = response.get("_meta", {}).get("tool_proposals", [])
    mode = expectation.get("mode", "unnecessary")
    allowed_names = set(expectation.get("allowed_tool_names", []))
    allowed_priorities = set(expectation.get("allowed_priorities", []))

    matched = None
    for proposal in proposals:
        if allowed_names and proposal.get("tool_name") not in allowed_names:
            continue
        if allowed_priorities and proposal.get("priority") not in allowed_priorities:
            continue
        matched = proposal
        break

    if mode == "required":
        passed = matched is not None
        note = (
            f"Matched required proposal: {matched['tool_name']}"
            if matched else
            "Required tool proposal was not made."
        )
    elif mode == "optional":
        passed = (not proposals) or (matched is not None)
        if not proposals:
            note = "No proposal made; acceptable because proposal is optional."
        elif matched:
            note = f"Matched optional proposal: {matched['tool_name']}"
        else:
            note = "Proposal was made, but it did not match the expected optional tool."
    elif mode == "unnecessary":
        passed = len(proposals) == 0
        note = (
            "No proposal made, as expected."
            if passed else
            "Agent proposed a tool even though the fixture should be solvable without one."
        )
    else:
        return {
            "proposal_score": 0,
            "proposal_possible": 0,
            "proposal_score_pct": 0,
            "mode": "invalid_expectation",
            "notes": f"Unknown tool proposal expectation mode: {mode}",
        }

    return {
        "proposal_score": 1 if passed else 0,
        "proposal_possible": 1,
        "proposal_score_pct": 100.0 if passed else 0.0,
        "mode": mode,
        "allowed_tool_names": sorted(allowed_names),
        "allowed_priorities": sorted(allowed_priorities),
        "matched_tool_name": matched.get("tool_name") if matched else None,
        "matched_priority": matched.get("priority") if matched else None,
        "notes": note,
    }


def assemble_result(
    fixture: dict,
    response: dict,
    output_scores: dict,
    reasoning_scores: dict,
    proposal_scores: dict = None,
    *,
    layer: int = 1,
    git_sha: str,
    timestamp: str = None,
) -> dict:
    """Assemble the full eval result with traceability metadata."""
    proposal_scores = proposal_scores or {
        "proposal_score": 0,
        "proposal_possible": 0,
        "proposal_score_pct": 0,
    }
    if proposal_scores.get("proposal_possible", 0) > 0:
        overall_pct = round(
            output_scores["numeric_pct"] * 0.5 +
            reasoning_scores["reasoning_score_pct"] * 0.35 +
            proposal_scores["proposal_score_pct"] * 0.15,
            1,
        )
    else:
        overall_pct = round(
            output_scores["numeric_pct"] * 0.6 +
            reasoning_scores["reasoning_score_pct"] * 0.4,
            1,
        )

    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    eval_id = f"{fixture['id']}-L{layer}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    return {
        "run_id": response.get("_meta", {}).get("run_id"),
        "eval_id": eval_id,
        "fixture_id": fixture["id"],
        "fixture_version": fixture.get("version", "unknown"),
        "layer": layer,
        "timestamp": timestamp,
        "git_sha": git_sha,
        "agent_meta": response.get("_meta", {}),
        "scores": {
            "numeric": output_scores,
            "reasoning": reasoning_scores,
            "tool_proposals": proposal_scores,
            "overall_pct": overall_pct,
        },
        "agent_response": {
            "reasoning": response.get("reasoning", ""),
            "assumptions": response.get("assumptions", []),
            "method": response.get("method", ""),
            "outputs": response.get("outputs", {}),
            "confidence": response.get("confidence", None),
            "skill_notes": response.get("skill_notes", ""),
        },
        "tool_proposals": response.get("_meta", {}).get("tool_proposals", []),
        "artifacts": response.get("_meta", {}).get("artifacts", []),
    }

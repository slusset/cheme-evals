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
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HARNESS_ROOT = Path(__file__).resolve().parent
SRC_DIR = HARNESS_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cheme_evals.adapters.storage.archive_store import append_archive_record as append_archive_record_to_file
from cheme_evals.adapters.cli.script_eval_runner import (
    ScriptAgentAdapterConfig,
    ScriptArchiveAdapterConfig,
    ScriptArtifactAdapterConfig,
    ScriptEvalRunnerAdapterConfig,
    ScriptFixtureAdapterConfig,
    ScriptPresenterAdapterConfig,
    ScriptPromptAdapterConfig,
    ScriptResultStoreAdapterConfig,
    ScriptRuntimeAdapterConfig,
    ScriptScoringAdapterConfig,
    ScriptTraceAdapterConfig,
    build_script_eval_runner_dependencies,
)
from cheme_evals.adapters.storage.artifact_store import (
    get_artifact_path as get_artifact_path_in_dir,
    list_artifacts as list_artifacts_in_dir,
    load_artifact as load_artifact_from_dir,
    record_artifact as record_artifact_in_dir,
    save_artifact as save_artifact_in_dir,
)
from cheme_evals.adapters.storage.result_store import (
    append_jsonl_record,
    read_jsonl_records,
    write_result,
)
from cheme_evals.application.fixtures import (
    load_fixture as load_fixture_service,
)
from cheme_evals.application.prompts import (
    build_system_prompt as build_system_prompt_service,
    build_user_prompt as build_user_prompt_service,
)
from cheme_evals.application.runtime import (
    call_agent as call_agent_service,
    save_mock as save_mock_service,
)
from cheme_evals.application.presentation import (
    load_trace_events as load_trace_events_service,
    print_results as print_results_service,
    print_trace_summary as print_trace_summary_service,
)
from cheme_evals.application.scoring import (
    assemble_result as assemble_result_service,
    normalize_unit as normalize_unit_service,
    score_outputs as score_outputs_service,
    score_reasoning as score_reasoning_service,
    score_reasoning_keyword as score_reasoning_keyword_service,
    score_tool_proposals as score_tool_proposals_service,
)
from cheme_evals.adapters.storage.trace_store import (
    append_trace_event as append_trace_event_to_dir,
    get_trace_path as get_trace_path_in_dir,
)
from cheme_evals.application.eval_runner import (
    EvalRunnerDependencies,
    compare_experiments as compare_experiments_service,
    log_experiment as log_experiment_service,
    run_fixture as run_fixture_service,
)
from cheme_evals.domain.config import HarnessPaths

FIXTURES_DIR = HARNESS_ROOT / "fixtures"
MOCKS_DIR = HARNESS_ROOT / "mocks"
RESULTS_DIR = HARNESS_ROOT / "results"
TRACES_DIR = RESULTS_DIR / "traces"
ARTIFACTS_DIR = RESULTS_DIR / "artifacts"
ARCHIVE_LOG = RESULTS_DIR / "archive.jsonl"
SKILLS_DIR = HARNESS_ROOT / "agent" / "skills"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TRACES_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENT_LOG = RESULTS_DIR / "experiments.jsonl"
ARTIFACT_STATUS_TRANSITIONS = {
    "proposed": {"validated", "rejected"},
    "validated": {"promoted", "rejected", "retired"},
    "promoted": {"retired"},
    "rejected": set(),
    "retired": set(),
}


def get_harness_paths() -> HarnessPaths:
    """Return the active filesystem configuration for this harness process."""
    return HarnessPaths(
        harness_root=HARNESS_ROOT,
        fixtures_dir=FIXTURES_DIR,
        mocks_dir=MOCKS_DIR,
        results_dir=RESULTS_DIR,
        traces_dir=TRACES_DIR,
        artifacts_dir=ARTIFACTS_DIR,
        archive_log=ARCHIVE_LOG,
        experiment_log=EXPERIMENT_LOG,
        skills_dir=SKILLS_DIR,
    )


def build_eval_runner_dependencies() -> EvalRunnerDependencies:
    """Build the current application-service dependency set."""
    return build_script_eval_runner_dependencies(ScriptEvalRunnerAdapterConfig(
        runtime=ScriptRuntimeAdapterConfig(
            new_run_id_fn=new_run_id,
            get_git_sha_fn=get_git_sha,
            judge_default_model=globals().get(
                "JUDGE_DEFAULT_MODEL", "claude-opus-4-20250514"
            ),
        ),
        fixtures=ScriptFixtureAdapterConfig(),
        prompts=ScriptPromptAdapterConfig(
            skills_dir=get_harness_paths().skills_dir,
        ),
        agent=ScriptAgentAdapterConfig(
            resolve_provider_fn=resolve_provider,
            providers=PROVIDERS,
            get_api_key_fn=get_api_key,
            anthropic_tool_loop_fn=call_anthropic_tool_loop,
            mocks_dir=get_harness_paths().mocks_dir,
        ),
        scoring=ScriptScoringAdapterConfig(
            llm_judge_fn=score_reasoning_llm_judge,
            get_git_sha_fn=get_git_sha,
        ),
        presenter=ScriptPresenterAdapterConfig(
            print_results_fn=print_results,
        ),
        traces=ScriptTraceAdapterConfig(
            append_trace_event_fn=append_trace_event,
            get_trace_path_fn=get_trace_path,
        ),
        artifacts=ScriptArtifactAdapterConfig(
            record_artifact_fn=record_artifact,
        ),
        archive=ScriptArchiveAdapterConfig(
            append_archive_record_fn=append_archive_record,
        ),
        results=ScriptResultStoreAdapterConfig(
            write_result_fn=write_result,
            append_jsonl_record_fn=append_jsonl_record,
            read_jsonl_records_fn=read_jsonl_records,
        ),
    ))


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


def new_run_id() -> str:
    """Create a stable identifier for one eval run."""
    return str(uuid.uuid4())


def get_trace_path(run_id: str) -> Path:
    """Return the JSONL trace path for a run."""
    return get_trace_path_in_dir(get_harness_paths().traces_dir, run_id)


def append_trace_event(run_id: str, event_type: str, payload: dict, sequence: int) -> int:
    """Append one event to the run's trace log and return the next sequence number."""
    return append_trace_event_to_dir(
        get_harness_paths().traces_dir, run_id, event_type, payload, sequence
    )


def append_archive_record(record_type: str, record_id: str, payload: dict) -> dict:
    """Append one record to the central archive ledger."""
    return append_archive_record_to_file(
        get_harness_paths().archive_log, record_type, record_id, payload
    )


def get_artifact_path(artifact_id: str) -> Path:
    """Return the file path for a stored artifact."""
    return get_artifact_path_in_dir(get_harness_paths().artifacts_dir, artifact_id)


def load_artifact(artifact_id: str) -> dict:
    """Load one artifact record by ID."""
    return load_artifact_from_dir(get_harness_paths().artifacts_dir, artifact_id)


def save_artifact(artifact: dict) -> dict:
    """Persist one artifact record to disk."""
    return save_artifact_in_dir(get_harness_paths().artifacts_dir, artifact)


def transition_artifact_status(
    artifact_id: str,
    new_status: str,
    *,
    reviewer: str = None,
    notes: str = None,
) -> dict:
    """Transition an artifact through the promotion state machine."""
    artifact = load_artifact(artifact_id)
    current_status = artifact["status"]
    allowed = ARTIFACT_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid artifact transition: {current_status} -> {new_status}"
        )

    artifact["status"] = new_status
    artifact.setdefault("lifecycle", [])
    artifact["lifecycle"].append({
        "from_status": current_status,
        "to_status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reviewer": reviewer,
        "notes": notes,
    })
    validation = artifact.setdefault("validation", {})
    validation["status"] = new_status if new_status in {"validated", "rejected"} else validation.get("status", "not_validated")
    if reviewer is not None:
        validation["reviewed_by"] = reviewer
    if new_status == "validated":
        validation["tests_passed"] = True
    if notes:
        validation["notes"] = notes

    save_artifact(artifact)
    append_archive_record(
        "artifact_transition",
        artifact_id,
        {
            "artifact_id": artifact_id,
            "artifact_type": artifact.get("artifact_type"),
            "source_run_id": artifact.get("source_run_id"),
            "from_status": current_status,
            "to_status": new_status,
            "reviewer": reviewer,
            "notes": notes,
            "path": artifact["artifact_path"],
        },
    )
    return artifact


def list_artifacts(status: str = None, artifact_type: str = None) -> list[dict]:
    """List artifact records from the local registry with optional filters."""
    return list_artifacts_in_dir(
        get_harness_paths().artifacts_dir, status=status, artifact_type=artifact_type
    )


def print_artifact_summary(artifact: dict):
    """Print one artifact summary in a human-readable format."""
    print(f"{artifact['artifact_id']}  {artifact.get('artifact_type', '?'):<8}  "
          f"{artifact.get('status', '?'):<10}  {artifact.get('source_fixture_id', '?'):<24}  "
          f"{artifact.get('proposal', {}).get('tool_name', artifact.get('summary', ''))}")


def print_artifact_detail(artifact: dict):
    """Print full detail for one artifact record."""
    print(json.dumps(artifact, indent=2))


def record_artifact(
    *,
    run_id: str,
    fixture: dict,
    artifact_type: str,
    proposal: dict,
    git_sha: str,
) -> dict:
    """Persist a first-class artifact record and return it."""
    return record_artifact_in_dir(
        artifacts_dir=get_harness_paths().artifacts_dir,
        archive_log=get_harness_paths().archive_log,
        run_id=run_id,
        fixture=fixture,
        artifact_type=artifact_type,
        proposal=proposal,
        git_sha=git_sha,
    )


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

def load_fixture(path: str) -> dict:
    """Compatibility wrapper for fixture loading."""
    return load_fixture_service(path)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_system_prompt(fixture: dict, layer: int = 1) -> str:
    """Compatibility wrapper for system prompt assembly."""
    return build_system_prompt_service(
        fixture,
        layer=layer,
        skills_dir=get_harness_paths().skills_dir,
    )


def build_user_prompt(fixture: dict, layer: int = 1) -> str:
    """Compatibility wrapper for user prompt assembly."""
    return build_user_prompt_service(fixture, layer=layer)


# ---------------------------------------------------------------------------
# Agent execution
# ---------------------------------------------------------------------------

from providers import PROVIDERS, resolve_provider, get_api_key, call_anthropic_tool_loop


def call_agent(system_prompt: str, user_prompt: str, mock_path: str = None,
               provider_name: str = None, model: str = None,
               layer: int = 1) -> dict:
    """Compatibility wrapper for agent execution."""
    return call_agent_service(
        system_prompt,
        user_prompt,
        mock_path,
        provider_name=provider_name,
        model=model,
        layer=layer,
        resolve_provider_fn=resolve_provider,
        providers=PROVIDERS,
        get_api_key_fn=get_api_key,
        anthropic_tool_loop_fn=call_anthropic_tool_loop,
    )


def save_mock(response: dict, fixture_id: str):
    """Compatibility wrapper for mock persistence."""
    return save_mock_service(response, fixture_id, mocks_dir=get_harness_paths().mocks_dir)


def normalize_unit(actual_val: float, actual_unit: str, expected_unit: str) -> tuple:
    """Compatibility wrapper for unit normalization."""
    return normalize_unit_service(actual_val, actual_unit, expected_unit)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_outputs(actual: dict, expected: dict, tolerances: dict) -> dict:
    """Compatibility wrapper for numeric scoring."""
    return score_outputs_service(actual, expected, tolerances)


def score_reasoning_keyword(response: dict, fixture: dict) -> dict:
    """Compatibility wrapper for heuristic reasoning scoring."""
    return score_reasoning_keyword_service(response, fixture)


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


def score_reasoning(response: dict, fixture: dict, use_judge: bool = True,
                    judge_provider: str = "anthropic", judge_model: str = None) -> dict:
    """Compatibility wrapper for reasoning scoring."""
    return score_reasoning_service(
        response,
        fixture,
        use_judge=use_judge,
        judge_provider=judge_provider,
        judge_model=judge_model,
        llm_judge_fn=score_reasoning_llm_judge,
    )


def score_tool_proposals(response: dict, fixture: dict) -> dict:
    """Compatibility wrapper for proposal scoring."""
    return score_tool_proposals_service(response, fixture)


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------

def assemble_result(fixture: dict, response: dict, output_scores: dict, reasoning_scores: dict,
                    proposal_scores: dict = None, layer: int = 1) -> dict:
    """Compatibility wrapper for result assembly."""
    return assemble_result_service(
        fixture,
        response,
        output_scores,
        reasoning_scores,
        proposal_scores,
        layer=layer,
        git_sha=get_git_sha(),
    )


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def print_results(result: dict):
    """Compatibility wrapper for result presentation."""
    print_results_service(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_fixture(fixture_path: str, use_mock: bool = False, save_mock_flag: bool = False,
                provider_name: str = None, model: str = None, layer: int = 1,
                use_judge: bool = True, judge_provider: str = "anthropic",
                judge_model: str = None):
    """Run a single fixture evaluation."""
    return run_fixture_service(
        paths=get_harness_paths(),
        deps=build_eval_runner_dependencies(),
        fixture_path=fixture_path,
        use_mock=use_mock,
        save_mock_flag=save_mock_flag,
        provider_name=provider_name,
        model=model,
        layer=layer,
        use_judge=use_judge,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )


def log_experiment(results: list, tag: str, layer: int, provider_name: str, model: str):
    """
    Append a single line to experiments.jsonl for this run.
    Each line is one experiment (one invocation of the harness).
    This is the 'lab notebook' — append-only, never edited.
    """
    return log_experiment_service(
        paths=get_harness_paths(),
        deps=build_eval_runner_dependencies(),
        results=results,
        tag=tag,
        layer=layer,
        provider_name=provider_name,
        model=model,
    )


def compare_experiments(last_n: int = 10):
    """
    Print a comparison table of recent experiments from the JSONL log.
    This is the 'did it get better?' view.
    """
    return compare_experiments_service(
        paths=get_harness_paths(),
        deps=build_eval_runner_dependencies(),
        last_n=last_n,
    )


def load_trace_events(run_id: str) -> list[dict]:
    """Compatibility wrapper for trace loading."""
    return load_trace_events_service(get_trace_path(run_id))


def print_trace_summary(run_id: str, event_types: list[str] = None):
    """Compatibility wrapper for trace summary presentation."""
    events = load_trace_events(run_id)
    print_trace_summary_service(run_id, events, event_types=event_types)


def main():
    import argparse
    available_providers = ", ".join(sorted(PROVIDERS))
    parser = argparse.ArgumentParser(description="ChemE Agent Eval Runner")
    parser.add_argument("--list-artifacts", action="store_true",
                        help="List recorded artifacts and exit")
    parser.add_argument("--artifact-id", type=str,
                        help="Artifact ID for show/transition operations")
    parser.add_argument("--show-artifact", action="store_true",
                        help="Show a recorded artifact as JSON and exit")
    parser.add_argument("--transition-artifact", type=str,
                        choices=["validated", "rejected", "promoted", "retired"],
                        help="Transition an artifact to a new lifecycle state and exit")
    parser.add_argument("--artifact-status", type=str,
                        choices=["proposed", "validated", "rejected", "promoted", "retired"],
                        help="Filter list-artifacts by status")
    parser.add_argument("--artifact-type", type=str,
                        help="Filter list-artifacts by artifact type")
    parser.add_argument("--trace-summary", action="store_true",
                        help="Show a human-readable summary for one run trace and exit")
    parser.add_argument("--run-id", type=str,
                        help="Run ID for trace summary operations")
    parser.add_argument("--trace-event-type", action="append",
                        help="Optional event type filter for trace summary (repeatable)")
    parser.add_argument("--reviewer", type=str,
                        help="Reviewer name for artifact transition operations")
    parser.add_argument("--notes", type=str,
                        help="Optional notes for artifact transition operations")

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
    parser.add_argument("--skip-judge", action="store_true",
                        help="Skip LLM-as-judge and use keyword heuristic only for reasoning scoring")
    parser.add_argument("--judge-provider", type=str, default="anthropic",
                        help=f"Provider for the judge model ({available_providers}). Default: anthropic")
    parser.add_argument("--judge-model", type=str, default=None,
                        help=f"Judge model override. Default: {JUDGE_DEFAULT_MODEL}")
    args = parser.parse_args()

    if args.list_artifacts:
        artifacts = list_artifacts(status=args.artifact_status, artifact_type=args.artifact_type)
        if not artifacts:
            print("No artifacts found.")
            return
        print(f"{'Artifact ID':<36}  {'Type':<8}  {'Status':<10}  {'Fixture':<24}  Summary")
        print("-" * 110)
        for artifact in artifacts:
            print_artifact_summary(artifact)
        return

    if args.show_artifact:
        if not args.artifact_id:
            parser.error("--show-artifact requires --artifact-id")
        artifact = load_artifact(args.artifact_id)
        print_artifact_detail(artifact)
        return

    if args.transition_artifact:
        if not args.artifact_id:
            parser.error("--transition-artifact requires --artifact-id")
        artifact = transition_artifact_status(
            args.artifact_id,
            args.transition_artifact,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        print(f"Artifact {artifact['artifact_id']} -> {artifact['status']}")
        print(f"Path: {artifact['artifact_path']}")
        return

    if args.trace_summary:
        if not args.run_id:
            parser.error("--trace-summary requires --run-id")
        print_trace_summary(args.run_id, event_types=args.trace_event_type)
        return

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
        use_judge=not args.skip_judge,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
    )

    results = []
    if args.fixture:
        r = run_fixture(args.fixture, **run_kwargs)
        results.append(r)
    else:
        fixtures = sorted(get_harness_paths().fixtures_dir.glob("*.json"))
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

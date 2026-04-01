"""Application services for running and comparing evals."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cheme_evals.domain.config import HarnessPaths
from cheme_evals.ports.eval_runner import (
    AgentPort,
    ArchivePort,
    ArtifactPort,
    FixturePort,
    PresenterPort,
    ResultStorePort,
    RuntimeInfoPort,
    ScoringPort,
    TracePort,
)


@dataclass(frozen=True)
class EvalRunnerDependencies:
    """Composable dependencies for run orchestration."""

    runtime: RuntimeInfoPort
    fixtures: FixturePort
    agent: AgentPort
    scoring: ScoringPort
    presenter: PresenterPort
    traces: TracePort
    artifacts: ArtifactPort
    archive: ArchivePort
    results: ResultStorePort


def run_fixture(
    *,
    paths: HarnessPaths,
    deps: EvalRunnerDependencies,
    fixture_path: str,
    use_mock: bool = False,
    save_mock_flag: bool = False,
    provider_name: str = None,
    model: str = None,
    layer: int = 1,
    use_judge: bool = False,
    judge_provider: str = "anthropic",
    judge_model: str = None,
) -> dict:
    """Run a single fixture evaluation."""
    run_id = deps.runtime.new_run_id()
    trace_seq = 1
    git_sha = deps.runtime.get_git_sha()

    print(f"\nLoading fixture: {fixture_path}")
    fixture = deps.fixtures.load_fixture(fixture_path)
    print(f"  ID: {fixture['id']}")
    print(f"  Layer: {layer}")
    if use_judge:
        print(f"  Judge: {judge_provider}/{judge_model or deps.runtime.judge_default_model}")
    print(f"  Problem: {fixture['problem']['statement'][:80]}...")
    print(f"  Run ID: {run_id}")

    trace_seq = deps.traces.append_trace_event(
        run_id,
        "run_started",
        {
            "fixture_path": fixture_path,
            "fixture_id": fixture["id"],
            "fixture_version": fixture.get("version", "unknown"),
            "layer": layer,
            "use_mock": use_mock,
            "provider_name": provider_name,
            "model": model,
            "use_judge": use_judge,
            "judge_provider": judge_provider,
            "judge_model": judge_model,
            "git_sha": git_sha,
        },
        trace_seq,
    )

    system_prompt = deps.fixtures.build_system_prompt(fixture, layer=layer)
    user_prompt = deps.fixtures.build_user_prompt(fixture, layer=layer)
    trace_seq = deps.traces.append_trace_event(
        run_id,
        "prompt_built",
        {
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "layer": layer,
        },
        trace_seq,
    )

    mock_path = None
    if use_mock:
        mock_path = str(paths.mocks_dir / "agent-responses" / f"{fixture['id']}.json")
    trace_seq = deps.traces.append_trace_event(
        run_id,
        "agent_call_started",
        {
            "provider_name": provider_name,
            "model": model,
            "layer": layer,
            "mock_path": mock_path,
        },
        trace_seq,
    )

    response = deps.agent.call_agent(
        system_prompt,
        user_prompt,
        mock_path,
        provider_name=provider_name,
        model=model,
        layer=layer,
    )
    response.setdefault("_meta", {})
    response["_meta"]["run_id"] = run_id
    response["_meta"]["artifacts"] = []
    trace_seq = deps.traces.append_trace_event(
        run_id,
        "agent_response_received",
        {
            "provider": response.get("_meta", {}).get("provider"),
            "model": response.get("_meta", {}).get("model"),
            "elapsed_seconds": response.get("_meta", {}).get("elapsed_seconds"),
            "input_tokens": response.get("_meta", {}).get("input_tokens"),
            "output_tokens": response.get("_meta", {}).get("output_tokens"),
            "tool_turns": response.get("_meta", {}).get("tool_turns", 0),
            "tool_proposals": response.get("_meta", {}).get("tool_proposals", []),
            "parse_error": response.get("parse_error"),
        },
        trace_seq,
    )

    for proposal in response.get("_meta", {}).get("tool_proposals", []):
        artifact = deps.artifacts.record_artifact(
            run_id=run_id,
            fixture=fixture,
            artifact_type="tool",
            proposal=proposal,
            git_sha=git_sha,
        )
        response["_meta"]["artifacts"].append(artifact)
        trace_seq = deps.traces.append_trace_event(
            run_id,
            "artifact_proposed",
            {
                "artifact_type": "tool",
                "artifact_id": artifact["artifact_id"],
                "artifact_path": artifact["artifact_path"],
                "proposal": proposal,
            },
            trace_seq,
        )

    if save_mock_flag and not use_mock:
        deps.agent.save_mock(response, fixture["id"])

    agent_outputs = response.get("outputs", {})
    tolerances = fixture.get("acceptance_criteria", {}).get("tolerances", {})
    output_scores = deps.scoring.score_outputs(agent_outputs, fixture["expected_outputs"], tolerances)
    reasoning_scores = deps.scoring.score_reasoning(
        response,
        fixture,
        use_judge=use_judge,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )
    proposal_scores = deps.scoring.score_tool_proposals(response, fixture)
    trace_seq = deps.traces.append_trace_event(
        run_id,
        "scores_computed",
        {
            "numeric_pct": output_scores["numeric_pct"],
            "reasoning_pct": reasoning_scores["reasoning_score_pct"],
            "proposal_pct": proposal_scores["proposal_score_pct"],
            "reasoning_method": reasoning_scores.get("judge_method"),
            "score_reliability": reasoning_scores.get("score_reliability"),
        },
        trace_seq,
    )

    result = deps.scoring.assemble_result(
        fixture, response, output_scores, reasoning_scores, proposal_scores, layer=layer
    )

    result_filename = (
        f"{fixture['id']}-L{layer}-{git_sha}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    result_path = deps.results.write_result(paths.results_dir, result_filename, result)
    trace_seq = deps.traces.append_trace_event(
        run_id,
        "result_written",
        {
            "result_path": str(result_path),
            "overall_pct": result["scores"]["overall_pct"],
        },
        trace_seq,
    )

    deps.presenter.print_results(result)
    print(f"\n  Result saved: {result_path}")
    print(f"  Trace saved:  {deps.traces.get_trace_path(run_id)}")
    deps.archive.append_archive_record(
        "run",
        run_id,
        {
            "run_id": run_id,
            "fixture_id": fixture["id"],
            "fixture_version": fixture.get("version", "unknown"),
            "layer": layer,
            "git_sha": git_sha,
            "result_path": str(result_path),
            "trace_path": str(deps.traces.get_trace_path(run_id)),
            "overall_pct": result["scores"]["overall_pct"],
            "provider": result.get("agent_meta", {}).get("provider"),
            "model": result.get("agent_meta", {}).get("model"),
        },
    )
    deps.traces.append_trace_event(
        run_id,
        "run_completed",
        {
            "result_path": str(result_path),
            "trace_path": str(deps.traces.get_trace_path(run_id)),
            "overall_pct": result["scores"]["overall_pct"],
        },
        trace_seq,
    )

    return result


def log_experiment(
    *,
    paths: HarnessPaths,
    deps: EvalRunnerDependencies,
    results: list,
    tag: str,
    layer: int,
    provider_name: str,
    model: str,
) -> dict:
    """Append a single experiment summary record to the experiment log."""
    fixture_scores = {}
    for result in results:
        fixture_id = result["fixture_id"]
        scores = result["scores"]
        fixture_scores[fixture_id] = {
            "numeric_pct": scores["numeric"]["numeric_pct"],
            "reasoning_pct": scores["reasoning"]["reasoning_score_pct"],
            "proposal_pct": scores.get("tool_proposals", {}).get("proposal_score_pct"),
            "overall_pct": scores["overall_pct"],
            "confidence": result["agent_response"].get("confidence"),
        }

    avg_overall = (
        sum(fs["overall_pct"] for fs in fixture_scores.values()) / len(fixture_scores)
        if fixture_scores else 0
    )
    avg_numeric = (
        sum(fs["numeric_pct"] for fs in fixture_scores.values()) / len(fixture_scores)
        if fixture_scores else 0
    )
    avg_reasoning = (
        sum(fs["reasoning_pct"] for fs in fixture_scores.values()) / len(fixture_scores)
        if fixture_scores else 0
    )
    proposal_values = [
        fs["proposal_pct"] for fs in fixture_scores.values() if fs["proposal_pct"] is not None
    ]
    avg_proposal = sum(proposal_values) / len(proposal_values) if proposal_values else None

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
            judge_info = {"judge_method": "heuristic"}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "git_sha": deps.runtime.get_git_sha(),
        "layer": layer,
        "provider": provider_name or "anthropic",
        "model": model or results[0].get("agent_meta", {}).get("model", "unknown")
        if results else "unknown",
        **judge_info,
        "n_fixtures": len(results),
        "avg_overall_pct": round(avg_overall, 1),
        "avg_numeric_pct": round(avg_numeric, 1),
        "avg_reasoning_pct": round(avg_reasoning, 1),
        "avg_proposal_pct": round(avg_proposal, 1) if avg_proposal is not None else None,
        "fixtures": fixture_scores,
    }
    return deps.results.append_jsonl_record(paths.experiment_log, entry)


def compare_experiments(
    *,
    paths: HarnessPaths,
    deps: EvalRunnerDependencies,
    last_n: int = 10,
) -> None:
    """Print a comparison table of recent experiment runs."""
    if not paths.experiment_log.exists():
        print("No experiments logged yet. Run some evals first!")
        return

    entries = deps.results.read_jsonl_records(paths.experiment_log)
    if not entries:
        print("No experiments logged yet.")
        return

    entries = entries[-last_n:]
    print("\n" + "=" * 100)
    print("  EXPERIMENT COMPARISON (last {})".format(len(entries)))
    print("=" * 100)
    print(f"  {'Tag':<20} {'Layer':>5} {'Model':<30} {'#Fix':>4} {'Num%':>6} {'Reas%':>6} {'Prop%':>6} {'Over%':>6}  {'Time'}")
    print("  " + "-" * 95)

    for entry in entries:
        tag = (entry.get("tag") or "—")[:20]
        model = (entry.get("model") or "?")[:30]
        ts = entry["timestamp"][:16].replace("T", " ")
        proposal_pct = entry.get("avg_proposal_pct")
        proposal_str = f"{proposal_pct:>5.1f}%" if proposal_pct is not None else "    —"
        print(
            f"  {tag:<20} {entry['layer']:>5} {model:<30} {entry['n_fixtures']:>4} "
            f"{entry['avg_numeric_pct']:>5.1f}% {entry['avg_reasoning_pct']:>5.1f}% "
            f"{proposal_str} {entry['avg_overall_pct']:>5.1f}%  {ts}"
        )

    if len(entries) >= 2:
        prev, curr = entries[-2], entries[-1]
        all_fixtures = sorted(set(list(prev.get("fixtures", {}).keys()) + list(curr.get("fixtures", {}).keys())))
        if all_fixtures:
            print(f"\n  DIFF: '{prev.get('tag', '?')}' → '{curr.get('tag', '?')}'")
            print(f"  {'Fixture':<30} {'Before':>8} {'After':>8} {'Delta':>8}")
            print("  " + "-" * 56)
            for fixture_id in all_fixtures:
                before = prev.get("fixtures", {}).get(fixture_id, {}).get("overall_pct")
                after = curr.get("fixtures", {}).get(fixture_id, {}).get("overall_pct")
                b_str = f"{before:.1f}%" if before is not None else "—"
                a_str = f"{after:.1f}%" if after is not None else "—"
                if before is not None and after is not None:
                    delta = after - before
                    d_str = f"{'+' if delta >= 0 else ''}{delta:.1f}%"
                else:
                    d_str = "—"
                print(f"  {fixture_id:<30} {b_str:>8} {a_str:>8} {d_str:>8}")

    print("=" * 100)

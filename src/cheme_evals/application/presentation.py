"""Human-readable presentation helpers."""

import json
from datetime import datetime
from pathlib import Path


def print_results(result: dict) -> None:
    """Print a human-readable summary of the eval results."""
    scores = result["scores"]
    numeric = scores["numeric"]
    reasoning = scores["reasoning"]
    proposal_score = scores.get("tool_proposals", {})

    layer_labels = {
        1: "Layer 1 (base model)",
        2: "Layer 2 (model + skills)",
        3: "Layer 3 (model + tools)",
    }
    layer = result.get("layer", 1)

    print("\n" + "=" * 60)
    print(f"  EVAL: {result['fixture_id']} v{result['fixture_version']}")
    print(f"  {layer_labels.get(layer, f'Layer {layer}')}")
    print(f"  Time: {result['timestamp']}")
    print(f"  Git:  {result['git_sha']}")
    print("=" * 60)

    print(
        f"\n  NUMERIC ACCURACY: {numeric['numeric_score']}/{numeric['numeric_possible']} "
        f"({numeric['numeric_pct']}%)"
    )
    print("  " + "-" * 40)
    for key, item in numeric["output_scores"].items():
        status = "PASS" if item["status"] == "PASS" else "FAIL"
        icon = "  ✓" if status == "PASS" else "  ✗"
        print(f"  {icon} {key}")
        print(f"      expected: {item['expected']}, actual: {item.get('actual', 'MISSING')}")
        if "error" in item:
            print(f"      error: {item['error']}")

    judge_method = reasoning.get("judge_method", "heuristic")
    method_label = "LLM JUDGE" if judge_method == "llm" else "ROUGH HEURISTIC"
    print(f"\n  REASONING ({method_label}): {reasoning['reasoning_score_pct']}%")
    if judge_method == "llm":
        print(f"  Judge: {reasoning.get('judge_provider', '?')}/{reasoning.get('judge_model', '?')}")
        baseline = reasoning.get("heuristic_baseline", {})
        if baseline:
            print(f"  Heuristic baseline: {baseline.get('reasoning_score_pct', '?')}%")
    elif reasoning.get("score_notes"):
        print(f"  Note: {reasoning['score_notes']}")
    print("  " + "-" * 40)
    for checkpoint in reasoning.get("reasoning_checkpoints", []):
        icon = "  ✓" if checkpoint["found"] else "  ✗"
        evidence = checkpoint.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(f"  {icon} {checkpoint['checkpoint']} (weight: {checkpoint['weight']}){evidence_str}")

    for item in reasoning.get("must_include", []):
        icon = "  ✓" if item["found"] else "  ✗"
        evidence = item.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(f"  {icon} Must include: {item['requirement']}{evidence_str}")

    for item in reasoning.get("must_not_include", []):
        icon = "  ✓" if not item["violated"] else "  ✗"
        evidence = item.get("evidence", "")
        evidence_str = f"\n        → {evidence}" if evidence else ""
        print(
            f"  {icon} Must NOT: {item['requirement']}"
            + (" [VIOLATED]" if item["violated"] else "")
            + evidence_str
        )

    if reasoning.get("judge_notes"):
        print(f"\n  JUDGE NOTES: {reasoning['judge_notes']}")

    if proposal_score.get("proposal_possible", 0) > 0:
        print(f"\n  TOOL PROPOSAL QUALITY: {proposal_score['proposal_score_pct']}%")
        print(f"  Note: {proposal_score.get('notes', '')}")
    print(f"\n  OVERALL SCORE: {scores['overall_pct']}%")
    if proposal_score.get("proposal_possible", 0) > 0:
        print("    (50% numeric accuracy + 35% reasoning quality + 15% proposal quality)")
    else:
        print("    (60% numeric accuracy + 40% reasoning quality)")

    proposals = result.get("tool_proposals", [])
    if proposals:
        print(f"\n  TOOL PROPOSALS: {len(proposals)}")
        print("  " + "-" * 40)
        for proposal in proposals:
            priority_icon = {
                "blocking": "🔴",
                "would_improve": "🟡",
                "nice_to_have": "🟢",
            }.get(proposal.get("priority", ""), "⚪")
            print(f"  {priority_icon} {proposal.get('tool_name', 'unnamed')} [{proposal.get('priority', '?')}]")
            print(f"      Why: {proposal.get('reason', '(no reason given)')}")
            interface = proposal.get("interface", {})
            if interface:
                inputs = interface.get("inputs", [])
                outputs = interface.get("outputs", [])
                if inputs:
                    print(f"      Inputs:  {', '.join(item['name'] for item in inputs)}")
                if outputs:
                    print(f"      Returns: {', '.join(item['name'] for item in outputs)}")
            if proposal.get("implementation_hint"):
                print(f"      Hint: {proposal['implementation_hint']}")

    confidence = result["agent_response"].get("confidence")
    if confidence is not None:
        print(f"\n  AGENT SELF-ASSESSED CONFIDENCE: {confidence}")
        calibration = abs(confidence * 100 - scores["overall_pct"])
        print(f"  CALIBRATION ERROR: {calibration:.1f} points")

    print("\n" + "=" * 60)


def load_trace_events(trace_path: Path) -> list[dict]:
    """Load all append-only trace events from a JSONL trace file."""
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace does not exist: {trace_path}")
    with open(trace_path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _parse_trace_timestamp(value: str):
    """Parse an ISO8601 trace timestamp into a datetime when possible."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def print_trace_summary(run_id: str, events: list[dict], event_types: list[str] = None) -> None:
    """Print a human-readable summary of one run trace."""
    filtered_events = [
        event for event in events
        if not event_types or event["type"] in event_types
    ]

    if not filtered_events:
        print(f"No matching trace events for run {run_id}.")
        return

    started = next((event for event in events if event["type"] == "run_started"), None)
    response = next((event for event in events if event["type"] == "agent_response_received"), None)
    scores = next((event for event in events if event["type"] == "scores_computed"), None)
    completed = next((event for event in events if event["type"] == "run_completed"), None)
    proposals = [event for event in events if event["type"] == "artifact_proposed"]

    start_ts = _parse_trace_timestamp(events[0].get("timestamp"))
    end_ts = _parse_trace_timestamp(events[-1].get("timestamp"))
    elapsed = None
    if start_ts and end_ts:
        elapsed = round((end_ts - start_ts).total_seconds(), 2)

    print("\n" + "=" * 60)
    print(f"  TRACE SUMMARY: {run_id}")
    print("=" * 60)
    if started:
        payload = started["payload"]
        print(f"  Fixture: {payload.get('fixture_id', '?')} v{payload.get('fixture_version', '?')}")
        print(f"  Layer:   {payload.get('layer', '?')}")
        print(f"  Mock:    {payload.get('use_mock', False)}")
        print(f"  Model:   {payload.get('provider_name') or '?'} / {payload.get('model') or '?'}")
    if response:
        payload = response["payload"]
        print(f"  Response: provider={payload.get('provider', '?')} model={payload.get('model', '?')}")
        print(f"  Tokens:   in={payload.get('input_tokens', '?')} out={payload.get('output_tokens', '?')}")
        print(f"  Tool turns: {payload.get('tool_turns', 0)}")
        if payload.get("parse_error"):
            print(f"  Parse error: {payload['parse_error']}")
    if scores:
        payload = scores["payload"]
        print(
            f"  Scores:   numeric={payload.get('numeric_pct', '?')} "
            f"reasoning={payload.get('reasoning_pct', '?')} "
            f"proposal={payload.get('proposal_pct', '?')}"
        )
        print(
            f"  Reasoning method: {payload.get('reasoning_method', '?')} "
            f"[{payload.get('score_reliability', '?')}]"
        )
    if completed:
        payload = completed["payload"]
        print(f"  Overall:  {payload.get('overall_pct', '?')}%")
        print(f"  Result:   {payload.get('result_path', '?')}")
    if elapsed is not None:
        print(f"  Trace span: {elapsed}s")
    print(f"  Events:   {len(events)} total, {len(filtered_events)} shown")
    print(f"  Artifacts proposed: {len(proposals)}")

    print("\n  EVENTS")
    print("  " + "-" * 40)
    for event in filtered_events:
        ts = event.get("timestamp", "")
        payload = event.get("payload", {})
        detail = ""
        if event["type"] == "artifact_proposed":
            detail = payload.get("proposal", {}).get("tool_name", "")
        elif event["type"] == "scores_computed":
            detail = (
                f"numeric={payload.get('numeric_pct')} "
                f"reasoning={payload.get('reasoning_pct')} "
                f"proposal={payload.get('proposal_pct')}"
            )
        elif event["type"] == "agent_response_received":
            detail = (
                f"tool_turns={payload.get('tool_turns', 0)} "
                f"parse_error={bool(payload.get('parse_error'))}"
            )
        elif event["type"] == "run_started":
            detail = f"fixture={payload.get('fixture_id')} layer={payload.get('layer')}"
        elif event["type"] in {"result_written", "run_completed"}:
            detail = payload.get("result_path", "")
        print(f"  {event['sequence']:>2}. {event['type']:<24} {ts} {detail}".rstrip())

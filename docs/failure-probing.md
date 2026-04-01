# Failure Probing Workflow

## Purpose

This document defines the current operator workflow for probing failure modes
in the eval framework and the embedded agent harness.

The goal is not only to notice that a run failed. The goal is to classify:

- where the failure occurred
- whether it is confirmed or still a hypothesis
- what artifact should be created to preserve the learning

This workflow follows the repo's governing dharma in [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md):

1. declare intent before acting
2. verify outcomes against declared intent
3. classify learning as confirmed or hypothesis
4. crystallize confirmed patterns into reusable process or code

## Operator Loop

For every failure probe:

1. Declare the failure hypothesis.
2. Select the smallest fixture or transcript that should expose it.
3. Run the harness under the intended conditions.
4. Inspect the run trace summary first.
5. Inspect raw trace JSONL only if the summary is insufficient.
6. Classify the result.
7. Preserve the learning in the appropriate artifact.

## Failure Classes

Use one primary class for each probe result.

- `protocol_failure`
  The agent/tool transcript did not progress through the expected state path.

- `runtime_failure`
  The run failed operationally: tool error, timeout, parse failure, missing file, or similar.

- `scoring_failure`
  The harness scored the run incorrectly or misleadingly.

- `policy_failure`
  The run violated an intended operating mode, such as mock replay falling through to live.

- `artifact_failure`
  A proposal or artifact was not recorded, linked, or transitioned correctly.

- `model_behavior`
  The framework behaved correctly, but the model made a poor or unexpected choice.

## Recommended Workflow

### 1. Declare the hypothesis

Examples:

- "Layer 3 run does not record the proposed tool artifact."
- "Mock replay is accidentally hitting the live provider."
- "Reasoning heuristic is overstating performance on parse-failure cases."

Do not skip this step. The declared hypothesis is the comparison point for
later classification.

### 2. Choose the smallest probe

Prefer, in order:

- an existing synthetic transcript test
- a single fixture run
- a small curated fixture subset
- a full suite run

### 3. Run the probe

Examples:

```bash
uv run python run_eval.py --fixture fixtures/flash-distillation-01.json --mock
uv run python run_eval.py --fixture fixtures/steam-table-saturation-01.json --layer 3
```

### 4. Inspect the trace summary

Use the run ID from the result output:

```bash
uv run python run_eval.py --trace-summary --run-id <run-id>
```

Filter by event type when narrowing a failure:

```bash
uv run python run_eval.py --trace-summary --run-id <run-id> --trace-event-type scores_computed
uv run python run_eval.py --trace-summary --run-id <run-id> --trace-event-type artifact_proposed
```

The trace summary is the first-line observability tool.

It should help answer:

- did the run start under the intended mode?
- did prompt construction complete?
- did the model return a response?
- were tools used?
- were artifacts proposed?
- were scores computed?
- did the run complete?

### 5. Escalate to raw trace only when needed

If the trace summary is not enough, inspect:

- `results/traces/<run-id>.jsonl`
- `results/archive.jsonl`
- `results/artifacts/<artifact-id>.json`

Do not start with raw JSON unless the summary is insufficient.

## Classification Rules

At the end of the probe, record one of:

- `confirmed_framework_bug`
- `confirmed_harness_bug`
- `confirmed_scoring_issue`
- `confirmed_policy_issue`
- `confirmed_model_behavior_issue`
- `hypothesis_not_confirmed`
- `insufficient_evidence`

## Crystallization Rules

When the issue is confirmed, preserve it in the smallest durable artifact that
prevents the system from drifting back.

Use:

- a regression test when the issue is executable
- a canonical transcript when the issue is protocol-shaped
- a spec or state-machine update when the issue exposes missing behavior definition
- a traceability/evidence-map update when the issue changes what counts as proof

## Minimal Operator Checklist

- hypothesis declared
- probe selected
- run executed
- trace summary inspected
- result classified
- follow-up artifact created or explicitly deferred

## Current Observability Commands

- `uv run python run_eval.py --compare`
- `uv run python run_eval.py --list-artifacts`
- `uv run python run_eval.py --show-artifact --artifact-id <artifact-id>`
- `uv run python run_eval.py --trace-summary --run-id <run-id>`

## Current Limitation

The trace summary is intentionally concise. It is an operator view, not a full
trace analytics system. If broader cross-run observability becomes necessary,
the next step should be derived summaries and indexed queries over archive and
trace records rather than immediately introducing a heavy external platform.

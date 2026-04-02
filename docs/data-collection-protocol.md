# Data Collection Protocol

## Purpose

This document connects report claims to the evidence needed to support them.
It serves two functions: an experimental plan for systematic data collection,
and an appendix to the semester project report showing that evidence was
gathered deliberately rather than ad hoc.

The discipline is simple: **no claim without a planned run, no run without
a hypothesis, no result without classification.**

## How to use this document

1. Before running an eval, find the claim it supports in the table below.
2. Record the hypothesis you are testing (what you expect to observe and why).
3. Run the eval, inspect the trace.
4. Classify the result: confirmed, refuted, or inconclusive.
5. Update the evidence column with the run_id and a one-line finding.

If you run an eval that does not map to any claim below, either add a new
claim row or acknowledge the run as exploratory (which is fine, but it does
not count as evidence).

---

## Part 1: Report Claims and Required Evidence

Each row extracts a claim from `docs/semester-project-report.md`, states
what evidence would make that claim credible, and tracks whether the
evidence exists.

### Architecture and Design Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact |
|---|-------------|---------|-------------------|--------|----------------|
| A1 | The system follows hexagonal architecture with ports and adapters | §4, §5.4 | All domain logic reachable through port interfaces; no direct adapter calls from application layer | **Blocked** | Requires hex refactor completion. Demonstrate by: running full test suite through adapter-injected paths only |
| A2 | The evaluation framework and agent harness are recognized as separate concerns | §4 | At minimum, the boundary is documented; ideally, a second agent runtime can be substituted without modifying the eval framework | **Partial** | Architecture doc exists. No substitution test yet |
| A3 | Persistence is append-only for traces and archive | §4.2 | Integration test that writes events, then verifies no prior events were mutated | **Have** | tests/test_integration.py covers this |

### Traceability Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact |
|---|-------------|---------|-------------------|--------|----------------|
| T1 | Runs receive stable identifiers and append-only traces | §3, §5.3 | Each run_id is unique; trace events are ordered; no events lost between run start and run complete | **Have** | Unit + integration tests confirm |
| T2 | Trace summaries support operator failure probing | §5.3 | A concrete example: run a fixture that fails, use --trace-summary to diagnose, document the finding | **Need** | Run a deliberate failure case, record the trace walkthrough |
| T3 | The failure probing workflow is usable in practice | §6.3 | Walk through the six-step workflow on a real failure, not a synthetic one | **Need** | Requires a live run that produces an unexpected result |

### Scoring Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact                                                                                   |
|---|-------------|---------|-------------------|--------|--------------------------------------------------------------------------------------------------|
| S1 | Numeric scoring compares agent output to expected values with tolerances | §5.1 | Fixture with known answer → run → score matches expected within tolerance | **Have** | Existing L1/L2 runs on 11 fixtures                                                               |
| S2 | Reasoning scoring evaluates quality of agent reasoning | §5.1 | At least two runs on the same fixture where reasoning quality differs, and scores reflect that difference | **Need** | Compare L1 (no skills) vs L2 (with skills) on a fixture where reasoning changes                  |
| S3 | Proposal-quality scoring distinguishes required, optional, and unnecessary proposals | §5.2 | Three fixture runs: one where proposal is required, one optional, one unnecessary — scores reflect the distinction | **Need** | Use flash-distillation-01 (no proposal needed), a proposal-required fixture, and an optional one |

### Artifact Lifecycle Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact |
|---|-------------|---------|-------------------|--------|----------------|
| L1 | Artifacts move through governed lifecycle states | §4.3 | A proposal artifact transitions proposed → validated → promoted, with each transition recorded in archive | **Need** | Run a Layer 3 fixture, then exercise the CLI lifecycle commands |
| L2 | Invalid transitions are rejected | §4.3 | Attempt proposed → promoted (skipping validated) and confirm it fails | **Have** | tests/test_integration.py covers this |
| L3 | The artifact directory records actual tool proposals | §5.2 | At least one artifact file exists in results/artifacts/ from a real (non-test) run | **Need** | Run a Layer 3 fixture against a live model |

### Validation Approach Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact |
|---|-------------|---------|-------------------|--------|----------------|
| V1 | The test suite validates scoring, tracing, archiving, and CLI behavior | §6.1 | Test suite passes; test count matches report (96 tests) | **Verify** | Run pytest, confirm count and all-pass |
| V2 | Documentation artifacts are part of the validation system | §6.2 | Evidence map, state machine, and mock transcript docs are consistent with current implementation | **Verify** | Audit each doc against current code |
| V3 | Replay through saved mock responses works | §5.1 | Run a fixture in mock mode, confirm output matches saved transcript | **Have** | Integration tests confirm |

### Fixture Coverage Claims

| # | Report Claim | Section | Evidence Required | Status | Run / Artifact |
|---|-------------|---------|-------------------|--------|----------------|
| F1 | Cases distinguish proposal behavior across required/optional/unnecessary | §7 | All three fixture types run at Layer 3 with scores recorded | **Need** | Run the proposal-expectation fixtures |
| F2 | Multi-turn tool transcript handling works | §7 | A fixture that exercises tool_use → tool_result → final_answer, with trace showing all turns | **Have** | Synthetic transcript tests confirm |
| F3 | The corpus is sufficient for local experimentation | §7 | At least: all 11 fixtures run at L1, 6+ at L2, 3+ at L3 | **Need** | 5 fixtures have never been run |

---

## Part 2: Run Plan

Planned runs to close the evidence gaps above, in priority order.

### Phase 1: Close the easy gaps (verify what we think we have)

| Run | Fixture | Layer | Hypothesis | Supports Claims |
|-----|---------|-------|-----------|----------------|
| R01 | (all) | — | Test suite still passes at reported count | V1 |
| R02 | evidence-map.md | — | Docs are consistent with current code | V2 |

### Phase 2: Run untested fixtures at Layer 1

| Run | Fixture | Layer | Hypothesis                  | Supports Claims |
|-----|---------|-------|-----------------------------|-----------------|
| R03 | all     | L1    | Baseline numeric scoring    | F3, S1          |
| R04 | all     | L2    | Baseline scoring with tools | F2, S1          |

### Phase 3: Comparative runs for scoring evidence

| Run | Fixture | Layer | Hypothesis | Supports Claims |
|-----|---------|-------|-----------|----------------|
| R08 | flash-distillation-01 | L1 vs L2 | Reasoning score should improve with skills; numeric should stay similar | S2 |
| R09 | steam-table-saturation-01 | L1 vs L2 | Same comparison on a different problem type | S2 |

### Phase 4: Layer 3 runs for proposal evidence

| Run | Fixture | Layer | Hypothesis | Supports Claims |
|-----|---------|-------|-----------|----------------|
| R10 | (proposal-required fixture) | L3 | Agent proposes a tool; artifact recorded in results/artifacts/ | S3, L1, L3, F1 |
| R11 | flash-distillation-01 | L3 | Agent should NOT propose a tool (problem is solvable) | S3, F1 |
| R12 | (proposal-optional fixture) | L3 | Agent may or may not propose; score reflects optional status | S3, F1 |

### Phase 5: Failure probing evidence

| Run | Fixture | Layer | Hypothesis | Supports Claims |
|-----|---------|-------|-----------|----------------|
| R13 | (pick a fixture that scored 0% at L2) | L2 | Walk the failure-probing workflow end-to-end, document the diagnosis | T2, T3 |

### Phase 6: Artifact lifecycle evidence

| Run | Fixture | Layer | Hypothesis | Supports Claims |
|-----|---------|-------|-----------|----------------|
| R14 | (use artifact from R10) | — | Transition proposed → validated → promoted via CLI; confirm archive entries | L1 |

---

## Part 3: Run Log

The canonical run log lives in [`/RUN_LOG.md`](/RUN_LOG.md) at the repo root.
This protocol defines what to run and why; the run log records what happened.

Every entry in the run log should trace back to a planned run in Part 2 above,
or be explicitly marked as exploratory. The run log is append-only.

---

## Part 4: Execution Model and Environment

### Who runs what

Runs are executed manually from the local development environment. The Cowork
sandbox (Python 3.10, no project deps) cannot execute the eval harness or the
test suite. This was confirmed on 2026-04-01 (R01 in the run log).

This is acceptable for a prototype. The protocol does not depend on automation —
it depends on discipline: hypothesis before run, classification after run,
log entry always.

Future work may establish a reproducible CI environment, but that is not
required for the current evidence goals.

### Environment baseline

Record this once and update if it changes. The report should state these
so a reader understands what "a run" means.

| Property | Value | Notes |
|----------|-------|-------|
| Python version | >=3.12 | per pyproject.toml |
| OS | (record locally) | |
| Model provider | (record per run) | Anthropic, OpenAI, mock |
| Model | (record per run) | e.g. claude-sonnet-4-20250514 |
| Git SHA | (recorded automatically) | harness captures this in trace |
| Fixture schema version | (record if it changes) | currently fixture-schema.json |

### Run checklist

Before each run:

1. Confirm you are on a clean git state (or note the SHA)
2. Find the planned run in Part 2 — write down the hypothesis
3. Note the fixture, layer, and provider/model

After each run:

1. Inspect the trace summary (`--trace-summary --run-id <id>`)
2. Classify: confirmed, refuted, inconclusive, or exploratory
3. Append an entry to `RUN_LOG.md`
4. If the result changes your understanding, update the relevant claim
   status in Part 1

---

## Part 5: Hex Refactor as Evidence

The hex refactor completion (claim A1) is not a run — it is a code change.
But it still follows the same discipline:

1. **Claim**: the system follows hexagonal architecture
2. **Hypothesis**: if we remove the 22 duplicate functions from run_eval.py
   and route all calls through adapters, the test suite still passes
3. **Evidence**: green test suite after removal, plus a brief audit showing
   no application-layer code directly calls file I/O
4. **Classification**: confirmed if tests pass and audit is clean

This should be done before Phase 4 (Layer 3 runs) so that those runs
exercise the clean architecture rather than the legacy paths.

---

## Revision History

- 2026-04-01: Initial protocol created.
- 2026-04-01: R01 attempted in Cowork sandbox — blocked by Python 3.10 vs >=3.12. Logged as inconclusive.
- 2026-04-01: R02 completed locally by operator — test suite passes. V1 confirmed.
- 2026-04-01: Consolidated run log into `/RUN_LOG.md`. Added execution model (Part 4) documenting manual-first approach and environment baseline.

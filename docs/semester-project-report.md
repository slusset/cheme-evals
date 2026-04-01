# Designing a Traceable Evaluation and Governance Harness for Tool-Proposing Agents

## Abstract

This project explores how to build an evaluation framework for agents that may
eventually evaluate, improve, and govern themselves. The current implementation
is a Python prototype, not a finished agent platform. Its purpose is to make
the right abstractions explicit before later reimplementation in the BEAM.

The central claim of the work so far is modest but important: before studying
self-improving or multi-agent systems, it is necessary to build a harness that
can trace what an agent did, score what happened, distinguish confirmed facts
from hypotheses, and govern the promotion of proposed improvements. The current
prototype implements fixtures, run traces, artifact recording, artifact
lifecycle states, proposal-quality scoring, replay support, and an initial
hexagonal refactor toward explicit ports and adapters.

This report describes the current system, the design principles behind it, the
validation workflow used so far, and the limitations that remain before more
ambitious work such as sandboxed adaptation, self-evaluation, and multi-agent
coordination should be treated as rigorous.

## 1. Motivation

The long-term motivation for this project is to understand three connected
problems:

1. How to build evaluation frameworks for agentic systems
2. How to build agents that can evaluate and improve themselves safely
3. How to eventually study systems of intelligence with coordination and
   emergent behavior

The project does not assume that agents should immediately be allowed to
self-modify. Instead, it assumes that evaluation, traceability, and governance
must come first. Without those, it is difficult to distinguish progress from
drift, learning from hallucination, or meaningful adaptation from accidental
behavior.

## 2. Problem Statement

Standard single-call benchmarking is not sufficient for tool-using or
artifact-proposing agents.

An agent run may involve:

- prompt assembly
- multiple model turns
- tool requests
- tool results
- proposal of new capabilities
- scoring across multiple dimensions
- persistence of run and artifact history

If those steps are not recorded and governed explicitly, then later claims
about "improvement" or "emergence" are weak. The project therefore asks:

How can an evaluation harness make agent behavior inspectable, replayable, and
governable before any deeper self-improvement mechanisms are introduced?

## 3. Design Principles

The governing principles are captured in [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md).
They can be summarized as four operational rules:

1. Declare intent before acting.
2. Verify outcomes against declared intent.
3. Classify learning as confirmed or hypothesis.
4. Crystallize confirmed patterns into durable structure.

These principles influence the current design directly:

- runs receive stable identifiers and append-only traces
- heuristic scorers are labeled as rough heuristics, not authoritative judges
- proposed tools become explicit artifacts rather than silently changing the system
- artifacts move through lifecycle states instead of being trusted immediately

The architectural framing in [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
extends those principles into runtime design: traceability over convenience,
replay over speed, and explicit promotion over autonomous self-modification.

## 4. System Overview

The current system has two intertwined roles:

1. Evaluation framework
2. Agent harness for the system under test

At present, the agent harness is embedded inside the evaluation framework.
That is acceptable for a prototype, but it is explicitly recognized as a future
separation point.

### 4.1 Core entities

The project now treats the following as first-class entities:

- `Fixture`: a frozen evaluation case with expected outputs and reasoning criteria
- `Run`: one execution of one fixture under one configuration
- `Trace`: append-only event history for a run
- `Artifact`: a proposed improvement or capability output
- `ArchiveRecord`: append-only catalog entry linking runs and artifacts

### 4.2 Current persistence model

The current file-backed model uses:

- `results/*.json` for run summaries
- `results/traces/*.jsonl` for append-only run traces
- `results/artifacts/*.json` for proposed artifacts
- `results/archive.jsonl` for the central append-only archive ledger

This is intentionally lightweight. The current system is optimized for local
research and operator visibility, not yet for large-scale analytics.

### 4.3 Current artifact lifecycle

Artifacts currently move through governed states:

- `proposed`
- `validated`
- `rejected`
- `promoted`
- `retired`

This prevents capability proposals from being treated as trusted behavior
before review.

## 5. Implementation Status

### 5.1 Evaluation mechanics

The harness supports:

- fixture loading from versioned JSON files
- multiple evaluation layers
- numeric scoring
- reasoning scoring
- proposal-quality scoring
- experiment logging
- replay through saved mock responses

### 5.2 Tool proposal support

The harness now supports a `propose_tool` flow for Layer 3 style runs.
This means the system can:

- record when an agent proposes a missing tool
- persist that proposal as an artifact
- score whether a proposal was required, optional, or unnecessary for a fixture

This is one of the most important learning-oriented features in the current
prototype because it creates a controlled path between observed capability gaps
and governed future improvements.

### 5.3 Traceability and operator workflow

Each run gets a `run_id` and append-only trace events. The trace includes
events such as:

- run start
- prompt construction
- agent call start
- agent response received
- artifact proposed
- scores computed
- result written
- run completed

Operator visibility was improved further with:

- a `--trace-summary --run-id ...` CLI path
- event-type filtering for trace summaries
- a documented failure probing workflow in
  [`docs/failure-probing.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/failure-probing.md)

### 5.4 Current structural refactor

The repository began as a script-centric harness. It has since been refactored
toward a file-backed hexagonal architecture with:

- domain records and config objects under `src/cheme_evals/domain`
- storage adapters under `src/cheme_evals/adapters/storage`
- application orchestration under `src/cheme_evals/application`
- explicit ports under `src/cheme_evals/ports`
- script-backed adapter composition under `src/cheme_evals/adapters/cli`

This refactor is incomplete, but it is now real enough to support further work
without the architecture collapsing back into a single script.

## 6. Validation Approach

Validation in the current project is not based on one mechanism. It is layered.

### 6.1 Tests

The project currently includes:

- unit tests for scoring and result assembly
- integration tests for run execution, trace writing, artifact recording, and
  CLI behavior
- synthetic transcript-style tests for multi-turn tool use

At the time of writing, the suite passes with `96` tests.

### 6.2 Documentation as validation support

Several documentation artifacts are intentionally treated as part of the
validation system rather than as passive prose:

- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`docs/mock-transcripts.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/mock-transcripts.md)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)

These define protocol coverage, evidence links, and the difference between
implemented behavior and intended future behavior.

### 6.3 Failure probing workflow

The project now has an explicit failure-probing workflow:

1. declare a failure hypothesis
2. choose the smallest probe
3. run the probe
4. inspect the trace summary
5. classify the result
6. crystallize confirmed patterns into tests, transcripts, specs, or docs

This is important because the project aims to support learning and adaptation.
Without disciplined failure probing, traces become data exhaust rather than
operational evidence.

## 7. Example Cases

The current fixture set includes cases that distinguish proposal behavior:

- a case where a blocking external capability should be proposed
- a case where the problem is solvable from provided information and no proposal
  should be made
- a case where a proposal is optional but not required

In addition, the synthetic `tool use -> final answer` integration path confirms
that the harness can manage a multi-turn tool transcript rather than only
single-shot answer evaluation.

These cases are enough to support meaningful local experimentation with tool
proposal behavior, even though they do not yet constitute a large benchmark.

## 8. Current Limitations

Several limitations remain and should be stated plainly.

### 8.1 Sandboxing is not finished

The current `python_execute` path is not yet a real sandbox in the sense needed
for safe experimentation. Sandboxing remains future work and should be treated
as such.

### 8.2 The agent runtime and eval framework are still coupled

The architecture now recognizes the difference between the evaluation framework
and the embedded agent harness, but they are still intertwined in one runtime.
That is acceptable for now, but it limits clean substitution of alternative
agent runtimes.

### 8.3 Some domain logic still lives in the legacy shell

Important logic has been moved into `src/`, but fixture/prompt and scoring
logic still rely on legacy script functions. The refactor is structurally
credible, but still transitional.

### 8.4 Observability is local and file-based

The trace and archive system is useful, but it is still oriented toward local
inspection and lightweight operator workflows rather than richer indexed
analytics across many runs.

### 8.5 The corpus is still small

The current fixture set is enough to support design work and failure probing,
but not enough to support strong claims about general agent behavior.

## 9. Future Work

The most important next steps are:

1. real sandbox policy and execution boundary
2. further separation of agent runtime from evaluation framework
3. richer observability and derived trace summaries
4. deeper fixture coverage for failure modes and proposal quality
5. eventual BEAM reimplementation of the key runtime abstractions

Longer term, the project may explore:

- `SKILL.md` promotion workflows
- richer artifact types beyond tools
- self-evaluation and governed adaptation
- multi-agent coordination under explicit trace and policy boundaries

These should remain future directions until the underlying evaluation and
governance foundations are stronger.

## 10. Reflection

The main lesson so far is that ambitious ideas like self-improving agents or
emergent multi-agent systems are less about clever prompting than about
infrastructure for traceability, classification, and controlled promotion.

The current prototype does not solve those larger problems. What it does
provide is a disciplined starting point: a way to run agents, observe what
happened, score outcomes, record proposed changes, and preserve evidence.

That is enough for a semester-project scale contribution because it establishes
the scaffolding required before stronger claims can be made.

## Appendix: Repo Artifacts Most Relevant To This Report

- [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md)
- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)
- [`docs/mock-transcripts.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/mock-transcripts.md)
- [`docs/failure-probing.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/failure-probing.md)
- [`docs/hex-refactor-plan.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/hex-refactor-plan.md)

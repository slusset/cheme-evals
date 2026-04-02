# Agent Eval Architecture

## Purpose

This project is a learning and prototyping harness for three related goals:

1. Understand evaluation frameworks
2. Learn how to build agents that can evaluate and improve themselves safely
3. Evolve toward systems of intelligence with multi-agent coordination and emergent behavior

The current Python implementation is not the final runtime. It is a traceable
prototype whose main job is to make the right abstractions explicit before they
are reimplemented in the BEAM.

The framework should optimize for:

- traceability over convenience
- replayability over speed
- explicit promotion over autonomous self-modification
- capability boundaries over ad hoc execution
- reproducible experiments over clever behavior


## Design Principles

### 1. Evaluation before adaptation

The system must be able to measure behavior before it is allowed to change
behavior. If adaptation comes first, the harness cannot distinguish progress
from drift.

### 2. Sandboxing as an epistemic boundary

Sandboxing is not only about process safety. It defines what an agent can:

- observe
- execute
- mutate
- persist
- promote

Those boundaries are part of the experiment.

### 3. Artifacts, not magical learning

Every improvement should be represented as an inspectable artifact:

- `SKILL.md`
- tool contract
- prompt template revision
- memory record
- model selection policy
- later: learned parameter update or model snapshot reference

Agents may propose artifacts, but promotion into trusted system state must be
explicit and reviewable.

### 4. Replay must be first-class

Any meaningful result should be reproducible from frozen inputs:

- fixture
- model identity
- prompt state
- tool definitions
- tool outputs or mocks
- sandbox policy
- scoring policy

### 5. Architecture should map cleanly to BEAM

The Python harness is a prototype. The conceptual model should translate to:

- isolated processes
- message passing
- capability-scoped workers
- append-only event traces
- supervised promotion workflows


## Core Concepts

### Fixture

A fixture is a frozen evaluation case. It should define:

- problem statement
- allowed context
- expected outputs
- reasoning rubric
- safety / policy constraints

Fixtures are versioned and never mutated in place during a run.

### Run

A run is one execution of one agent configuration against one fixture under one
policy envelope.

A run must have:

- `run_id`
- `fixture_id`
- `fixture_version`
- `git_sha`
- timestamp
- provider / model identity
- layer / capability profile
- sandbox policy version
- scoring policy version

### Trace

A trace is the full record of what happened during a run.

At minimum it should capture:

- prompts
- model responses
- tool calls
- tool outputs
- proposed artifacts
- scoring decisions
- final result

The trace is the primary source of truth for debugging and later learning.

### Capability Policy

A capability policy defines what the agent is allowed to use. It includes:

- allowed tools
- allowed filesystems paths
- network permissions
- persistence permissions
- artifact proposal permissions
- promotion permissions

This policy is part of the run definition and must be logged.

### Adaptation Artifact

An adaptation artifact is any output intended to improve future performance.

Examples:

- new or revised `SKILL.md`
- proposed tool
- tool schema revision
- retrieval source addition
- memory snippet
- prompt template change

Artifacts should be stored with provenance and status, not injected directly
into trusted runtime state.

### Promotion

Promotion is the act of moving an artifact from experimental output into trusted
system state.

Promotion must be explicit. The system should support at least:

- `proposed`
- `validated`
- `rejected`
- `promoted`
- `retired`


## Runtime Boundaries

The architecture should be split into separate responsibilities.

### 1. Orchestrator

Responsible for:

- loading fixtures
- selecting model/provider
- selecting policy profile
- starting a run
- coordinating scoring
- writing traces and results

The orchestrator should not also act as the sandbox or the scorer.

### 2. Agent Runtime

Responsible for:

- receiving prompt context
- generating responses
- invoking allowed tools
- proposing artifacts

The runtime is where agent cognition happens, but it should not directly write
to trusted project state.

### 3. Sandbox Runtime

Responsible for:

- executing model-requested code or tools
- enforcing resource and access limits
- returning auditable outputs

The sandbox should be treated as a controlled execution worker, not as a
general shell.

### 4. Scoring Engine

Responsible for:

- numeric output validation
- reasoning evaluation
- policy violation detection
- result aggregation

Scoring should be versioned and independently testable.

### 5. Artifact Registry

Responsible for:

- storing proposed artifacts
- tracking provenance
- tracking review / validation status
- supporting promotion decisions

This should eventually become more important than flat files.

### 6. Trace Store

Responsible for:

- append-only run events
- replay support
- auditability
- downstream analysis


## Suggested Data Model

These entities matter more than the current Python file boundaries.

### Run Record

```json
{
  "run_id": "uuid",
  "fixture_id": "flash-distillation-01",
  "fixture_version": "1.0.0",
  "git_sha": "abc1234",
  "timestamp": "2026-03-31T22:00:00Z",
  "agent_profile": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "layer": 3
  },
  "policy_profile": {
    "tool_policy": "layer3-v1",
    "sandbox_policy": "python-sandbox-v1",
    "scoring_policy": "scoring-v2"
  }
}
```

### Trace Event

```json
{
  "event_id": "uuid",
  "run_id": "uuid",
  "sequence": 12,
  "timestamp": "2026-03-31T22:00:01Z",
  "type": "tool_call",
  "actor": "agent",
  "payload": {
    "tool_name": "python_execute",
    "input": {"code": "print(2+2)"}
  }
}
```

Recommended event types:

- `run_started`
- `prompt_built`
- `model_called`
- `model_responded`
- `tool_called`
- `tool_returned`
- `artifact_proposed`
- `artifact_validated`
- `artifact_promoted`
- `score_computed`
- `run_completed`

### Artifact Record

```json
{
  "artifact_id": "uuid",
  "artifact_type": "skill",
  "status": "proposed",
  "source_run_id": "uuid",
  "source_event_id": "uuid",
  "content_ref": "artifacts/skills/steam-tables-v1.md",
  "summary": "Lookup guidance for steam table usage",
  "validation": {
    "tests_passed": false,
    "reviewed_by": null
  }
}
```


## Scoring Strategy

### Numeric scoring

Numeric scoring should stay deterministic wherever possible:

- unit normalization
- tolerance checks
- output completeness

This is the strongest part of the current framework and should remain the anchor.

### Reasoning scoring

Reasoning scoring should be tiered:

1. `rough_heuristic`
2. `llm_judge`
3. later: rubric ensembles / specialist judges

The rough heuristic should never be presented as authoritative. It is useful
for fast offline baselines and regression checks only.

### Policy scoring

Add explicit scoring for policy compliance:

- attempted forbidden tool use
- filesystem policy violations
- unsupported self-modification attempts
- unsafe artifact promotion attempts

This becomes more important as self-evolution increases.


## Sandboxing Model

The near-term sandbox should be designed around explicit capability boundaries.

### Required properties

- time limits
- memory limits
- working directory isolation
- restricted filesystem access
- explicit network policy
- explicit subprocess policy
- output truncation with traceability
- immutable run inputs

### Persistence policy

The sandbox should distinguish between:

- ephemeral scratch state
- run-local artifacts
- promotable artifacts
- trusted system state

Only orchestrator-approved promotion should move artifacts upward.

### Reintegration rule

Nothing produced in the sandbox should silently become trusted context.
Reintegration should always produce:

- an artifact record
- provenance metadata
- validation status
- a promotion decision


## Artifact Lifecycle

This is the core path for self-improvement.

### Stage 1: Proposal

The agent proposes an artifact:

- `propose_tool`
- `propose_skill`
- `propose_memory`
- later: `propose_policy_change`

### Stage 2: Materialization

The proposed artifact is rendered into a concrete object:

- markdown file
- JSON tool schema
- retrieval entry
- prompt diff

### Stage 3: Validation

Validation can include:

- schema validation
- unit tests
- replay against fixture subset
- policy review
- human review

### Stage 4: Promotion

Promotion moves the artifact into a trusted registry or runtime profile.

### Stage 5: Measurement

Promoted artifacts must be evaluated against:

- win rate / score delta
- failure modes introduced
- policy violations
- cost / latency changes


## Promotion Workflow

Promotion should be a first-class workflow, not an afterthought.

### Proposed workflow

1. Agent proposes artifact during a run
2. Harness records artifact with provenance
3. Validator runs offline checks
4. Candidate artifact is tested against a benchmark slice
5. Reviewer or promotion policy approves / rejects
6. Registry updates artifact status
7. Future runs may opt into the promoted artifact via profile versioning

### Hard rule

An agent should not be allowed to directly modify the active trusted skill set
for the same run in which it proposes the modification. That collapses the
experimental boundary.


## Multi-Agent Path

The long-term “agent society” direction should still be grounded in traceable
roles.

Suggested roles:

- solver agent
- critic / evaluator agent
- tool designer agent
- skill synthesizer agent
- promotion reviewer agent
- orchestrator

These roles do not need separate models at first. What matters is that their
responsibilities and trace boundaries are distinct.

Emergence should happen from:

- explicit coordination protocols
- different information access profiles
- artifact exchange
- evaluation feedback

Not from unstructured agent chatter.


## BEAM Mapping

This architecture is intentionally compatible with a BEAM implementation.

### Natural BEAM correspondences

- orchestrator -> supervised process / GenServer
- run worker -> isolated process per run
- sandbox worker -> supervised external worker boundary / port / controlled executor
- trace store -> append-only event stream
- artifact registry -> durable state + versioned records
- promotion workflow -> explicit state machine

### Why BEAM fits

BEAM is strong for:

- isolated lightweight processes
- supervision trees
- fault containment
- message passing
- explicit state transitions

That makes it well-suited for agent societies, sandbox coordination, and
traceable promotion workflows.

### Porting guidance

When working in Python, prefer boundaries that survive the port:

- message-shaped inputs and outputs
- append-only event records
- immutable run definitions
- explicit state machines for artifact status

Avoid Python-specific coupling that will be thrown away later.


## Near-Term Implementation Priorities

### Priority 1: Stronger traceability

- add stable `run_id`
- emit append-only trace events
- version scoring policy and sandbox policy
- attach provenance to proposed artifacts

### Priority 2: Real sandbox boundary

- separate sandbox worker from harness process
- isolate filesystem and subprocess access
- make persistence and promotion explicit

### Priority 3: Artifact registry

- store tool proposals and future skill proposals as first-class records
- track status and validation outcomes

### Priority 4: Promotion workflow

- define validation rules
- support reviewable promotion decisions
- replay promoted artifacts against benchmark slices

### Priority 5: Multi-agent experiments

- introduce distinct roles with different capability profiles
- evaluate coordination protocols, not just agent outputs


## Immediate Guidance For This Repo

The current repo should evolve in this direction:

- `fixtures/` remains the frozen task corpus
- `mocks/` becomes replay input, not just convenience files
- `results/` should split into run summaries vs append-only traces
- `agent/skills/` becomes one artifact class within a broader registry model
- `propose_tool` should be treated as the first artifact proposal mechanism

Recommended next steps:

1. Add a `run_id` and append-only trace log per run
2. Store tool proposals as explicit artifact records, not only embedded in result JSON
3. Define a `sandbox_policy` object and log it on every run
4. Separate scratch outputs from promotable artifacts
5. Add a `propose_skill` flow after `propose_tool` is stable


## Non-Goals For Now

To keep the framework disciplined, avoid these shortcuts:

- silent self-modification
- live mutation of trusted skills during a run
- scoring heuristics presented as authoritative
- untracked memory injection
- hidden retrieval or tool access outside policy
- coupling adaptation logic directly to final production deployment


## Summary

This framework should become an instrumented laboratory for agent behavior.

The right sequence is:

1. build traceable evaluation
2. enforce capability boundaries
3. represent improvement as governed artifacts
4. validate and promote improvements explicitly
5. then scale toward self-improving and multi-agent systems

If that discipline is maintained, the eventual BEAM implementation can inherit
the architecture rather than merely reimplement the code.

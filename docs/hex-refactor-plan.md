# Hexagonal Refactor Plan

## Purpose

This document defines the next structural refactor for the harness:

- introduce explicit domain record schemas
- introduce hexagonal ports and adapters
- separate application services from infrastructure
- preserve the current CLI and test behavior during migration

This is not a greenfield redesign. It is an incremental extraction plan from
the current `run_eval.py` script into a package-oriented architecture that is
closer to the eventual BEAM implementation.

It should be read with:

- [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md)
- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)

## Refactor Goal

Move from:

- one large script as the effective architecture

To:

- domain records as the core model
- ports as interfaces
- adapters as infrastructure
- application services as orchestration
- CLI as a thin shell

The immediate design target is a file-backed hex architecture in Python.
The longer-term target is a BEAM implementation with equivalent boundaries.

## Design Commitments

### 1. Record schemas and refactor happen together

The refactor should not merely move functions into folders. It should first
make the domain records explicit, then organize code around those records.

### 2. Filesystem storage is an adapter, not the architecture

The current `results/`, `traces/`, `artifacts/`, and archive files are useful,
but they should become one implementation of persistence ports rather than the
system's conceptual model.

### 3. `run_eval.py` remains a compatibility shell during migration

Existing commands and tests should continue to work while internals move under
`src/cheme_evals/`.

### 4. Domain records must be stable and portable

Domain record definitions should be suitable for:

- local JSON / JSONL persistence
- future analytics export
- future BEAM message contracts

## Proposed Package Layout

```text
src/cheme_evals/
  __init__.py

  domain/
    __init__.py
    records.py
    artifact_lifecycle.py
    scoring_policy.py

  application/
    __init__.py
    run_fixture.py
    score_run.py
    manage_artifacts.py
    compare_experiments.py

  ports/
    __init__.py
    model_gateway.py
    tool_executor.py
    fixture_store.py
    result_store.py
    trace_store.py
    artifact_store.py
    archive_store.py

  adapters/
    __init__.py
    providers/
      __init__.py
      anthropic_gateway.py
      openai_gateway.py
      provider_registry.py
    storage/
      __init__.py
      file_fixture_store.py
      file_result_store.py
      file_trace_store.py
      file_artifact_store.py
      file_archive_store.py
    tools/
      __init__.py
      python_subprocess_executor.py
    cli/
      __init__.py
      main.py
```

## Core Domain Records

These should be the first stable schemas extracted from `run_eval.py`.

### RunRecord

Represents one completed run.

Fields:

- `run_id`
- `eval_id`
- `fixture_id`
- `fixture_version`
- `layer`
- `timestamp`
- `git_sha`
- `agent_meta`
- `scores`
- `agent_response`
- `tool_proposals`
- `artifacts`

Current source:

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) `assemble_result`

### TraceEvent

Represents one append-only event in run execution.

Fields:

- `event_id`
- `run_id`
- `sequence`
- `timestamp`
- `type`
- `payload`

Current source:

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) `append_trace_event`

### ArtifactRecord

Represents a first-class proposed or promoted artifact.

Fields:

- `artifact_id`
- `artifact_type`
- `status`
- `summary`
- `source_run_id`
- `source_fixture_id`
- `source_fixture_version`
- `timestamp`
- `git_sha`
- `proposal`
- `validation`
- `lifecycle`

Current source:

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) `record_artifact`
- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) `transition_artifact_status`

### ArchiveRecord

Represents one append-only ledger entry.

Fields:

- `record_type`
- `record_id`
- `timestamp`
- `payload`

Current source:

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) `append_archive_record`

### ScoreBundle

Represents the scored result dimensions for one run.

Fields:

- `numeric`
- `reasoning`
- `tool_proposals`
- `overall_pct`

Current source:

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py) scoring + result assembly

## Recommended Schema Form

Near term:

- Python dataclasses or `TypedDict` in `domain/records.py`

Later:

- optional Pydantic or JSON Schema generation if stronger validation is needed

Guidance:

- use explicit field names matching persisted JSON
- avoid burying critical fields in nested untyped dicts when the structure is stable
- keep records serialization-friendly and BEAM-portable

## Ports

These are the interfaces the application layer should depend on.

### FixtureStore

Responsibilities:

- load fixture by path or ID
- enumerate fixtures

Current implementation source:

- `load_fixture`
- fixture enumeration logic in `main`

### ResultStore

Responsibilities:

- write run result
- optionally read historical run summaries

Current implementation source:

- result-writing logic in `run_fixture`

### TraceStore

Responsibilities:

- append trace events
- resolve trace path by run ID

Current implementation source:

- `append_trace_event`
- `get_trace_path`

### ArtifactStore

Responsibilities:

- create artifact
- load artifact
- update artifact
- list artifacts

Current implementation source:

- `record_artifact`
- `load_artifact`
- `save_artifact`
- `list_artifacts`
- `transition_artifact_status`

### ArchiveStore

Responsibilities:

- append archive records
- optionally query archive history

Current implementation source:

- `append_archive_record`

### ModelGateway

Responsibilities:

- invoke provider/model
- support direct response mode
- support tool loop mode

Current implementation source:

- `call_agent`
- `providers.py`

### ToolExecutor

Responsibilities:

- execute allowed tools
- return structured tool result

Current implementation source:

- `providers.py` `_execute_python_sandbox`

## Adapters

These should implement the ports above.

### File-backed storage adapters

Examples:

- `FileTraceStore`
- `FileArtifactStore`
- `FileArchiveStore`
- `FileResultStore`
- `FileFixtureStore`

These will preserve the current on-disk JSON / JSONL behavior.

### Provider adapters

Examples:

- `AnthropicGateway`
- `OpenAIGateway`

The goal is to move provider-specific request/response logic out of the
application service layer.

### Tool executor adapter

Examples:

- `PythonSubprocessExecutor`

This is an infrastructure adapter, not domain logic.

### CLI adapter

Examples:

- `adapters/cli/main.py`

This should parse arguments and call application services only.

## Application Services

These should orchestrate the domain through ports.

### RunFixtureService

Responsibilities:

- create run ID
- load fixture
- build prompts
- call model gateway
- score outputs
- persist traces, artifacts, results, archive records

Current extraction target:

- `run_fixture`

### ScoreRunService

Responsibilities:

- numeric scoring
- reasoning scoring
- proposal scoring
- overall score aggregation

Current extraction targets:

- `score_outputs`
- `score_reasoning_*`
- `score_tool_proposals`
- overall score assembly logic

### ArtifactLifecycleService

Responsibilities:

- create artifacts from proposals
- apply validated transitions
- append lifecycle archive records

Current extraction targets:

- `record_artifact`
- `transition_artifact_status`

### ExperimentComparisonService

Responsibilities:

- compare recent experiments
- summarize deltas

Current extraction target:

- `compare_experiments`

## Current Function Mapping

This maps the current script functions into future modules.

### To domain

- artifact lifecycle transition rules
- score aggregation policy
- record field definitions

### To application

- `run_fixture`
- `score_reasoning`
- `compare_experiments`

### To ports/adapters

- `append_trace_event`
- `append_archive_record`
- `load_artifact`
- `save_artifact`
- provider calls in `providers.py`
- `_execute_python_sandbox`

### To CLI shell

- `main`

## Incremental Migration Plan

### Phase 1: Introduce `src/cheme_evals/` with domain records

Do:

- create `src/cheme_evals/domain/records.py`
- define initial record types for run, trace, artifact, archive
- keep existing persistence format unchanged

Success condition:

- tests still pass
- no behavior change yet

### Phase 2: Extract file-backed persistence adapters

Do:

- move trace/archive/artifact/result file operations into adapters
- keep `run_eval.py` calling the new adapter functions

Success condition:

- no JSON / JSONL layout changes
- tests still pass unchanged

### Phase 3: Extract scoring services

Do:

- move numeric, reasoning, and proposal scoring into `application/score_run.py`
- keep result shape stable

Success condition:

- current scoring tests remain green

### Phase 4: Extract run orchestration service

Do:

- move `run_fixture` logic into `application/run_fixture.py`
- keep `run_eval.py` as a thin shell

Success condition:

- CLI behavior is unchanged
- trace/result/artifact/archive behavior remains unchanged

### Phase 5: Extract provider gateways and tool executor

Do:

- move provider selection and Anthropic tool loop behind `ModelGateway`
- move python execution behind `ToolExecutor`

Success condition:

- integration tests continue to confirm transcript families T2, T3, T9

### Phase 6: Move CLI into adapter package

Do:

- create `src/cheme_evals/adapters/cli/main.py`
- keep `run_eval.py` as a compatibility entrypoint that delegates

Success condition:

- existing commands still work
- packaging becomes straightforward

## Packaging Goal

After the extraction is stable, the repo should support:

```bash
uv run python -m cheme_evals.adapters.cli.main
```

And later a console script entrypoint if desired.

`run_eval.py` can remain temporarily as:

- a backward-compatible shim
- a transition aid for documentation and scripts

## What Not To Do

- do not mix schema design with persistence-specific hacks
- do not make the file layout the domain model
- do not force a database migration before ports exist
- do not break current CLI/operator workflows during the refactor
- do not move everything at once

## Recommended First Extraction

If starting implementation next, do this first:

1. create `src/cheme_evals/domain/records.py`
2. create `src/cheme_evals/adapters/storage/` file stores
3. update `run_eval.py` to use those stores with no behavior change

That gives the cleanest first boundary and sets up the rest of the refactor.

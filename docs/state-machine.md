# Harness State Machine

## Purpose

This document describes the core harness state machines that govern run
execution, proposal capture, artifact lifecycle, and validation. It serves two
purposes:

- design documentation for the system under construction
- validation evidence artifact that explains what behaviors the tests are meant
  to prove

It should be kept aligned with:

- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`specs/capabilities/eval-harness-governance.capability.yaml`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/capabilities/eval-harness-governance.capability.yaml)
- [`specs/features/run-traceability.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/run-traceability.feature)
- [`specs/features/tool-proposal-governance.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/tool-proposal-governance.feature)

## 1. Run Execution State Machine

### States

- `initialized`
- `fixture_loaded`
- `prompts_built`
- `agent_call_started`
- `agent_response_received`
- `scored`
- `result_written`
- `completed`
- `failed`

### Transitions

`initialized -> fixture_loaded`
Condition:
- fixture file exists and passes basic validation

`fixture_loaded -> prompts_built`
Condition:
- system and user prompts are assembled for the selected layer

`prompts_built -> agent_call_started`
Condition:
- mock path or provider/model is resolved

`agent_call_started -> failed`
Condition:
- mock mode requested but mock file is missing

`agent_call_started -> agent_response_received`
Condition:
- mock or live response is returned and parsed or captured as parse error

`agent_response_received -> scored`
Condition:
- numeric, reasoning, and proposal scoring complete

`scored -> result_written`
Condition:
- result JSON is persisted

`result_written -> completed`
Condition:
- trace and archive records are appended successfully

## Validation Mapping

- `tests/test_integration.py`
  Covers mock replay, trace creation, missing mock failure, and run archival.

## 2. Agent Interaction Loop State Machine

### States

- `waiting_for_model`
- `tool_requested`
- `tool_result_returned`
- `final_answer_returned`
- `max_turns_exhausted`

### Transitions

`waiting_for_model -> final_answer_returned`
Condition:
- model ends turn with text response

`waiting_for_model -> tool_requested`
Condition:
- model emits `tool_use`

`tool_requested -> tool_result_returned`
Condition:
- harness executes or acknowledges the requested tool and appends tool_result

`tool_result_returned -> waiting_for_model`
Condition:
- model is called again with updated message history

`waiting_for_model -> max_turns_exhausted`
Condition:
- loop exceeds configured maximum turns

## Validation Mapping

- `tests/test_integration.py`
  Covers `propose_tool` response capture and acknowledgement path.

## 3. Proposal Evaluation State Machine

### Fixture Expectation Modes

- `required`
- `optional`
- `unnecessary`
- `not_scored`

### Evaluation Rules

`required`
- Pass only if a matching proposal is made

`optional`
- Pass if no proposal is made
- Pass if a matching proposal is made
- Fail if a non-matching proposal is made

`unnecessary`
- Pass only if no proposal is made

`not_scored`
- Fixture does not declare proposal expectations

## Validation Mapping

- `tests/test_scoring.py`
  Covers `required`, `optional`, and `unnecessary` scoring logic.

## 4. Artifact Lifecycle State Machine

### States

- `proposed`
- `validated`
- `rejected`
- `promoted`
- `retired`

### Allowed Transitions

- `proposed -> validated`
- `proposed -> rejected`
- `validated -> promoted`
- `validated -> rejected`
- `validated -> retired`
- `promoted -> retired`

### Forbidden Examples

- `proposed -> promoted`
- `rejected -> validated`
- `retired -> proposed`

## Validation Mapping

- `tests/test_integration.py`
  Covers valid transition to `validated` and invalid direct promotion.

## 5. Record-Keeping State Machine

### Durable Stores

- run summary JSON under `results/`
- trace JSONL under `results/traces/`
- artifact JSON under `results/artifacts/`
- central archive JSONL under `results/archive.jsonl`

### Record Flow

When a run completes:
- write result summary
- append trace events
- append archive run record

When a proposal is captured:
- write artifact record
- append trace artifact event
- append archive artifact record

When a lifecycle transition occurs:
- update artifact record
- append archive transition record

## Why This Document Is A Validation Artifact

This document is useful as validation evidence because it states:

- what states exist
- which transitions are allowed
- which transitions are forbidden
- which tests are supposed to prove those behaviors

That means it is not just explanatory prose. It is a traceability layer between:

- architectural intent
- behavior specs
- tests
- runtime implementation

For stronger certification later, each section can be extended with direct links
to the exact tests or trace fields that provide evidence.

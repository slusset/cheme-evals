# Canonical Mock Transcripts

## Purpose

This document defines the canonical mock transcript stories for the harness.
These are not arbitrary saved responses. They are named protocol narratives that
cover the important state transitions in the system.

The goal is to avoid two failure modes:

- treating mocks as a pile of unrelated canned outputs
- trying to capture every possible branch in one giant state diagram

Instead, each canonical transcript should cover one meaningful protocol slice.

This document is both:

- a design guide for future mock construction
- a validation artifact for deciding whether transcript coverage is sufficient

It should stay aligned with:

- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`specs/features/mock-transcripts.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/mock-transcripts.feature)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)

## Transcript Design Rules

### 1. One transcript, one protocol story

Each canonical transcript should prove a specific state-machine path, not a
grab bag of unrelated behavior.

### 2. Cover transitions, not permutations

The purpose of a transcript is to validate important transitions:

- direct final answer
- tool call loop
- proposal capture
- tool failure
- parse failure
- max-turn exhaustion

Not every cross-product of fixture, model, tool, and policy.

### 3. Transcript names should encode intent

Good names:

- `direct-solve-no-tool`
- `tool-use-then-final-answer`
- `proposal-only-then-fallback-solve`
- `missing-required-proposal`
- `tool-timeout-then-recovery`
- `malformed-final-json`

Bad names:

- `mock-1`
- `flash-alt`
- `test-case-b`

### 4. Keep transcripts replayable offline

A canonical transcript should be replayable without network access. If it
depends on provider behavior that cannot be represented offline, it is not a
good canonical transcript yet.

### 5. Distinguish confirmed transcripts from hypothetical ones

Following [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md):

- confirmed transcript: encoded in tests or mocks and exercised by the harness
- hypothesis transcript: defined as a desired protocol story but not yet encoded

Do not treat a hypothetical transcript as if it were already covered.

## Canonical Transcript Set

### T1. Direct Solve, No Tool, No Proposal

Intent:
- prove the simplest run path

State-machine coverage:
- `agent_call_started -> agent_response_received -> scored -> result_written -> completed`

Use cases:
- Layer 1 or Layer 2 fixture
- no tool proposals expected

Current status:
- partially confirmed through mock-backed run integration

### T2. Proposal Only, Then Fallback Solve

Intent:
- prove that the agent can propose a missing tool and still produce a final answer

State-machine coverage:
- `waiting_for_model -> tool_requested(propose_tool) -> tool_result_returned -> waiting_for_model -> final_answer_returned`

Use cases:
- capability-gap fixtures with `required` or `optional` proposal expectation

Current status:
- confirmed through synthetic integration tests

### T3. Tool Use, Then Final Answer

Intent:
- prove the iterative tool execution loop independent of proposal capture

State-machine coverage:
- `waiting_for_model -> tool_requested(python_execute) -> tool_result_returned -> waiting_for_model -> final_answer_returned`

Use cases:
- numerical iterative calculations

Current status:
- confirmed through synthetic integration tests

### T4. Missing Required Proposal

Intent:
- prove that a run can numerically succeed yet fail proposal-quality scoring

State-machine coverage:
- proposal evaluation mode `required` with no matching proposal

Use cases:
- property-lookup fixture solved without acknowledging a true capability gap

Current status:
- hypothesis

### T5. Unnecessary Proposal

Intent:
- prove that the harness penalizes proposing tools when the fixture is locally solvable

State-machine coverage:
- proposal evaluation mode `unnecessary` with one or more proposals present

Use cases:
- provided-data fixture where the agent asks for an external tool anyway

Current status:
- confirmed at scoring level; not yet confirmed as a full transcript

### T6. Optional Proposal

Intent:
- prove that both “no proposal” and “matching proposal” are acceptable

State-machine coverage:
- proposal evaluation mode `optional`

Use cases:
- fixture with local table excerpt where a convenience lookup tool is optional

Current status:
- confirmed at scoring level; not yet confirmed as a full transcript

### T7. Malformed Final JSON

Intent:
- prove parse-failure handling and traceability

State-machine coverage:
- `agent_response_received` with parse error captured

Use cases:
- resilience of result assembly and trace recording

Current status:
- hypothesis

### T8. Tool Failure Or Timeout, Then Recovery

Intent:
- prove that a failed tool call is observable and that the run can still complete or fail cleanly

State-machine coverage:
- `tool_requested -> tool_result_returned(error) -> waiting_for_model`

Use cases:
- sandbox timeout
- disallowed tool behavior
- calculation failure

Current status:
- hypothesis

### T9. Mock Mode Missing Transcript

Intent:
- prove that mock replay is strict and never falls back to live execution

State-machine coverage:
- `agent_call_started -> failed`

Current status:
- confirmed through integration tests

## Coverage Strategy

The harness does not need dozens of transcript families immediately.

A practical order is:

1. T1 direct solve
2. T2 proposal then fallback solve
3. T9 missing mock failure
4. T3 tool use then final answer
5. T4 missing required proposal
6. T5 unnecessary proposal
7. T7 malformed final JSON
8. T8 tool failure or timeout

That sequence gives strong protocol coverage without exploding maintenance cost.

## Validation Role

This document serves as validation evidence when it is used to answer:

- which protocol stories are confirmed
- which are only hypothesized
- which tests or mocks prove each transcript
- which transitions still lack offline replay coverage

It should be updated whenever:

- a new transcript family becomes confirmed
- a transcript is retired as redundant
- the state machine gains a new meaningful branch

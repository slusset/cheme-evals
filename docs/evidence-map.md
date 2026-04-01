# Evidence Map

## Purpose

This document maps governing intent to specifications, implementation, and
validation evidence. It is the repo's current traceability bridge from
principle to proof.

It should be read alongside:

- [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md)
- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)

## Pillar 1: Declare Intent Before Acting

### Intent

Know why before deciding what.

### Spec Artifacts

- [`specs/capabilities/eval-harness-governance.capability.yaml`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/capabilities/eval-harness-governance.capability.yaml)
- [`specs/features/run-traceability.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/run-traceability.feature)
- [`specs/features/tool-proposal-governance.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/tool-proposal-governance.feature)
- [`specs/features/mock-transcripts.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/mock-transcripts.feature)

### Implementation Evidence

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py)
  `run_id`, fixture metadata, scoring mode, proposal expectation handling, artifact lifecycle

### Test Evidence

- [`tests/test_integration.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_integration.py)
- [`tests/test_fixtures.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_fixtures.py)

## Pillar 2: Verify Outcomes Against Declared Intent

### Intent

Check what happened against what was supposed to happen.

### Spec Artifacts

- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`specs/features/run-traceability.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/run-traceability.feature)
- [`docs/mock-transcripts.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/mock-transcripts.md)

### Implementation Evidence

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py)
  append-only trace events, archive records, result persistence, proposal scoring

### Test Evidence

- [`tests/test_integration.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_integration.py)
  mock replay, missing mock failure, trace ordering, archive records, lifecycle transitions

- [`tests/test_results.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_results.py)
  result shape and score aggregation

## Pillar 3: Classify What Is Learned

### Intent

Keep confirmed knowledge distinct from hypothesis.

### Spec Artifacts

- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
  artifact lifecycle and proposal evaluation states

- [`specs/features/tool-proposal-governance.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/tool-proposal-governance.feature)

### Implementation Evidence

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py)
  heuristic reasoning labels, artifact status machine, archive transition records

### Test Evidence

- [`tests/test_scoring.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_scoring.py)
  heuristic scoring labels, proposal scoring modes

- [`tests/test_integration.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_integration.py)
  artifact transition validation and invalid transition rejection

## Pillar 4: Crystallize Confirmed Patterns

### Intent

Turn validated patterns into durable system behavior.

### Spec Artifacts

- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`specs/capabilities/eval-harness-governance.capability.yaml`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/capabilities/eval-harness-governance.capability.yaml)

### Implementation Evidence

- [`run_eval.py`](/Users/tedslusser/PycharmProjects/cheme-evals/run_eval.py)
  first-class artifacts, archive ledger, governed transitions, CLI for artifact lifecycle

- [`README.md`](/Users/tedslusser/PycharmProjects/cheme-evals/README.md)
  explicit operator workflow for artifact review and promotion

### Test Evidence

- [`tests/test_integration.py`](/Users/tedslusser/PycharmProjects/cheme-evals/tests/test_integration.py)
  artifact record persistence, archive creation, CLI lifecycle management

## Current Confidence Boundaries

### Confirmed

- runs receive stable `run_id` values
- traces are written per run
- archive ledger records runs, artifacts, and transitions
- tool proposals are first-class artifacts
- artifact transitions are validated
- proposal quality is scored for fixtures that declare expectations
- canonical transcript family T3 is confirmed for `python_execute` tool use followed by final answer

### Hypothesis / Not Yet Fully Confirmed

- live model behavior against the new proposal fixtures
- long multi-turn transcript replay beyond the current integration cases
- canonical transcript families T4, T7, and T8 from `docs/mock-transcripts.md`
- certification-grade evidence coverage beyond current tests
- eventual BEAM equivalence of these architectural boundaries

These should not be treated as settled facts until exercised and validated.

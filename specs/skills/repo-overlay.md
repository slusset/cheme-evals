# Repo Overlay

## Scope

This repository is a Python-based eval harness prototype intended to validate
architecture and workflow concepts before a later BEAM implementation.

## Preferred Skills

- Workflow orchestration: `idd-workflow`
- Requirements / system framing: `solution-narrative`
- Behavior specification: `behavior-contract`
- Validation evidence: `certification`

## Authoritative Architecture Docs

- [`SOUL.md`](/Users/tedslusser/PycharmProjects/cheme-evals/SOUL.md)
- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)

## Architecture Constraints

- `SOUL.md` is a governing document, not optional prose.
- The repo is a traceable prototype, not the final runtime.
- Traceability, replayability, and explicit promotion take priority over convenience.
- Artifacts must be recorded with provenance and lifecycle state.
- Mock mode must not silently fall back to live execution.
- Heuristic scoring must not be presented as authoritative judging.
- Tool proposal quality is a distinct scoring dimension from reasoning quality.

## Testing Commands

- Unit and integration tests: `uv run pytest`
- Coverage check: `uv run --with pytest-cov pytest --cov=run_eval --cov=providers --cov-report=term-missing -q`

## Tooling Constraints

- Dependency management uses `uv`
- Test runner is `pytest`
- Primary harness entrypoint is `run_eval.py`
- Durable records are stored under `results/`
  - run summaries
  - traces
  - artifacts
  - archive ledger

## CI / Certification Expectations

- Changes to eval flow should preserve traceability and replayability.
- New runtime behaviors should be covered by focused tests.
- New fixture sets should be encoded as versioned JSON fixtures and validated by tests.
- State-machine and lifecycle changes should update both documentation and tests.

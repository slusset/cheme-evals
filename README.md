# ChemE Agent Eval Harness

A reproducible evaluation framework for domain-tailored AI agents operating
in chemical engineering process simulation.

## Core Concept

Every eval is a **fixture**: a frozen, version-controlled test case that defines
an engineering problem with known correct answers. Run any agent against the
fixtures. Score the results. Compare across runs, agents, and git commits.

## Directory Structure

```
eval-harness/
  fixtures/           # Test cases (the "textbook problems")
  mocks/              # Recorded tool outputs for deterministic replay
  results/            # Scored outcomes from eval runs
  schemas/            # JSON schemas defining fixture format
  scripts/            # Eval runner, scorer, mock recorder
```

## Fixture Anatomy

A fixture has five parts:

1. **Problem** - What the agent is asked to do (natural language + structured data)
2. **Inputs** - The known values, in engineering units
3. **Expected outputs** - The correct answers, from a verified source
4. **Acceptance criteria** - How close is close enough (tolerances)
5. **Domain context** - What tools, models, and knowledge apply

## Running an eval

```bash
uv sync

# Baseline: Layer 1, Sonnet, no skills
uv run python run_eval.py --layer 1 --tag "baseline-L1-sonnet"

# Add skills: Layer 2, same model
uv run python run_eval.py --layer 2 --tag "with-skills-L2-sonnet"

# Different model: Layer 1, Opus
uv run python run_eval.py --layer 1 --provider anthropic --model claude-opus-4-0-20250514 --tag "baseline-L1-opus"

# See what changed
uv run python run_eval.py --compare
```

## Running tests

```bash
uv run pytest
```

## Artifact workflow

Tool proposals are recorded as first-class artifacts in `results/artifacts/`,
indexed in `results/archive.jsonl`, and linked back to runs and traces.
For fixtures that declare a tool proposal expectation, proposal quality is also
scored as an explicit evaluation dimension.

```bash
# List all artifacts
uv run python run_eval.py --list-artifacts

# List only proposed tool artifacts
uv run python run_eval.py --list-artifacts --artifact-status proposed --artifact-type tool

# Show one artifact
uv run python run_eval.py --show-artifact --artifact-id <artifact-id>

# Validate an artifact
uv run python run_eval.py --transition-artifact validated --artifact-id <artifact-id> --reviewer ted --notes "Passed initial review"

# Promote a validated artifact
uv run python run_eval.py --transition-artifact promoted --artifact-id <artifact-id> --reviewer ted

```

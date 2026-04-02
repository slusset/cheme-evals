# ChemE Agent Eval Harness

A reproducible evaluation framework for domain-tailored AI agents operating
in chemical engineering process simulation.

## Core Concept

Every eval is a **fixture**: a frozen, version-controlled test case that defines
an engineering problem with known correct answers. Run any agent against the
fixtures. Score the results. Compare across runs, agents, and git commits.

## Evaluation Tiers (L1 / L2 / L3)

The harness tests agent capability at three progressively harder tiers.
The same fixture is used at every tier — what changes is *what information
the agent receives* and *what tools it has access to*.

| Tier | Problem Data | Reference Data | Skills | Tools | What It Tests |
|------|-------------|----------------|--------|-------|---------------|
| **L1** | Provided | Provided | None | None | Can the agent solve the problem when all values are given? Pure reasoning + calculation. |
| **L2** | Provided | **Suppressed** | Loaded from `agent/skills/` | None | Can the agent retrieve the reference data it needs (Antoine coefficients, critical properties, etc.) from skill documents? |
| **L3** | Provided | **Suppressed** | Loaded | `python_execute`, `propose_tool` | Can the agent write code, execute it, and propose new tools for problems that require computational approaches? |

**How it works in the fixture:** Each input has an `input_class` field —
either `"problem_data"` (always provided) or `"reference_data"` (provided at
L1, suppressed at L2/L3). The harness builds the prompt differently per tier.

**Example:** A flash distillation problem gives the agent feed composition and
pressure (problem data) at all tiers. At L1 it also gives Antoine coefficients;
at L2 the agent must look them up in the Antoine parameters skill document.

## Scoring

Agents are scored on three dimensions:

- **Numeric accuracy** (50% weight) — Is the answer within tolerance?
- **Reasoning quality** (30% weight) — Did the agent demonstrate correct
  methodology? (keyword heuristic + optional LLM judge)
- **Tool proposals** (20% weight) — Did the agent propose tools when the
  fixture expected it? (L3 only, scored as required/optional/unnecessary)

## Directory Structure

```
cheme-evals/
  fixtures/           # Test cases (JSON) — the "textbook problems"
  agent/skills/       # Reference documents loaded at L2/L3
  mocks/              # Recorded agent responses for deterministic replay
  results/            # Scored outcomes, traces, artifacts, experiments
  src/cheme_evals/    # Hexagonal architecture: domain/ports/application/adapters
  tests/              # 103 tests covering fixtures, scoring, harness
  docs/               # Architecture, state machine, data collection protocol
```

## Fixture Anatomy

A fixture has five parts:

1. **Problem** — What the agent is asked to do (natural language + structured data)
2. **Inputs** — The known values, in engineering units, with `input_class` tags
3. **Expected outputs** — The correct answers, from a verified source
4. **Acceptance criteria** — Tolerances (absolute or relative), reasoning keywords
5. **Domain context** — Recommended tools, thermo models, common mistakes

## Running an Eval

```bash
uv sync

# Baseline: Layer 1, Sonnet, all data provided
uv run python run_eval.py --layer 1 --tag "baseline-L1-sonnet"

# Add skills: Layer 2, agent must retrieve reference data
uv run python run_eval.py --layer 2 --tag "with-skills-L2-sonnet"

# Tool use: Layer 3, agent can write + execute code
uv run python run_eval.py --layer 3 --tag "tool-use-L3-sonnet"

# Different model
uv run python run_eval.py --layer 1 --provider anthropic --model claude-opus-4-0-20250514 --tag "baseline-L1-opus"

# Compare experiments
uv run python run_eval.py --compare
```

## Running Tests

```bash
uv run pytest -q      # 103 tests, ~0.2s
just check            # tests + architecture contracts
```

## Fixture Status

| Fixture | Difficulty | Topic | Status |
|---------|-----------|-------|--------|
| flash-distillation-01 | Introductory | VLE flash, binary benzene/toluene | Complete |
| scibench-thermo-1.3 | Introductory | Van der Waals EOS, real gas | Complete |
| scibench-thermo-1.5 | Intermediate | Ideal gas mixture composition | Complete |
| scibench-thermo-2.13 | Intermediate | First law, electrical heating | Complete |
| scibench-thermo-8.13 | Intermediate | Clausius-Clapeyron, autoclave | Complete |
| scibench-thermo-8.25 | Intermediate | Clausius-Clapeyron, altitude | Complete |
| scibench-thermo-9.8 | Introductory | Raoult's law, ideal solution | Complete |
| local-steam-table-interpolation-01 | Intermediate | Steam table lookup | Complete |
| provided-antoine-ethanol-01 | Introductory | Antoine equation, ethanol | Complete |
| steam-table-saturation-01 | Intermediate | Saturation properties | Complete |
| multistage-flash-01 | Intermediate | Multi-stage flash separation | Complete |

## Artifact Workflow

Tool proposals from L3 runs are recorded as first-class artifacts with a
governed lifecycle: `proposed → validated → promoted → retired`.

```bash
uv run python run_eval.py --list-artifacts
uv run python run_eval.py --show-artifact --artifact-id <id>
uv run python run_eval.py --transition-artifact validated --artifact-id <id> --reviewer ted --notes "Passed review"
uv run python run_eval.py --transition-artifact promoted --artifact-id <id> --reviewer ted
```

## Running Experiments

The project follows a disciplined experiment protocol: **no claim without a
planned run, no run without a hypothesis, no result without classification.**

See [`docs/data-collection-protocol.md`](docs/data-collection-protocol.md) for
the full plan, including report claims, evidence gaps, and the run plan.

Quick experiment workflow:

1. Pick a fixture and tier from the run plan
2. Write down your hypothesis (what you expect and why)
3. Run: `uv run python run_eval.py --fixture fixtures/<name>.json --layer <N> --tag "<description>"`
4. Inspect: `uv run python run_eval.py --trace-summary --run-id <id>`
5. Classify: confirmed / refuted / inconclusive
6. Log the result in `RUN_LOG.md`
7. Compare across runs: `uv run python run_eval.py --compare`

Results are stored in `results/experiments.jsonl` (experiment-level) and
individual JSON files per run. Traces are append-only in `results/traces/`.

## Workflow Shortcuts

```bash
just test             # pytest
just arch             # import linter (hex architecture contracts)
just check            # test + arch
just eval --fixture fixtures/flash-distillation-01.json --mock
```

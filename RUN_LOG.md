# Run Log

Canonical record of all evaluation runs and verification attempts.
Each entry should trace back to a planned run in
[`docs/data-collection-protocol.md`](docs/data-collection-protocol.md) Part 2,
or be marked as exploratory.

This file is append-only.

## Environment

<!-- Fill in once and update if it changes -->

| Property         | Value                    |
|------------------|--------------------------|
| Python           | 3.12.12                  |
| OS               | macOS 15.7.3             |
| Default provider | Anthropic                |
| Default model    | claude-sonnet-4-20250514 |

## Runs

| Run ID | Date       | agent llm | judge llm | Fixture      | Layer | Hypothesis                      | Result                                       | Classification                      | Claims Supported |
|--------|------------|-----------|-----------|--------------|-------|---------------------------------|----------------------------------------------|-------------------------------------|------------------|
| R01    | 2026-04-01 | sonnet    | opus      | (test suite) | —     | Tests pass at reported count    | Sandbox Python 3.10, project requires >=3.12 | Inconclusive — environment mismatch | V1               |
| R01    | 2026-04-01 | sonnet    | opus      | (test suite) | —     | Tests pass from local env       | Tests pass                                   | Confirmed                           | V1               |
| R01    | 2026-04-01 | sonnet    | opus      | (test suite) | —     | Tests pass from local env       | Tests pass                                   | Confirmed                           | V1               |
| R03    | 2026-04-01 | sonnet    | opus      | all          | L1    | LLM judge results higher scores | Average: 95.4%                               | Confirmed                           | S1               |
| R03    | 2026-04-01 | sonnet    | opus      | all          | L2    | tool use results higher scores  | Average: 86.0%                               | Fail                                |                  |
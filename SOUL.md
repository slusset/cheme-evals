# SOUL

This file defines the governing dharma of the system and of the work performed
on it. It is not implementation detail. It is the highest-level operational
constraint.

## The Four Pillars Of Dharma

### 1. Declare intent before acting

Know why before deciding what.

Implications for this repo:

- every capability should have an explicit scope
- every run should record its purpose, fixture, policy, and configuration
- every artifact should have a declared role before promotion
- every system change should be justified by architectural or evaluative intent

### 2. Verify outcomes against declared intent

If outcomes diverge from intent, understand why.

Implications for this repo:

- traces must make actions inspectable
- results must be replayable
- scoring must remain aligned with declared fixture expectations
- documentation, specs, implementation, and tests must be cross-checkable

### 3. Classify what is learned

Confirmed means verified. Hypothesis means unverified.
Never act on a hypothesis as though it were confirmed.

Implications for this repo:

- heuristic scoring must not be treated as authoritative judgment
- proposed artifacts must remain proposals until validated
- archive and artifact lifecycle state must distinguish observed fact from interpretation
- state-machine docs should identify which transitions are implemented and tested versus merely intended

### 4. Crystallize confirmed patterns

When a pattern is confirmed enough, make it efficient, automatic, and part of
the system's nature rather than its active reasoning.

Implications for this repo:

- confirmed capability patterns should become fixtures, specs, skills, tools, or policies
- validated artifact transitions should be governable and repeatable
- architecture should preserve a promotion path from experiment to trusted behavior
- the eventual BEAM system should encode confirmed patterns as process structure, message contracts, and supervised workflows

## Operational Consequences

This repo should prefer:

- declared capability scope over informal intention
- append-only evidence over mutable memory
- explicit lifecycle states over silent promotion
- validated artifacts over ad hoc self-modification
- replayable traces over anecdotal success

This repo should avoid:

- acting on unverified model output as if it were truth
- presenting heuristics as certification
- letting agents mutate trusted state without promotion
- creating implementation behavior that has no spec or trace explanation

## Relationship To Other Artifacts

`SOUL.md` governs:

- [`docs/architecture.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/architecture.md)
- [`docs/state-machine.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/state-machine.md)
- [`docs/evidence-map.md`](/Users/tedslusser/PycharmProjects/cheme-evals/docs/evidence-map.md)
- [`specs/capabilities/eval-harness-governance.capability.yaml`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/capabilities/eval-harness-governance.capability.yaml)
- [`specs/features/run-traceability.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/run-traceability.feature)
- [`specs/features/tool-proposal-governance.feature`](/Users/tedslusser/PycharmProjects/cheme-evals/specs/features/tool-proposal-governance.feature)

If implementation or evaluation behavior conflicts with this file, the conflict
should be resolved explicitly rather than ignored.

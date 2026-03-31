---
name: ChemE evals long-term vision
description: BEAM/ReasoningNode integration, self-organizing agents, ad-hoc tool generation
type: project
---

Goal is not just evaluating ChemE reasoning but building toward self-organizing agent architecture.

**Why:** Exploring whether smaller LLMs can be fine-tuned for domain specialization, generate their own tools, and develop collaboration protocols autonomously.

**How to apply:** Every feature added to the eval harness should move toward this architecture, not just "better evals":
- Fixture expansion → training data for fine-tuning
- LLM judge → self-evaluation capability
- Tool loop (L3) → foundation for ad-hoc tool generation
- BEAM/ReasoningNode merge → agents that can experiment with their own reasoning strategies

Key milestones mentioned by user:
1. Expand fixture dataset (current step)
2. Merge with BEAM and ReasoningNode architecture
3. Agents generate and self-eval their own ad-hoc tools
4. Agents optimize their own "reasoning in head" vs "use tools" decisions
5. Self-organization and collaboration protocols

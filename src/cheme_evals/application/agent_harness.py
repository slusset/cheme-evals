"""Independently testable agent pipeline.

This module exposes the agent harness without scoring, tracing, or result
storage.  Use it to diagnose prompt construction, skill injection, and
agent retrieval quality separately from the eval scoring pipeline.
"""

from cheme_evals.ports.eval_runner import AgentPort, PromptPort


def run_agent_harness(
    *,
    prompts: PromptPort,
    agent: AgentPort,
    fixture: dict,
    layer: int = 1,
    mock_path: str = None,
    provider_name: str = None,
    model: str = None,
) -> dict:
    """Run the agent pipeline without scoring.

    Returns the system prompt, user prompt, and agent response
    for independent inspection and testing.
    """
    system_prompt = prompts.build_system_prompt(fixture, layer=layer)
    user_prompt = prompts.build_user_prompt(fixture, layer=layer)
    response = agent.call_agent(
        system_prompt,
        user_prompt,
        mock_path,
        provider_name=provider_name,
        model=model,
        layer=layer,
    )
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response,
    }

"""Agent runtime and replay services."""

import json
import os
import time
from pathlib import Path
from typing import Callable


def call_agent(
    system_prompt: str,
    user_prompt: str,
    mock_path: str = None,
    *,
    provider_name: str = None,
    model: str = None,
    layer: int = 1,
    resolve_provider_fn: Callable[[str | None], str],
    providers: dict,
    get_api_key_fn: Callable[[str], str],
    anthropic_tool_loop_fn: Callable[..., dict],
) -> dict:
    """Send the problem to the agent or replay a mock response."""
    if mock_path:
        if not os.path.exists(mock_path):
            raise FileNotFoundError(
                f"Requested mock response does not exist: {mock_path}"
            )
        print(f"  [mock] Loading from {mock_path}")
        with open(mock_path) as f:
            return json.load(f)

    provider_name = resolve_provider_fn(provider_name)
    provider = providers[provider_name]
    model = model or provider["default_model"]
    api_key = get_api_key_fn(provider_name)

    if layer == 3 and provider_name == "anthropic":
        print(f"  [live] Calling {provider_name} ({model}) with tool loop...")
        start_time = time.time()
        raw = anthropic_tool_loop_fn(
            system=system_prompt,
            user=user_prompt,
            model=model,
            temperature=0,
            max_tokens=4096,
            api_key=api_key,
        )
    else:
        print(f"  [live] Calling {provider_name} ({model})...")
        start_time = time.time()
        raw = provider["call"](
            system=system_prompt,
            user=user_prompt,
            model=model,
            temperature=0,
            max_tokens=4096,
            api_key=api_key,
        )

    elapsed = time.time() - start_time
    cleaned = raw["text"].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        response = json.loads(cleaned)
    except json.JSONDecodeError as error:
        response = {
            "parse_error": str(error),
            "raw_text": raw["text"],
            "outputs": {},
        }

    meta = {
        "provider": provider_name,
        "model": raw["model"],
        "temperature": 0,
        "elapsed_seconds": round(elapsed, 2),
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
    }
    if "tool_turns" in raw:
        meta["tool_turns"] = raw["tool_turns"]
    if "tool_proposals" in raw:
        meta["tool_proposals"] = raw["tool_proposals"]
    response["_meta"] = meta
    return response


def save_mock(response: dict, fixture_id: str, *, mocks_dir: Path) -> Path:
    """Save a response as a deterministic replay mock."""
    mock_dir = mocks_dir / "agent-responses"
    mock_dir.mkdir(parents=True, exist_ok=True)
    mock_path = mock_dir / f"{fixture_id}.json"
    with open(mock_path, "w") as f:
        json.dump(response, f, indent=2)
    print(f"  [mock] Saved to {mock_path}")
    return mock_path

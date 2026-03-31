"""
LLM provider abstraction — zero third-party dependencies.

Each provider translates a (system_prompt, user_prompt, model, temperature,
max_tokens) call into an HTTP request and normalises the response into a
common shape:

    {
        "text":          str,   # raw completion text
        "model":         str,   # model actually used
        "input_tokens":  int,
        "output_tokens": int,
    }

Supported providers:
    anthropic   — Anthropic Messages API
    openai      — OpenAI Chat Completions API (also Azure)
    openrouter  — OpenRouter (any model)

Adding a new provider:
    1. Write a function with signature (system, user, model, temperature,
       max_tokens, api_key) -> dict  that returns the shape above.
    2. Register it in PROVIDERS.
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_json(url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
    """POST JSON and return the parsed response body."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode(errors="replace")
        raise RuntimeError(
            f"{e.code} from {url}:\n{error_body}"
        ) from None


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"

def call_anthropic(system: str, user: str, model: str, temperature: float,
                   max_tokens: int, api_key: str) -> dict:
    resp = _post_json(
        url="https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        body={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
    )
    return {
        "text": resp["content"][0]["text"],
        "model": resp.get("model", model),
        "input_tokens": resp["usage"]["input_tokens"],
        "output_tokens": resp["usage"]["output_tokens"],
    }


# ---------------------------------------------------------------------------
# Anthropic — Layer 3 tool-use loop
# ---------------------------------------------------------------------------

PYTHON_EXECUTE_TOOL = {
    "name": "python_execute",
    "description": (
        "Execute Python code and return stdout/stderr. Use for iterative "
        "numerical calculations (e.g., bisection, Newton-Raphson, Rachford-Rice). "
        "The code runs in a sandboxed subprocess with a 30-second timeout. "
        "Use print() to return results."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use print() to output results.",
            }
        },
        "required": ["code"],
    },
}


def _execute_python_sandbox(code: str, timeout: int = 30) -> dict:
    """Run Python code in a subprocess with minimal environment."""
    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=safe_env,
        )
        return {
            "stdout": result.stdout[-10_000:],
            "stderr": result.stderr[-5_000:],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds",
            "exit_code": -1,
        }


def call_anthropic_tool_loop(system: str, user: str, model: str,
                             temperature: float, max_tokens: int,
                             api_key: str, max_turns: int = 10) -> dict:
    """
    Multi-turn tool-use loop for Layer 3.

    The model can call python_execute to run iterative calculations,
    then incorporate the results into its final JSON answer.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    messages = [{"role": "user", "content": user}]
    total_input = 0
    total_output = 0
    tool_turns = 0

    for turn in range(max_turns):
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
            "tools": [PYTHON_EXECUTE_TOOL],
        }
        resp = _post_json(
            url="https://api.anthropic.com/v1/messages",
            headers=headers,
            body=body,
            timeout=180,
        )

        total_input += resp["usage"]["input_tokens"]
        total_output += resp["usage"]["output_tokens"]

        # Append assistant response to conversation history
        messages.append({"role": "assistant", "content": resp["content"]})

        if resp["stop_reason"] == "end_turn":
            # Extract text from content blocks
            text = "".join(
                block["text"] for block in resp["content"]
                if block["type"] == "text"
            )
            return {
                "text": text,
                "model": resp.get("model", model),
                "input_tokens": total_input,
                "output_tokens": total_output,
                "tool_turns": tool_turns,
            }

        if resp["stop_reason"] == "tool_use":
            tool_results = []
            for block in resp["content"]:
                if block["type"] == "tool_use":
                    tool_turns += 1
                    code = block["input"]["code"]
                    print(f"    [tool] Turn {tool_turns}: executing python ({len(code)} chars)...")
                    result = _execute_python_sandbox(code)

                    # Format output for the model
                    output = result["stdout"]
                    if result["stderr"]:
                        output += f"\n[stderr]\n{result['stderr']}"
                    if result["exit_code"] != 0:
                        output += f"\n[exit_code: {result['exit_code']}]"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": output or "(no output)",
                    })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop_reason — bail
        break

    # Fell through max_turns — extract whatever text the model produced
    text = ""
    for msg in reversed(messages):
        if msg["role"] == "assistant" and isinstance(msg["content"], list):
            text = "".join(
                b["text"] for b in msg["content"]
                if isinstance(b, dict) and b.get("type") == "text"
            )
            if text:
                break
    text += "\n\n[WARNING: max tool turns reached, answer may be incomplete]"
    return {
        "text": text,
        "model": model,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "tool_turns": tool_turns,
    }


# ---------------------------------------------------------------------------
# OpenAI-compatible  (OpenAI, Azure, local servers)
# ---------------------------------------------------------------------------

OPENAI_DEFAULT_MODEL = "gpt-4o"

def call_openai(system: str, user: str, model: str, temperature: float,
                max_tokens: int, api_key: str) -> dict:
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    resp = _post_json(
        url=f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    choice = resp["choices"][0]["message"]
    usage = resp.get("usage", {})
    return {
        "text": choice["content"],
        "model": resp.get("model", model),
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


# ---------------------------------------------------------------------------
# OpenRouter  (any model via openrouter.ai)
# ---------------------------------------------------------------------------

OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"

def call_openrouter(system: str, user: str, model: str, temperature: float,
                    max_tokens: int, api_key: str) -> dict:
    resp = _post_json(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    choice = resp["choices"][0]["message"]
    usage = resp.get("usage", {})
    return {
        "text": choice["content"],
        "model": resp.get("model", model),
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PROVIDERS = {
    "anthropic": {
        "call": call_anthropic,
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": ANTHROPIC_DEFAULT_MODEL,
    },
    "openai": {
        "call": call_openai,
        "env_key": "OPENAI_API_KEY",
        "default_model": OPENAI_DEFAULT_MODEL,
    },
    "openrouter": {
        "call": call_openrouter,
        "env_key": "OPENROUTER_API_KEY",
        "default_model": OPENROUTER_DEFAULT_MODEL,
    },
}

DEFAULT_PROVIDER = "anthropic"


def resolve_provider(name: str | None) -> str:
    """Return a valid provider name, falling back to DEFAULT_PROVIDER."""
    if name is None:
        return DEFAULT_PROVIDER
    if name not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown provider {name!r}. Choose from: {available}")
    return name


def get_api_key(provider_name: str) -> str:
    """Read the API key from the environment or raise a clear error."""
    env_var = PROVIDERS[provider_name]["env_key"]
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(f"{env_var} not set (required for provider {provider_name!r})")
    return key

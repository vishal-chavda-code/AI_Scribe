"""LLM client abstraction. Supports Anthropic and OpenAI-compatible endpoints."""

import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))


def get_completion(system_prompt: str, messages: list) -> str:
    """Send messages to the configured LLM and return the response text.

    Args:
        system_prompt: The system-level instruction.
        messages: List of dicts with 'role' and 'content' keys.

    Returns:
        The assistant's response text.
    """
    if PROVIDER == "anthropic":
        return _anthropic_completion(system_prompt, messages)
    else:
        return _openai_completion(system_prompt, messages)


def _anthropic_completion(system_prompt: str, messages: list) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _openai_completion(system_prompt: str, messages: list) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_tokens=MAX_TOKENS,
        messages=full_messages,
    )
    return response.choices[0].message.content

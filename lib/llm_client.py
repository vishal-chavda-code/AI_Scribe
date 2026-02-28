"""LLM client — OpenAI-compatible endpoint only."""

import os
from dotenv import load_dotenv

load_dotenv()

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))


def get_completion(system_prompt: str, messages: list) -> str:
    """Send messages to the configured LLM and return the response text.

    Args:
        system_prompt: The system-level instruction.
        messages: List of dicts with 'role' and 'content' keys.

    Returns:
        The assistant's response text.
    """
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

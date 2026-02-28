"""LLM client — OpenAI-compatible endpoint only."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Safe MAX_TOKENS parsing ────────────────────────────────────────────────────────
_DEFAULT_MAX_TOKENS = 16384

try:
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", str(_DEFAULT_MAX_TOKENS)))
except (ValueError, TypeError):
    MAX_TOKENS = _DEFAULT_MAX_TOKENS
    logger.warning(
        "Invalid MAX_TOKENS value in .env — falling back to %d", _DEFAULT_MAX_TOKENS
    )

# ── LLM timeout (seconds) ────────────────────────────────────────────────────
try:
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
except (ValueError, TypeError):
    LLM_TIMEOUT = 120

# ── OpenAI client (reuse across calls for connection pooling) ────────────
_client = None


def _get_client():
    """Return (and cache) an OpenAI client instance."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            timeout=LLM_TIMEOUT,
        )
    return _client


def validate_llm_config() -> tuple[bool, str]:
    """Check that required LLM environment variables are set.

    Returns:
        Tuple of (is_valid, message).
    """
    missing = []
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        val = os.getenv(var)
        if not val or val.startswith("your-"):
            missing.append(var)
    if missing:
        return False, f"Missing or placeholder values for: {', '.join(missing)}. Check your .env file."
    return True, "LLM config OK"


def get_completion(system_prompt: str, messages: list) -> str:
    """Send messages to the configured LLM and return the response text.

    Args:
        system_prompt: The system-level instruction.
        messages: List of dicts with 'role' and 'content' keys.

    Returns:
        The assistant's response text.

    Raises:
        RuntimeError: If the LLM returns an empty response.
    """
    client = _get_client()
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_tokens=MAX_TOKENS,
        messages=full_messages,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(
            "LLM returned an empty response. The model may have refused the request "
            "or hit a content filter. Try rephrasing or reducing input size."
        )
    return content

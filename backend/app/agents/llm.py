"""Shared LLM routing helpers for local agents."""

DIRECT_MODEL_ALIASES = {
    "claude-sonnet": "anthropic/claude-sonnet-4-20250514",
    "claude-haiku": "anthropic/claude-3-5-haiku-20241022",
}


def resolve_model_alias(model_name: str) -> str:
    return DIRECT_MODEL_ALIASES.get(model_name, model_name)

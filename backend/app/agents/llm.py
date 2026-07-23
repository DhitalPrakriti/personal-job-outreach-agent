"""Shared LLM routing helpers for local agents."""

DIRECT_MODEL_ALIASES = {
    "claude-opus": "anthropic/claude-opus-4-8",
    "claude-sonnet": "anthropic/claude-sonnet-5",
    "claude-haiku": "anthropic/claude-haiku-4-5",
}


def resolve_model_alias(model_name: str) -> str:
    return DIRECT_MODEL_ALIASES.get(model_name, model_name)

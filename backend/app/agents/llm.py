"""Shared LLM routing helpers for local agents."""

DIRECT_MODEL_ALIASES = {
    "gemini-flash-lite": "gemini/gemini-3.5-flash-lite",
    "gemini-flash": "gemini/gemini-3.6-flash",
    "gemini-pro": "gemini/gemini-3.5-flash",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "claude-opus": "anthropic/claude-opus-4-8",
    "claude-sonnet": "anthropic/claude-sonnet-5",
    "claude-haiku": "anthropic/claude-haiku-4-5",
    "local-smollm": "ollama/smollm2:135m",
    "local-qwen": "ollama/qwen2.5:0.5b",
}


def resolve_model_alias(model_name: str) -> str:
    return DIRECT_MODEL_ALIASES.get(model_name, model_name)

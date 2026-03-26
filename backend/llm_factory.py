"""Helpers for constructing ChatOpenAI clients safely across model families."""

from langchain_openai import ChatOpenAI


def supports_temperature(model: str) -> bool:
    """Return whether this model family supports custom temperature values."""
    normalized = (model or "").strip().lower()
    # Current GPT-5 variants reject non-default temperature settings.
    return not normalized.startswith("gpt-5")


def create_chat_model(model: str, api_key: str, temperature: float | None = None) -> ChatOpenAI:
    """Create ChatOpenAI with only supported arguments for the model."""
    kwargs = {
        "model": model,
        "api_key": api_key,
    }
    if supports_temperature(model):
        if temperature is not None:
            kwargs["temperature"] = temperature
    else:
        # GPT-5 family currently accepts only the default temperature of 1.
        kwargs["temperature"] = 1
    return ChatOpenAI(**kwargs)

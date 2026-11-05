"""Provider table: prefix -> SDK, base URL and API-key env vars."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    sdk: str  # "openai" | "anthropic"
    base_url: str | None = None  # default base URL (None = SDK default)
    base_url_env: str | None = None  # env var that overrides the base URL
    key_envs: tuple[str, ...] = ()  # env vars tried in order for the API key
    key_required: bool = True


PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in [
        Provider("openai", "openai", None, "OPENAI_BASE_URL", ("OPENAI_API_KEY",)),
        Provider("anthropic", "anthropic", None, "ANTHROPIC_BASE_URL", ("ANTHROPIC_API_KEY",)),
        Provider("ollama", "openai", "http://localhost:11434/v1", "OLLAMA_BASE_URL", ("OLLAMA_API_KEY",), False),
        Provider("groq", "openai", "https://api.groq.com/openai/v1", "GROQ_BASE_URL", ("GROQ_API_KEY",)),
        Provider("openrouter", "openai", "https://openrouter.ai/api/v1", "OPENROUTER_BASE_URL", ("OPENROUTER_API_KEY",)),
        Provider("together", "openai", "https://api.together.ai/v1", "TOGETHER_BASE_URL", ("TOGETHER_API_KEY",)),
        Provider("deepseek", "openai", "https://api.deepseek.com", "DEEPSEEK_BASE_URL", ("DEEPSEEK_API_KEY",)),
        Provider(
            "gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai/",
            "GEMINI_BASE_URL", ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        ),
        Provider("mistral", "openai", "https://api.mistral.ai/v1", "MISTRAL_BASE_URL", ("MISTRAL_API_KEY",)),
        Provider("xai", "openai", "https://api.x.ai/v1", "XAI_BASE_URL", ("XAI_API_KEY",)),
    ]
}


def parse_model(model: str) -> tuple[Provider, str]:
    """Split ``"provider/model-id"``. The model id may itself contain slashes
    (``openrouter/anthropic/claude-sonnet-5-5``, ``together/meta-llama/...``)."""
    if "/" not in model:
        raise ValueError(
            f"Model {model!r} must look like 'provider/model', e.g. 'openai/gpt-5'. "
            f"Providers: {', '.join(PROVIDERS)}."
        )
    prefix, rest = model.split("/", 1)
    provider = PROVIDERS.get(prefix.lower())
    if provider is None:
        raise ValueError(f"Unknown provider {prefix!r} in model {model!r}. Providers: {', '.join(PROVIDERS)}.")
    if not rest:
        raise ValueError(f"Model {model!r} is missing a model id after the provider.")
    return provider, rest

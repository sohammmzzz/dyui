"""Provider table: base URLs + key env vars, verified against each provider's docs (Nov 2026)."""
from __future__ import annotations

import pytest

from dyui.llm._providers import PROVIDERS, parse_model

EXPECTED = {
    "openai": (None, "OPENAI_API_KEY"),
    "anthropic": (None, "ANTHROPIC_API_KEY"),
    "ollama": ("http://localhost:11434/v1", "OLLAMA_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "together": ("https://api.together.ai/v1", "TOGETHER_API_KEY"),
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_provider_table(name):
    p = PROVIDERS[name]
    url, key = EXPECTED[name]
    assert p.base_url == url and p.key_envs[0] == key
    assert p.base_url is None or p.base_url.startswith(("https://", "http://localhost"))


def test_no_unexpected_providers():
    assert set(PROVIDERS) == set(EXPECTED)


@pytest.mark.parametrize("model,provider,rest", [
    ("openai/gpt-5", "openai", "gpt-5"),
    ("OpenRouter/anthropic/claude-sonnet-5-5", "openrouter", "anthropic/claude-sonnet-5-5"),
    ("together/meta-llama/Llama-4", "together", "meta-llama/Llama-4"),
])
def test_parse_model(model, provider, rest):
    p, r = parse_model(model)
    assert p.name == provider and r == rest


@pytest.mark.parametrize("bad", ["gpt-5", "nope/x", "openai/"])
def test_parse_model_errors(bad):
    with pytest.raises(ValueError):
        parse_model(bad)

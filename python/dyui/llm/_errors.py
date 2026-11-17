"""Friendly errors for the llm helpers."""
from __future__ import annotations

API_KEYS_DOCS = "https://sohammmzzz.github.io/dyui/get-started/api-keys/"


class MissingDependencyError(ImportError):
    """Raised when an optional SDK (openai / anthropic) is not installed."""


class MissingAPIKeyError(RuntimeError):
    """Raised before any request when a provider needs an API key and none is set.

    The message names the environment variable(s) to set, never a value, so it is
    safe to show in the chat.
    """

    def __init__(self, provider: str, envs: tuple[str, ...]) -> None:
        self.provider = provider
        self.envs = envs
        names = " or ".join(envs) if envs else "an API key"
        super().__init__(
            f"{names} is not set (needed for '{provider}/' models). "
            f"Add it to a .env file next to app.py (dyui run loads it), set it in your shell, "
            f"or pass api_key=... to dyui.llm.stream(). See {API_KEYS_DOCS}"
        )


def missing_sdk(extra: str, package: str | None = None) -> MissingDependencyError:
    package = package or extra
    return MissingDependencyError(
        f"dyui.llm needs the '{package}' package for this model. "
        f'Install it with:  pip install "dyui[{extra}]"'
    )

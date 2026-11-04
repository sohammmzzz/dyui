"""Friendly errors for the llm helpers."""
from __future__ import annotations


class MissingDependencyError(ImportError):
    """Raised when an optional SDK (openai / anthropic) is not installed."""


def missing_sdk(extra: str, package: str | None = None) -> MissingDependencyError:
    package = package or extra
    return MissingDependencyError(
        f"dyui.llm needs the '{package}' package for this model. "
        f'Install it with:  pip install "dyui[{extra}]"'
    )

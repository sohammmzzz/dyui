"""The DyUI MCP server: version-exact DyUI docs, component schemas and validators for coding agents.

Run it with ``dyui mcp`` (or ``python -m dyui.mcp``); register it with ``dyui mcp install``.
The server needs the optional ``mcp`` package (``pip install "dyui[mcp]"``). The helper
modules (``docs``, ``introspect``, ``check``, ``install``) do not, and are importable on their own.
"""
from __future__ import annotations

__all__ = ["available", "INSTALL_HINT"]

INSTALL_HINT = 'pip install "dyui[mcp]"'


def available() -> bool:
    """Whether the ``mcp`` SDK the server needs is importable."""
    import importlib.util

    for module in ("mcp.server.mcpserver", "mcp.server.fastmcp"):  # mcp 2.x, then 1.x
        try:
            if importlib.util.find_spec(module) is None:
                continue
            if module.endswith("fastmcp"):
                __import__(module)  # mcp 2.x keeps a stub that raises on import
            return True
        except (ImportError, ValueError):
            continue
    return False

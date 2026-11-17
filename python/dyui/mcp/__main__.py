"""``python -m dyui.mcp``: run the DyUI MCP server over stdio (same as ``dyui mcp``)."""
from __future__ import annotations

from .server import main

if __name__ == "__main__":
    raise SystemExit(main())

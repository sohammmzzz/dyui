"""Generate docs/src/data/components.json from the live dyui component registry.

The component facts (fields, examples, signatures) come from ``dyui.mcp.introspect``, the
same module the DyUI MCP server's ``get_component`` tool uses, so the docs site and what a
coding agent sees can never drift. Every Python example is *executed* against the installed
package, so the docs never show a constructor call that doesn't work.

Usage:  python docs/scripts/gen_components.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import dyui
from dyui.mcp.introspect import component_classes, component_record

sys.path.insert(0, str(Path(__file__).resolve().parent))
from component_apps import component_app  # noqa: E402  (a complete app.py per component page)

OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "components.json"


def main() -> int:
    try:
        comps = [component_record(cls) for cls in component_classes()]
    except ValueError as exc:  # a component with no working Python example
        raise SystemExit(f"gen_components: {exc}") from None
    for comp in comps:
        comp["app"] = component_app(comp)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": dyui.__version__, "components": comps}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"gen_components: wrote {len(comps)} components -> {OUT.relative_to(OUT.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import { describe, expect, it } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { getHljs, loadHljs, useHljs } from "./hljs";
import { highlight } from "../shell/highlight";
import { highlight as highlightNodes } from "../components/dyui/util/highlight";

describe("lazy highlight.js", () => {
  it("renders plain text until loaded, then highlights", async () => {
    // before load: both highlighters degrade to plain text
    expect(highlight(getHljs(), "x = 1", "python")).toBeNull();
    expect(highlightNodes(getHljs(), "x = 1", "python").nodes).toBe("x = 1");

    const { result } = renderHook(() => useHljs());
    await waitFor(() => expect(result.current).not.toBeNull());
    const hl = getHljs()!;
    expect(hl.getLanguage("python")).toBeTruthy();
    expect(hl.getLanguage("tsx")).toBeTruthy(); // alias
    expect(hl.getLanguage("console")).toBeTruthy();

    const html = highlight(hl, "def f(): return 1", "py");
    expect(html).toContain("hljs-keyword");
    expect(highlight(hl, "x", "not-a-language")).toBeNull();
    const nodes = highlightNodes(hl, "const a = 1", "ts");
    expect(nodes.language).toBe("ts");
    expect(typeof nodes.nodes).not.toBe("string");
  });

  it("loads once", async () => {
    const [a, b] = await act(() => Promise.all([loadHljs(), loadHljs()]));
    expect(a).toBe(b);
  });
});

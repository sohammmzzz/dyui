import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MarkdownCard, ProgressCard } from "../src/cards/builtins";
import type { DyUICard } from "../src/types";

function card(props: Record<string, unknown>): DyUICard {
  return { id: "1", component: "x", props, status: "done", surface: "default" };
}

function render(node: React.ReactElement): string {
  return renderToStaticMarkup(node);
}

describe("MarkdownCard", () => {
  it("renders [text](url) as a safe link", () => {
    const html = render(
      <MarkdownCard
        card={card({})}
        props={{ text: "see [docs](https://example.com)" }}
        status="done"
      />
    );
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain(">docs</a>");
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("does not linkify javascript: schemes", () => {
    const html = render(
      <MarkdownCard
        card={card({})}
        props={{ text: "[x](javascript:alert(1))" }}
        status="done"
      />
    );
    expect(html.toLowerCase()).not.toContain("href=");
  });

  it("still renders bold and code", () => {
    const html = render(
      <MarkdownCard card={card({})} props={{ text: "**b** and `c`" }} status="done" />
    );
    expect(html).toContain("<strong>b</strong>");
    expect(html).toContain("c</code>");
  });
});

describe("ProgressCard", () => {
  it("renders a literal label, never NaN, for non-numeric values", () => {
    const html = render(
      <ProgressCard card={card({})} props={{ value: "oops" }} status="done" />
    );
    expect(html).not.toContain("NaN");
    expect(html).toContain("0%");
  });

  it("computes a percentage for numeric values", () => {
    const html = render(
      <ProgressCard card={card({})} props={{ value: 1, max: 4 }} status="done" />
    );
    expect(html).toContain("25%");
  });
});

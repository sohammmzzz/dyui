// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";

import { sanitizeHtml } from "../src/cards/sanitize";

/** Does the sanitized output still contain an executable handler/scheme? */
function isNeutralised(out: string): boolean {
  const lower = out.toLowerCase();
  return (
    !/\son\w+\s*=/.test(lower) &&
    !lower.includes("javascript:") &&
    !lower.includes("<script") &&
    !lower.includes("<iframe") &&
    !lower.includes("<svg") &&
    !lower.includes("vbscript:")
  );
}

describe("sanitizeHtml — known bypasses of the old regex sanitizer", () => {
  // Each of these passed straight through the previous regex implementation.
  const bypasses: Array<[string, string]> = [
    ["svg/onload separator", "<svg/onload=alert(1)>"],
    ["img/onerror slash separator", "<img/src=x/onerror=alert(1)>"],
    ["unquoted javascript: href", "<a href=javascript:alert(1)>x</a>"],
    ["entity-obfuscated scheme", '<a href="java&Tab;script:alert(1)">x</a>'],
    ["button formaction", "<button formaction=javascript:alert(1)>x</button>"],
    ["details ontoggle", "<details/open/ontoggle=alert(1)>x</details>"],
    ["svg set attributeName", "<svg><set attributeName=onmouseover>x</svg>"],
    ["newline in scheme", '<a href="java\nscript:alert(1)">x</a>'],
  ];

  for (const [name, payload] of bypasses) {
    it(`neutralises ${name}`, () => {
      const out = sanitizeHtml(payload);
      expect(isNeutralised(out), `leaked: ${out}`).toBe(true);
    });
  }

  it("still blocks the classic vectors", () => {
    expect(sanitizeHtml("<script>alert(1)</script>")).not.toContain("<script");
    expect(sanitizeHtml('<img src=x onerror="alert(1)">')).not.toMatch(/onerror/i);
  });
});

describe("sanitizeHtml — preserves safe markup", () => {
  it("keeps allowed tags, text and inline styles", () => {
    const out = sanitizeHtml(
      '<div style="color:red"><strong>Berlin</strong> 21&deg;</div>'
    );
    expect(out).toContain("<strong>Berlin</strong>");
    expect(out).toContain("color:red");
  });

  it("keeps safe links and images", () => {
    const out = sanitizeHtml('<a href="https://example.com">ok</a>');
    expect(out).toContain('href="https://example.com"');
    const img = sanitizeHtml('<img src="https://x/y.png" alt="pic">');
    expect(img).toContain('src="https://x/y.png"');
  });

  it("unwraps unknown tags but keeps their text", () => {
    const out = sanitizeHtml("<unknown>hello</unknown>");
    expect(out).not.toContain("<unknown");
    expect(out).toContain("hello");
  });

  it("strips a dangerous inline style but keeps the element", () => {
    const out = sanitizeHtml(
      '<div style="background:url(javascript:alert(1))">hi</div>'
    );
    expect(out).toContain("hi");
    expect(out.toLowerCase()).not.toContain("javascript:");
  });

  it("returns empty for non-strings", () => {
    // @ts-expect-error testing runtime guard
    expect(sanitizeHtml(null)).toBe("");
    // @ts-expect-error testing runtime guard
    expect(sanitizeHtml(42)).toBe("");
  });
});

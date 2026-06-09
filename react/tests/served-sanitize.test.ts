// @vitest-environment happy-dom
//
// The served zero-frontend UI (python/dyui/static/index.html) ships its own
// JS `sanitize()` for `html` cards. It has no React/DOMPurify override path, so
// it must be robust on its own. This test extracts that exact function from the
// shipped HTML and runs the known regex-sanitizer bypasses against it.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// vitest runs with cwd = the react package dir; the served page lives a level up.
const html = readFileSync(
  resolve(process.cwd(), "../python/dyui/static/index.html"),
  "utf-8"
);

// Pull the sanitizer block (SAN_ALLOW ... function sanitize) out of the page.
const match = html.match(/const SAN_ALLOW[\s\S]*?return doc\.body\.innerHTML;}/);
if (!match) throw new Error("could not locate sanitize() in served index.html");
// eslint-disable-next-line @typescript-eslint/no-implied-eval
const sanitize = new Function(match[0] + "\nreturn sanitize;")() as (
  h: string
) => string;

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

describe("served index.html sanitize() — bypasses neutralised", () => {
  const bypasses: Array<[string, string]> = [
    ["svg/onload separator", "<svg/onload=alert(1)>"],
    ["img/onerror slash separator", "<img/src=x/onerror=alert(1)>"],
    ["unquoted javascript: href", "<a href=javascript:alert(1)>x</a>"],
    ["entity-obfuscated scheme", '<a href="java&Tab;script:alert(1)">x</a>'],
    ["button formaction", "<button formaction=javascript:alert(1)>x</button>"],
    ["details ontoggle", "<details/open/ontoggle=alert(1)>x</details>"],
    ["svg set attributeName", "<svg><set attributeName=onmouseover>x</svg>"],
  ];
  for (const [name, payload] of bypasses) {
    it(`neutralises ${name}`, () => {
      expect(isNeutralised(sanitize(payload)), `leaked: ${sanitize(payload)}`).toBe(
        true
      );
    });
  }

  it("preserves safe markup and inline styles", () => {
    const out = sanitize('<div style="color:red"><strong>Berlin</strong></div>');
    expect(out).toContain("<strong>Berlin</strong>");
    expect(out).toContain("color:red");
  });
});

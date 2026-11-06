import { afterEach, describe, expect, it } from "vitest";
import { appBase, fileUrl, isFileUrl, safeLink, safeMarkdownHref, safeMedia } from "./url";
import { safeMediaUrl, safeUrl } from "../components/dyui/util/props";
import { safeUrl as shellSafeUrl } from "../shell/Markdown";

const setBase = (href: string | null) => {
  document.querySelectorAll("base").forEach((b) => b.remove());
  if (href) {
    const b = document.createElement("base");
    b.href = href;
    document.head.appendChild(b);
  }
};
afterEach(() => setBase(null));

const HOSTILE = [
  "javascript:alert(1)",
  "JaVaScRiPt:alert(1)",
  " javascript:alert(1)",
  "java\tscript:alert(1)",
  "java\nscript:alert(1)",
  "\u0001javascript:alert(1)",
  "data:text/html,<script>alert(1)</script>",
  "data:image/svg+xml;base64,PHN2Zz4=",
  "vbscript:msgbox(1)",
  "file:///etc/passwd",
  "//evil.example/x",
  "/\\evil.example",
  "\\\\evil.example\\share",
  "https:\\\\evil.example",
  "api/files/../secret",
  "api/files/f_1/../../x",
  "api/files//evil.example",
  "api/files/f_1:2",
];

describe("safeLink / safeMedia", () => {
  it("allows http(s) and mailto", () => {
    expect(safeLink("https://example.com/a?b=1")).toBe("https://example.com/a?b=1");
    expect(safeLink("http://example.com")).toBe("http://example.com/");
    expect(safeLink("mailto:hi@example.com")).toBe("mailto:hi@example.com");
    expect(safeMedia("mailto:hi@example.com")).toBeNull();
  });

  it("rejects hostile and malformed URLs", () => {
    for (const u of HOSTILE) {
      expect(safeLink(u), u).toBeNull();
      expect(safeMedia(u), u).toBeNull();
      expect(safeUrl(u), u).toBeNull();
      expect(safeMediaUrl(u), u).toBeNull();
    }
    expect(safeLink(42)).toBeNull();
    expect(safeLink("")).toBeNull();
    expect(safeLink("https://")).toBeNull();
  });

  it("resolves the app's file URLs (relative and absolute forms)", () => {
    expect(isFileUrl("api/files/f_abc123")).toBe(true);
    expect(isFileUrl("/api/files/f_abc123")).toBe(true);
    expect(isFileUrl("https://x.test/api/files/f_1")).toBe(false);
    expect(safeLink("api/files/f_abc123")).toBe("/api/files/f_abc123");
    expect(safeMedia("/api/files/f_abc123")).toBe("/api/files/f_abc123");
  });

  it("resolves file URLs against a sub-path mount", () => {
    setBase("http://localhost/tools/bot/");
    expect(appBase()).toBe("/tools/bot/");
    expect(fileUrl("api/files/f_1")).toBe("/tools/bot/api/files/f_1");
    expect(fileUrl("/api/files/f_1")).toBe("/tools/bot/api/files/f_1");
    expect(safeMediaUrl("api/files/f_1")).toBe("/tools/bot/api/files/f_1");
  });
});

describe("chat markdown hrefs", () => {
  it("keeps anchors and app-relative paths, blocks the rest", () => {
    expect(safeMarkdownHref("#notes")).toBe("#notes");
    expect(safeMarkdownHref("/docs/start")).toBe("/docs/start");
    expect(safeMarkdownHref("./x")).toBe("./x");
    expect(shellSafeUrl("https://example.com")).toBe("https://example.com/");
    for (const u of HOSTILE) expect(shellSafeUrl(u), u).toBe("");
  });
});

import { afterEach, describe, expect, it } from "vitest";
import { cspNonce, withNonce } from "./Html";

describe("html component CSP nonce", () => {
  afterEach(() => document.head.querySelectorAll('meta[name="dyui-csp-nonce"]').forEach((m) => m.remove()));

  it("reads the page nonce from the server's meta tag", () => {
    expect(cspNonce()).toBeNull();
    const m = document.createElement("meta");
    m.name = "dyui-csp-nonce";
    m.content = "abc123_-XYZ";
    document.head.append(m);
    expect(cspNonce()).toBe("abc123_-XYZ");
  });

  it("ignores a malformed nonce (no attribute injection)", () => {
    const m = document.createElement("meta");
    m.name = "dyui-csp-nonce";
    m.content = 'x" onload="alert(1)';
    document.head.append(m);
    expect(cspNonce()).toBeNull();
  });

  it("stamps every script tag, replacing existing nonces", () => {
    const html = `<script>a()</script><SCRIPT type="module">b()</SCRIPT><script nonce="old" src="x.js"></script><script nonce='o2'>c()</script><p>script</p>`;
    const out = withNonce(html, "N1");
    expect(out.match(/<script nonce="N1"/gi)?.length).toBe(4);
    expect(out).not.toMatch(/old|o2/);
    expect(out).toContain("<p>script</p>");
  });

  it("is a no-op without a nonce (CSP disabled)", () => {
    expect(withNonce("<script>a()</script>", null)).toBe("<script>a()</script>");
  });
});

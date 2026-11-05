/** Code highlighting for chat markdown; the highlighter itself loads lazily (see lib/hljs). */
import type { HLJSApi } from "highlight.js";

/** Highlighted HTML (hljs escapes the source), or null when the language is unknown. */
export function highlight(hljs: HLJSApi | null, code: string, language: string | null | undefined): string | null {
  if (!hljs || !language) return null;
  const lang = language.toLowerCase();
  if (!hljs.getLanguage(lang)) return null;
  try {
    return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
  } catch {
    return null;
  }
}

/** Pretty label for the code block header. */
export function languageLabel(language: string | null | undefined): string {
  if (!language) return "text";
  const l = language.toLowerCase();
  const names: Record<string, string> = {
    js: "javascript",
    ts: "typescript",
    py: "python",
    sh: "bash",
    yml: "yaml",
    md: "markdown",
    rs: "rust",
    cs: "c#",
    csharp: "c#",
    cpp: "c++",
    txt: "text",
    plaintext: "text",
  };
  return names[l] ?? l;
}

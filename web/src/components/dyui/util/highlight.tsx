/**
 * Syntax highlighting with highlight.js (loaded lazily: see lib/hljs; pass `useHljs()`).
 * hljs returns escaped HTML made only of <span class="hljs-*"> — we convert that
 * string to React elements with a tiny tokenizer (no innerHTML, SSR-safe).
 */
import { Fragment, createElement, type ReactNode } from "react";
import type { HLJSApi } from "highlight.js";

const LABELS: Record<string, string> = {
  js: "JavaScript", javascript: "JavaScript", jsx: "JSX", ts: "TypeScript", typescript: "TypeScript", tsx: "TSX",
  py: "Python", python: "Python", sh: "Shell", bash: "Bash", shell: "Shell", zsh: "Zsh", json: "JSON", sql: "SQL",
  html: "HTML", xml: "XML", css: "CSS", yaml: "YAML", yml: "YAML", md: "Markdown", markdown: "Markdown", go: "Go",
  rust: "Rust", rs: "Rust", java: "Java", c: "C", cpp: "C++", csharp: "C#", cs: "C#", ruby: "Ruby", rb: "Ruby",
  php: "PHP", swift: "Swift", kotlin: "Kotlin", kt: "Kotlin", diff: "Diff", dockerfile: "Dockerfile", docker: "Dockerfile",
  toml: "TOML", ini: "INI", text: "Text", plaintext: "Text", console: "Console",
};
export const languageLabel = (lang?: string) => (lang ? LABELS[lang.toLowerCase()] ?? lang : undefined);

const ENT: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#x27;": "'", "&#39;": "'" };
const unescape = (s: string) => s.replace(/&(?:amp|lt|gt|quot|#x27|#39);/g, (m) => ENT[m] ?? m);

type TNode = { cls: string; children: (TNode | string)[] };

function toReact(html: string): ReactNode[] {
  const root: TNode = { cls: "", children: [] };
  const stack: TNode[] = [root];
  const re = /<span class="([^"]*)">|<\/span>|([^<]+)|(<)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) {
    if (m[1] !== undefined) {
      const n: TNode = { cls: m[1], children: [] };
      stack[stack.length - 1].children.push(n);
      stack.push(n);
    } else if (m[0] === "</span>") {
      if (stack.length > 1) stack.pop();
    } else {
      stack[stack.length - 1].children.push(unescape(m[2] ?? m[3] ?? ""));
    }
  }
  let k = 0;
  const build = (n: TNode | string): ReactNode =>
    typeof n === "string" ? n : createElement("span", { key: k++, className: n.cls }, n.children.map(build));
  return root.children.map(build);
}

/** Highlight `code`; returns React nodes plus the resolved language name. */
export function highlight(hljs: HLJSApi | null, code: string, language?: string): { nodes: ReactNode; language?: string } {
  const lang = language?.toLowerCase().trim();
  if (!hljs) return { nodes: code, language: lang };
  try {
    if (lang && hljs.getLanguage(lang)) {
      const r = hljs.highlight(code, { language: lang, ignoreIllegals: true });
      return { nodes: createElement(Fragment, null, ...toReact(r.value)), language: lang };
    }
    if (!lang && code.length < 4000 && code.includes("\n")) {
      const r = hljs.highlightAuto(code, ["python", "javascript", "typescript", "bash", "json", "sql", "yaml", "css", "xml", "go", "rust"]);
      if (r.relevance >= 5 && r.language) return { nodes: createElement(Fragment, null, ...toReact(r.value)), language: r.language };
    }
  } catch {
    /* fall through to plain text */
  }
  return { nodes: code, language: lang };
}

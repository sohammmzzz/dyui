/**
 * Syntax highlighting with highlight.js core + common languages.
 * hljs returns escaped HTML made only of <span class="hljs-*"> — we convert that
 * string to React elements with a tiny tokenizer (no innerHTML, SSR-safe).
 */
import { Fragment, createElement, type ReactNode } from "react";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import kotlin from "highlight.js/lib/languages/kotlin";
import markdown from "highlight.js/lib/languages/markdown";
import php from "highlight.js/lib/languages/php";
import plaintext from "highlight.js/lib/languages/plaintext";
import python from "highlight.js/lib/languages/python";
import ruby from "highlight.js/lib/languages/ruby";
import rust from "highlight.js/lib/languages/rust";
import shell from "highlight.js/lib/languages/shell";
import sql from "highlight.js/lib/languages/sql";
import swift from "highlight.js/lib/languages/swift";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

const LANGS: Record<string, any> = {
  bash, c, cpp, csharp, css, diff, dockerfile, go, ini, java, javascript, json, kotlin, markdown,
  php, plaintext, python, ruby, rust, shell, sql, swift, typescript, xml, yaml,
};
let registered = false;
function ensure() {
  if (registered) return;
  registered = true;
  for (const [name, def] of Object.entries(LANGS)) hljs.registerLanguage(name, def);
  hljs.registerAliases(["toml"], { languageName: "ini" });
  hljs.registerAliases(["zsh", "sh", "console"], { languageName: "bash" });
  hljs.registerAliases(["jsx"], { languageName: "javascript" });
  hljs.registerAliases(["tsx"], { languageName: "typescript" });
  hljs.registerAliases(["text", "txt"], { languageName: "plaintext" });
}

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
export function highlight(code: string, language?: string): { nodes: ReactNode; language?: string } {
  ensure();
  const lang = language?.toLowerCase().trim();
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

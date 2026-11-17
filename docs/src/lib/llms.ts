// Builds /llms.txt (an index of every page) and /llms-full.txt (every page as Markdown,
// with the complete examples inlined) from the same content the site renders.
//
// MDX contract (shared with the DyUI MCP server's docs reader): complete examples appear
// only as inline fenced code, or as `import x from "<rel>/examples/<f>.py?raw"` plus
// `<Code code={x} lang="python" title="app.py" />`. Other imports and JSX are dropped;
// `<TabItem label="X">` becomes a **X** sub-heading.
import { getCollection } from "astro:content";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import data from "../data/components.json";
import { GROUP_LABELS, SECTIONS } from "../data/nav.mjs";

type Page = { slug: string; title: string; description: string; section: string; markdown: string };

const site = (import.meta.env.SITE ?? "").replace(/\/$/, "");
const base = import.meta.env.BASE_URL.replace(/\/?$/, "/");
/** Absolute URL of a page slug ("concepts/actions" → …/concepts/actions/), or of a file ("llms-full.txt"). */
export const url = (slug: string) => {
  const s = slug.replace(/^\/|\/$/g, "");
  return `${site}${base}${s}${s && !s.includes(".") ? "/" : ""}`;
};

/** MDX body → plain Markdown, following the contract above. */
export function resolveMdx(body: string, filePath: string | undefined): string {
  const raws = new Map<string, string>();
  const dir = filePath ? dirname(resolve(filePath)) : process.cwd();
  body = body.replace(/^import\s+(\w+)\s+from\s+["']([^"']+)\?raw["'];?\s*$/gm, (_m, name: string, rel: string) => {
    raws.set(name, readFileSync(resolve(dir, rel), "utf8").replace(/\r\n?/g, "\n"));
    return "";
  });
  body = body.replace(/^import\s.+$/gm, "");
  body = body.replace(/<Code\s+([^>]*?)\/>/g, (_m, attrs: string) => {
    const name = /code=\{(\w+)\}/.exec(attrs)?.[1];
    const code = name ? raws.get(name) : undefined;
    if (code === undefined) return "";
    const lang = /lang="([^"]+)"/.exec(attrs)?.[1] ?? "";
    const title = /title="([^"]+)"/.exec(attrs)?.[1];
    return "```" + lang + (title ? ` title="${title}"` : "") + "\n" + code.replace(/\n*$/, "\n") + "```";
  });
  body = body.replace(/<TabItem\s+label="([^"]+)"\s*>/g, "**$1**");
  body = body.replace(/<\/?(Tabs|TabItem|Aside)[^>]*>/g, "");
  body = body.replace(/^\s*<[A-Z][\w.]*[^>]*\/>\s*$/gm, "");
  return body.replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

function componentMarkdown(c: (typeof data.components)[number]): string {
  const props = c.fields
    .map((f) => `| \`${f.name}\` | \`${f.type.replace(/\|/g, "\\|")}\` | ${f.required ? "required" : JSON.stringify(f.default ?? null)} |`)
    .join("\n");
  const app = (c as { app?: string }).app ?? "";
  return [
    `${c.description}${c.details ? " " + c.details : ""}`,
    `Python: \`ui.${c.class}\` · group: ${GROUP_LABELS[c.group as keyof typeof GROUP_LABELS]} · ${c.llm ? "offered to the model" : "never offered to the model"}`,
    c.llm ? "Prompt line:\n\n```text\n" + c.signature + "\n```" : "",
    "| Prop | Type | Default |\n|---|---|---|\n" + props,
    app ? "Complete example:\n\n```python title=\"app.py\"\n" + app + "```" : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

/** Every page, in sidebar order. */
export async function pages(): Promise<Page[]> {
  const entries = await getCollection("docs");
  const bySlug = new Map(entries.map((e) => [e.id.replace(/\/index$/, "").replace(/^index$/, ""), e]));
  const out: Page[] = [];
  const used = new Set<string>();
  const add = (slug: string, section: string) => {
    const e = bySlug.get(slug);
    if (!e || used.has(slug)) return;
    used.add(slug);
    out.push({
      slug,
      section,
      title: e.data.title,
      description: e.data.description ?? "",
      // relative links (../../concepts/actions/) become absolute, since the file is read on its own
      markdown: resolveMdx(e.body ?? "", e.filePath).replace(/\]\((\.\.?\/[^)\s]*)\)/g, (_m, rel: string) =>
        site ? `](${new URL(rel, url(slug)).href})` : `](${rel})`,
      ),
    });
  };
  for (const s of SECTIONS as Array<Record<string, any>>) {
    if (s.link) add(s.link.replace(/^\/|\/$/g, ""), s.label);
    else if (s.components) {
      out.push({ slug: "components", section: s.label, title: "Components", description: "Every built-in component.", markdown: "" });
      for (const c of data.components) {
        out.push({ slug: `components/${c.name}`, section: s.label, title: c.name, description: c.description.replace(/`/g, ""), markdown: componentMarkdown(c) });
      }
    } else {
      for (const i of s.items) {
        if (i.api) {
          for (const slug of [...bySlug.keys()].filter((k) => k.startsWith("reference/api")).sort()) add(slug, `${s.label}: ${i.label}`);
        } else add(i.link.replace(/^\/|\/$/g, ""), s.label);
      }
    }
  }
  // anything not in the sidebar (except the splash page) goes last
  for (const slug of [...bySlug.keys()].sort()) if (slug && !used.has(slug)) add(slug, "More");
  return out;
}

export const INTRO =
  "DyUI is a Python framework for generative-UI chat apps: an LLM (or your code) replies with tables, charts, cards, " +
  "forms and buttons, rendered in a finished chat app. `pip install dyui`, write an `app.py` with `dyui.App` and an " +
  "`@app.on_message` handler that yields text and `ui.*` components (or streams `dyui.llm.stream(model, chat.history, " +
  "components=app.catalog)`), then `dyui run app.py`. `dyui run` loads `.env` next to the app; model keys go there " +
  "(e.g. NVIDIA_API_KEY).";

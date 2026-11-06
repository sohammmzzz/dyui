// DyUI docs — Astro + Starlight (SPEC §8).
// Live demos import the real component library from ../web/src, so web fixes flow through.
import { defineConfig, passthroughImageService } from "astro/config";
import starlight from "@astrojs/starlight";
import react from "@astrojs/react";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const { components } = JSON.parse(readFileSync(here("./src/data/components.json"), "utf8"));

// GitHub Pages serves the site at /dyui; other hosts (Vercel, Netlify) can set DOCS_BASE=/
const base = process.env.DOCS_BASE ?? "/dyui";
const site = process.env.DOCS_SITE ?? "https://sohammmzzz.github.io";

const GROUP_LABELS = {
  content: "Content", data: "Data", media: "Media", interactive: "Interactive",
  layout: "Layout", agent: "Agent", developer: "Developer-only",
};
const componentGroups = Object.entries(GROUP_LABELS).map(([group, label]) => ({
  label,
  collapsed: true,
  items: components
    .filter((c) => c.group === group)
    .map((c) => ({ label: c.name, link: `/components/${c.name}/` })),
}));

export default defineConfig({
  site,
  base,
  trailingSlash: "always",
  image: { service: passthroughImageService() },
  integrations: [
    react(),
    starlight({
      title: "DyUI",
      description: "Chatbots that answer in interfaces — the Python framework for generative-UI chat apps.",
      logo: { light: "../brand/wordmark.svg", dark: "../brand/wordmark-dark.svg", alt: "DyUI", replacesTitle: true },
      favicon: "/favicon.svg",
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/sohammmzzz/dyui" }],
      editLink: { baseUrl: "https://github.com/sohammmzzz/dyui/edit/main/docs/" },
      lastUpdated: false,
      customCss: [
        "@fontsource-variable/instrument-sans/standard.css",
        "@fontsource/instrument-serif/400.css",
        "@fontsource/instrument-serif/400-italic.css",
        "@fontsource-variable/geist-mono",
        "./src/styles/theme.css",
      ],
      expressiveCode: {
        themes: ["github-light", "github-dark-dimmed"],
        styleOverrides: {
          borderRadius: "12px",
          borderColor: "var(--dy-border)",
          codeFontFamily: "var(--dy-font-mono)",
          uiFontFamily: "var(--dy-font)",
          codeFontSize: "13.5px",
          frames: { shadowColor: "transparent" },
        },
      },
      head: [
        { tag: "meta", attrs: { name: "theme-color", content: "#F7F6F3", media: "(prefers-color-scheme: light)" } },
        { tag: "meta", attrs: { name: "theme-color", content: "#0B0C10", media: "(prefers-color-scheme: dark)" } },
      ],
      sidebar: [
        {
          label: "Get started",
          items: [
            { label: "Installation", link: "/get-started/installation/" },
            { label: "Quickstart", link: "/get-started/quickstart/" },
            { label: "Your first LLM bot", link: "/get-started/first-llm-bot/" },
            { label: "Project structure", link: "/get-started/project-structure/" },
          ],
        },
        {
          label: "Concepts",
          items: [
            { label: "How DyUI works", link: "/concepts/how-it-works/" },
            { label: "Messages & streaming", link: "/concepts/messages-and-streaming/" },
            { label: "Generative UI", link: "/concepts/generative-ui/" },
            { label: "Custom components", link: "/concepts/custom-components/" },
            { label: "Actions & human-in-the-loop", link: "/concepts/actions/" },
            { label: "Steps & reasoning", link: "/concepts/steps-and-reasoning/" },
            { label: "Sessions & persistence", link: "/concepts/sessions-and-persistence/" },
            { label: "Theming & branding", link: "/concepts/theming/" },
            { label: "Authentication", link: "/concepts/auth/" },
          ],
        },
        {
          label: "Components",
          items: [{ label: "Overview", link: "/components/" }, ...componentGroups],
        },
        {
          label: "Integrations",
          items: [
            { label: "OpenAI", link: "/integrations/openai/" },
            { label: "Anthropic", link: "/integrations/anthropic/" },
            { label: "Ollama & local models", link: "/integrations/ollama/" },
            { label: "Groq, OpenRouter & others", link: "/integrations/other-providers/" },
            { label: "LangGraph", link: "/integrations/langgraph/" },
            { label: "Bring your own SDK", link: "/integrations/bring-your-own-sdk/" },
          ],
        },
        {
          label: "Deploy",
          items: [
            { label: "Production server", link: "/deploy/production/" },
            { label: "Docker", link: "/deploy/docker/" },
            { label: "Render, Fly & Railway", link: "/deploy/platforms/" },
            { label: "Behind a reverse proxy", link: "/deploy/reverse-proxy/" },
          ],
        },
        {
          label: "Cookbook",
          items: [
            { label: "Travel bot", link: "/cookbook/travel-bot/" },
            { label: "Data analyst", link: "/cookbook/data-analyst/" },
            { label: "Support bot", link: "/cookbook/support-bot/" },
            { label: "LangGraph agent", link: "/cookbook/langgraph-agent/" },
            { label: "No-LLM bot", link: "/cookbook/no-llm-bot/" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "CLI", link: "/reference/cli/" },
            { label: "Protocol", link: "/reference/protocol/" },
            { label: "Python API", collapsed: true, items: [{ autogenerate: { directory: "reference/api" } }] },
          ],
        },
        { label: "Changelog", link: "/changelog/" },
      ],
    }),
  ],
  vite: {
    resolve: {
      // the component library lives in ../web/src and must share docs' single React copy
      dedupe: ["react", "react-dom"],
      alias: { "@": here("../web/src") },
    },
    server: { fs: { allow: [here("..")] } },
    ssr: { noExternal: ["motion", "lucide-react", "react-markdown", "remark-gfm", "highlight.js"] },
  },
});

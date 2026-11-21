// DyUI docs — Astro + Starlight (SPEC §8).
// Live demos import the real component library from ../web/src, so web fixes flow through.
import { defineConfig, passthroughImageService } from "astro/config";
import starlight from "@astrojs/starlight";
import { satteri } from "@astrojs/markdown-satteri";
import react from "@astrojs/react";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { sidebar } from "./src/data/nav.mjs";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const { components } = JSON.parse(readFileSync(here("./src/data/components.json"), "utf8"));

// GitHub Pages serves the site at /dyui; other hosts (Vercel, Netlify) can set DOCS_BASE=/
const base = process.env.DOCS_BASE ?? "/dyui";
const site = process.env.DOCS_SITE ?? "https://sohammmzzz.github.io";

// The changelog page renders ../CHANGELOG.md, whose links to repo files (SECURITY.md) are
// relative to the repository. Point them at GitHub instead of a page that doesn't exist here.
// A Satteri (Astro's default Markdown processor) HTML-tree plugin; Starlight adds its own
// plugins to the same processor.
const REPO_FILE = /^[A-Z][\w.-]*\.md$/;
const repoFileLinks = {
  name: "dyui-repo-file-links",
  element: {
    filter: ["a"],
    visit(node, ctx) {
      const href = String(node.properties?.href ?? "");
      if (REPO_FILE.test(href)) ctx.setProperty(node, "href", `https://github.com/sohammmzzz/dyui/blob/main/${href}`);
    },
  },
};

export default defineConfig({
  site,
  base,
  trailingSlash: "always",
  image: { service: passthroughImageService() },
  markdown: { processor: satteri({ hastPlugins: [repoFileLinks] }) },
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
      // Expressive Code options live in ec.config.mjs (the <Code> component needs them there)
      head: [
        { tag: "meta", attrs: { name: "theme-color", content: "#F7F6F3", media: "(prefers-color-scheme: light)" } },
        { tag: "meta", attrs: { name: "theme-color", content: "#0B0C10", media: "(prefers-color-scheme: dark)" } },
      ],
      sidebar: sidebar(components),
      // loading splash (the DyUI mark assembling), once per browser session
      components: {
        Head: "./src/components/overrides/Head.astro",
        PageFrame: "./src/components/overrides/PageFrame.astro",
      },
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

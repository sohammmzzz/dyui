import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** python/dyui/__version__.py, shown in the demo's sidebar like the real app shows it. */
function pythonVersion(): string {
  try {
    return /__version__\s*=\s*["']([^"']+)["']/.exec(readFileSync(resolve(__dirname, "../python/dyui/__version__.py"), "utf8"))?.[1] ?? "";
  } catch {
    return "";
  }
}

/**
 * `vite build --mode demo` (npm run build:demo) builds the same shell for the docs site's
 * embedded demo: it plays `dyui demo` in the browser (src/demo/), never calls a server and
 * never stores anything. Output: dist-demo/, copied to docs/public/demo/ by the docs prebuild.
 * The demo frame takes its first theme from `?theme=` (boot.js reads localStorage instead).
 */
const demoPlugin = {
  name: "dyui-demo-html",
  transformIndexHtml(html: string) {
    const boot =
      '<script>try{var t=new URLSearchParams(location.search).get("theme");' +
      'if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>';
    return html
      .replace("<!-- external (not inline) so the app runs under a strict script-src CSP -->", "<!-- theme from the embedding page -->")
      .replace('<script src="./boot.js"></script>', boot)
      .replace("<title>DyUI</title>", "<title>DyUI demo</title>");
  },
};

// The built app is served by the Python package from dyui/_static.
export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    plugins: demo ? [react(), demoPlugin] : [react()],
    base: "./",
    define: demo ? { "import.meta.env.VITE_DYUI_VERSION": JSON.stringify(pythonVersion()) } : {},
    resolve: { alias: { "@": resolve(__dirname, "src") } },
    server: {
      port: 5173,
      proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
    },
    build: {
      outDir: demo ? "dist-demo" : "dist",
      assetsDir: "assets",
      sourcemap: false,
      rolldownOptions: {
        input: demo
          ? { main: resolve(__dirname, "index.html") }
          : {
              main: resolve(__dirname, "index.html"),
              gallery: resolve(__dirname, "gallery.html"),
            },
        output: {
          // Long-lived vendor chunks (cache well across releases); highlight.js stays a
          // lazy chunk of its own (see src/lib/hljs.ts).
          codeSplitting: {
            groups: [
              { name: "react", test: /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
              { name: "motion", test: /[\\/]node_modules[\\/](motion|motion-dom|motion-utils|framer-motion)[\\/]/ },
              {
                name: "markdown",
                test: /[\\/]node_modules[\\/](react-markdown|remark-[^\\/]+|rehype-[^\\/]+|micromark[^\\/]*|mdast-[^\\/]+|hast-[^\\/]+|unist-[^\\/]+|unified|vfile[^\\/]*|property-information|space-separated-tokens|comma-separated-tokens|html-url-attributes|decode-named-character-reference|character-entities[^\\/]*|devlop|bail|trough|is-plain-obj|ccount|escape-string-regexp|markdown-table|longest-streak|zwitch|trim-lines|estree-util-[^\\/]+|style-to-js|style-to-object|inline-style-parser|extend)[\\/]/,
              },
            ],
          },
        },
      },
    },
    test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
  } as any;
});

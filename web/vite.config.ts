import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// The built app is served by the Python package from dyui/_static.
export default defineConfig({
  plugins: [react()],
  base: "./",
  resolve: { alias: { "@": resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
    rolldownOptions: {
      input: {
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
} as any);

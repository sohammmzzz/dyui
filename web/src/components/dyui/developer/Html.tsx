import { useEffect, useMemo, useRef, useState } from "react";
import { Bloom } from "../util/motion";
import { num, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/agent.css";

const TOKENS = ["--dy-bg", "--dy-surface", "--dy-surface-2", "--dy-border", "--dy-text", "--dy-text-muted", "--dy-text-faint", "--dy-accent", "--dy-accent-text", "--dy-teal", "--dy-success", "--dy-warning", "--dy-danger"];

/**
 * `html` — developer-authored HTML in a sandboxed iframe (allow-scripts only, never
 * allow-same-origin). The iframe reports its height via postMessage. Theme tokens are
 * copied in as CSS variables so templates can match the app.
 */
export function Html({ node }: DyProps) {
  const p = node.props;
  const html = str(p.html);
  const fixed = num(p.height);
  const ref = useRef<HTMLIFrameElement>(null);
  const [vars, setVars] = useState<string | null>(null);
  const [h, setH] = useState<number>(fixed ?? 120);
  const [loaded, setLoaded] = useState(false);
  const key = useMemo(() => Math.random().toString(36).slice(2), []);

  useEffect(() => {
    const cs = getComputedStyle(ref.current?.parentElement ?? document.documentElement);
    setVars(TOKENS.map((t) => `${t}:${cs.getPropertyValue(t).trim()};`).join("") + `--dy-font:${cs.getPropertyValue("--dy-font")};color-scheme:${cs.colorScheme || "normal"};`);
  }, []);

  useEffect(() => {
    if (fixed) return;
    const onMsg = (e: MessageEvent) => {
      if (e.source !== ref.current?.contentWindow) return;
      const d = e.data;
      if (d && d.__dyui_html === key && typeof d.height === "number") setH(Math.max(24, Math.min(4000, Math.ceil(d.height))));
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [key, fixed]);

  const srcdoc = useMemo(() => {
    if (vars === null) return null;
    const reporter = `<script>(function(){var k=${JSON.stringify(key)};function s(){parent.postMessage({__dyui_html:k,height:document.documentElement.scrollHeight},"*")}addEventListener("load",s);if(window.ResizeObserver){new ResizeObserver(s).observe(document.documentElement)}s()})()</script>`;
    const base = `<style>:root{${vars}}html,body{margin:0;background:transparent;color:var(--dy-text);font-family:var(--dy-font);font-size:14px;line-height:1.5}</style>`;
    return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">${base}</head><body>${html}${reporter}</body></html>`;
  }, [html, vars, key]);

  return (
    <Bloom className="dy-c dy-html" data-dy-ui="html">
      {!loaded && <Skel h={Math.min(h, 160)} style={{ borderRadius: 12 }} />}
      {srcdoc !== null && (
        <iframe
          ref={ref}
          title={str(p.title) || "Embedded content"}
          sandbox="allow-scripts"
          srcDoc={srcdoc}
          onLoad={() => setLoaded(true)}
          style={{ height: h, display: loaded ? "block" : "block", opacity: loaded ? 1 : 0, position: loaded ? "static" : "absolute" }}
        />
      )}
    </Bloom>
  );
}

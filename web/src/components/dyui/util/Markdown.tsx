/**
 * Safe markdown: react-markdown + GFM, raw HTML skipped, URLs filtered
 * (http(s) / mailto / /api/files only), links open in a new tab.
 */
import { memo, isValidElement, type ReactElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "../content/CodeBlock";
import { cx, safeMediaUrl, safeUrl } from "./props";
import "../styles/base.css";
import "../styles/content.css";

const textOf = (n: ReactNode): string => {
  if (typeof n === "string" || typeof n === "number") return String(n);
  if (Array.isArray(n)) return n.map(textOf).join("");
  if (isValidElement(n)) return textOf((n.props as any).children);
  return "";
};

const components: Components = {
  a({ href, children }) {
    const safe = safeUrl(href);
    if (!safe) return <span className="dy-md-badlink">{children}</span>;
    return (
      <a href={safe} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
  img({ src, alt }) {
    const safe = safeMediaUrl(src);
    if (!safe) return null;
    return <img src={safe} alt={alt ?? ""} loading="lazy" decoding="async" />;
  },
  pre({ children }) {
    const child = (Array.isArray(children) ? children[0] : children) as ReactElement<any> | undefined;
    const cls: string = (isValidElement(child) && (child.props as any).className) || "";
    const lang = /language-([\w+#-]+)/.exec(cls)?.[1];
    const code = textOf(isValidElement(child) ? (child.props as any).children : children).replace(/\n$/, "");
    return <CodeBlock code={code} language={lang} />;
  },
  table({ children }) {
    return (
      <div className="dy-md-table">
        <table>{children}</table>
      </div>
    );
  },
  input({ checked, type }) {
    if (type !== "checkbox") return null;
    return <span className={cx("dy-md-check", checked && "is-on")} aria-label={checked ? "done" : "not done"} />;
  },
};

const urlTransform = (url: string) => safeUrl(url) ?? "";

export const Prose = memo(function Prose({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cx("dy-md", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={urlTransform} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
});

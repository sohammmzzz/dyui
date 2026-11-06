/**
 * Chat prose. react-markdown + GFM, no raw HTML, safe URLs only (SPEC §5.1),
 * external links in a new tab with rel="noopener noreferrer".
 */
import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CopyButton } from "./CopyButton";
import { highlight, languageLabel } from "./highlight";
import { useHljs } from "@/lib/hljs";
import { safeMarkdownHref } from "@/lib/url";
import { cx } from "./anim";

type HastNode = { type: string; value?: string; tagName?: string; properties?: Record<string, unknown>; children?: HastNode[] };

function hastText(n: HastNode | undefined): string {
  if (!n) return "";
  if (n.type === "text") return n.value ?? "";
  return (n.children ?? []).map(hastText).join("");
}

/** Allow http(s), mailto, app files, anchors and app-relative paths; drop everything else (see lib/url). */
export function safeUrl(url: string): string {
  return safeMarkdownHref(url);
}

export const CodeBlock = memo(function CodeBlock({ code, language }: { code: string; language?: string | null }) {
  const source = code.replace(/\n$/, "");
  const hljs = useHljs();
  const html = useMemo(() => highlight(hljs, source, language), [hljs, source, language]);
  const label = languageLabel(language);
  return (
    <div className="sh-code">
      <div className="sh-code-head">
        <span className="sh-code-lang">{label}</span>
        <CopyButton text={source} />
      </div>
      <pre tabIndex={0} aria-label={`${label} code`}>
        {html !== null ? (
          <code className={`hljs language-${language}`} dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <code>{source}</code>
        )}
      </pre>
    </div>
  );
});

const components: Components = {
  a({ node: _n, href, children, ...rest }) {
    const internal = !!href && (href.startsWith("#") || (href.startsWith("/") && !href.startsWith("//")));
    return (
      <a href={href} {...rest} {...(internal ? {} : { target: "_blank", rel: "noopener noreferrer" })}>
        {children}
      </a>
    );
  },
  pre({ node }) {
    const code = (node as HastNode | undefined)?.children?.find((c) => c.tagName === "code");
    const cls = code?.properties?.className;
    const list = Array.isArray(cls) ? cls.map(String) : typeof cls === "string" ? cls.split(" ") : [];
    const lang = list.find((c) => c.startsWith("language-"))?.slice(9) ?? null;
    return <CodeBlock code={hastText(code)} language={lang} />;
  },
  table({ node: _n, ...props }) {
    return (
      <div className="sh-md-table" tabIndex={0}>
        <table {...props} />
      </div>
    );
  },
  img({ node: _n, src, alt }) {
    if (!src || typeof src !== "string") return null;
    return <img src={src} alt={alt ?? ""} loading="lazy" decoding="async" />;
  },
};

const plugins = [remarkGfm];

export const Markdown = memo(function Markdown({ text, streaming = false, className }: { text: string; streaming?: boolean; className?: string }) {
  return (
    <div className={cx("sh-md", streaming && "is-streaming", className)}>
      <ReactMarkdown remarkPlugins={plugins} components={components} urlTransform={safeUrl} skipHtml>
        {text}
      </ReactMarkdown>
    </div>
  );
});

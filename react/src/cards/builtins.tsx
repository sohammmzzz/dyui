/**
 * The built-in card library. Each component is a plain function of
 * `{ props }` and renders with `dyui-*` class names that ship in `styles.css`.
 * Every one is overridable: register a component under the same key to replace
 * it, or register brand-new keys for your own card types.
 */
import * as React from "react";

import type { CardComponentProps } from "../types";
import { sanitizeHtml } from "./sanitize";

/** Render any value as a compact, readable string. */
function asText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

/** Plain text / paragraph card. props: { text } */
export function TextCard({ props }: CardComponentProps) {
  return <p className="dyui-text">{asText((props as any).text ?? props)}</p>;
}

/** Minimal-markdown card. Supports #/##/### headings, **bold**, `code`, and
 * `- ` bullet lists. Anything fancier should use the `html` card. props: { text } */
export function MarkdownCard({ props }: CardComponentProps) {
  const text = asText((props as any).text ?? "");
  const lines = text.split("\n");
  const out: React.ReactNode[] = [];
  let list: string[] = [];

  const flushList = (key: number) => {
    if (list.length) {
      out.push(
        <ul className="dyui-md-list" key={`ul-${key}`}>
          {list.map((li, i) => (
            <li key={i}>{inline(li)}</li>
          ))}
        </ul>
      );
      list = [];
    }
  };

  lines.forEach((line, i) => {
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) {
      flushList(i);
      const level = Math.min(h[1].length + 2, 6);
      out.push(
        React.createElement(
          `h${level}`,
          { className: "dyui-md-h", key: i },
          inline(h[2])
        )
      );
    } else if (/^\s*-\s+/.test(line)) {
      list.push(line.replace(/^\s*-\s+/, ""));
    } else if (line.trim() === "") {
      flushList(i);
    } else {
      flushList(i);
      out.push(
        <p className="dyui-md-p" key={i}>
          {inline(line)}
        </p>
      );
    }
  });
  flushList(lines.length);
  return <div className="dyui-md">{out}</div>;

  function inline(s: string): React.ReactNode[] {
    // Split on **bold** and `code`, keeping the delimiters.
    const parts = s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
    return parts.map((p, i) => {
      if (p.startsWith("**") && p.endsWith("**"))
        return <strong key={i}>{p.slice(2, -2)}</strong>;
      if (p.startsWith("`") && p.endsWith("`"))
        return (
          <code className="dyui-code" key={i}>
            {p.slice(1, -1)}
          </code>
        );
      return <React.Fragment key={i}>{p}</React.Fragment>;
    });
  }
}

/** Table card. props: { columns: string[], rows: unknown[][] } */
export function TableCard({ props }: CardComponentProps) {
  const columns = ((props as any).columns ?? []) as string[];
  const rows = ((props as any).rows ?? []) as unknown[][];
  return (
    <div className="dyui-table-wrap">
      <table className="dyui-table">
        {columns.length > 0 && (
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i}>{asText(c)}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {(Array.isArray(row) ? row : [row]).map((cell, ci) => (
                <td key={ci}>{asText(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Single statistic card. props: { label, value, unit?, delta? } */
export function StatCard({ props }: CardComponentProps) {
  const p = props as any;
  return (
    <div className="dyui-stat">
      <div className="dyui-stat-value">
        {asText(p.value)}
        {p.unit ? <span className="dyui-stat-unit"> {asText(p.unit)}</span> : null}
      </div>
      {p.label ? <div className="dyui-stat-label">{asText(p.label)}</div> : null}
      {p.delta != null ? <div className="dyui-stat-delta">{asText(p.delta)}</div> : null}
    </div>
  );
}

/** Progress bar card. props: { value, max?, label? } */
export function ProgressCard({ props }: CardComponentProps) {
  const p = props as any;
  const max = Number(p.max ?? 100) || 1;
  const value = Number(p.value ?? 0);
  // Guard against a non-numeric value: NaN would render a literal "NaN%".
  const pct = Number.isFinite(value)
    ? Math.max(0, Math.min(100, (value / max) * 100))
    : 0;
  return (
    <div className="dyui-progress">
      <div className="dyui-progress-track">
        <div className="dyui-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="dyui-progress-label">
        {p.label ? asText(p.label) : `${Math.round(pct)}%`}
      </div>
    </div>
  );
}

/** List card. props: { items: (string | {title, subtitle?, badge?})[] } */
export function ListCard({ props }: CardComponentProps) {
  const items = ((props as any).items ?? []) as any[];
  return (
    <ul className="dyui-list">
      {items.map((it, i) => {
        const obj = typeof it === "object" && it !== null ? it : { title: it };
        return (
          <li className="dyui-list-item" key={i}>
            <div className="dyui-list-main">
              <span className="dyui-list-title">{asText(obj.title)}</span>
              {obj.subtitle ? (
                <span className="dyui-list-sub">{asText(obj.subtitle)}</span>
              ) : null}
            </div>
            {obj.badge != null ? (
              <span className="dyui-badge">{asText(obj.badge)}</span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** Key/value card. props: { data: Record<string, unknown> } or props itself. */
export function KeyValueCard({ props }: CardComponentProps) {
  const data = ((props as any).data ?? props) as Record<string, unknown>;
  return (
    <dl className="dyui-kv">
      {Object.entries(data).map(([k, v]) => (
        <div className="dyui-kv-row" key={k}>
          <dt>{k}</dt>
          <dd>{asText(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Raw JSON card. props: any */
export function JsonCard({ props }: CardComponentProps) {
  return (
    <pre className="dyui-json">{JSON.stringify((props as any).value ?? props, null, 2)}</pre>
  );
}

/** Alert/callout card. props: { text, level?: "info"|"success"|"warning"|"error" } */
export function AlertCard({ props }: CardComponentProps) {
  const p = props as any;
  const level = p.level ?? "info";
  return (
    <div className={`dyui-alert dyui-alert-${level}`}>
      {p.title ? <div className="dyui-alert-title">{asText(p.title)}</div> : null}
      <div className="dyui-alert-body">{asText(p.text ?? p.message)}</div>
    </div>
  );
}

/** Image card. props: { src, alt?, caption? } */
export function ImageCard({ props }: CardComponentProps) {
  const p = props as any;
  return (
    <figure className="dyui-image">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={asText(p.src)} alt={asText(p.alt ?? "")} />
      {p.caption ? <figcaption>{asText(p.caption)}</figcaption> : null}
    </figure>
  );
}

/** Raw (sanitized) HTML card -- lets agents ship fully custom markup with no
 * frontend code. props: { html }. Override this key with your own sanitizer
 * (e.g. DOMPurify) for untrusted input. */
export function HtmlCard({ props }: CardComponentProps) {
  const html = sanitizeHtml(asText((props as any).html ?? ""));
  return <div className="dyui-html" dangerouslySetInnerHTML={{ __html: html }} />;
}

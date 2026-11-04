/**
 * Defensive prop readers. Props come from an LLM (validated server-side, but
 * possibly partial while streaming), so every reader tolerates anything.
 */
import type { UINode } from "../../../lib/types";

export const isObj = (v: unknown): v is Record<string, any> =>
  !!v && typeof v === "object" && !Array.isArray(v);

export const str = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : typeof v === "number" && Number.isFinite(v) ? String(v) : typeof v === "boolean" ? String(v) : fallback;

export const optStr = (v: unknown): string | undefined => {
  const s = str(v);
  return s.length ? s : undefined;
};

export const num = (v: unknown): number | undefined => {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v.trim());
    if (Number.isFinite(n)) return n;
  }
  return undefined;
};

export const arr = <T = any>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
export const bool = (v: unknown): boolean => v === true || v === "true";

/** True when item `i` of a streaming list is known to be complete (a later item exists). */
export const settled = (i: number, len: number, streaming: boolean) => !streaming || i < len - 1;

/* ------------------------------------------------------------------ nodes */

/**
 * Accept both UINode shape ({id, ui, props, children}) and the flat LLM shape
 * ({ui, ...props, children}) — nested node arrays inside props (tabs, accordion)
 * may arrive in either form.
 */
export function normalizeNode(x: unknown, fallbackId: string, status?: UINode["status"]): UINode | null {
  if (!isObj(x) || typeof x.ui !== "string" || !x.ui) return null;
  if (isObj(x.props)) {
    return {
      id: typeof x.id === "string" && x.id ? x.id : fallbackId,
      ui: x.ui,
      props: x.props,
      children: Array.isArray(x.children) ? x.children : undefined,
      status: x.status ?? status,
      error: x.error,
    };
  }
  const { ui, id, children, status: st, error, ...props } = x;
  return {
    id: typeof id === "string" && id ? id : fallbackId,
    ui,
    props,
    children: Array.isArray(children) ? children : undefined,
    status: st ?? status,
    error,
  };
}

/** Normalize a child array; while the parent streams, its last child is partial. */
export function childNodes(raw: unknown, parentId: string, parentStatus?: UINode["status"]): UINode[] {
  const list = arr(raw);
  const out: UINode[] = [];
  list.forEach((c, i) => {
    const n = normalizeNode(c, `${parentId}.${i}`, parentStatus === "streaming" && i === list.length - 1 ? "streaming" : undefined);
    if (n) out.push(n);
  });
  return out;
}

/* ------------------------------------------------------------------ URLs */

/** Links: http(s), mailto, and app-relative /api/files/. Anything else → null. */
export function safeUrl(v: unknown): string | null {
  const s = str(v).trim();
  if (!s) return null;
  if (/^\/api\/files\/[^\s]*$/.test(s) && !s.startsWith("//")) return s;
  try {
    const u = new URL(s);
    if (u.protocol === "http:" || u.protocol === "https:" || u.protocol === "mailto:") return u.href;
  } catch {
    /* not absolute */
  }
  return null;
}

/** Media sources: http(s) and /api/files/ only. */
export function safeMediaUrl(v: unknown): string | null {
  const u = safeUrl(v);
  return u && !u.startsWith("mailto:") ? u : null;
}

export function domainOf(url: string | null | undefined): string {
  if (!url) return "";
  if (url.startsWith("/")) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export const linkProps = (href: string) => ({ href, target: "_blank", rel: "noopener noreferrer" }) as const;

/* ------------------------------------------------------------------ numbers */

const NF = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const NF_NOGROUP = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, useGrouping: false });
const NF_COMPACT = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export function fmtNum(n: number, opts: { compact?: boolean; group?: boolean } = {}): string {
  if (!Number.isFinite(n)) return "—";
  if (opts.compact && Math.abs(n) >= 10000) return NF_COMPACT.format(n);
  return (opts.group === false ? NF_NOGROUP : NF).format(n).replace("-", "−");
}

const MULT: Record<string, number> = { k: 1e3, K: 1e3, m: 1e6, M: 1e6, b: 1e9, B: 1e9, bn: 1e9, t: 1e12, T: 1e12 };

/** "$1,234.5", "12%", "−3.2k", "48.2M" → number; otherwise null. */
export function parseNumberish(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v !== "string") return null;
  const s = v.trim().replace(/[−‒–]/g, "-");
  const m = s.match(/^([+-])?\s*[$€£¥₹]?\s*([+-])?(\d[\d,]*(?:\.\d+)?|\.\d+)\s*(k|K|m|M|b|B|bn|t|T)?\s*(%|[a-zA-Z$€£/]{0,6})?$/);
  if (!m) return null;
  const sign = m[1] === "-" || m[2] === "-" ? -1 : 1;
  const n = Number(m[3].replace(/,/g, ""));
  if (!Number.isFinite(n)) return null;
  return sign * n * (m[4] ? MULT[m[4]] ?? 1 : 1);
}

/** Split "$48.2k" into prefix/number/suffix so it can count up while keeping its format. */
export function splitNumeric(v: unknown): { prefix: string; value: number; suffix: string; decimals: number; group: boolean } | null {
  if (typeof v === "number" && Number.isFinite(v)) {
    const decimals = (String(v).split(".")[1] || "").length;
    return { prefix: "", value: v, suffix: "", decimals: Math.min(decimals, 2), group: Math.abs(v) >= 10000 };
  }
  if (typeof v !== "string") return null;
  const m = v.match(/^(\D*?)(-?\d[\d,]*(?:\.\d+)?)(.*)$/);
  if (!m) return null;
  const raw = m[2];
  const value = Number(raw.replace(/,/g, ""));
  if (!Number.isFinite(value)) return null;
  const decimals = (raw.split(".")[1] || "").length;
  return { prefix: m[1], value, suffix: m[3], decimals, group: raw.includes(",") };
}

export function formatSplit(p: { prefix: string; suffix: string; decimals: number; group: boolean }, n: number) {
  const s = n.toLocaleString("en-US", {
    minimumFractionDigits: p.decimals,
    maximumFractionDigits: p.decimals,
    useGrouping: p.group,
  });
  return `${p.prefix}${s}${p.suffix}`;
}

export function formatBytes(n: unknown): string | undefined {
  if (typeof n === "string" && n.trim() && !/^\d+(\.\d+)?$/.test(n.trim())) return n; // already "2.4 MB"
  const b = num(n);
  if (b === undefined) return undefined;
  if (b < 1024) return `${b} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = b / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v >= 100 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`;
}

export function formatDuration(ms: unknown): string | undefined {
  const n = num(ms);
  if (n === undefined) return undefined;
  if (n < 1000) return `${Math.round(n)}ms`;
  const s = n / 1000;
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

/** Stable small hash (for deterministic decorative patterns). */
export function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

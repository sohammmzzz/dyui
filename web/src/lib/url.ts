/**
 * URL policy for anything the model (or a component's props) supplies — SPEC §5.1.
 *
 * Allowed: http(s), mailto, and the app's own uploaded files (`api/files/<id>` or
 * `/api/files/<id>`, resolved against the app's base so a sub-path mount works).
 * Everything else — javascript:, data:, vbscript:, file:, protocol-relative
 * `//host`, backslash tricks — is rejected. The server applies the same policy;
 * this is defence in depth.
 */

// ASCII control chars + whitespace: browsers drop these inside URLs ("java\tscript:")
// eslint-disable-next-line no-control-regex
const CTRL = /[\u0000- \u007f]/g;
const DANGEROUS = /^(javascript|data|vbscript|file|blob|about|filesystem):/i;
const FILE_PATH = /^\/?api\/files\/([A-Za-z0-9_-]+)((?:[?#][^\s\\:]*)?)$/;

/** The app's base path ("/" or "/sub/"), from the document base URI. */
export function appBase(): string {
  if (typeof document === "undefined") return "/";
  try {
    return new URL("./", document.baseURI).pathname;
  } catch {
    return "/";
  }
}

/** `api/files/<id>` / `/api/files/<id>` → `<base>api/files/<id>`; anything else → null. */
export function fileUrl(raw: string): string | null {
  const m = FILE_PATH.exec(raw);
  if (!m || raw.includes("..")) return null;
  return `${appBase()}api/files/${m[1]}${m[2] ?? ""}`;
}

/** Is this one of the app's own uploaded-file URLs? */
export const isFileUrl = (raw: unknown): boolean => typeof raw === "string" && FILE_PATH.test(raw.trim());

/** Links: http(s), mailto, app files. Returns a safe href or null. */
export function safeLink(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim();
  if (!s || s.includes("\\")) return null;
  const squashed = s.replace(CTRL, "");
  if (DANGEROUS.test(squashed)) return null;
  if (squashed !== s && /^[a-z][a-z0-9+.-]*:/i.test(squashed)) return null; // "java\tscript:", "\u0001https:"
  const file = fileUrl(s);
  if (file) return file;
  if (s.startsWith("//")) return null;
  try {
    const u = new URL(s);
    if (u.protocol === "http:" || u.protocol === "https:") return u.hostname ? u.href : null;
    if (u.protocol === "mailto:") return u.href;
  } catch {
    /* not absolute */
  }
  return null;
}

/** Media sources (img/video/audio): http(s) and app files only. */
export function safeMedia(raw: unknown): string | null {
  const u = safeLink(raw);
  return u && !u.startsWith("mailto:") ? u : null;
}

/**
 * Links inside chat markdown: everything `safeLink` allows, plus in-page anchors
 * (`#section`) and app-relative paths (`/docs`, `./x`, `?q=1`).
 */
export function safeMarkdownHref(raw: string): string {
  const s = (raw ?? "").trim();
  if (!s || s.includes("\\")) return "";
  const squashed = s.replace(CTRL, "");
  if (DANGEROUS.test(squashed)) return "";
  const ok = safeLink(s);
  if (ok) return ok;
  if (squashed !== s) return "";
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//")) return "";
  // only well-formed file URLs may point into the API (handled by safeLink above)
  if (/^(\.?\/)?api(\/|$)/i.test(s) || s.includes("..")) return "";
  if (/^(#|\?|\.\/|\/(?!\/))/.test(s) || /^[\w-]/.test(s)) return s;
  return "";
}

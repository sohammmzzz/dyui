/**
 * A deliberately small HTML sanitizer used by the built-in `html` card.
 *
 * It strips the obvious script-injection vectors (script/style/iframe/object
 * tags, `on*` event-handler attributes, and `javascript:` URLs). It is a sane
 * default so that agent-authored HTML can be shown without trivial XSS, but it
 * is NOT a replacement for a hardened sanitizer. For untrusted input in
 * production, pass your own (e.g. DOMPurify) via the registry's `html` override.
 */
const BLOCK_TAGS = /<\s*(script|style|iframe|object|embed|link|meta|base)\b[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi;
const SELF_CLOSING_BLOCK = /<\s*(script|style|iframe|object|embed|link|meta|base)\b[^>]*\/?>/gi;
const ON_ATTR = /\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi;
const JS_URL = /(href|src|xlink:href)\s*=\s*("|')\s*javascript:[^"']*\2/gi;

export function sanitizeHtml(html: string): string {
  if (typeof html !== "string") return "";
  return html
    .replace(BLOCK_TAGS, "")
    .replace(SELF_CLOSING_BLOCK, "")
    .replace(ON_ATTR, "")
    .replace(JS_URL, "");
}

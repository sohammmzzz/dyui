/**
 * The HTML sanitizer used by the built-in `html` card.
 *
 * Unlike a naive regex stripper (which is trivially defeated by separators like
 * `<svg/onload=...>`, unquoted `javascript:` URLs, or entity obfuscation such as
 * `java&Tab;script:`), this is a *parser-based, allowlist* sanitizer: it parses
 * the markup into a detached DOM, walks it, and keeps only known-safe tags and
 * attributes. Because the browser's parser decodes entities for us, obfuscated
 * payloads are normalised *before* we inspect them.
 *
 * It is still a sane default rather than a full security product. For high-stakes
 * untrusted input, register your own `html` card backed by DOMPurify via the
 * registry's `html` override.
 */

// Tags that are kept. Anything not listed is unwrapped (children preserved) or,
// if dangerous, dropped entirely (see DROP_TAGS).
const ALLOWED_TAGS = new Set([
  "a", "abbr", "address", "article", "aside", "b", "bdi", "bdo", "blockquote",
  "br", "caption", "cite", "code", "col", "colgroup", "data", "dd", "del",
  "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "footer",
  "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "i", "img",
  "ins", "kbd", "li", "main", "mark", "nav", "ol", "p", "picture", "pre", "q",
  "rp", "rt", "ruby", "s", "samp", "section", "small", "source", "span",
  "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th",
  "thead", "time", "tr", "u", "ul", "var", "wbr",
]);

// Tags removed together with all of their contents. These can execute script,
// load external resources, or smuggle nested markup past the parser.
const DROP_TAGS = new Set([
  "script", "style", "iframe", "object", "embed", "link", "meta", "base",
  "form", "input", "button", "select", "option", "optgroup", "textarea",
  "template", "noscript", "svg", "math", "head", "title", "frame", "frameset",
  "applet", "param", "audio", "video", "track", "portal",
]);

// Attributes whose values are URLs and therefore need protocol checking.
const URL_ATTRS = new Set([
  "href", "src", "xlink:href", "action", "formaction", "poster", "background",
  "cite", "data", "ping", "longdesc", "usemap", "srcset", "manifest",
  "codebase", "profile", "lowsrc", "dynsrc",
]);

/** Strip control chars + whitespace so "java\tscript:" can't hide its scheme. */
function normalizeUrl(value: string): string {
  return value.replace(/[\x00-\x20\x7f]+/g, "").toLowerCase();
}

/** True when a URL value is safe to keep (no script-bearing scheme). */
function isSafeUrl(value: string, allowDataImage: boolean): boolean {
  const v = normalizeUrl(value);
  if (v === "") return true;
  if (v.startsWith("data:")) {
    return allowDataImage && /^data:image\/(png|jpe?g|gif|webp|avif|bmp);/.test(v);
  }
  return !/^(javascript|vbscript|data|file|blob|about):/.test(v);
}

/** Drop any srcset whose candidate URLs aren't safe. */
function isSafeSrcset(value: string, allowDataImage: boolean): boolean {
  return value
    .split(",")
    .map((part) => part.trim().split(/\s+/)[0] ?? "")
    .every((url) => isSafeUrl(url, allowDataImage));
}

/** True when an inline style value is free of known script vectors. */
function isSafeStyle(value: string): boolean {
  const v = value.replace(/[\x00-\x20\x7f]+/g, "").toLowerCase();
  return !/(expression\(|javascript:|vbscript:|-moz-binding|behavior:|@import)/.test(v);
}

function cleanAttributes(el: Element, tag: string): void {
  const mediaTag = tag === "img" || tag === "source" || tag === "picture";
  for (const attr of Array.from(el.attributes)) {
    const name = attr.name.toLowerCase();
    if (name.startsWith("on") || name === "is" || name === "srcdoc") {
      el.removeAttribute(attr.name);
      continue;
    }
    if (name === "style") {
      if (!isSafeStyle(attr.value)) el.removeAttribute(attr.name);
      continue;
    }
    if (URL_ATTRS.has(name)) {
      const ok =
        name === "srcset"
          ? isSafeSrcset(attr.value, mediaTag)
          : isSafeUrl(attr.value, mediaTag);
      if (!ok) el.removeAttribute(attr.name);
    }
  }
}

function sanitizeNode(node: Node): void {
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === 8) {
      // Comment node: drop (conditional comments are an injection vector).
      child.parentNode?.removeChild(child);
      continue;
    }
    if (child.nodeType !== 1) continue; // keep text, drop the rest implicitly
    const el = child as Element;
    const tag = el.tagName.toLowerCase();
    if (DROP_TAGS.has(tag)) {
      el.remove();
      continue;
    }
    if (!ALLOWED_TAGS.has(tag)) {
      // Unknown-but-not-dangerous tag: sanitize then unwrap, keeping its text.
      sanitizeNode(el);
      const parent = el.parentNode;
      if (parent) {
        while (el.firstChild) parent.insertBefore(el.firstChild, el);
        parent.removeChild(el);
      }
      continue;
    }
    cleanAttributes(el, tag);
    sanitizeNode(el);
  }
}

export function sanitizeHtml(html: string): string {
  if (typeof html !== "string" || html === "") return "";
  // Without a DOM parser (e.g. SSR), fail closed rather than emit raw markup.
  const Parser =
    typeof DOMParser !== "undefined" ? DOMParser : (globalThis as any).DOMParser;
  if (!Parser) return "";
  let doc: Document;
  try {
    doc = new Parser().parseFromString(html, "text/html");
  } catch {
    return "";
  }
  if (!doc.body) return "";
  sanitizeNode(doc.body);
  return doc.body.innerHTML;
}

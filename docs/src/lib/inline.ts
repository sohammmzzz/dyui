/** Escape text and render `backtick` spans as <code> — for docstring-derived copy. */
export function inline(text: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  return text
    .split(/(`[^`]+`)/g)
    .map((part) => (part.startsWith("`") && part.endsWith("`") && part.length > 1 ? `<code>${esc(part.slice(1, -1))}</code>` : esc(part)))
    .join("");
}

/** Plain text (for meta descriptions): drop the backticks. */
export function plain(text: string): string {
  return text.replace(/`([^`]+)`/g, "$1");
}

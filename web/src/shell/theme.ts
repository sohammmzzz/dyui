/**
 * Theme + accent application (SPEC §1.3). Theme lives on <html data-theme>;
 * absent means "follow the OS". The accent is injected as a small stylesheet so
 * light and dark get their own shade, and every derived token (soft, border,
 * strong, focus ring, bloom) follows through color-mix() in tokens.css.
 */
import { flushSync } from "react-dom";
import type { ThemeMode } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/motion";

/** Named accents: [light, dark]. Light shades keep AA contrast for white text. */
export const NAMED_ACCENTS: Record<string, [string, string]> = {
  indigo: ["#5B4FE0", "#8B80FF"],
  teal: ["#0E857A", "#3DD6C3"],
  rose: ["#D23F70", "#FF8DB1"],
  amber: ["#A35F0A", "#F5B544"],
  emerald: ["#13855A", "#4ADE9B"],
  slate: ["#475569", "#A9B6CB"],
};

const HEX = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i;

function expand(hex: string): string {
  return hex.length === 4 ? "#" + [...hex.slice(1)].map((c) => c + c).join("") : hex;
}

function luminance(hex: string): number {
  const h = expand(hex).slice(1);
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export type AccentPair = { light: string; dark: string; lightText: string; darkText: string };

/** Resolve a named accent or hex to light/dark shades; null for unknown input. */
export function resolveAccent(accent: string | null | undefined): AccentPair | null {
  const key = (accent || "").trim().toLowerCase();
  if (!key) return null;
  if (NAMED_ACCENTS[key]) {
    const [light, dark] = NAMED_ACCENTS[key];
    return { light, dark, lightText: "#FFFFFF", darkText: "#0B0C10" };
  }
  if (!HEX.test(key)) return null;
  const hex = expand(key);
  const L = luminance(hex);
  return {
    light: hex,
    // lift dark hues so they read on the midnight background
    dark: L < 0.32 ? `color-mix(in oklab, ${hex} 68%, white)` : hex,
    lightText: L > 0.45 ? "#0B0C10" : "#FFFFFF",
    darkText: "#0B0C10",
  };
}

export function applyAccent(accent: string | null | undefined) {
  if (typeof document === "undefined") return;
  const id = "dy-accent";
  document.getElementById(id)?.remove();
  const pair = resolveAccent(accent);
  if (!pair || (accent || "").toLowerCase() === "indigo") return; // tokens.css default
  const dark = `--dy-accent: ${pair.dark}; --dy-accent-text: ${pair.darkText};`;
  const style = document.createElement("style");
  style.id = id;
  style.textContent =
    `:root { --dy-accent: ${pair.light}; --dy-accent-text: ${pair.lightText}; }\n` +
    `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ${dark} } }\n` +
    `:root[data-theme="dark"] { ${dark} }\n`;
  document.head.appendChild(style);
}

const THEME_KEY = "dyui:theme";

export function storedTheme(): ThemeMode | null {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" || v === "system" ? v : null;
  } catch {
    return null;
  }
}

export function storeTheme(mode: ThemeMode) {
  try {
    localStorage.setItem(THEME_KEY, mode);
  } catch {
    /* private mode */
  }
}

const THEME_COLORS = { light: "#F7F6F3", dark: "#0B0C10" };

export function setThemeAttr(mode: ThemeMode) {
  const root = document.documentElement;
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
    const media = m.getAttribute("media") || "";
    const scheme = media.includes("dark") ? "dark" : "light";
    m.setAttribute("content", mode === "system" ? THEME_COLORS[scheme] : THEME_COLORS[mode]);
  });
}

/** Switch theme with a calm cross-fade (View Transitions where available). */
export function switchTheme(mode: ThemeMode, commit: () => void) {
  const run = () => {
    setThemeAttr(mode);
    commit();
  };
  const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
  if (doc.startViewTransition && !prefersReducedMotion()) {
    doc.startViewTransition(() => flushSync(run));
  } else {
    run();
  }
}

export function setFavicon(href: string | null) {
  if (!href) return;
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = href;
  if (!/\.svg(\?|$)/i.test(href)) link.removeAttribute("type");
}

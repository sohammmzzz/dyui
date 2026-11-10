import { useCallback, useEffect, useState } from "react";
import { MotionConfig } from "motion/react";
import { connect, describeError, type Transport } from "@/lib/api";
import type { AppConfig, ThemeMode } from "@/lib/types";
import { AppShell } from "@/shell/AppShell";
import { BootError, BootScreen, PasswordGate } from "@/shell/Gate";
import { ToastProvider } from "@/shell/Toasts";
import { applyAccent, setFavicon, setThemeAttr, storeTheme, storedTheme, switchTheme } from "@/shell/theme";

/** Keep the loading splash up at least this long (since navigation), so the mark finishes assembling. */
const SPLASH_MIN_MS = 1400;
const splashEl = () => (typeof document === "undefined" ? null : document.getElementById("dy-splash"));

type Boot =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; transport: Transport; config: AppConfig };

export function App() {
  const [boot, setBoot] = useState<Boot>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [theme, setTheme] = useState<ThemeMode>(() => storedTheme() ?? "system");
  // The static splash in index.html covers the page until the app is ready; the chat is
  // mounted only as the splash leaves, so its own entrance plays in view.
  const [revealed, setRevealed] = useState(() => !splashEl());

  useEffect(() => {
    let alive = true;
    connect()
      .then(({ transport, config }) => alive && setBoot({ status: "ready", transport, config }))
      .catch((e) => alive && setBoot({ status: "error", message: describeError(e) }));
    return () => {
      alive = false;
    };
  }, [attempt]);

  useEffect(() => {
    if (boot.status === "loading") return;
    const el = splashEl();
    if (!el) {
      setRevealed(true);
      return;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const wait = boot.status === "error" || reduced ? 0 : Math.max(0, SPLASH_MIN_MS - performance.now());
    let gone: ReturnType<typeof setTimeout> | undefined;
    const leave = setTimeout(() => {
      el.classList.add("is-leaving");
      setRevealed(true);
      gone = setTimeout(() => el.remove(), 600);
    }, wait);
    return () => {
      clearTimeout(leave);
      if (gone) clearTimeout(gone);
    };
  }, [boot.status]);

  const config = boot.status === "ready" ? boot.config : null;

  // config-driven chrome: accent, theme default, favicon
  useEffect(() => {
    if (!config) return;
    applyAccent(config.accent);
    if (config.logo) setFavicon(config.logo);
    const mode = storedTheme() ?? config.theme ?? "system";
    setTheme(mode);
    setThemeAttr(mode);
  }, [config]);

  const onTheme = useCallback((mode: ThemeMode) => {
    storeTheme(mode);
    switchTheme(mode, () => setTheme(mode));
  }, []);

  const refreshConfig = useCallback(() => {
    if (boot.status !== "ready") return;
    const { transport } = boot;
    transport
      .getConfig()
      .then((cfg) => setBoot({ status: "ready", transport, config: cfg }))
      .catch((e) => setBoot({ status: "error", message: describeError(e) }));
  }, [boot]);

  const onUnauthorized = useCallback(() => {
    setBoot((b) => (b.status === "ready" ? { ...b, config: { ...b.config, authenticated: false } } : b));
  }, []);

  let body;
  if (boot.status === "loading" || (boot.status === "ready" && !revealed)) body = <BootScreen />;
  else if (boot.status === "error") body = <BootError message={boot.message} onRetry={() => {
    setBoot({ status: "loading" });
    setAttempt((a) => a + 1);
  }} />;
  else if (boot.config.features.auth && !boot.config.authenticated)
    body = <PasswordGate config={boot.config} transport={boot.transport} onSuccess={refreshConfig} />;
  else
    body = (
      <AppShell transport={boot.transport} config={boot.config} theme={theme} onTheme={onTheme} onUnauthorized={onUnauthorized} />
    );

  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>{body}</ToastProvider>
    </MotionConfig>
  );
}

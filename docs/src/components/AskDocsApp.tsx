/**
 * The DyUI Docs assistant, rendered natively in the docs page (no iframe): the real DyUI web app
 * shell from ../web/src, talking to the assistant backend over its HTTP API (cross-origin, CORS
 * granted by the backend for the docs' origin). Loaded lazily by AskDocsDialog.astro on the first
 * open, so readers who never open it download none of it.
 *
 * The page's own theme drives the shell (both use `html[data-theme]` and the same tokens), so the
 * shell's theme toggle is hidden (ask.css). Requests go without credentials; the backend keeps a
 * conversation together by its thread id.
 */
import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHttpTransport } from "@/lib/api";
import type { AppConfig, ThemeMode } from "@/lib/types";
import { AppShell } from "@/shell/AppShell";
import { ToastProvider } from "@/shell/Toasts";
import "@/styles/base.css";
import "@/shell/shell.css";

const theme = (): ThemeMode => {
  const t = document.documentElement.dataset.theme;
  return t === "light" || t === "dark" ? t : "system";
};

let current: Root | null = null;

/** Load the assistant's config from `server` and mount the chat into `el`. Rejects when the
 *  backend is unreachable, so the caller can show its own error state and retry. */
export async function mountAssistant(el: HTMLElement, server: string): Promise<Root> {
  const base = new URL("api/", server.replace(/\/?$/, "/")).href;
  const transport = createHttpTransport(base);
  const config: AppConfig = await transport.getConfig();
  current?.unmount(); // a retry after a late first success: never two roots on one element
  const root = (current = createRoot(el));
  root.render(
    <StrictMode>
      <ToastProvider>
        <AppShell transport={transport} config={config} theme={theme()} onTheme={() => {}} onUnauthorized={() => {}} />
      </ToastProvider>
    </StrictMode>,
  );
  return root;
}

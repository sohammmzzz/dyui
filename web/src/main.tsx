import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/base.css";
import "./shell/shell.css";
import { App } from "./App";
import { installScrollForwarding } from "./demo/embed";

// docs-site demo build only (compiled out of the real app): hand unused wheel/touch
// scrolling to the embedding page — see src/demo/embed.ts for the message contract
if (import.meta.env.MODE === "demo") installScrollForwarding();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

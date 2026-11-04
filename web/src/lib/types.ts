/**
 * DyUI protocol types — mirrors SPEC.md §4 exactly. Python models in
 * python/dyui/server + python/dyui/chat produce these shapes. Do not drift.
 */

export type ThemeMode = "system" | "light" | "dark";

export type Starter = { label: string; message: string; icon: string | null };

export type AppConfig = {
  title: string;
  description: string | null;
  welcome: string;
  placeholder: string;
  logo: string | null;
  theme: ThemeMode;
  accent: string;
  starters: Starter[];
  features: { history: boolean; uploads: boolean; feedback: boolean; auth: boolean };
  authenticated: boolean;
  version: string;
};

export type ThreadSummary = { id: string; title: string; created_at: number; updated_at: number };
export type Thread = ThreadSummary & { messages: Message[] };

export type MessageStatus = "streaming" | "done" | "cancelled" | "error";

export type Message = {
  id: string;
  role: "user" | "assistant";
  created_at: number;
  parts: Part[];
  feedback?: 1 | -1 | 0;
  status?: MessageStatus;
  action?: { name: string; label: string } | null;
};

export type UINode = {
  id: string;
  ui: string;
  props: Record<string, any>;
  children?: UINode[];
  status?: "streaming" | "done" | "error";
  error?: string;
};

export type StepStatus = "pending" | "running" | "done" | "error";
export type Step = {
  id: string;
  title: string;
  type: string;
  status: StepStatus;
  input?: any;
  output?: any;
  logs?: string[];
  started_at: number;
  duration_ms?: number;
  parent_id?: string | null;
};

export type FileRef = { id: string; name: string; type: string; size: number; url: string };

export type Part =
  | { type: "text"; text: string }
  | { type: "ui"; node: UINode }
  | { type: "step"; step: Step }
  | { type: "reasoning"; text: string; duration_ms?: number }
  | { type: "file"; file: FileRef };

export type ChatRequest = {
  thread_id?: string | null;
  message?: { text: string; files?: string[] };
  regenerate?: boolean;
  edit?: { message_id: string; text: string };
};

export type ActionRequest = {
  thread_id: string;
  message_id: string;
  component_id: string;
  action: string;
  label?: string;
  data?: Record<string, any>;
  values?: Record<string, any>;
};

/** SSE events (SPEC §4). */
export type StreamEvent =
  | { event: "thread"; data: ThreadSummary }
  | { event: "user_message"; data: Message }
  | { event: "message_start"; data: { id: string; role: "assistant"; created_at: number } }
  | { event: "text"; data: { message_id: string; delta: string } }
  | { event: "ui"; data: { message_id: string; node: UINode } }
  | { event: "step"; data: { message_id: string; step: Step } }
  | { event: "reasoning"; data: { message_id: string; delta: string } }
  | { event: "message_end"; data: { id: string; status: "done" | "cancelled" | "error"; duration_ms?: number } }
  | { event: "title"; data: { thread_id: string; title: string } }
  | { event: "error"; data: { message: string; message_id?: string } }
  | { event: "done"; data: Record<string, never> };

/** Context handed to every rendered component (SPEC §7). */
export type NodeContext = {
  messageId: string;
  threadId: string | null;
  /** fire a component action (buttons, form, confirm, choice, rating, list rows) */
  onAction: (req: Omit<ActionRequest, "thread_id" | "message_id">) => void;
  /** send plain text as a new user message (quick_replies) */
  onReply: (text: string) => void;
  /** false for components in older/finished history where interaction is disabled */
  interactive: boolean;
};

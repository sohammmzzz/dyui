import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CircleAlert, CircleCheck, Info } from "lucide-react";
import { useMotionKit } from "./anim";

export type ToastKind = "info" | "success" | "error";
type Toast = { id: number; message: string; kind: ToastKind };
export type ToastFn = (message: string, kind?: ToastKind) => void;

const ToastContext = createContext<ToastFn>(() => {});

export function useToast(): ToastFn {
  return useContext(ToastContext);
}

const ICON = { info: Info, success: CircleCheck, error: CircleAlert } as const;

/** Subtle, self-dismissing status pills (top centre, max three). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);
  const m = useMotionKit();

  const toast = useCallback<ToastFn>((message, kind = "info") => {
    const id = ++seq.current;
    setToasts((t) => [...t.filter((x) => x.message !== message).slice(-2), { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 4200 : 2600);
  }, []);

  const value = useMemo(() => toast, [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="sh-toasts" role="status" aria-live="polite">
        <AnimatePresence initial={false}>
          {toasts.map((t) => {
            const Icon = ICON[t.kind];
            return (
              <motion.div
                key={t.id}
                layout={m.reduced ? false : "position"}
                className={`sh-toast is-${t.kind}`}
                initial={m.reduced ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.98, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
                exit={m.reduced ? { opacity: 0 } : { opacity: 0, y: -6, filter: "blur(3px)", transition: { duration: 0.2 } }}
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              >
                <Icon size={15} strokeWidth={2} aria-hidden="true" />
                <span>{t.message}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

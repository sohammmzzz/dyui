import { useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, Lock, RotateCcw } from "lucide-react";
import { ApiError, describeError, type Transport } from "@/lib/api";
import type { AppConfig } from "@/lib/types";
import { BloomLogo, Logo } from "./Logo";
import { useMotionKit } from "./anim";

/** Shared-password gate (features.auth && !authenticated). */
export function PasswordGate({ config, transport, onSuccess }: { config: AppConfig; transport: Transport; onSuccess: () => void }) {
  const kit = useMotionKit();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async () => {
    if (!password || pending) return;
    setPending(true);
    setError(null);
    try {
      await transport.login(password);
      onSuccess();
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? e.message || "That password isn’t right. Try again." : describeError(e));
      setPending(false);
    }
  };

  return (
    <main className="sh-gate">
      <motion.div className="sh-gate-card" variants={kit.bloom} initial="hidden" animate="show">
        <BloomLogo src={config.logo} size={44} />
        <h1 className="sh-gate-title">{config.title}</h1>
        <p className="sh-gate-sub">This app is password protected.</p>
        <form
          className="sh-gate-form"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label htmlFor="dy-password" className="sh-eyebrow">
            Password
          </label>
          <div className={error ? "sh-field is-error" : "sh-field"}>
            <Lock size={15} strokeWidth={1.9} aria-hidden="true" />
            <input
              id="dy-password"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (error) setError(null);
              }}
              aria-invalid={!!error}
              aria-describedby={error ? "dy-password-error" : undefined}
            />
          </div>
          {error && (
            <motion.p id="dy-password-error" className="sh-field-error" role="alert" variants={kit.rise} initial="hidden" animate="show">
              {error}
            </motion.p>
          )}
          <motion.button type="submit" className="sh-btn is-primary is-lg" disabled={!password || pending} {...kit.press}>
            {pending ? <span className="sh-spinner is-light" aria-hidden="true" /> : null}
            <span>{pending ? "Checking" : "Continue"}</span>
            {!pending && <ArrowRight size={16} strokeWidth={2} aria-hidden="true" />}
          </motion.button>
        </form>
      </motion.div>
    </main>
  );
}

export function BootScreen() {
  return (
    <main className="sh-boot" aria-busy="true" aria-label="Loading">
      <div className="sh-breathe">
        <Logo size={36} />
      </div>
    </main>
  );
}

export function BootError({ message, onRetry }: { message: string; onRetry: () => void }) {
  const kit = useMotionKit();
  return (
    <main className="sh-boot">
      <motion.div className="sh-boot-error" variants={kit.bloom} initial="hidden" animate="show">
        <Logo size={36} />
        <h1>Can’t reach the app</h1>
        <p>{message}</p>
        <button type="button" className="sh-btn is-outline" onClick={onRetry}>
          <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
          Try again
        </button>
      </motion.div>
    </main>
  );
}

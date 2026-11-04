import { AnimatePresence, motion } from "motion/react";
import { Monitor, Moon, PanelLeftOpen, SquarePen, Sun } from "lucide-react";
import type { ThemeMode } from "@/lib/types";
import { Logo } from "./Logo";
import { cx, useMotionKit } from "./anim";

const MODES: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: "light", label: "Light", Icon: Sun },
  { mode: "system", label: "System", Icon: Monitor },
  { mode: "dark", label: "Dark", Icon: Moon },
];

export function ThemeToggle({ value, onChange }: { value: ThemeMode; onChange: (m: ThemeMode) => void }) {
  const kit = useMotionKit();
  return (
    <div className="sh-seg" role="radiogroup" aria-label="Theme">
      {MODES.map(({ mode, label, Icon }) => {
        const on = value === mode;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={on}
            aria-label={`${label} theme`}
            data-tip={label}
            data-tip-pos="bottom"
            className={cx("sh-seg-btn", on && "is-on")}
            onClick={() => onChange(mode)}
          >
            {on && <motion.span layoutId="sh-seg-pill" className="sh-seg-pill" transition={kit.reduced ? { duration: 0 } : kit.spring} />}
            <Icon size={14} strokeWidth={1.9} aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}

export function Header({
  title,
  appTitle,
  logo,
  showOpenSidebar,
  showNewChat,
  showBrand,
  scrolled,
  theme,
  onTheme,
  onOpenSidebar,
  onNewChat,
}: {
  title: string | null;
  appTitle: string;
  logo: string | null;
  showOpenSidebar: boolean;
  showNewChat: boolean;
  showBrand: boolean;
  scrolled: boolean;
  theme: ThemeMode;
  onTheme: (m: ThemeMode) => void;
  onOpenSidebar: () => void;
  onNewChat: () => void;
}) {
  const kit = useMotionKit();
  return (
    <header className={cx("sh-header", scrolled && "is-scrolled")}>
      <div className="sh-header-left">
        {showOpenSidebar && (
          <button type="button" className="sh-icon-btn" onClick={onOpenSidebar} aria-label="Open sidebar" data-tip="Sidebar" data-tip-pos="bottom">
            <PanelLeftOpen size={18} strokeWidth={1.8} />
          </button>
        )}
        {showNewChat && (
          <button type="button" className="sh-icon-btn" onClick={onNewChat} aria-label="New chat" data-tip="New chat" data-tip-pos="bottom">
            <SquarePen size={17} strokeWidth={1.9} />
          </button>
        )}
        <div className="sh-header-title">
          <AnimatePresence mode="wait" initial={false}>
            {title ? (
              <motion.h1
                key={`t:${title}`}
                className="sh-title"
                initial={kit.reduced ? { opacity: 0 } : { opacity: 0, y: 4, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={kit.reduced ? { opacity: 0 } : { opacity: 0, y: -4, filter: "blur(4px)" }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              >
                {title}
              </motion.h1>
            ) : showBrand ? (
              <motion.div
                key="brand"
                className="sh-header-brand"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <Logo src={logo} size={20} />
                <span>{appTitle}</span>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
      <div className="sh-header-right">
        <ThemeToggle value={theme} onChange={onTheme} />
      </div>
    </header>
  );
}

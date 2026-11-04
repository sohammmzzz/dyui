import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import type { AppConfig } from "@/lib/types";
import { BloomLogo } from "./Logo";
import { starterIcon } from "./icons";
import { useMotionKit } from "./anim";

/**
 * Split the welcome heading into [before, accent, after]. `*word*` marks the
 * accent explicitly; otherwise the last word gets the serif-italic treatment.
 */
export function splitHeading(text: string): [string, string, string] {
  const marked = /^(.*?)\*([^*]+)\*(.*)$/.exec(text);
  if (marked) return [marked[1], marked[2], marked[3]];
  const m = /^(.*\s)?(\S+?)([.?!…]*)$/.exec(text.trim());
  if (!m) return ["", text, ""];
  return [m[1] ?? "", m[2], m[3] ?? ""];
}

export function Welcome({ config, onStarter }: { config: AppConfig; onStarter: (message: string) => void }) {
  const kit = useMotionKit();
  const [before, accent, after] = splitHeading(config.welcome || "How can I help?");
  const starters = config.starters.slice(0, 6);
  return (
    <div className="sh-welcome">
      <BloomLogo src={config.logo} size={56} />
      <motion.h2 className="sh-welcome-title" variants={kit.delayed(kit.bloom, 0.18)} initial="hidden" animate="show">
        {before}
        <em className="sh-accent-word">{accent}</em>
        {after}
      </motion.h2>
      {config.description && (
        <motion.p className="sh-welcome-desc" variants={kit.delayed(kit.bloom, 0.28)} initial="hidden" animate="show">
          {config.description}
        </motion.p>
      )}
      {starters.length > 0 && (
        <ul className="sh-starters" aria-label="Suggestions" data-count={starters.length}>
          {starters.map((s, i) => {
            const Icon = starterIcon(s.icon);
            return (
              <motion.li key={`${s.label}-${i}`} variants={kit.delayed(kit.rise, 0.38 + Math.min(i, 8) * 0.045)} initial="hidden" animate="show">
                <motion.button type="button" className="sh-starter" onClick={() => onStarter(s.message || s.label)} {...kit.press}>
                  <span className="sh-starter-icon" aria-hidden="true">
                    <Icon size={16} strokeWidth={1.9} />
                  </span>
                  <span className="sh-starter-label">{s.label}</span>
                  {s.message && s.message !== s.label && <span className="sh-starter-msg">{s.message}</span>}
                  <ArrowUpRight className="sh-starter-arrow" size={15} strokeWidth={1.9} aria-hidden="true" />
                </motion.button>
              </motion.li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

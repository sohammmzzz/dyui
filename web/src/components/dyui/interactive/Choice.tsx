import { useRef, useState, type KeyboardEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { arr, bool, isObj, optStr, str } from "../util/props";
import { DyButton, ResolvedNote, Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/interactive.css";

/** Selection indicator: a radio dot or a checkbox tick that pops in. */
export function OptIndicator({ on, multiple }: { on: boolean; multiple: boolean }) {
  return (
    <span className="dy-opt-ind" data-kind={multiple ? "check" : "radio"} data-on={on || undefined} aria-hidden>
      <AnimatePresence initial={false}>
        {on && (
          <motion.span
            key="on"
            className="dy-opt-ind-mark"
            initial={{ opacity: 0, scale: 0.4 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.4 }}
            transition={{ duration: dur[2], ease }}
          >
            {multiple ? <Check width={12} height={12} strokeWidth={3} /> : null}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

const OTHER = "\u0000other";

/** `choice` — single or multiple choice, with optional free-text "Other". values: {selected, other?} */
export function Choice({ node, ctx }: DyProps) {
  const p = node.props;
  const ia = useInteraction(node, ctx);
  const question = str(p.question ?? p.title);
  const options = arr(p.options)
    .map((o) => (isObj(o) ? str(o.label ?? o.value) : str(o)))
    .filter(Boolean);
  const multiple = bool(p.multiple);
  const allowOther = bool(p.allow_other);
  const action = optStr(p.action) ?? "choice";
  const submitLabel = optStr(p.submit_label) ?? (multiple ? "Continue" : "Choose");
  const [sel, setSel] = useState<string[]>([]);
  const [other, setOther] = useState("");
  const otherInput = useRef<HTMLInputElement>(null);
  const groupRef = useRef<HTMLDivElement>(null);

  const r = ia.resolved ?? ia.pending;
  const rSel: string[] = r ? arr(r.values?.selected).map(str) : [];
  const rOther = r ? optStr(r.values?.other) : undefined;
  const selected = r ? [...rSel, ...(rOther ? [OTHER] : [])] : sel;
  const otherText = r ? rOther ?? "" : other;
  const otherOn = selected.includes(OTHER);
  const locked = ia.disabled;

  const toggle = (o: string) => {
    if (locked) return;
    setSel((s) => (multiple ? (s.includes(o) ? s.filter((x) => x !== o) : [...s, o]) : [o]));
    if (o === OTHER) setTimeout(() => otherInput.current?.focus(), 60);
  };
  const all = allowOther ? [...options, OTHER] : options;
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (multiple || locked) return;
    const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"];
    if (!keys.includes(e.key)) return;
    if ((e.target as HTMLElement).tagName === "INPUT") return;
    e.preventDefault();
    const cur = Math.max(0, all.indexOf(sel[0]));
    const next = (cur + (e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : -1) + all.length) % all.length;
    toggle(all[next]);
    const btns = groupRef.current?.querySelectorAll<HTMLButtonElement>("[data-opt]");
    btns?.[next]?.focus();
  };

  const realSel = selected.filter((s) => s !== OTHER);
  const canSubmit = realSel.length > 0 || (otherOn && otherText.trim().length > 0);
  const submit = () => {
    if (!canSubmit) return;
    const values: Record<string, any> = { selected: realSel };
    if (otherOn && other.trim()) values.other = other.trim();
    const label = [...realSel, ...(values.other ? [values.other] : [])].join(", ");
    ia.fire({ action, label, values });
  };

  const tabTarget = multiple ? null : sel[0] ?? all[0];
  return (
    <Bloom className="dy-c dy-choice dy-panel" data-dy-ui="choice" data-state={ia.state}>
      <div className="dy-ihead">
        <div className="dy-ititle" id={`${node.id}-q`}>
          {question || <Skel w={220} h={18} />}
        </div>
        {multiple && <div className="dy-eyebrow">Select all that apply</div>}
      </div>
      <div
        ref={groupRef}
        className="dy-opts"
        role={multiple ? "group" : "radiogroup"}
        aria-labelledby={`${node.id}-q`}
        onKeyDown={onKey}
        data-locked={locked || undefined}
      >
        {all.map((o, i) => {
          const on = selected.includes(o);
          const isOther = o === OTHER;
          return (
            <div key={i} className="dy-opt-wrap dy-a-rise" style={{ ["--i" as any]: i }}>
              <button
                type="button"
                data-opt=""
                role={multiple ? "checkbox" : "radio"}
                aria-checked={on}
                tabIndex={multiple ? 0 : o === tabTarget ? 0 : -1}
                className="dy-opt"
                data-on={on || undefined}
                data-dim={r && !on ? "" : undefined}
                disabled={locked && !on}
                aria-disabled={locked || undefined}
                onClick={() => toggle(o)}
              >
                <OptIndicator on={on} multiple={multiple} />
                <span className="dy-opt-label">{isOther ? (r && otherText ? `Other: ${otherText}` : "Other…") : o}</span>
              </button>
              <AnimatePresence initial={false}>
                {isOther && on && !r && (
                  <motion.div
                    className="dy-opt-other"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: dur[2], ease }}
                  >
                    <input
                      ref={otherInput}
                      className="dy-input"
                      placeholder="Type your answer"
                      value={other}
                      disabled={locked}
                      onChange={(e) => setOther(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submit()}
                      aria-label="Other answer"
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
        {ia.streaming && options.length === 0 && [0, 1, 2].map((i) => <Skel key={i} h={44} style={{ borderRadius: 12 }} />)}
      </div>
      <div className="dy-ifoot">
        {r ? (
          <ResolvedNote label={r.label || "Sent"} sending={ia.state === "sending"} />
        ) : (
          <>
            <span className="dy-ifoot-hint">{multiple && realSel.length > 0 ? `${realSel.length} selected` : ""}</span>
            <DyButton variant="primary" disabled={!canSubmit || ia.disabled} onClick={submit}>
              {submitLabel}
            </DyButton>
          </>
        )}
      </div>
    </Bloom>
  );
}

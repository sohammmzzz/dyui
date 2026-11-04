import { useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, CircleAlert } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { AutoHeight, Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { arr, bool, cx, fmtNum, isObj, num, optStr, settled, str } from "../util/props";
import { DyButton, ResolvedNote, Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { OptIndicator } from "./Choice";
import "../styles/interactive.css";

const TYPES = ["text", "textarea", "number", "email", "select", "multiselect", "date", "time", "checkbox", "radio", "slider"] as const;
type FType = (typeof TYPES)[number];
type Field = {
  name: string;
  label: string;
  type: FType;
  options: string[];
  required: boolean;
  placeholder?: string;
  default?: any;
  min?: number;
  max?: number;
  step?: number;
};

const SHORT: FType[] = ["text", "email", "number", "date", "time", "select"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function readFields(raw: unknown): Field[] {
  return arr(raw)
    .filter(isObj)
    .map((f, i) => {
      const type: FType = (TYPES as readonly string[]).includes(f.type) ? f.type : "text";
      return {
        name: str(f.name) || `field_${i + 1}`,
        label: str(f.label) || str(f.name) || `Field ${i + 1}`,
        type,
        options: arr(f.options).map((o) => (isObj(o) ? str(o.label ?? o.value) : str(o))).filter(Boolean),
        required: bool(f.required),
        placeholder: optStr(f.placeholder),
        default: f.default,
        min: num(f.min),
        max: num(f.max),
        step: num(f.step),
      };
    });
}

function initial(f: Field): any {
  const d = f.default;
  switch (f.type) {
    case "multiselect":
      return Array.isArray(d) ? d.map((x) => str(x)) : [];
    case "checkbox":
      return f.options.length ? (Array.isArray(d) ? d.map((x) => str(x)) : []) : bool(d);
    case "slider":
      return num(d) ?? f.min ?? 0;
    case "number":
      return d === undefined || d === null ? "" : String(d);
    default:
      return d === undefined || d === null ? "" : str(d);
  }
}

function empty(f: Field, v: any) {
  if (Array.isArray(v)) return v.length === 0;
  if (f.type === "checkbox" && !f.options.length) return v !== true;
  return v === "" || v === undefined || v === null;
}

function validate(f: Field, v: any): string | null {
  if (f.required && empty(f, v)) return f.type === "checkbox" && !f.options.length ? "Please check this to continue" : "This field is required";
  if (empty(f, v)) return null;
  if (f.type === "email" && !EMAIL.test(String(v).trim())) return "Enter a valid email address";
  if (f.type === "number") {
    const n = Number(v);
    if (!Number.isFinite(n)) return "Enter a number";
    if (f.min !== undefined && n < f.min) return `Must be at least ${fmtNum(f.min)}`;
    if (f.max !== undefined && n > f.max) return `Must be at most ${fmtNum(f.max)}`;
  }
  return null;
}

function out(f: Field, v: any) {
  if (f.type === "number") return v === "" ? null : Number(v);
  if (f.type === "slider") return Number(v);
  return v;
}

function display(f: Field, v: any): string {
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return fmtNum(v);
  return String(v);
}

/* ------------------------------------------------------------------ controls */
function Control({ f, v, set, id, err, disabled }: { f: Field; v: any; set: (v: any) => void; id: string; err: boolean; disabled: boolean }) {
  const common = { id, name: f.name, disabled, "aria-invalid": err || undefined, "aria-describedby": err ? `${id}-err` : undefined, "aria-required": f.required || undefined } as const;
  switch (f.type) {
    case "textarea":
      return <textarea {...common} className="dy-input" rows={3} placeholder={f.placeholder} value={v} onChange={(e) => set(e.target.value)} />;
    case "select":
      return (
        <span className="dy-select">
          <select {...common} className="dy-input" value={v} onChange={(e) => set(e.target.value)} data-empty={v === "" || undefined}>
            <option value="" disabled>
              {f.placeholder ?? "Select…"}
            </option>
            {f.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          <ChevronDown width={15} height={15} aria-hidden />
        </span>
      );
    case "multiselect":
      return (
        <div className="dy-chips" role="group" aria-labelledby={`${id}-label`} aria-invalid={err || undefined}>
          {f.options.map((o) => {
            const on = (v as string[]).includes(o);
            return (
              <button
                key={o}
                type="button"
                className="dy-chip-toggle"
                aria-pressed={on}
                disabled={disabled}
                onClick={() => set(on ? (v as string[]).filter((x) => x !== o) : [...v, o])}
              >
                <span className="dy-chip-check" aria-hidden>
                  <Check width={12} height={12} strokeWidth={3} />
                </span>
                {o}
              </button>
            );
          })}
        </div>
      );
    case "radio": {
      const seg = f.options.length <= 4 && f.options.every((o) => o.length <= 16);
      if (seg)
        return (
          <div className="dy-seg" role="radiogroup" aria-labelledby={`${id}-label`}>
            {f.options.map((o) => (
              <button key={o} type="button" role="radio" aria-checked={v === o} className="dy-seg-btn" disabled={disabled} onClick={() => set(o)}>
                {v === o && <motion.span layoutId={`${id}-seg`} className="dy-seg-pill" transition={{ type: "spring", stiffness: 420, damping: 38 }} />}
                <span className="dy-seg-label">{o}</span>
              </button>
            ))}
          </div>
        );
      return (
        <div className="dy-opts dy-opts--compact" role="radiogroup" aria-labelledby={`${id}-label`}>
          {f.options.map((o) => (
            <button key={o} type="button" role="radio" aria-checked={v === o} className="dy-opt" data-on={v === o || undefined} disabled={disabled} onClick={() => set(o)}>
              <OptIndicator on={v === o} multiple={false} />
              <span className="dy-opt-label">{o}</span>
            </button>
          ))}
        </div>
      );
    }
    case "checkbox":
      if (f.options.length)
        return (
          <div className="dy-opts dy-opts--compact" role="group" aria-labelledby={`${id}-label`}>
            {f.options.map((o) => {
              const on = (v as string[]).includes(o);
              return (
                <button key={o} type="button" role="checkbox" aria-checked={on} className="dy-opt" data-on={on || undefined} disabled={disabled} onClick={() => set(on ? (v as string[]).filter((x) => x !== o) : [...v, o])}>
                  <OptIndicator on={on} multiple />
                  <span className="dy-opt-label">{o}</span>
                </button>
              );
            })}
          </div>
        );
      return (
        <button type="button" role="checkbox" id={id} aria-checked={!!v} aria-invalid={err || undefined} className="dy-check-row" disabled={disabled} onClick={() => set(!v)}>
          <OptIndicator on={!!v} multiple />
          <span>{f.label}</span>
          {f.required && <span className="dy-req" aria-hidden>*</span>}
        </button>
      );
    case "slider": {
      const min = f.min ?? 0;
      const max = f.max ?? 100;
      const pct = ((Number(v) - min) / (max - min || 1)) * 100;
      return (
        <div className="dy-range-wrap">
          <input
            {...common}
            type="range"
            className="dy-range"
            min={min}
            max={max}
            step={f.step ?? 1}
            value={v}
            style={{ ["--pct" as any]: `${Math.max(0, Math.min(100, pct))}%` }}
            onChange={(e) => set(Number(e.target.value))}
          />
          <div className="dy-range-scale" aria-hidden>
            <span>{fmtNum(min)}</span>
            <span>{fmtNum(max)}</span>
          </div>
        </div>
      );
    }
    default:
      return (
        <input
          {...common}
          className="dy-input"
          type={f.type === "number" ? "number" : f.type}
          inputMode={f.type === "number" ? "decimal" : undefined}
          autoComplete={f.type === "email" ? "email" : undefined}
          placeholder={f.placeholder}
          min={f.min}
          max={f.max}
          step={f.step}
          value={v}
          onChange={(e) => set(e.target.value)}
        />
      );
  }
}

/* ------------------------------------------------------------------ form */
/** `form` — fields with validation. values: {<name>: value} */
export function Form({ node, ctx }: DyProps) {
  const p = node.props;
  const ia = useInteraction(node, ctx);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const fields = useMemo(() => readFields(p.fields), [p.fields]);
  const title = optStr(p.title);
  const description = optStr(p.description ?? p.text);
  const submitLabel = optStr(p.submit_label) ?? "Submit";
  const action = optStr(p.action) ?? "form_submit";
  const [vals, setVals] = useState<Record<string, any>>({});
  const [errs, setErrs] = useState<Record<string, string>>({});
  const formRef = useRef<HTMLFormElement>(null);
  const valueOf = (f: Field) => (f.name in vals ? vals[f.name] : initial(f));
  const set = (f: Field, v: any) => {
    setVals((s) => ({ ...s, [f.name]: v }));
    if (errs[f.name]) setErrs(({ [f.name]: _, ...rest }) => rest);
  };

  // pair short fields side by side on wide containers
  const spans = useMemo(() => {
    const s: number[] = fields.map(() => 2);
    for (let i = 0; i < fields.length - 1; i++) {
      if (SHORT.includes(fields[i].type) && SHORT.includes(fields[i + 1].type)) {
        s[i] = 1;
        s[i + 1] = 1;
        i++;
      }
    }
    return s;
  }, [fields]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (ia.disabled) return;
    const next: Record<string, string> = {};
    for (const f of fields) {
      const m = validate(f, valueOf(f));
      if (m) next[f.name] = m;
    }
    setErrs(next);
    const first = fields.find((f) => next[f.name]);
    if (first) {
      const root = formRef.current;
      const el =
        root?.querySelector<HTMLElement>(`#${CSS.escape(`${uid}-${first.name}`)}`) ??
        root?.querySelector<HTMLElement>(`[aria-labelledby="${CSS.escape(`${uid}-${first.name}-label`)}"] button`);
      el?.focus();
      return;
    }
    const values: Record<string, any> = {};
    for (const f of fields) values[f.name] = out(f, valueOf(f));
    ia.fire({ action, label: title ? `${submitLabel} · ${title}` : submitLabel, values });
  };

  const r = ia.resolved;
  const shownVals: Record<string, any> = r?.values ?? {};
  let body: ReactNode;
  if (r) {
    body = (
      <motion.div key="done" className="dy-form-summary" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: dur[3], ease }}>
        <dl className="dy-form-sum">
          {fields.map((f, i) => (
            <div key={f.name} className="dy-form-sum-row dy-a-rise" style={{ ["--i" as any]: i }}>
              <dt>{f.label}</dt>
              <dd>{display(f, shownVals[f.name])}</dd>
            </div>
          ))}
        </dl>
        <div className="dy-ifoot">
          <ResolvedNote label="Submitted" />
        </div>
      </motion.div>
    );
  } else {
    body = (
      <motion.form key="form" ref={formRef} className="dy-form-grid" noValidate onSubmit={submit} exit={{ opacity: 0, transition: { duration: dur[1] } }}>
        {fields.map((f, i) => {
          const id = `${uid}-${f.name}`;
          const err = errs[f.name];
          const inline = f.type === "checkbox" && !f.options.length;
          const v = valueOf(f);
          const done = settled(i, fields.length, ia.streaming);
          return (
            <div key={f.name + i} className={cx("dy-field dy-a-rise", spans[i] === 1 && "dy-field--half")} style={{ ["--i" as any]: i }} data-invalid={err ? "" : undefined}>
              {!inline && (
                <div className="dy-field-top">
                  <label className="dy-field-label" id={`${id}-label`} htmlFor={["multiselect", "radio", "checkbox"].includes(f.type) ? undefined : id}>
                    {f.label}
                    {f.required && <span className="dy-req" aria-hidden>*</span>}
                  </label>
                  {f.type === "slider" && <span className="dy-field-val">{fmtNum(Number(v))}</span>}
                </div>
              )}
              {done ? <Control f={f} v={v} set={(x) => set(f, x)} id={id} err={!!err} disabled={ia.disabled} /> : <Skel h={40} style={{ borderRadius: 10 }} />}
              <AnimatePresence initial={false}>
                {err && (
                  <motion.div
                    id={`${id}-err`}
                    className="dy-field-err"
                    role="alert"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: dur[2], ease }}
                  >
                    <CircleAlert width={13} height={13} aria-hidden />
                    {err}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
        {ia.streaming && fields.length === 0 &&
          [0, 1].map((i) => (
            <div key={i} className="dy-field" aria-hidden>
              <Skel w={90} h={10} />
              <Skel h={40} style={{ borderRadius: 10 }} />
            </div>
          ))}
        <div className="dy-ifoot dy-field--full">
          <span className="dy-ifoot-hint">{fields.some((f) => f.required) ? "* Required" : ""}</span>
          <DyButton type="submit" variant="primary" state={ia.state === "sending" ? "sending" : "idle"} disabled={ia.disabled}>
            {ia.state === "sending" ? "Sending…" : submitLabel}
          </DyButton>
        </div>
      </motion.form>
    );
  }

  return (
    <Bloom className="dy-c dy-form dy-panel" data-dy-ui="form" data-state={ia.state}>
      {(title || description) && (
        <div className="dy-ihead">
          {title && <div className="dy-ititle">{title}</div>}
          {description && <p className="dy-idesc">{description}</p>}
        </div>
      )}
      <AutoHeight>
        <AnimatePresence mode="wait" initial={false}>
          {body}
        </AnimatePresence>
      </AutoHeight>
    </Bloom>
  );
}

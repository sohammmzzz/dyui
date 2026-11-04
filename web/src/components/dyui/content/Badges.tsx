import { Bloom } from "../util/motion";
import { arr, isObj, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/content.css";

const COLORS = ["gray", "accent", "green", "amber", "red", "blue", "violet"];

export function Badge({ label, color, index = 0 }: { label: string; color?: string; index?: number }) {
  const c = color && COLORS.includes(color) ? color : "gray";
  return (
    <span className="dy-badge dy-a-rise" data-color={c} style={{ ["--i" as any]: index }}>
      {c !== "gray" && <span className="dy-badge-dot" aria-hidden />}
      {label}
    </span>
  );
}

/** `badges` — a row of tinted pills. */
export function Badges({ node }: DyProps) {
  const items = arr(node.props.items)
    .map((it) => (isObj(it) ? { label: str(it.label ?? it.text), color: str(it.color) } : { label: str(it), color: "" }))
    .filter((it) => it.label);
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-badges" data-dy-ui="badges">
      {items.map((it, i) => (
        <Badge key={i} label={it.label} color={it.color} index={i} />
      ))}
      {streaming && <Skel w={64} h={25} round />}
    </Bloom>
  );
}

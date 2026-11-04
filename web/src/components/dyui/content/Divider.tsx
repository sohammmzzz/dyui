import { Bloom } from "../util/motion";
import { optStr } from "../util/props";
import type { DyProps } from "../util/types";
import "../styles/content.css";

/** `divider` — a hairline, optionally with a centered eyebrow label. */
export function Divider({ node }: DyProps) {
  const label = optStr(node.props.label);
  return (
    <Bloom className="dy-c dy-divider" data-dy-ui="divider" role="separator" aria-label={label}>
      <span className="dy-divider-line" />
      {label && <span className="dy-divider-label dy-eyebrow">{label}</span>}
      {label && <span className="dy-divider-line" />}
    </Bloom>
  );
}

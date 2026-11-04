import { CircleCheck, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { Bloom } from "../util/motion";
import { Prose } from "../util/Markdown";
import { optStr, str } from "../util/props";
import { SkelLines } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/content.css";

const ICONS = { info: Info, success: CircleCheck, warning: TriangleAlert, error: OctagonAlert } as const;
type Level = keyof typeof ICONS;

/** `callout` — soft tinted box with an icon. */
export function Callout({ node }: DyProps) {
  const p = node.props;
  const level: Level = (["info", "success", "warning", "error"] as const).includes(p.level) ? p.level : "info";
  const Icon = ICONS[level];
  const title = optStr(p.title);
  const text = str(p.text);
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-callout" data-dy-ui="callout" data-level={level} role={level === "error" ? "alert" : "note"}>
      <span className="dy-callout-icon dy-a-pop" style={{ ["--d" as any]: "160ms" }} aria-hidden>
        <Icon strokeWidth={2.1} />
      </span>
      <div className="dy-callout-main">
        {title && <div className="dy-callout-title">{title}</div>}
        {text ? <Prose text={text} /> : streaming && !title ? <SkelLines lines={2} /> : null}
      </div>
    </Bloom>
  );
}

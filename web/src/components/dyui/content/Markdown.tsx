import { Bloom } from "../util/motion";
import { Prose } from "../util/Markdown";
import { str } from "../util/props";
import { SkelLines } from "../util/ui";
import type { DyProps } from "../util/types";

/** `markdown` — rich text, mostly inside layouts. */
export function Markdown({ node }: DyProps) {
  const text = str(node.props.text ?? node.props.content);
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-markdown" data-dy-ui="markdown">
      {text ? <Prose text={text} /> : streaming ? <SkelLines lines={3} /> : null}
    </Bloom>
  );
}

import { Bloom } from "../util/motion";
import { optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { CodeBlock } from "./CodeBlock";

/** `code` — highlighted code with filename/language header and copy. */
export function Code({ node }: DyProps) {
  const p = node.props;
  const code = str(p.code);
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-code-wrap" data-dy-ui="code">
      {code || !streaming ? (
        <CodeBlock code={code} language={optStr(p.language)} filename={optStr(p.filename)} streaming={streaming} />
      ) : (
        <div className="dy-code" aria-busy>
          <div className="dy-code-head">
            <Skel w={90} h={10} />
          </div>
          <div style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
            <Skel w="56%" h={10} />
            <Skel w="74%" h={10} />
            <Skel w="40%" h={10} />
          </div>
        </div>
      )}
    </Bloom>
  );
}

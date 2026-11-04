import { Bloom, useBloomDelay } from "../util/motion";
import { arr, isObj, settled } from "../util/props";
import type { DyProps } from "../util/types";
import { StatBody } from "./Stat";
import "../styles/data.css";

/** `stats` — a responsive row of stats in one quiet panel. */
export function Stats({ node }: DyProps) {
  const streaming = node.status === "streaming";
  const items = arr(node.props.items).filter(isObj);
  const delay = useBloomDelay();
  const n = Math.max(items.length, streaming ? items.length + 1 : 1);
  const cols = n <= 4 ? n : n <= 6 ? 3 : 4;
  const cells = streaming && items.length === 0 ? [{}, {}, {}] : items;
  return (
    <Bloom className="dy-c dy-stats dy-panel" data-dy-ui="stats">
      <div className="dy-stats-grid" style={{ ["--cols" as any]: Math.max(1, Math.min(cols, 4)) }}>
        {cells.map((it, i) => (
          <div key={i} className="dy-stats-cell dy-a-rise" style={{ ["--i" as any]: i }}>
            <StatBody p={it} settled={settled(i, items.length, streaming) && items.length > 0} delay={delay + i * 0.08} />
          </div>
        ))}
      </div>
    </Bloom>
  );
}

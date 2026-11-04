import { NodeList } from "../NodeView";
import { Badge } from "../content/Badges";
import { readButtons, ActionRow } from "../interactive/Buttons";
import { BlurImage } from "../media/Image";
import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { childNodes, cx, isObj, optStr, safeMediaUrl, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `card` — the default container: optional image, title, badge, children and actions. */
export function Card({ node, ctx }: DyProps) {
  const p = node.props;
  const ia = useInteraction(node, ctx);
  const children = childNodes(node.children ?? p.children, node.id, node.status);
  const title = optStr(p.title);
  const subtitle = optStr(p.subtitle);
  const image = safeMediaUrl(p.image);
  const actions = readButtons(p.actions);
  const badge = isObj(p.badge) ? { label: str(p.badge.label ?? p.badge.text), color: str(p.badge.color) || "accent" } : optStr(p.badge) ? { label: str(p.badge), color: "accent" } : null;
  const empty = !title && !subtitle && !children.length && node.status === "streaming";
  return (
    <Bloom className={cx("dy-c dy-card dy-panel", image && "dy-card--media")} data-dy-ui="card">
      {image && (
        <div className="dy-card-media">
          <BlurImage src={image} alt={optStr(p.image_alt) ?? ""} cover />
        </div>
      )}
      <div className="dy-card-inner">
        {(title || subtitle || badge || empty) && (
          <div className="dy-card-head">
            <div className="dy-card-titles">
              {title ? <div className={image ? "dy-card-title dy-card-title--hero" : "dy-card-title"}>{title}</div> : empty ? <Skel w={160} h={14} /> : null}
              {subtitle && <div className="dy-card-sub">{subtitle}</div>}
            </div>
            {badge?.label && <Badge label={badge.label} color={badge.color} />}
          </div>
        )}
        {children.length > 0 && <NodeList nodes={children} ctx={ctx} className="dy-card-body" baseDelay={0.08} />}
        {actions.length > 0 && (
          <div className="dy-card-actions">
            <ActionRow items={actions} ia={ia} />
          </div>
        )}
      </div>
    </Bloom>
  );
}

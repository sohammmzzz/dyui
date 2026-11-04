import type { ReactNode } from "react";
import type { NodeContext, UINode } from "../../../lib/types";

/** Props every DyUI component receives. */
export type DyProps = { node: UINode; ctx: NodeContext };
export type DyComponent = (props: DyProps) => ReactNode;

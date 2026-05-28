/** Public API of dyui-react. */
export { streamAgent } from "./client";
export type { StreamOptions } from "./client";

export { useDyUIAgent } from "./useDyUI";
export type { UseDyUIOptions, UseDyUIResult, DyUIState } from "./useDyUI";

export { DyUISurface, DyUICard } from "./Surface";
export type { DyUISurfaceProps, DyUICardProps } from "./Surface";

export { defaultRegistry, createRegistry } from "./registry";
export * as cards from "./cards/builtins";
export { sanitizeHtml } from "./cards/sanitize";

export {
  reducer,
  initialState,
  selectCards,
  selectSurfaces,
} from "./store";
export type { DyUIAction } from "./store";

export type {
  CardStatus,
  DyUIEvent,
  DyUICard as DyUICardData,
  CardComponent,
  CardComponentProps,
  CardRegistry,
  StreamFrame,
  ConnectionStatus,
} from "./types";

/**
 * The card registry maps a `component` key (as emitted by the agent) to the
 * React component that renders it. `defaultRegistry` ships with a useful set of
 * primitives; `createRegistry` lets you add or override entries.
 */
import type { CardRegistry } from "./types";
import {
  AlertCard,
  HtmlCard,
  ImageCard,
  JsonCard,
  KeyValueCard,
  ListCard,
  MarkdownCard,
  ProgressCard,
  StatCard,
  TableCard,
  TextCard,
} from "./cards/builtins";

export const defaultRegistry: CardRegistry = {
  text: TextCard,
  markdown: MarkdownCard,
  table: TableCard,
  stat: StatCard,
  progress: ProgressCard,
  list: ListCard,
  keyvalue: KeyValueCard,
  json: JsonCard,
  alert: AlertCard,
  image: ImageCard,
  html: HtmlCard,
};

/**
 * Merge custom cards over the defaults. Pass your own components keyed by the
 * `component` names your agent emits:
 *
 *   const registry = createRegistry({
 *     calc_result: MyCalculatorCard,   // brand-new card type
 *     stat: MyFancyStatCard,           // override a built-in
 *   });
 */
export function createRegistry(overrides: CardRegistry = {}): CardRegistry {
  return { ...defaultRegistry, ...overrides };
}

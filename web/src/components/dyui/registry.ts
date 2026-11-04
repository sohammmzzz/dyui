import type { DyComponent } from "./util/types";
import { Markdown } from "./content/Markdown";
import { Callout } from "./content/Callout";
import { Code } from "./content/Code";
import { Quote } from "./content/Quote";
import { Sources } from "./content/Sources";
import { Badges } from "./content/Badges";
import { Divider } from "./content/Divider";
import { Table } from "./data/Table";
import { Stat } from "./data/Stat";
import { Stats } from "./data/Stats";
import { KeyValue } from "./data/KeyValue";
import { Chart } from "./data/Chart";
import { Progress } from "./data/Progress";
import { Timeline } from "./data/Timeline";
import { Json } from "./data/Json";
import { Image } from "./media/Image";
import { Gallery } from "./media/Gallery";
import { Video } from "./media/Video";
import { Audio } from "./media/Audio";
import { File } from "./media/File";
import { LinkPreview } from "./media/LinkPreview";
import { Buttons } from "./interactive/Buttons";
import { QuickReplies } from "./interactive/QuickReplies";
import { Choice } from "./interactive/Choice";
import { Form } from "./interactive/Form";
import { Confirm } from "./interactive/Confirm";
import { Rating } from "./interactive/Rating";
import { Card } from "./layout/Card";
import { Grid } from "./layout/Grid";
import { Tabs } from "./layout/Tabs";
import { Accordion } from "./layout/Accordion";
import { Carousel } from "./layout/Carousel";
import { List } from "./layout/List";
import { Step } from "./agent/Step";
import { Reasoning } from "./agent/Reasoning";
import { Plan } from "./agent/Plan";
import { Html } from "./developer/Html";
import { Invalid } from "./developer/Invalid";

/** ui name → component (SPEC §6). */
export const registry: Record<string, DyComponent> = {
  markdown: Markdown, callout: Callout, code: Code, quote: Quote, sources: Sources, badges: Badges, divider: Divider,
  table: Table, stat: Stat, stats: Stats, keyvalue: KeyValue, chart: Chart, progress: Progress, timeline: Timeline, json: Json,
  image: Image, gallery: Gallery, video: Video, audio: Audio, file: File, link_preview: LinkPreview,
  buttons: Buttons, quick_replies: QuickReplies, choice: Choice, form: Form, confirm: Confirm, rating: Rating,
  card: Card, grid: Grid, tabs: Tabs, accordion: Accordion, carousel: Carousel, list: List,
  step: Step, reasoning: Reasoning, plan: Plan,
  html: Html, invalid: Invalid,
};

/** Catalog groups, in spec order (used by the gallery and docs). */
export const GROUPS: Record<string, string[]> = {
  content: ["markdown", "callout", "code", "quote", "sources", "badges", "divider"],
  data: ["table", "stat", "stats", "keyvalue", "chart", "progress", "timeline", "json"],
  media: ["image", "gallery", "video", "audio", "file", "link_preview"],
  interactive: ["buttons", "quick_replies", "choice", "form", "confirm", "rating"],
  layout: ["card", "grid", "tabs", "accordion", "carousel", "list"],
  agent: ["step", "reasoning", "plan"],
  developer: ["html", "invalid"],
};

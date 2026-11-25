/**
 * Renders nothing. AskDocsDialog.astro renders it as a `client:only="react"` island in `astro dev`
 * only: a page gets @vitejs/plugin-react's React Refresh preamble only when it has a React island,
 * and without it the assistant's lazily imported .tsx modules throw "can't detect preamble" on
 * pages that have none. Production builds need no preamble, so they keep zero up-front cost.
 */
export default function ReactDevPreamble() {
  return null;
}

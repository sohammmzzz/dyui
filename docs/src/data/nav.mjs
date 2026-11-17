// The docs navigation, shared by astro.config.mjs (the Starlight sidebar) and the
// llms.txt / llms-full.txt endpoints (page order), so both always list the same pages.
//
// Order follows Diátaxis: a tutorial path (Get started), how DyUI works (Concepts),
// reference material (Components, Integrations, Reference), then deploy and cookbook.

export const GROUP_LABELS = {
  content: "Content", data: "Data", media: "Media", interactive: "Interactive",
  layout: "Layout", agent: "Agent", developer: "Developer-only",
};

export const SECTIONS = [
  {
    label: "Get started",
    items: [
      { label: "Installation", link: "/get-started/installation/" },
      { label: "Quickstart", link: "/get-started/quickstart/" },
      { label: "API keys & environment", link: "/get-started/api-keys/" },
      { label: "Your first LLM bot", link: "/get-started/first-llm-bot/" },
      { label: "Project structure", link: "/get-started/project-structure/" },
      { label: "Build with AI", link: "/get-started/coding-agents/" },
    ],
  },
  {
    label: "Concepts",
    items: [
      { label: "How DyUI works", link: "/concepts/how-it-works/" },
      { label: "Messages & streaming", link: "/concepts/messages-and-streaming/" },
      { label: "Generative UI", link: "/concepts/generative-ui/" },
      { label: "Custom components", link: "/concepts/custom-components/" },
      { label: "Actions & human-in-the-loop", link: "/concepts/actions/" },
      { label: "Steps & reasoning", link: "/concepts/steps-and-reasoning/" },
      { label: "Sessions & persistence", link: "/concepts/sessions-and-persistence/" },
      { label: "Theming & branding", link: "/concepts/theming/" },
      { label: "Authentication", link: "/concepts/auth/" },
    ],
  },
  { label: "Components", components: true },
  {
    label: "Integrations",
    items: [
      { label: "Models & providers", link: "/integrations/overview/" },
      { label: "OpenAI", link: "/integrations/openai/" },
      { label: "Anthropic", link: "/integrations/anthropic/" },
      { label: "Ollama & local models", link: "/integrations/ollama/" },
      { label: "Groq, OpenRouter & others", link: "/integrations/other-providers/" },
      { label: "LangGraph", link: "/integrations/langgraph/" },
      { label: "Bring your own SDK", link: "/integrations/bring-your-own-sdk/" },
    ],
  },
  {
    label: "Deploy",
    items: [
      { label: "Production server", link: "/deploy/production/" },
      { label: "Docker", link: "/deploy/docker/" },
      { label: "Render, Fly & Railway", link: "/deploy/platforms/" },
      { label: "Behind a reverse proxy", link: "/deploy/reverse-proxy/" },
    ],
  },
  {
    label: "Cookbook",
    items: [
      { label: "Travel bot", link: "/cookbook/travel-bot/" },
      { label: "Data analyst", link: "/cookbook/data-analyst/" },
      { label: "Support bot", link: "/cookbook/support-bot/" },
      { label: "LangGraph agent", link: "/cookbook/langgraph-agent/" },
      { label: "No-LLM bot", link: "/cookbook/no-llm-bot/" },
    ],
  },
  {
    label: "Reference",
    items: [
      { label: "CLI", link: "/reference/cli/" },
      { label: "Protocol", link: "/reference/protocol/" },
      { label: "Python API", api: true },
    ],
  },
  { label: "Changelog", link: "/changelog/" },
];

/** The Starlight sidebar config. */
export function sidebar(components) {
  const componentGroups = Object.entries(GROUP_LABELS).map(([group, label]) => ({
    label,
    collapsed: true,
    items: components
      .filter((c) => c.group === group)
      .map((c) => ({ label: c.name, link: `/components/${c.name}/` })),
  }));
  return SECTIONS.map((s) => {
    if (s.link) return { label: s.label, link: s.link };
    if (s.components) return { label: s.label, items: [{ label: "Overview", link: "/components/" }, ...componentGroups] };
    return {
      label: s.label,
      items: s.items.map((i) =>
        i.api ? { label: i.label, collapsed: true, items: [{ autogenerate: { directory: "reference/api" } }] } : i,
      ),
    };
  });
}

// /llms.txt — an index of every docs page for language models (https://llmstxt.org).
import type { APIRoute } from "astro";
import { INTRO, pages, url } from "../lib/llms";

export const GET: APIRoute = async () => {
  const all = await pages();
  const lines = ["# DyUI", "", `> ${INTRO}`, "", `The whole documentation as one file: ${url("llms-full.txt").replace(/\/$/, "")}`, ""];
  let section = "";
  for (const p of all) {
    if (p.section !== section) {
      section = p.section;
      lines.push("", `## ${section}`, "");
    }
    lines.push(`- [${p.title}](${url(p.slug)})${p.description ? `: ${p.description}` : ""}`);
  }
  return new Response(lines.join("\n").replace(/\n{3,}/g, "\n\n") + "\n", {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};

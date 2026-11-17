// /llms-full.txt — every docs page as Markdown, complete examples inlined, in sidebar order.
import type { APIRoute } from "astro";
import { INTRO, pages, url } from "../lib/llms";

export const GET: APIRoute = async () => {
  const all = await pages();
  const parts = [`# DyUI documentation\n\n> ${INTRO}\n`];
  for (const p of all) {
    if (!p.markdown.trim()) continue;
    parts.push(
      `\n---\n\n# ${p.title}\n\nURL: ${url(p.slug)}\n${p.description ? `\n> ${p.description}\n` : ""}\n${p.markdown}`,
    );
  }
  return new Response(parts.join(""), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};

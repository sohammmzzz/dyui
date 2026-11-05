# DyUI — Logo design handover

Everything the logo work produced before it was paused to save budget: the brief, the research,
the principles adopted, six explored concepts with all exploration renders, the designer's critique
notes, and the source scripts to keep iterating. **No concept was chosen.** The current droplet mark
in the repo is a placeholder the owner dislikes.

## 1. Brief
- **Product:** DyUI, a Python framework for professional chatbots whose LLM replies with rendered UI
  (cards, charts, forms). Tagline: *"Chatbots that answer in interfaces."*
- **Brand concept:** *dye in still water*. Interfaces emerge out of text, calmly.
- **Voice:** calm, precise, quietly premium. Never flashy, bouncy or neon.
- **Palette:**

  | Colour | Light | Dark |
  |---|---|---|
  | Indigo dye (accent) | `#5B4FE0` | `#8B80FF` |
  | Teal (secondary) | `#14A394` | `#3DD6C3` |

  Ink `#1A1A1F` on paper `#F7F6F3`; midnight background `#0B0C10`.
- **Type:**
  - Instrument Serif: display and the wordmark.
  - Instrument Sans: UI.
  - Geist Mono: code.
- **The owner's verdict on the current logo:** rejected as "not artistic or professional". It is a
  gradient teardrop with three concentric white rings; see `screenshots/current-brand/`.
- **The ask:** a more artistic, professional mark, designed the way the big brand studios design marks.

## 2. Research summary
The full research is in `research/logo_research_full.md`. Caveat: it is mostly secondary sources;
anything unverified is marked [U] there.

### Principles adopted
1. **Concept first.** One idea per mark. A mark that needs explaining has too many.
2. **Design the system, not just the logo.** Plan the mark, wordmark, lockups, app icon and favicon together.
3. **Monochrome first.** The mark must work flat in one colour; colour and gradient only reinforce it.
4. **Must read at 16px.** Avoid fine detail that disappears at favicon size, and check at true size.
5. **One geometric logic.** A consistent curve and stroke logic, built on a grid (100×100), with three elements at most.
6. **Optical over mathematical.** Correct for visual weight and balance. OpenAI's 2025 refresh fixed
   exactly this kind of asymmetry.
7. **At most one negative-space idea.**
8. **Gradients are secondary.** Indigo→teal is allowed as an alternate treatment, never the identity itself.
9. **Restraint in use.** The mark is used sparingly and the wordmark carries the brand. Define clear
   space and an app-icon safe area of about 15–20%.
10. **Timeless over trendy.**

### Territory to avoid
- AI sparkles and 4-point stars (generic AI).
- Radial petal "blossoms" (OpenAI and Claude territory).
- Concentric rings (the rejected mark).
- Gradient blobs.
- Map-pin silhouettes.
- Four-square grids (Microsoft).
- "Layers" stack icons.

### Case-study takeaways
- **Vercel:** a solid triangle. Pure geometry in one flat colour.
- **Claude:** a hand-feeling radial spark. Warmth comes from the form and the colour.
- **OpenAI:** the "blossom", refined optically in 2025. "Bloom" is now crowded territory.
- **Linear:** a simple abstract form inside a strong visual system.
- **Figma, Notion, Mistral:** letterform marks built from simple shapes.
- **Common pattern:** strong developer-tool marks are one flat shape made of simple geometry.

## 3. Concepts explored (renders in `screenshots/concepts/`)
- **File naming:** `x-c<N>.png` is the first pass; `b` and `c` are later refinement passes.
- **Boards:** each board shows the mark large on paper and on midnight, mono versions, app icons,
  favicons at 32 and 16px, and lockups.
- `glyphs.png` and `glyphs2.png` are wordmark and letterform studies in Instrument Serif.

| # | Concept | Idea | Renders | Designer's notes when stopped |
|---|---|---|---|---|
| C1 | **Ink Card** | A drop and a UI card in one shape: a rounded square with one sharp corner as the drop tip, and negative-space "text lines" that become an interface | `x-c1`, `b`, `c` | Not yet critiqued. The research ranked it as the strongest link to "dye". Risk: it can look like a map pin or the Android shape, so use an asymmetric tip angle |
| C2 | **Speech Drop** | A drop that, tilted, is also a chat bubble | `x-c2`, `b`, `c` | ❌ "Reads as a list/notes icon (generic)" |
| C3 | **D-Card monogram** | A geometric D whose counter is an interface card | `x-c3`, `b`, `c` | ❌ Construction bug: the bowl circle protrudes left of the stem. The header-bar variants look like trash cans. The bar needs dropping at small sizes |
| C4 | **Dy ligature** | A serif-feeling "Dy" whose y-tail curls into a chat-bubble tail, with a D-only fallback for tiny sizes | `x-c4` | Not yet critiqued. Artistic, but the "Dy" is lost at 16px |
| C5 | **Quarter-circle bloom** | Petals with unequal radii whose negative-space cross reads as a UI grid | `x-c5`, `b` | Was being reviewed when stopped. Risk: closeness to pinwheel, Microsoft and OpenAI forms |
| C6 | **Layered emergence** | A line of text turning into a card: ink spreading into layout, three shapes at most | `x-c6`, `b`, `c` | Was being reviewed when stopped. Risk: fussy at small sizes, or reads as a "layers" icon |

**Recommended next step:**
- Review the `c` passes of C1, C5 and C6, plus C4.
- Shortlist two.
- Refine each on the 100×100 grid with optical corrections.
- Test it at a true 16px, in mono, and in the serif lockup.
- Show the owner a single contact sheet to choose from.

## 4. Deliverables expected once a concept is chosen
- **Mark files:** `mark.svg`, `mark-mono.svg`, `mark-white.svg`.
- **App icons:** `app-icon-light.svg` and `app-icon-dark.svg` (rounded tile, about 18% safe area).
- **Favicon:** must work at 32 and 16px.
- **Lockups:** `lockup-light.svg` and `lockup-dark.svg`, with "DyUI" in Instrument Serif converted to
  outlines. Use `source/current-brand/textpath.py`.
- **Swapping it into the repo (`sohammmzzz/dyui`, branch `claude/friendly-cerf-om5ed0`):**
  1. Replace `brand/logo.svg`, `brand/favicon.svg`, `brand/wordmark.svg` and `brand/wordmark-dark.svg`.
  2. Replace `web/src/styles/logo.svg` and `web/public/favicon.svg`. The app renders the logo only
     through `web/src/shell/Logo.tsx`.
  3. Regenerate the README hero: update `mark()` in `brand/tools/brand_svgs.py`, then run it.

## 5. Folder contents
```
logo_design_handover.md          this file
research/logo_research_full.md   full research report (principles, case studies, 8 concept specs)
screenshots/concepts/            all exploration boards (x-c1 … x-c6, passes a/b/c, glyph studies)
screenshots/current-brand/       the rejected mark in the README hero + wordmark, and the app with it
source/build/                    the designer's generator scripts (geo.py, shapes.py, explore.py, x1–x3.py),
                                 board HTML pages, shoot.cjs (Playwright renderer), fonts.css
source/current-brand/            current SVGs + textpath.py / brand_svgs.py (text→outline tools)
```
To re-render a board: open `source/build/x-c<N>.html` in a browser. Or run
`NODE_PATH=$(npm root -g) node shoot.cjs`; it needs Playwright, and the fonts from `web/node_modules`.
The scripts reference absolute paths from the original session, so adjust them to your checkout.

## 6. v1 — chosen mark (2026-11-05)
Fresh exploration on the brief "dynamic UI, no water drop, keep the colours, relatable".
- **Explored:** 8 candidates in round 1: Typing → Card, Rising reply, Window bubble,
  Prompt → Card, D-bubble, Switch bubble, Unfold, Caret → Card (`screenshots/v1/r1-*.png`).
  Rejected:
  - Window bubble: generic, and the tail seam is crude.
  - Unfold: reads as the "copy" icon.
  - Caret: reads as "align left" or a sidebar icon.
  - Rising reply: mushy at 16px.
  - Prompt: reads as a terminal or media "next" icon.
- **Shortlist** (refined in round 2): Typing → Card, Switch bubble and D-bubble. See
  `screenshots/v1/contact-sheet.png` and the `board-*.png` files.
- **Chosen: Typing → Card.**
  - It is the moment every chat user knows (the typing dots), and the answer arrives as an
    interface: DyUI's whole promise in one glance.
  - It has three flat elements, reads at 16px, and is outside every avoided territory.
  - It doubles as the product's own motion: the avatar "types" while thinking, and the
    welcome mark assembles.
- **Why the other two lost:**
  - Switch bubble is witty, but a toggle drifts toward "settings app".
  - D-bubble has the strongest silhouette, but D-shaped chat bubbles are a crowded,
    generic territory.
- **Swap-ready alternates:** `brand/alternates/{typing-card,switch-bubble,d-bubble}.svg`.
  To switch, change `MARK_D` in `brand/tools/brand_svgs.py` and the three shapes in
  `web/src/shell/Logo.tsx`.
- **Tools:** `source/v1/explore.py` (candidates and boards) and `source/v1/shoot.mjs`
  (Playwright renderer):
  `python source/v1/explore.py <out>`, then `node shoot.mjs <out>`.

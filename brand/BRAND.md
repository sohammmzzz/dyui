# DyUI brand sheet

**Idea:** dye in still water. Interfaces emerge from text, calmly.
**Voice:** calm, precise, quietly premium. Never flashy, bouncy or neon.
**Tagline:** Chatbots that answer in interfaces.

## Mark

<img src="logo.svg" width="96" alt="DyUI mark">

"Typing → Card": two typing dots, then the reply arrives as an interface card. The card's one
tight corner (bottom-left) is the chat-bubble convention.

- Grid 100×100. Dots r 9 at (11, 50) and (35, 50). Card 46×50 at (52, 25), radii 14, tight corner 4.
- Tight box x 2–98, y 25–75 (about 2:1). The same geometry is drawn and animated by
  `web/src/shell/Logo.tsx`; change one only with the other.
- One flat colour. Indigo on paper, lifted indigo or white on midnight, ink for one-colour print.
- Minimum size: 16 px wide (favicon). Below 24 px use `favicon.svg`, which is pixel-fitted.

## Lockups

| | Light | Dark |
|---|---|---|
| Horizontal | <img src="wordmark.svg" height="40" alt="DyUI lockup"> | `wordmark-dark.svg` |
| Stacked | <img src="lockup-stacked.svg" height="72" alt="DyUI stacked lockup"> | `lockup-stacked-dark.svg` |

- Wordmark: "DyUI" in Instrument Serif Regular, tracking −0.012 em, converted to outlines.
- Horizontal: the mark is exactly as tall as the capitals and stands on the baseline; the gap
  between mark and "D" is half the mark's height.
- Stacked: mark and wordmark share one width.
- **Clear space:** one mark height (= cap height) on every side. Nothing enters it.
- **Minimum size:** horizontal lockup 20 px high; stacked 48 px high.
- Prefer the lockup. Use the mark alone only where the name is already present (app chrome, favicon, avatar).

## Colour

| Role | Light | Dark |
|---|---|---|
| Indigo (identity) | `#5B4FE0` | `#8B80FF` |
| Teal (secondary) | `#14A394` | `#3DD6C3` |
| Text | ink `#1A1A1F` | `#ECECF1` |
| Background | paper `#F7F6F3` | midnight `#0B0C10` |
| Surface / border | `#FFFFFF` / `#E6E3DC` | `#14151C` / `#24252F` |

Indigo is the identity. Teal appears only as a second data series or a small positive signal.
Indigo and teal together are a secondary treatment, never the logo. Canonical values:
`web/src/styles/tokens.css`.

## Type

| Use | Face |
|---|---|
| Display, wordmark, big numbers | Instrument Serif (italic for one emphasised word) |
| UI and body | Instrument Sans |
| Code | Geist Mono |

Text inside SVGs is converted to outlines (`tools/textpath.py`) because GitHub does not load web fonts.

## App icon and favicon

- Tile corner radius 22.5%. The mark is 64% of the tile width (18% safe area each side) and is
  centred optically, slightly left of its box centre, because the card outweighs the dots.
- `app-icon-maskable.svg` is full-bleed with the mark inside the central 80% circle (Android / PWA).
- `favicon.svg` is the bare mark; it switches to lifted indigo in dark browser chrome.

## Do / don't

- Do keep the mark flat and in one colour.
- Do give it its clear space and let the wordmark carry the name.
- Don't redraw, stretch, rotate, outline or add effects to the mark.
- Don't fill the mark with the indigo→teal gradient in static assets.
- Don't set the wordmark in another typeface or weight.
- Don't add sparkles, 4-point stars, petals, rings, blobs or "layers" motifs around it.

## Files

| File | What |
|---|---|
| `logo.svg`, `mark-mono.svg`, `mark-white.svg` | Mark in indigo, ink, white (100×100 box) |
| `wordmark.svg`, `wordmark-dark.svg` | Horizontal lockup (docs site logo) |
| `lockup-stacked.svg`, `lockup-stacked-dark.svg` | Stacked lockup |
| `app-icon-light.svg`, `app-icon-dark.svg`, `app-icon-maskable.svg` | App icon tiles |
| `png/app-icon-192.png`, `png/app-icon-512.png`, `png/app-icon-maskable-512.png` | PNG exports for manifests |
| `favicon.svg` | Favicon; copied to `web/public/` by the generator and to `docs/public/` by the docs prebuild |
| `readme-hero-light.svg`, `readme-hero-dark.svg` | README banner, 1280×520 |
| `social-card-light.svg/.png`, `social-card-dark.svg/.png` | Open Graph card, 1200×630 |
| `screenshots/` | Product screenshots used in the README |
| `alternates/` | Shortlisted marks from the v1 exploration, kept for reference |
| `proposals/` | Proposed refinements of the mark. Not applied; see `proposals/README.md` |
| `tools/` | Generators. Nothing in this folder is edited by hand |

## Regenerating

```
python brand/tools/brand_svgs.py                           # every SVG
node brand/tools/render.cjs brand/tools/render-jobs.json   # the PNGs
```

Needs `fonttools` and `brotli` for Python, the fonts from `web/node_modules` (or
`DYUI_NODE_MODULES=<path to a node_modules with the three @fontsource packages>`), and
`playwright` resolvable by node for the PNG step.

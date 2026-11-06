# DyUI logo research

> Research notes for the DyUI logo redesign. **Resolved in v1 (2026-11-05):** the mark is
> "Typing → Card" (see SPEC §1.2 and `brand/logo_design_handover/logo_design_handover.md` §6).

# DyUI logo research (2026-11-04)

## Source quality note
Web search returned mostly secondary/SEO sources; very few primary studio case studies. Items marked [V] have a cited source below; [U] = unverified, from general design knowledge (treat as hypothesis).

## 1. Process and principles
1. Concept first, form second. Pentagram's Paula Scher: Citi mark reportedly sketched on a napkin in the meeting and barely changed [V, anecdote] https://www.creativebloq.com/features/paula-scher-logo-sketches ; https://sva.edu/features/svas-paula-scher-discusses-pentagrams-design-process
2. Design the system, not the logo: Bierut, "you're not designing the rocket ship, you're designing the launch pad" [V] https://www.designboom.com/design/michael-bierut-interview/ ; https://www.logodesignlove.com/michael-bierut-talking-logos
3. Simplicity is the result of a lot of work (Bierut theme) [V, weak]. Simple + memorable + versatile + timeless + relevant is the consensus checklist [V, generic] https://www.vistaprint.com/hub/principles-of-logo-design ; https://cieden.com/book/atoms/logo/principles-of-logo-design
4. Scalability: must survive ~1 inch / 16px; avoid detail [V generic].
5. Monochrome first: draw in black/white to force form, spacing, contrast; color only reinforces [V generic] (same sources).
6. Ownability/distinctiveness: one idea, one silhouette recognisable at a glance [U, standard practice at Pentagram/Collins/Koto/Wolff Olins; no primary source fetched].
7. Construction: circles/grids, optical corrections (round shapes overshoot, joins thicken, symmetric marks look off if mathematically exact) [U]. OpenAI's 2025 refresh fixed blossom asymmetry and uneven line weight, enlarged the centre [V] https://www.creativereview.co.uk/openai-brand-refresh/ ; https://www.creativebloq.com/design/openais-bold-new-rebrand-is-surprisingly-human
8. Mark + wordmark: mark used sparingly, wordmark carries more (OpenAI) [V]. Wordmark in a custom/clear typeface (Vercel: Geist) [V].
9. Negative space and one trick, not three [U].
10. Timelessness over trend: avoid gradient blobs, sparkles; gradients only secondary [U].
11. Studios Koto, Collins, Wolff Olins, Sagmeister & Walsh: no primary pages retrieved; their public positions (idea-led, system-led, motion/behaviour of mark) are from general knowledge [U].

## 2. Case studies
- Vercel: solid up-pointing equilateral triangle, in-house, 2020 rebrand from Zeit; rationale is interpretive (stable polygon/"deploy up") [V secondary; origin story conflicted] https://basement.studio/post/scaling-vercel-years-of-building-refining-and-elevating ; https://madegooddesigns.com/vercel-brand-guidelines/ . Pure geometry, monochrome, abstract symbol.
- Anthropic/Claude: USPTO record describes a graphic symbol like an asterisk/star of 6 intersecting lines, "creative spark", first use 2024-03-04 [V] https://trademarkregistration.app/Trademark/Details/98432166 ; critique that it avoids clean AI geometry, warm and hand-feeling [V, blog] https://www.designrush.com/best-designs/logo/claude-logo-design-the-ai-mark-built-to-look-none-of-its-rivals . Abstract radial symbol; warm colour is key to ownability.
- OpenAI: "Blossom" (Ben Barry origin, per coverage) conveying precision/potential/optimism; 2025 refresh kept mark, refined it, added OpenAI Sans [V] links above. Abstract bloom built from interlocked strokes. DIRECT RELEVANCE: "bloom" is OpenAI territory, so DyUI bloom must be geometrically very different.
- Linear: associated with dark UI + gradient glow aesthetic ("Linear style") [V] https://bootcamp.uxdesign.cc/the-rise-of-linear-style-design-origins-trends-and-techniques-4fd96aab7646 ; mark is a simple abstract circular form [U].
- Mistral: orange palette and stripe/pixel-block motif [V weak, design-system file]; the "M" built from squares in a warm gradient stepping [U].
- Figma: "F"-like construction from rounded shapes in multiple colours [V weak]; letter-from-shapes [U detail].
- Notion: warm neutral palette [V weak]; N cube-in-a-box letterform, hand-drawn feel [U].
- Raycast: dark UI with glow [V weak]; mark is a red/rotated square/diamond-ish geometric abstraction [U].
- Stripe (wordmark only, slanted S), Supabase (green bolt-bracket), Framer (stacked angular glyph), Arc, Hugging Face (emoji hugging face, literal mascot), Streamlit (crown/sail stacked), Gradio, LangChain (chain links/parrot-chain), Perplexity (stylised asterisk/compass-like geometry), Cursor (isometric cube/cursor) : no sources fetched [U]; classification: letterform = Figma, Notion, Mistral, Stripe, Framer; abstract geometric = Vercel, Linear, Raycast; metaphor/mascot = Hugging Face, LangChain; radial/spark = Claude, OpenAI, Perplexity.
Takeaway pattern: nearly all strong dev-tool marks are one flat colour shape, constructed from simple geometry, with colour/gradient confined to marketing.

## 3. Craft
- Optical balance over mathematical (overshoot circles ~1-2%, thicken joins, balance visual weight not bounding box) [U; OpenAI fix is a V example].
- One stroke/curve logic: single radius family, single stroke weight or all filled; consistent corner radii.
- Few elements: max 2-3 shapes.
- Test 16px, 32px favicon, 1-colour, reversed, on photo; app-icon squircle with ~15-20% safe padding [U].
- Clear space = height of a key unit (e.g. counter or x); minimum size defined [U].
- Gradient only as secondary treatment; mark must work flat [V generic].
- Lockups: mark+wordmark horizontal, stacked, mark alone.

## 4. DyUI concept directions (coordinate system: 100x100 viewBox, centre 50,50)
Brand fit: "dye blooming in still water", text -> interface, indigo #5B4FE0 + teal #14A394.

C1. "Ink Card" (drop = interface card). A teardrop whose rounded-rect top is a UI card: shape = square 56x56 with corner radius 10 at three corners and a sharp 0-radius corner pointing top-right (or one corner extended to a point forming the drop tip). Negative space: a 3-line "text" cut-out (bars 28/20/12 wide, height 5, radius 2.5) in lower-left. Says: ink drop that lands as a card. Ownable: rounded square with a single point is distinctive. Risk: reads like a map pin / Google "leaf" shape / Android adaptive icons; keep point angle not 90 exactly (try 45-degree rotated asymmetry) .
C2. "Speech Drop". A circle r=34 centred (50,46) with a tail: tangent tail from bottom-left, tail formed by a quarter-circle r=34 sharing the circle's lower-left (i.e. bubble with one square corner, the iMessage/Slack-like "one-corner" bubble), then rotate whole 45 degrees so the sharp corner points up like a drop tip. Reads as drop from one angle, chat bubble from other. Risk: generic chat icons; Teardrop/pin; differentiate with a small concentric offset counter. 
C3. "D-card monogram". Bold geometric D: vertical stem x=26..38, bowl a semicircle r=28 centred (50,50). Counter (negative space) is a rounded rectangle 22x26 radius 5 (a card), not a semicircle, and a thin horizontal bar through it (a header line) at one-third height. Flat, monochrome-first. Says: D that is an interface. Risk: D monograms are common (Dropbox-adjacent, Docker); counter-as-card must be unmistakable; 16px legibility of the bar (make bar >=1/10 height or drop it at small sizes).
C4. "Dy ligature with speech tail". Lowercase serif-ish Instrument Serif-style "y" (or geometric) where the descender curves into a bubble tail pointing down-left; D drawn with a bowl radius 24 and y sharing its stem. Tail = quarter-circle r=18 ending in a point. Pairs naturally with Instrument Serif wordmark. Risk: letterform custom-drawing difficult; at 16px "Dy" is lost: provide a standalone "D" or the tail-only fallback. Must hand-kern.
C5. "Quarter-circle bloom" (petals from quarter-circles). Four quarter-circle petals r=22 placed in a 2x2 grid around centre, each rotated so their curved edge points outward and square corner touches centre, with 4-unit gap (cross of negative space = UI grid/window panes). Alternate colours indigo/teal/teal/indigo (flat) or mono. Reads as flower/bloom and as a 4-pane grid/dashboard. Risk: similar to Windows/Microsoft four-square, pinwheel and "Pinwheel" Google Fonts-style marks; OpenAI blossom adjacency; mitigate with the unequal radii (two petals r=22, two r=14) and rotation of 8 degrees only if optically needed.
C6. "Bloom of rounded rectangles". Central circle r=10 (the drop), surrounded by 3 rounded rectangles of decreasing size (e.g. 44x28 r=8, 30x20 r=6, 18x12 r=4) fanned at 0/120/240 or stacked offset, each at decreasing opacity-free solid tones (indigo -> teal). Expresses ink diffusing into card layouts. Risk: fussy at small sizes and gradients-looking; limit to 3 shapes; strongly dependent on colour for separation, so give it mono variant using outline gaps of 3 units.
C7. "Cut Drop" (text line becoming interface). Solid circle r=36 with a drop-tip (a 90-degree notch at top) and a horizontal chord cut (gap 4) at y=52: above the cut, the cap is a flat card top (rounded rect); below it, half circle. Or: a vertical sequence of a single dot (text caret) -> line -> rounded square forming a drop silhouette: three stacked elements (dot r=5, bar 30x8, rounded square 40x40 radius 12) with negative gaps 5, outline reading as an elongated drop. Says: character -> line -> interface, i.e. morphing. Risk: reads as "stack/layers" icon (Figma/Stack Overflow-like); keep silhouette continuous.
C8. "Caret Bloom" (text cursor). A text-insertion caret (I-beam) whose top serif blooms into a 6-point radial of rounded petals, or simpler: a vertical rounded bar (the caret, 8x44, r=4) with a circle r=16 centred on its upper third, with the circle's lower-right quadrant replaced by a rounded-square corner. Very ownable to "chat input -> interface". Risk: looks like a pin/info "i" icon or a lowercase "i" or a microphone; test.

Recommendation order for exploration (my view, unverified by user testing): C3 + C2 for professional, ownable monochrome; C5 for bloom brand-system potential; C1 for the dye-drop link.

Avoid across all: AI sparkle, generic gradient blob, three concentric rings (rejected), flower with 5-8 radial petals (OpenAI/Claude zone), 4-point star.

## Sources
https://www.creativebloq.com/features/paula-scher-logo-sketches
https://sva.edu/features/svas-paula-scher-discusses-pentagrams-design-process
https://www.designboom.com/design/michael-bierut-interview/
https://www.logodesignlove.com/michael-bierut-talking-logos
https://www.vistaprint.com/hub/principles-of-logo-design
https://cieden.com/book/atoms/logo/principles-of-logo-design
https://www.creativereview.co.uk/openai-brand-refresh/
https://www.creativebloq.com/design/openais-bold-new-rebrand-is-surprisingly-human
https://trademarkregistration.app/Trademark/Details/98432166
https://www.designrush.com/best-designs/logo/claude-logo-design-the-ai-mark-built-to-look-none-of-its-rivals
https://basement.studio/post/scaling-vercel-years-of-building-refining-and-elevating
https://madegooddesigns.com/vercel-brand-guidelines/
https://bootcamp.uxdesign.cc/the-rise-of-linear-style-design-origins-trends-and-techniques-4fd96aab7646

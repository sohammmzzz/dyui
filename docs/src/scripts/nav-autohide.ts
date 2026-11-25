/**
 * Auto-hiding top bar (Starlight's fixed `header.header`).
 *
 *   at the very top of a page (and always on the landing page's first stop)  shown
 *   scrolling down, past the bar's height                                     hides
 *   scrolling up · pointer in the top region · keyboard focus in the bar       shows
 *   shown away from the top and left alone                                    hides again after IDLE_MS
 *
 * Never hides while the bar is in use: pointer over it, focus inside it, or an overlay owning the
 * screen (search, the mobile menu, the assistant). Works with the landing page's magnetic scroller
 * (scripts/magnet-scroll.ts), which moves the page through native scroll positions, so plain
 * `scroll` events see its motion too. Toggles `html.dy-nav-hidden`; styles in styles/theme.css.
 */

const TOP_PX = 8; // "at the very top"
const DELTA_PX = 6; // ignore scroll jitter smaller than this
const REVEAL_ZONE_PX = 72; // pointer this close to the top edge reveals the bar
const IDLE_MS = 2600; // a revealed bar hides again after this much quiet

export function initNavAutohide(): void {
  const header = document.querySelector<HTMLElement>("header.header");
  if (!header) return;
  const root = document.documentElement;
  let lastY = window.scrollY;
  let hidden = false;
  let hover = false;
  let idle = 0;
  let frame = 0;

  const busy = () =>
    hover ||
    header.contains(document.activeElement) ||
    document.body.hasAttribute("data-search-modal-open") ||
    document.body.hasAttribute("data-assist-open") ||
    !!document.querySelector("#starlight__sidebar:popover-open, [data-mobile-menu-expanded]");

  const atTop = () => window.scrollY <= Math.max(TOP_PX, 0);

  function set(hide: boolean) {
    if (hide && (busy() || atTop())) hide = false;
    if (hide === hidden) return;
    hidden = hide;
    root.classList.toggle("dy-nav-hidden", hide);
  }
  function show(thenIdle: boolean) {
    clearTimeout(idle);
    set(false);
    if (thenIdle && !atTop()) idle = window.setTimeout(() => set(true), IDLE_MS);
  }

  function onScroll() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const y = window.scrollY;
      const dy = y - lastY;
      if (atTop()) {
        clearTimeout(idle);
        set(false);
      } else if (dy > DELTA_PX && y > header.offsetHeight) {
        clearTimeout(idle);
        set(true);
      } else if (dy < -DELTA_PX) {
        show(true);
      }
      if (Math.abs(dy) > DELTA_PX || atTop()) lastY = y;
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  // pointer near the top edge (mice / trackpads; touch has no hover)
  window.addEventListener(
    "pointermove",
    (e) => {
      if (e.pointerType === "touch") return;
      if (e.clientY <= REVEAL_ZONE_PX && hidden) show(true);
    },
    { passive: true },
  );
  header.addEventListener("pointerenter", () => {
    hover = true;
    clearTimeout(idle);
    set(false);
  });
  header.addEventListener("pointerleave", () => {
    hover = false;
    if (!atTop()) idle = window.setTimeout(() => set(true), IDLE_MS);
  });
  header.addEventListener("focusin", () => show(false));
  header.addEventListener("focusout", () => {
    if (!atTop()) idle = window.setTimeout(() => set(true), IDLE_MS);
  });
  // in-page anchor jumps land below the bar's slot: keep the bar out of the way afterwards
  window.addEventListener("hashchange", () => onScroll());
}

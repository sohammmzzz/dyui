/**
 * Magnetic scroll for the docs landing page.
 *
 * Every element marked `data-stop` is a "stop" (a slide). Its top edge, measured under the fixed
 * Starlight header, is a magnet; a stop taller than the viewport also gets a magnet at its bottom
 * edge and scrolls freely in between, so nothing is ever trapped.
 *
 *   while input is active  Lenis smooths the wheel and the page moves freely — no walls, no resistance,
 *                          so continuous scrolling flows straight through sections.
 *   when input stops       the rest point is projected (Lenis' target = where its lerp comes to rest) and
 *                          the magnets either side of it compete: the one ahead wins once the page is a
 *                          fair way into the gap (biased towards the direction of travel), and a soft
 *                          damped spring carries the page there from its current velocity.
 *   any new input          cancels the spring at once.
 *
 * Off on phones (coarse pointer, narrow) and with prefers-reduced-motion: native scrolling there.
 */
import Lenis from "lenis";
import "lenis/dist/lenis.css";

const IDLE_MS = 170; // wheel silence that ends a gesture (lets a slow, reading scroll breathe)
const GAP_MS = 220; // a longer silence starts a fresh gesture
const RADIUS = 0.45; // in a free zone (stop taller than the viewport), pull only from this close, in stop heights
const STEP = 1.15; // a neighbouring magnet this close (in stop heights) is "the next slide"
const LEAVE = 0.04; // travel out of a resting stop (in stop heights) that already means "next"…
const LEAVE_PX = 24; // …capped, so the lightest deliberate scroll is enough
const BIAS = 0.3; // past a magnet, how far into the gap (fraction) before the one ahead wins
const OMEGA = 7; // spring natural frequency, rad/s — softer, ~0.8s glide
const ZETA = 0.9; // damping ratio: a barely-there overshoot

type Gesture = { dir: number; start: number; origin: number; last: number; lastAbs: number; peak: number; rising: number };

/** Mass-spring-damper (m = 1), semi-implicit Euler in fixed sub-steps so it is frame-rate independent. */
class Spring {
  x = 0;
  v = 0;
  target = 0;
  active = false;
  start(x: number, v: number, target: number) {
    Object.assign(this, { x, v, target, active: Math.abs(target - x) > 0.5 || Math.abs(v) > 20 });
  }
  /** Advance by dt seconds; returns the new position. */
  step(dt: number): number {
    const k = OMEGA * OMEGA;
    const c = 2 * ZETA * OMEGA;
    for (let left = Math.min(dt, 1 / 20); left > 0; left -= 1 / 240) {
      const h = Math.min(left, 1 / 240);
      this.v += (-k * (this.x - this.target) - c * this.v) * h;
      this.x += this.v * h;
    }
    if (Math.abs(this.x - this.target) < 0.35 && Math.abs(this.v) < 6) {
      this.x = this.target;
      this.active = false;
    }
    return this.x;
  }
}

const editable = (el: EventTarget | null) =>
  el instanceof HTMLElement && !!el.closest("input, textarea, select, button, summary, [contenteditable], [role='button']");

export function initMagnetScroll(root: HTMLElement): () => void {
  const header = document.querySelector<HTMLElement>("header.header");
  const iframeOf = () => root.querySelector<HTMLIFrameElement>(".lp-stage iframe");
  let lenis: Lenis | null = null;
  let magnets: number[] = [];
  let navH = 0;
  let H = 1; // stop height: viewport below the header
  let restIndex = -1; // magnet the page rests on (kept across relayouts)
  let gesture: Gesture | null = null;
  let tail: Gesture | null = null; // the last released gesture, whose inertia may still be arriving
  let idleTimer = 0;
  let settleTimer = 0;
  let touching = false;
  let dragging = false; // scrollbar thumb held
  let suspended = false; // search dialog / mobile menu open
  let lastY = 0;
  let lastT = 0;
  let vel = 0; // px/s, smoothed
  let written = -1; // last position the spring wrote
  let raf = 0;
  const spring = new Spring();
  const off: Array<() => void> = [];
  const on = (t: EventTarget, type: string, fn: (e: any) => void, opts: AddEventListenerOptions = { passive: true }) => {
    t.addEventListener(type, fn, opts);
    off.push(() => t.removeEventListener(type, fn, opts));
  };

  // the spring's own position while it runs, Lenis' while it smooths a wheel, the page's otherwise
  const y = () => (spring.active ? spring.x : lenis?.isScrolling === "smooth" ? lenis.animatedScroll : window.scrollY);
  const limit = () => Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
  const clampY = (v: number) => Math.min(limit(), Math.max(0, v));

  /** Stop tops (and bottom edges of tall stops), sorted, de-duplicated. */
  function measure() {
    const before = restIndex >= 0 && Math.abs(window.scrollY - magnets[restIndex]) < 2 ? restIndex : -1;
    navH = header?.getBoundingClientRect().height ?? 0;
    H = Math.max(1, window.innerHeight - navH);
    const list: number[] = [];
    for (const el of root.querySelectorAll<HTMLElement>("[data-stop]")) {
      const r = el.getBoundingClientRect();
      const top = r.top + window.scrollY - (parseFloat(getComputedStyle(el).marginTop) || 0) - navH;
      list.push(clampY(top));
      if (r.height > H + 2) list.push(clampY(top + r.height - H));
    }
    list.push(0, limit());
    magnets = [...new Set(list.map(Math.round))].sort((a, b) => a - b).filter((m, i, a) => i === 0 || m - a[i - 1] > 4);
    lenis?.resize();
    // stay on the stop we were resting on when the layout moves under us
    if (before >= 0 && !spring.active && !gesture && magnets[before] !== undefined && Math.abs(window.scrollY - magnets[before]) >= 1) {
      lenis?.scrollTo(magnets[before], { immediate: true, force: true });
    }
  }

  const nearest = (p: number, filter: (m: number) => boolean = () => true) => {
    let best: number | null = null;
    for (const m of magnets) if (filter(m) && Math.abs(m - p) <= RADIUS * H && (best === null || Math.abs(m - p) < Math.abs(best - p))) best = m;
    return best;
  };
  /** First magnet strictly beyond `from` in direction `dir`. */
  const beyond = (from: number, dir: number) => (dir > 0 ? magnets.find((m) => m > from + 1) : [...magnets].reverse().find((m) => m < from - 1)) ?? null;
  const isMagnet = (p: number) => magnets.some((m) => Math.abs(m - p) < 2);

  /**
   * Where a directional gesture (wheel, keys) that counts from `origin` and would rest at `p` lands;
   * `travel` is how far the input itself moved the page (origin may be a goal it was already heading to).
   * Decisive: the next slide if it is a slide away, otherwise (free zone) the nearest magnet ahead
   * within the radius, otherwise rest. Tentative: back to the slide it started on, or onward to a
   * magnet ahead within the radius — never pulled back against the user's direction mid-free-zone.
   */
  function pick(origin: number, p: number, dir: number, travel = p - origin): number | null {
    // the magnets either side of the rest point, `back` behind it and `fwd` ahead (in the direction of travel)
    const back = dir > 0 ? [...magnets].reverse().find((m) => m <= p + 1) ?? null : magnets.find((m) => m >= p - 1) ?? null;
    const fwd = beyond(p, dir);
    if (back === null) return fwd;
    if (fwd === null) return back;
    const gap = Math.abs(fwd - back);
    if (gap > STEP * H) return nearest(p); // free zone inside a tall stop: rest unless close to an edge
    // still inside the stop it rested on: the lightest deliberate push already means "next"
    const leaving = Math.abs(back - origin) < 2 && isMagnet(origin);
    const into = Math.abs(p - back);
    if (leaving) return travel * dir >= Math.min(LEAVE * H, LEAVE_PX) ? fwd : back;
    return into >= BIAS * gap ? fwd : back;
  }

  function settleTo(goal: number | null, v = vel) {
    if (goal === null) return;
    const from = y();
    lenis?.scrollTo(from, { immediate: true, force: true }); // stop Lenis' own lerp
    spring.start(from, Math.max(-8000, Math.min(8000, v)), clampY(goal));
    written = from;
    restIndex = magnets.indexOf(Math.round(spring.target));
  }
  const cancel = () => {
    spring.active = false;
    clearTimeout(settleTimer);
  };

  /** Non-directional settle (scrollbar, anchors, focus, touch momentum): iron filings to the nearest magnet. */
  function settleFree() {
    if (touching || dragging || suspended || spring.active || gesture) return;
    settleTo(nearest(y()), 0); // native scrolls carry no usable momentum by the time they go idle
  }
  const scheduleFree = (ms = IDLE_MS + 20) => {
    clearTimeout(settleTimer);
    settleTimer = window.setTimeout(settleFree, ms);
  };

  // ── wheel (via Lenis' virtualScroll hook, which also sees forwarded demo wheels) ──
  function onWheelDelta(data: { deltaX: number; deltaY: number; event: WheelEvent | TouchEvent }): boolean {
    const e = data.event;
    if (!(e instanceof WheelEvent) || e.ctrlKey) return true; // touch stays native; pinch-zoom untouched
    if (Math.abs(data.deltaX) > Math.abs(data.deltaY)) return false; // horizontal: code blocks, marquee
    if (data.deltaY === 0 || suspended) return true;
    const now = e.timeStamp || performance.now();
    const dir = Math.sign(data.deltaY);
    const abs = Math.abs(data.deltaY);
    const g = gesture;
    // the fading inertia of a gesture we already settled is swallowed, not read as a new swipe
    if (!g && tail && dir === tail.dir && now - tail.last < 400 && tail.lastAbs < tail.peak * 0.8 && abs <= tail.lastAbs * 1.1 + 0.5) {
      Object.assign(tail, { last: now, lastAbs: abs });
      if (e.cancelable) e.preventDefault();
      return false;
    }
    tail = null;
    // an inertial tail only decays: deltas growing again after it has faded mean a new swipe
    const rising = g && abs > g.lastAbs * 1.12 + 0.5 ? g.rising + 1 : 0;
    const faded = !!g && g.lastAbs < g.peak * 0.7;
    const fresh = !g || now - g.last > GAP_MS || dir !== g.dir || (faded && (rising >= 2 || abs > g.lastAbs * 1.6 + 6));
    if (fresh) {
      // a gesture in the same direction as a motion already under way continues from where that motion was going
      const goal = spring.active
        ? spring.target
        : g && g.dir === dir
          ? pick(g.origin, lenis!.targetScroll, g.dir, lenis!.targetScroll - g.start)
          : lenis!.isScrolling === "smooth"
            ? lenis!.targetScroll
            : null;
      cancel();
      const here = y();
      lenis!.scrollTo(here, { immediate: true, force: true });
      let origin = here;
      if (goal !== null && (goal - here) * dir > 0) origin = magnets.find((m) => Math.abs(m - goal) < 2) ?? here;
      gesture = { dir, start: here, origin, last: now, lastAbs: abs, peak: abs, rising: 0 };
    } else {
      Object.assign(g!, { last: now, lastAbs: abs, peak: Math.max(g!.peak, abs), rising });
    }
    clearTimeout(idleTimer);
    idleTimer = window.setTimeout(release, IDLE_MS);
    return true; // free movement while scrolling; the magnets act on release
  }
  function release() {
    const g = gesture;
    gesture = null;
    tail = g;
    if (!g || !lenis || spring.active || suspended) return;
    settleTo(pick(g.origin, lenis.targetScroll, g.dir, lenis.targetScroll - g.start));
  }

  // ── keyboard: previous / next stop ──
  function onKey(e: KeyboardEvent) {
    if (suspended || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.("input, textarea, select, [contenteditable], dialog, iframe")) return;
    let dir = 0;
    if (e.key === "PageDown" || e.key === "ArrowDown" || (e.key === " " && !e.shiftKey)) dir = 1;
    else if (e.key === "PageUp" || e.key === "ArrowUp" || (e.key === " " && e.shiftKey)) dir = -1;
    else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      gesture = null;
      cancel();
      return settleTo(e.key === "Home" ? 0 : limit());
    } else return;
    if (e.key === " " && editable(t)) return; // space activates buttons
    e.preventDefault();
    const origin = spring.active ? spring.target : y();
    gesture = null;
    cancel();
    const next = beyond(origin, dir);
    settleTo(next !== null && Math.abs(next - origin) <= STEP * H ? next : clampY(origin + dir * 0.85 * H));
  }

  // ── in-page anchors ──
  function onClick(e: MouseEvent) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as HTMLElement).closest?.("a[href*='#']") as HTMLAnchorElement | null;
    if (!a || a.origin !== location.origin || a.pathname !== location.pathname || !a.hash) return;
    const el = document.getElementById(decodeURIComponent(a.hash.slice(1)));
    if (!el || !root.contains(el)) return;
    e.preventDefault();
    history.pushState(null, "", a.hash);
    settleTo(targetFor(el));
  }
  /** Scroll position that shows `el`: its stop's top when the stop fits, else the element itself. */
  function targetFor(el: Element): number {
    const stop = el.closest<HTMLElement>("[data-stop]");
    const box = (stop ?? el).getBoundingClientRect();
    if (stop && box.height <= H + 2) return clampY(box.top + window.scrollY - (parseFloat(getComputedStyle(stop).marginTop) || 0) - navH);
    return clampY(el.getBoundingClientRect().top + window.scrollY - navH - 24);
  }

  // ── focus moving into an off-screen part of the page ──
  let keyboardNav = false;
  function onFocusIn(e: FocusEvent) {
    if (!keyboardNav || suspended) return;
    const el = e.target as HTMLElement;
    if (!root.contains(el)) return;
    requestAnimationFrame(() => {
      const r = el.getBoundingClientRect();
      const goal = targetFor(el);
      if (r.top < navH || r.bottom > window.innerHeight || Math.abs(y() - goal) > 2) {
        gesture = null;
        cancel();
        settleTo(goal);
      }
    });
  }

  // ── the embedded demo forwards wheels it cannot use ──
  function onMessage(e: MessageEvent) {
    const frame = iframeOf();
    const d = e.data as { source?: string; type?: string; deltaX?: number; deltaY?: number; deltaMode?: number } | null;
    if (!frame || e.source !== frame.contentWindow || !d || d.source !== "dyui-demo") return;
    if (d.type !== "wheel" && d.type !== "touch") return;
    const unit = d.deltaMode === 1 ? 100 / 6 : d.deltaMode === 2 ? H : 1; // lines / pages → px (Lenis' factors)
    const dx = (Number(d.deltaX) || 0) * unit;
    const dy = (Number(d.deltaY) || 0) * unit;
    if (!lenis) return void window.scrollBy({ top: dy, behavior: "instant" as ScrollBehavior });
    // replay it as a wheel on the window: the very same Lenis + magnet pipeline as any other wheel
    window.dispatchEvent(new WheelEvent("wheel", { deltaX: dx, deltaY: dy, deltaMode: 0, cancelable: true }));
  }

  // ── dialogs: Starlight search and the mobile menu own the scroll while open ──
  function syncSuspended() {
    const menu = document.getElementById("starlight__sidebar");
    const open = document.body.hasAttribute("data-search-modal-open") || !!menu?.matches?.(":popover-open");
    if (open === suspended) return;
    suspended = open;
    gesture = null;
    cancel();
    if (open) lenis?.stop();
    else lenis?.start();
  }

  function loop(t: number) {
    raf = requestAnimationFrame(loop);
    lenis?.raf(t);
    const dt = lastT ? Math.min(0.05, (t - lastT) / 1000) : 1 / 60;
    lastT = t;
    if (spring.active && lenis) {
      const max = limit();
      let x = spring.step(dt);
      if (x < 0 || x > max) {
        x = Math.min(max, Math.max(0, x));
        Object.assign(spring, { x, v: 0 });
      }
      lenis.scrollTo(x, { immediate: true, force: true });
      written = x;
    }
    const now = y();
    // a jump of more than half a stop in one frame is a teleport (anchor, restore), not motion
    if (dt > 0) vel = Math.abs(now - lastY) > H / 2 ? 0 : vel * 0.35 + ((now - lastY) / dt) * 0.65;
    lastY = now;
  }

  function start() {
    lenis = new Lenis({
      autoRaf: false,
      lerp: 0.09, // a touch more glide
      smoothWheel: true,
      syncTouch: false, // tablets keep native touch momentum; we settle after it
      virtualScroll: onWheelDelta,
      prevent: (node) => node.nodeName === "DIALOG" || node.id === "starlight__sidebar",
    });
    lastY = y();
    measure();
    restIndex = magnets.findIndex((m) => Math.abs(m - window.scrollY) < 2);
    on(window, "keydown", onKey, { passive: false });
    on(window, "keydown", (e: KeyboardEvent) => (keyboardNav = e.key === "Tab" || keyboardNav));
    on(window, "pointerdown", (e: PointerEvent) => {
      keyboardNav = false;
      if (e.pointerType === "mouse" && e.clientX >= document.documentElement.clientWidth) {
        dragging = true;
        gesture = null;
        cancel();
      }
    });
    const endDrag = () => {
      if (!dragging) return;
      dragging = false;
      scheduleFree(60);
    };
    on(window, "pointerup", endDrag);
    on(window, "mouseup", endDrag);
    on(window, "pointermove", (e: PointerEvent) => e.buttons === 0 && endDrag());
    on(window, "touchstart", () => {
      touching = true;
      gesture = null;
      cancel();
    });
    const endTouch = () => {
      touching = false;
      scheduleFree();
    };
    on(window, "touchend", endTouch);
    on(window, "touchcancel", endTouch);
    on(window, "scroll", () => {
      // someone else moved the page while the spring ran (scrollbar, find-in-page, script): let go
      if (spring.active && Math.abs(window.scrollY - written) > 2) {
        cancel();
        lenis?.scrollTo(window.scrollY, { immediate: true, force: true });
      }
      // our own spring writes and Lenis' wheel smoothing are not "external" scrolls
      if (spring.active || gesture || lenis?.isScrolling === "smooth") return;
      scheduleFree();
    });
    on(document, "click", onClick, { passive: false });
    on(document, "focusin", onFocusIn);
    on(window, "resize", measure);
    const ro = new ResizeObserver(() => measure());
    ro.observe(root);
    for (const el of root.querySelectorAll("[data-stop]")) ro.observe(el);
    off.push(() => ro.disconnect());
    document.fonts?.ready.then(measure);
    const mo = new MutationObserver(syncSuspended);
    mo.observe(document.body, { attributes: true, attributeFilter: ["data-search-modal-open"] });
    off.push(() => mo.disconnect());
    const menu = document.getElementById("starlight__sidebar");
    if (menu) on(menu, "toggle", syncSuspended);
    raf = requestAnimationFrame(loop);
  }

  function stop() {
    cancelAnimationFrame(raf);
    clearTimeout(idleTimer);
    clearTimeout(settleTimer);
    off.splice(0).forEach((f) => f());
    lenis?.destroy();
    lenis = null;
    spring.active = false;
    gesture = null;
  }

  // Phones: native momentum beats any JS spring, and a tall section must never fight a thumb.
  // Reduced motion: native scroll with CSS proximity snapping (html.lp-snap).
  const phone = matchMedia("(pointer: coarse) and (max-width: 700px)");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  window.addEventListener("message", onMessage); // works in both modes
  function apply() {
    const native = phone.matches || reduced.matches;
    document.documentElement.classList.toggle("lp-snap", reduced.matches && !phone.matches);
    document.documentElement.classList.toggle("lp-magnet", !native);
    if (native && lenis) stop();
    if (!native && !lenis) start();
  }
  apply();
  phone.addEventListener("change", apply);
  reduced.addEventListener("change", apply);
  return () => {
    stop();
    window.removeEventListener("message", onMessage);
    phone.removeEventListener("change", apply);
    reduced.removeEventListener("change", apply);
    document.documentElement.classList.remove("lp-snap", "lp-magnet");
  };
}

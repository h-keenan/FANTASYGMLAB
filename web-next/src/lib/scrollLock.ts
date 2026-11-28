// Body scroll lock for pop-ups, safe on iOS Safari. `overflow: hidden` on <body> does not stop iOS from scrolling the page
// behind a sheet (and a page scrolled before opening drifts the layout viewport from the visible one). The reliable
// technique is to pin the body with `position: fixed; top: -scrollY`, then restore the exact scroll position on release.
// Reference counted so nested locks compose; the first lock saves, the last unlock restores.

type Saved = { scrollY: number; style: Record<string, string> };

const PROPS = ["position", "top", "left", "right", "width", "overflow"] as const;
let depth = 0;
let saved: Saved | null = null;

export function lockScroll(doc: Document = document): void {
  depth += 1;
  if (depth > 1) return;
  const win = doc.defaultView;
  const body = doc.body;
  const scrollY = win?.scrollY ?? 0;
  saved = { scrollY, style: {} };
  for (const prop of PROPS) saved.style[prop] = body.style[prop];
  body.style.position = "fixed";
  body.style.top = `-${scrollY}px`;
  body.style.left = "0";
  body.style.right = "0";
  body.style.width = "100%";
  body.style.overflow = "hidden";
  body.setAttribute("data-overlay-open", "");
}

export function unlockScroll(doc: Document = document): void {
  if (depth === 0) return;
  depth -= 1;
  if (depth > 0 || !saved) return;
  const body = doc.body;
  const { scrollY, style } = saved;
  saved = null;
  for (const prop of PROPS) body.style[prop] = style[prop];
  body.removeAttribute("data-overlay-open");
  // Instant, not smooth: a `scroll-behavior: smooth` page would otherwise animate back from the top.
  doc.defaultView?.scrollTo({ top: scrollY, left: 0, behavior: "instant" as ScrollBehavior });
}

/** Test hook: forget all state. */
export function __resetScrollLock(): void {
  depth = 0;
  saved = null;
}

// Twin-free (web only): the on-screen keyboard's height over the layout viewport. iOS Safari does not shrink `dvh` for the
// keyboard, so bottom sheets with a search field used to be covered by it. Pure so it is testable; mounted by OverlayRuntime.

/** Pixels of the layout viewport the virtual keyboard covers (0 when there is none or the page is zoomed). */
export function keyboardInset(innerHeight: number, viewport: { height: number; offsetTop: number; scale: number } | null | undefined): number {
  if (!viewport || viewport.scale > 1.01) return 0; // pinch-zoom also shrinks the visual viewport: not a keyboard
  const covered = innerHeight - viewport.height - viewport.offsetTop;
  return covered > 80 ? Math.round(covered) : 0; // ignore browser-chrome jitter under ~80px
}

/** True when a focused element should be scrolled into view above the keyboard (text inputs inside a pop-up). */
export function shouldScrollIntoView(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName;
  const textual = tag === "TEXTAREA" || (tag === "INPUT" && !["checkbox", "radio", "button", "submit", "range", "color", "file"].includes((el as HTMLInputElement).type));
  return textual && Boolean(el.closest(".ui-sheet, .pqv-modal, .tps-sheet, [role=dialog]"));
}

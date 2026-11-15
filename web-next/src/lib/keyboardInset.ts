// Twin-free (web only): the on-screen keyboard's height over the layout viewport. iOS Safari does not shrink `dvh` for the
// keyboard, so bottom sheets with a search field used to be covered by it. Pure so it is testable; mounted by OverlayRuntime.

/** Pixels of the layout viewport the virtual keyboard covers (0 when there is none or the page is zoomed). */
export function keyboardInset(
  innerHeight: number,
  viewport: { height: number; offsetTop: number; scale: number } | null | undefined,
  /** A text field is focused. No focused field = no keyboard: iOS leaves the visual viewport stale-small after a keyboard (or a toolbar) goes away, which used to
   * shrink every sheet to a cropped sliver (coridian_ 2026-11-14, Fantasy Sim navigator "opens too small"). Defaults to true for the pure maths. */
  fieldFocused = true,
): number {
  if (!fieldFocused) return 0;
  if (!viewport || viewport.scale > 1.01) return 0; // pinch-zoom also shrinks the visual viewport: not a keyboard
  const covered = innerHeight - viewport.height - viewport.offsetTop;
  if (covered <= 80) return 0; // ignore browser-chrome jitter under ~80px
  return Math.round(Math.min(covered, innerHeight * MAX_KEYBOARD_SHARE)); // no keyboard covers more than ~60%: anything bigger is a bad reading, never a reason to crush a sheet
}

/** The largest share of the screen a keyboard is allowed to claim. */
export const MAX_KEYBOARD_SHARE = 0.6;

/** True when the focused element is something that raises the on-screen keyboard. */
export function isEditableFocus(el: Element | null | undefined): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "TEXTAREA") return true;
  if (tag === "INPUT") return !["checkbox", "radio", "button", "submit", "reset", "range", "color", "file", "image"].includes((el as HTMLInputElement).type);
  return (el as HTMLElement).isContentEditable === true;
}

/** True when a focused element should be scrolled into view above the keyboard (text inputs inside a pop-up). */
export function shouldScrollIntoView(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName;
  const textual = tag === "TEXTAREA" || (tag === "INPUT" && !["checkbox", "radio", "button", "submit", "range", "color", "file"].includes((el as HTMLInputElement).type));
  return textual && Boolean(el.closest(".ui-sheet, .pqv-modal, .tps-sheet, [role=dialog]"));
}

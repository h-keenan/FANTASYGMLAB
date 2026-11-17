"use client";

import { useEffect } from "react";

import { nextFooterScroll } from "@/lib/bottomNav";

/**
 * Hide the phone footer while scrolling down, bring it back scrolling up (small threshold, always shown near the top).
 * `pinned` keeps it shown (a selection exists). State only: it writes `data-footer-hidden` on <html> and ui.css decides
 * how that looks (a slide, or just visibility under Reduce Motion), so the dock's measured height (--bottom-clearance)
 * never changes and the page never reflows. The app's footer (the Sim pill) does not hide.
 */
export function useFooterHideOnScroll(pinned: boolean) {
  useEffect(() => {
    const root = document.documentElement;
    if (pinned) {
      delete root.dataset.footerHidden;
      return;
    }
    let st: ReturnType<typeof nextFooterScroll> = { hidden: false, lastY: window.scrollY, anchorY: window.scrollY, dir: 0 };
    let raf = 0;
    const tick = () => {
      raf = 0;
      st = nextFooterScroll(st, Math.max(0, window.scrollY), false);
      if (st.hidden) root.dataset.footerHidden = "";
      else delete root.dataset.footerHidden;
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
      delete root.dataset.footerHidden;
    };
  }, [pinned]);
}

/** Reselecting the lit footer tab: scroll the page back to the top (instant under Reduce Motion). */
export function scrollPageToTop() {
  if (typeof window === "undefined") return;
  const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
}

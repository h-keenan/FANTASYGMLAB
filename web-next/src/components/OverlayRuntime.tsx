"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useSyncExternalStore } from "react";

import { keyboardInset, shouldScrollIntoView } from "@/lib/keyboardInset";
import { installOverlayHistory } from "@/lib/overlayHistory";
import { overlayStack } from "@/lib/overlayStack";

/**
 * Mounted once in the root layout. Owns the three global side effects of the overlay stack so no pop-up has to:
 * body scroll lock (while anything is open), browser-history integration (phone back gesture closes the newest
 * pop-up), and closing every pop-up when the page changes. Renders nothing.
 */
export function OverlayRuntime() {
  const pathname = usePathname();
  const size = useSyncExternalStore(overlayStack.subscribe, () => overlayStack.size(), () => 0);
  const history = useRef<ReturnType<typeof installOverlayHistory> | null>(null);

  useEffect(() => {
    history.current = installOverlayHistory(overlayStack);
    return () => history.current?.dispose();
  }, []);

  // One scroll lock for every pop-up, restored exactly.
  useEffect(() => {
    if (size === 0) return;
    const saved = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.body.setAttribute("data-overlay-open", "");
    return () => {
      document.body.style.overflow = saved;
      document.body.removeAttribute("data-overlay-open");
    };
  }, [size > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  // The on-screen keyboard: publish its height as --kb-inset (sheets lift above it) and scroll a focused text input in a
  // pop-up into view. iOS does not shrink dvh for the keyboard, so without this a search field in a sheet is covered.
  useEffect(() => {
    const vv = window.visualViewport;
    const root = document.documentElement;
    const update = () => root.style.setProperty("--kb-inset", `${keyboardInset(window.innerHeight, vv)}px`);
    update();
    vv?.addEventListener("resize", update);
    vv?.addEventListener("scroll", update);
    const onFocus = (event: FocusEvent) => {
      const el = event.target as Element | null;
      if (shouldScrollIntoView(el)) window.setTimeout(() => (el as HTMLElement).scrollIntoView({ block: "center", behavior: "auto" }), 280);
    };
    document.addEventListener("focusin", onFocus);
    return () => {
      vv?.removeEventListener("resize", update);
      vv?.removeEventListener("scroll", update);
      document.removeEventListener("focusin", onFocus);
      root.style.removeProperty("--kb-inset");
    };
  }, []);

  // A route change closes every pop-up; going back in history would now leave the NEW page, so forget our entries first.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    history.current?.reset();
    overlayStack.closeAll();
  }, [pathname]);

  return null;
}

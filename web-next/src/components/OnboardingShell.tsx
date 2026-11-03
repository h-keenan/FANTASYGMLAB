"use client";

import { createPortal } from "react-dom";
import { useState, useSyncExternalStore, type ReactNode } from "react";

/**
 * Creates the <body>-level portal root while mounted and makes every other
 * <body> child inert + aria-hidden. Null on the server and first render; the
 * root appears once the subscription is live.
 */
export function usePortalRoot(): HTMLElement | null {
  const [store] = useState(() => {
    let root: HTMLElement | null = null;
    const listeners = new Set<() => void>();
    const emit = () => listeners.forEach((l) => l());
    return {
      subscribe(listener: () => void) {
        listeners.add(listener);
        if (listeners.size > 1) return () => void listeners.delete(listener);
        const created = document.createElement("div");
        created.setAttribute("data-onboarding-root", "");
        document.body.appendChild(created);
        const hidden: Array<{ el: Element; inert: boolean; aria: string | null }> = [];
        for (const el of Array.from(document.body.children)) {
          if (el === created) continue;
          hidden.push({ el, inert: el.hasAttribute("inert"), aria: el.getAttribute("aria-hidden") });
          el.setAttribute("inert", "");
          el.setAttribute("aria-hidden", "true");
        }
        root = created;
        emit();
        return () => {
          listeners.delete(listener);
          if (listeners.size > 0) return;
          for (const { el, inert, aria } of hidden) {
            if (!inert) el.removeAttribute("inert");
            if (aria === null) el.removeAttribute("aria-hidden");
            else el.setAttribute("aria-hidden", aria);
          }
          created.remove();
          root = null;
        };
      },
      getSnapshot: () => root,
    };
  });
  return useSyncExternalStore(store.subscribe, store.getSnapshot, () => null);
}

/**
 * The glass onboarding stage: full-viewport, portaled to <body> (so the app
 * Header/search/ACCOUNT chrome and the landing footer are covered and inert),
 * one step at a time, with a scrolling body and a pinned footer for the
 * primary action. Shared by the carousel and the post-carousel steps
 * (connect league, offer) so the whole signed-in setup looks like one flow.
 */
export function OnboardingShell({
  children,
  footer,
  topbar,
}: {
  children: ReactNode;
  footer?: ReactNode;
  topbar?: ReactNode;
}) {
  const portalRoot = usePortalRoot();
  if (!portalRoot) return null;
  return createPortal(
    <div className="onboarding-shell">
      <div className="onboarding-aurora" aria-hidden="true" />
      <div className="onboarding-field" aria-hidden="true" />
      <div className="onboarding-sweep" aria-hidden="true" />
      <div className="onboarding-content">
        {topbar ? <div className="onboarding-topbar">{topbar}</div> : null}
        <div className="onboarding-scroll">{children}</div>
        {footer ? <div className="onboarding-footer onboarding-footer--stack">{footer}</div> : null}
      </div>
    </div>,
    portalRoot,
  );
}

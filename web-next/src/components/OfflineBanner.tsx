"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { BACK_ONLINE_TEXT, OFFLINE_BANNER_TEXT } from "@/lib/badDayCopy";

/**
 * The one offline banner (web). Driven by navigator.onLine and the window online/offline events; mounted once in the root layout. In flow and sticky (opaque) so it never covers the app header.
 * Offline: a persistent notice. Back online: "Back online" for a moment, then gone. It never blocks the page, so cached content stays
 * usable. Mobile twin: components/OfflineBanner.tsx (no NetInfo dependency yet, see lib/connectivity.ts).
 */
function subscribeOnline(notify: () => void): () => void {
  window.addEventListener("offline", notify);
  window.addEventListener("online", notify);
  return () => {
    window.removeEventListener("offline", notify);
    window.removeEventListener("online", notify);
  };
}

export function OfflineBanner() {
  // Server snapshot is "online" so the first client render matches the server HTML.
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
  const [recovered, setRecovered] = useState(false);
  const wasOnline = useRef(online);
  useEffect(() => {
    if (wasOnline.current === online) return undefined;
    wasOnline.current = online;
    if (!online) {
      const clear = setTimeout(() => setRecovered(false), 0);
      return () => clearTimeout(clear);
    }
    const show = setTimeout(() => setRecovered(true), 0);
    const hide = setTimeout(() => setRecovered(false), 3000);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [online]);
  if (online && !recovered) return null;
  return (
    <div
      role="status"
      data-testid="offline-banner"
      data-state={online ? "online" : "offline"}
      className="sticky top-0 z-[60] px-4 py-1.5 text-center text-xs font-semibold"
      style={{
        background: "var(--color-surface-primary)",
        color: online ? "var(--color-success)" : "var(--color-warning)",
        borderBottom: `1px solid ${online ? "var(--color-success)" : "var(--color-warning)"}`,
      }}
    >
      {online ? BACK_ONLINE_TEXT : OFFLINE_BANNER_TEXT}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

// One /v1/me read per signed-in user for the whole tab: the nav (orb and
// sidebar) and anything else that only needs "is this person on Pro?" share
// it instead of each fetching on mount.
let cache: { userId: string; promise: Promise<boolean | null> } | null = null;

function loadIsPro(userId: string): Promise<boolean | null> {
  if (cache?.userId !== userId) {
    const promise = api
      .getMe()
      .then((me) => (me.user.profile_status === "ok" ? me.user.entitlement === "premium" : null))
      .catch(() => {
        // Do not pin a failed read for the rest of the tab.
        if (cache?.promise === promise) cache = null;
        return null;
      });
    cache = { userId, promise };
  }
  return cache.promise;
}

/** `true` / `false` once known; `null` while loading, signed out, or when the
 * plan could not be read (callers then show no Pro/Free marker at all rather
 * than a wrong one). */
export function useIsPro(): boolean | null {
  const { session } = useAuth();
  const userId = session?.user?.id ?? null;
  const [state, setState] = useState<{ userId: string; isPro: boolean | null } | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void loadIsPro(userId).then((isPro) => {
      if (!cancelled) setState({ userId, isPro });
    });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  return userId && state?.userId === userId ? state.isPro : null;
}

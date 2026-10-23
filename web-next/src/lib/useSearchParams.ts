"use client";

import { useSearchParams as useNextSearchParams } from "next/navigation";
import { useMemo } from "react";

import { isPrivacyMode, maskLeagueNameIfPrivate } from "@/lib/privacy";

/**
 * Drop-in replacement for next/navigation's useSearchParams. In privacy mode
 * the `?name=` league-name param is shown as the masked league label (display
 * only: the real URL and league id are untouched). Every page/component that
 * reads `?name=` imports this instead of next/navigation's hook.
 */
export function useSearchParams(): ReturnType<typeof useNextSearchParams> {
  const params = useNextSearchParams();
  const raw = params?.get("name") ?? null;
  const on = isPrivacyMode();
  return useMemo(() => {
    if (!params || !on || !raw) return params;
    const copy = new URLSearchParams(params.toString());
    copy.set("name", String(maskLeagueNameIfPrivate(raw)));
    return copy as unknown as ReturnType<typeof useNextSearchParams>;
  }, [params, on, raw]);
}

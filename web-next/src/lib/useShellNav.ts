"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "@/context/AuthContext";
import { isFounderSession } from "@/lib/navDestinations";
import { SHELL_NAV_STORAGE_KEY, shellBarVisible, shellNavEnabled, shellNavQueryToStore } from "@/lib/shellNav";

function readFlag(isFounder: boolean): boolean {
  let queryNav: string | null = null;
  let stored: string | null = null;
  try {
    queryNav = new URLSearchParams(window.location.search).get("nav");
    const remember = shellNavQueryToStore(queryNav);
    if (remember) window.localStorage.setItem(SHELL_NAV_STORAGE_KEY, remember);
    stored = window.localStorage.getItem(SHELL_NAV_STORAGE_KEY);
  } catch {
    /* storage can throw (private mode); fall back to the env default */
  }
  return shellNavEnabled({ env: process.env.NEXT_PUBLIC_BOTTOM_NAV, queryNav, stored, isFounder });
}

/**
 * The phone shell's flag and visibility, read once the client mounts (so
 * prerendered pages never need a Suspense boundary for ?nav=). `barVisible`
 * is what Header, GmOrb and AppContentShell key off: when true the bottom
 * bar + standard header replace the floating orb on phones. Off switch:
 * NEXT_PUBLIC_BOTTOM_NAV=off, or ?nav=off (remembered).
 */
export function useShellNav(): { enabled: boolean; barVisible: boolean } {
  const { session } = useAuth();
  const pathname = usePathname();
  const founder = isFounderSession(session);
  const [enabled, setEnabled] = useState(false);
  const signedIn = Boolean(session);
  useEffect(() => {
    // Wait for the session: flipping earlier adds a render pass before the lazily hydrated boundaries
    // (sidebar, orb) finish hydrating, which made them mismatch. Reads window.location + localStorage, which only exist on the client.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (signedIn) setEnabled(readFlag(founder));
  }, [signedIn, founder, pathname]);
  return { enabled, barVisible: shellBarVisible({ enabled, signedIn: Boolean(session), pathname }) };
}

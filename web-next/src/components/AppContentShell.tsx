"use client";

import type { ReactNode } from "react";

import { useAuth } from "@/context/AuthContext";

/**
 * coridian_, 2026-10-19, screenshot: "still weird clipping and scaling on
 * the desktop welcome page" — the signed-out landing page rendered with a
 * large empty gap on the left instead of being centered.
 *
 * Root cause: layout.tsx's content wrapper applied `md:pl-60` (the space
 * reserved for DesktopSidebar) unconditionally on every page, but
 * DesktopSidebar itself already returns null for a signed-out visitor
 * (`if (!session) return null`, see that component). The padding and the
 * sidebar's own visibility were two independent checks that could drift —
 * exactly the "two sources of truth" bug class this fixes by reading the
 * same `session` check once, here, so the content can never be padded for
 * a sidebar that isn't actually there.
 */
export function AppContentShell({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return <div className={`flex flex-col flex-1 ${session ? "md:pl-60" : ""}`}>{children}</div>;
}

"use client";

import Link from "next/link";

import { useAuth } from "@/context/AuthContext";
import { freeLimitNote, type FreeLimitInput } from "@/lib/freeLimits";

/**
 * One small line, before a Free account hits a wall: "Free: 2 of 3 GM
 * Targets" plus the one upgrade path. Guests may not buy, so for them the
 * link reads "Create an account" (both go to /premium, which shows guests the
 * account step first). Renders nothing for Premium, an unknown plan or when
 * the server sent no limit. Mirrors mobile's FreeLimitNote.
 */
export function FreeLimitNote(props: Omit<FreeLimitInput, "isGuest">) {
  // Always inside AuthProvider in the app; tolerate its absence (isolated
  // component renders) by treating the viewer as a non-guest.
  let isGuest = false;
  try {
    // useAuth only reads context (same hook order whether or not it throws).
    // eslint-disable-next-line react-hooks/rules-of-hooks
    isGuest = useAuth().isGuest;
  } catch {
    isGuest = false;
  }
  const note = freeLimitNote({ ...props, isGuest });
  if (!note) return null;
  return (
    <p
      className="m-0 flex flex-wrap items-center gap-x-2 text-xs"
      style={{ color: "var(--color-text-muted)" }}
      data-free-limit-note="true"
    >
      <span>{note.text}</span>
      <Link href="/premium" className="tap-link font-bold" style={{ color: "var(--color-premium)" }}>
        {note.ctaLabel} →
      </Link>
    </p>
  );
}

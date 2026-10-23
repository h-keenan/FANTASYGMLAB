"use client";

import { useSyncExternalStore } from "react";

import { isPrivacyMode, setPrivacyMode, subscribePrivacyMode } from "@/lib/privacy";
import { Toggle } from "@/components/Toggle";

export function usePrivacyMode(): boolean {
  return useSyncExternalStore(subscribePrivacyMode, isPrivacyMode, () => false);
}

/**
 * Flip privacy mode and reload, so every screen refetches through the masking
 * layer (or back to real data) instead of leaving stale values on screen.
 */
export function changePrivacyMode(on: boolean): void {
  setPrivacyMode(on);
  if (typeof window !== "undefined") window.location.reload();
}

/** Small fixed pill shown on every page while privacy mode is on; tap to turn off. */
export function PrivacyPill() {
  const on = usePrivacyMode();
  if (!on) return null;
  return (
    <button
      type="button"
      onClick={() => changePrivacyMode(false)}
      aria-label="Privacy mode on. Tap to turn off"
      className="fixed text-xs font-bold px-3 py-1"
      style={{
        left: "50%",
        transform: "translateX(-50%)",
        bottom: "calc(env(safe-area-inset-bottom, 0px) + 8px)",
        zIndex: 9999,
        borderRadius: "var(--radius-pill)",
        background: "var(--color-accent-soft)",
        border: "var(--border-width-default) solid var(--color-accent)",
        color: "var(--color-accent)",
        opacity: 0.9,
      }}
    >
      Privacy mode on
    </button>
  );
}

/** Founder-only switch (rendered inside the founder analytics page). */
export function PrivacyModeToggle() {
  const on = usePrivacyMode();
  return (
    <div className="glass-surface flex items-center justify-between gap-3 p-4">
      <div className="flex flex-col gap-1">
        <span className="text-sm font-bold">Privacy mode</span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Hides manager, team and league names, avatars and email for screenshots. Display only.
        </span>
      </div>
      <Toggle label="Privacy mode" checked={on} onChange={changePrivacyMode} stateLabel={on ? "On" : "Off"} />
    </div>
  );
}

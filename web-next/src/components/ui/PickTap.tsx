"use client";

import { useContext, type ReactNode } from "react";

import { PickOpenContext, TapScopeContext } from "@/components/ui/PlayerOpenContext";

/**
 * THE pick tap target (pick twin of PlayerTap): opens the pick detail (the sim pick sheet via PickOpenContext, or an
 * explicit `onOpen`). Plain markup when nothing can open it or the caller opted out with a reason.
 */
export function PickTap({ id, label, detail, onOpen, nonInteractive, children }: { id?: string; label: string; detail?: string | null; onOpen?: () => void; nonInteractive?: string; children: ReactNode }) {
  const open = useContext(PickOpenContext);
  const inScope = useContext(TapScopeContext);
  if (inScope || nonInteractive || (!onOpen && !(open && id))) return <>{children}</>;
  return (
    <button
      type="button"
      aria-label={`Open ${label}`}
      data-pick-tap="true"
      className="block w-full min-w-0 text-left"
      style={{ background: "none", border: 0, padding: 0, minHeight: "var(--touch-target-min)" }}
      onClick={(event) => {
        event.stopPropagation();
        if (onOpen) onOpen();
        else if (open && id) open({ id, label, detail });
      }}
    >
      <TapScopeContext.Provider value>{children}</TapScopeContext.Provider>
    </button>
  );
}

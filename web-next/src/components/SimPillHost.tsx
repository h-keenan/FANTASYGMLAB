"use client";

import { useEffect } from "react";

import { PillContextOnly } from "@/components/ui/PillMorph";
import { setPillBarPresent } from "@/lib/bottomPillStore";
import { usePillState } from "@/lib/useBottomPillContext";

/**
 * Fantasy Sim's end of the smart pill. Marks the pill as on screen while the game is open on a phone (so pages such as the
 * draft room drop their own tab row), and when no action bar is mounted (draft) renders the page segment alone as an
 * `.action-pill`. With an Advance / offseason bar mounted that bar hosts the segment itself (PillMorph).
 */
export function SimPillHost({ standalone }: { standalone: boolean }) {
  const pill = usePillState();
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return; // no media queries (tests, very old browsers): the in-page tabs stay
    const mq = window.matchMedia("(max-width: 767px)");
    const sync = () => setPillBarPresent(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => {
      mq.removeEventListener("change", sync);
      setPillBarPresent(false);
    };
  }, []);
  if (!standalone || !pill.barPresent || !pill.ctx) return null;
  return (
    <div className="action-pill md:hidden p-1" data-testid="sim-pill-only">
      <PillContextOnly context={pill.ctx} />
    </div>
  );
}

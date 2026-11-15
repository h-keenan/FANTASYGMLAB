"use client";

import type { ReactNode } from "react";

import { PillContextLayer, usePillContextLayer } from "@/components/ui/BottomTabBar";
import type { PillContext } from "@/lib/bottomNav";

import "./ui.css";

/**
 * The smart pill of the Fantasy Sim bar (the site shell's version is BottomTabBar). ONE persistent orb leads the row (the
 * only navigation control: it opens the game's page menu; nothing else folds or unfolds), then one cell holds either the
 * bar's action row (`children`: [Sim to | page action] + Advance) or, when a page with tabs registers a `segment`
 * (the draft room), the page tabs + one primary. The layers cross-fade and slide (shared Presence, lib/presence.ts).
 * What shows when is decided by `simPillPlan` (lib/bottomNav.ts, rules table in docs/ui-patterns.md), never per page.
 * Without a segment on desktop it renders `children` untouched (`display: contents`). Mobile twin:
 * mobile/src/components/BottomPill.tsx.
 */
export function PillMorph({ segment, orb, children }: { segment?: PillContext | null; orb?: ReactNode; children: ReactNode }) {
  const live = Boolean(segment && segment.tabs.length + (segment.primary ? 1 : 0) > 0);
  const layer = usePillContextLayer(segment);
  const mode = live ? "context" : "global";
  return (
    <div className="pill-morph" data-mode={mode} data-has-context={live ? "" : undefined} data-testid="pill-morph">
      {orb}
      <div className="pill-cells">
        <div className="pill-layer pill-layer--global" inert={mode === "context"}>
          {children}
        </div>
        {layer ? <PillContextLayer key={layer.context.id} context={layer.context} leaving={layer.leaving} hidden={false} /> : null}
      </div>
    </div>
  );
}

/** The orb plus the page segment, with no action row (the Fantasy Sim draft room, where no action bar is mounted). */
export function PillContextOnly({ context, orb }: { context: PillContext | null; orb?: ReactNode }) {
  const layer = usePillContextLayer(context);
  return (
    <div className="pill-morph" data-mode="context" data-has-context="" data-testid="pill-context-only">
      {orb}
      <div className="pill-cells">{layer ? <PillContextLayer key={layer.context.id} context={layer.context} leaving={layer.leaving} hidden={false} /> : null}</div>
    </div>
  );
}

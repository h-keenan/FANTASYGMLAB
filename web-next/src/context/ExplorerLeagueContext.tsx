"use client";

import { createContext, useContext, type ReactNode } from "react";

/**
 * The league whose roster the Percentile Explorer should mark ("MY ROSTER").
 * Provided around the stat tiles on the player profile and quick view so the
 * sheet gets it without threading a prop through every stat-row component.
 * Null means no league context: the explorer then shows no roster marks.
 */
const ExplorerLeagueContext = createContext<string | null>(null);

export function ExplorerLeagueProvider({ leagueId, children }: { leagueId: string | null | undefined; children: ReactNode }) {
  return <ExplorerLeagueContext.Provider value={leagueId || null}>{children}</ExplorerLeagueContext.Provider>;
}

export function useExplorerLeague(): string | null {
  return useContext(ExplorerLeagueContext);
}

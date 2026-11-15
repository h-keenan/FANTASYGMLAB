"use client";

import type { ReactNode } from "react";

import { useExperienceCopy } from "@/context/ExperienceLevelContext";

/**
 * The page's one "?" explainer body (UI pass 5 D3, coridian_ 2026-11-14): pages hand their beginner lines to `PageTitle info`, which shows
 * them behind the "?" in the header. Replaces the labelled inline `BeginnerHelp` rows ("? My Team and value tiers", "? this matchup page",
 * "? playoff odds", "? waiver value") that sat as orphan lines above the first module. Returns undefined (no "?" at all) when the account
 * does not show help or there is nothing to say. Mobile twin: header `ScreenInfoNote`.
 */
export function usePageHelp(lines: Array<string | null | undefined>): ReactNode | undefined {
  const copy = useExperienceCopy();
  if (!copy.showsHelp) return undefined;
  const shown = lines.filter((line): line is string => Boolean(line));
  if (shown.length === 0) return undefined;
  return (
    <div className="flex flex-col gap-1">
      {shown.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

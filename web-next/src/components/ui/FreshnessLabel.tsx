"use client";

import { useState } from "react";

import { freshnessLabel, leagueStaleLabel, type FreshnessDataset, type FreshnessReport } from "@/lib/dataFreshness";
import { useDataFreshness } from "@/lib/useDataFreshness";

/**
 * THE "as of" line for data that can be stale (data-truth audit 2026-11-19, finding 4): "Values as of 2h ago",
 * "Injuries updated 9:40am". Every surface uses this one component with the datasets it shows; wording, thresholds and the
 * honesty rules (no timestamp means no label) live in lib/dataFreshness.ts. Muted text, never an error colour. Renders
 * nothing until the public report loads or when it cannot say. Pass `report` to skip the fetch (tests, server data).
 * Mobile twin: mobile/src/components/FreshnessLabel.tsx.
 */
export function FreshnessLabel({
  datasets,
  report,
  now,
  leagueAsOf,
  className = "",
}: {
  datasets: readonly FreshnessDataset[];
  report?: FreshnessReport | null;
  now?: number;
  /** The league response's `sleeper_data_as_of`: set only when the API served last-known provider data. */
  leagueAsOf?: string | null;
  className?: string;
}) {
  const fetched = useDataFreshness(report === undefined && datasets.length > 0);
  const source = report === undefined ? fetched : report;
  const [mountedAt] = useState(() => Date.now());
  const at = now ?? mountedAt;
  const labels = datasets.map((dataset) => freshnessLabel(source, dataset, at)).filter((text): text is string => Boolean(text));
  const stale = leagueStaleLabel(leagueAsOf, at);
  if (stale) labels.push(stale);
  if (labels.length === 0) return null;
  return (
    <span className={className} data-testid="freshness-label">
      {labels.join(" · ")}
    </span>
  );
}

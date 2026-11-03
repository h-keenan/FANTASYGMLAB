"use client";

import { StatRowsCard } from "@/components/StatRows";
import type { QuickViewStats, UsageProfile } from "@/lib/api";
import { seasonStatGroups } from "@/lib/playerQuickViewPresentation";
import { poolCaption, statItemRows, usageCardCoversLegacyTiles } from "@/lib/statRowsPresentation";

/** Season stats as percentile-row cards (Production / Fantasy / Efficiency),
 * shared by Player Quick View and the full profile. The legacy season "Usage"
 * tiles are dropped when the unified Usage card is shown (they were the same
 * numbers from a different, mostly empty source). */
export function SeasonStatsRows({
  stats,
  usageProfile,
  playerId,
  headlineLabels = ["PPR PPG"],
}: {
  stats: QuickViewStats | null;
  usageProfile: UsageProfile | null | undefined;
  playerId: string;
  /** Stats already shown as headline tiles are not repeated as rows. */
  headlineLabels?: string[];
}) {
  if (!stats) return null;
  const hideLegacyUsage = usageCardCoversLegacyTiles(usageProfile);
  return (
    <>
      {stats.seasons.map((season) => (
        <div key={season.label} className="sr-season">
          <p className="sr-season-title">
            {season.label}
            {season.games != null ? ` · ${season.games} games` : ""}
          </p>
          {seasonStatGroups(season)
            .filter((group) => !(hideLegacyUsage && group.title === "Usage"))
            .map((group) => (
              <StatRowsCard
                key={group.title}
                title={group.title}
                caption={poolCaption(stats.position, season.season) ? `Percentile ${poolCaption(stats.position, season.season)}` : null}
                rows={statItemRows(group.items, stats.position, season.season).filter((row) => !headlineLabels.includes(row.label))}
                collapseAfter={3}
                playerId={playerId}
              />
            ))}
        </div>
      ))}
    </>
  );
}

"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { NavProMarker } from "@/components/NavProMarker";
import { SectionHeading } from "@/components/SectionHeading";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { api, type TeamSnapshot } from "@/lib/api";
import { formatRank } from "@/lib/leagueRankingsPresentation";
import { PORTFOLIO_FREE_HEADING, PORTFOLIO_LOCKED_HEADING, PORTFOLIO_LOCKED_ROWS, portfolioRecordText } from "@/lib/portfolioFree";
import { TERMS } from "@/lib/terms";
import { useSavedLeagues } from "@/lib/useSavedLeagues";

/**
 * Portfolio's Free state: the first (only) saved league's real standing from the same Today snapshot, then the Pro part
 * locked and named. Renders nothing until the standing loads (or when there is no league): the upsell card below it is
 * always the fallback, so a failure here never blanks the page.
 */
export function PortfolioFreeStanding() {
  const { rows } = useSavedLeagues(true);
  const first = rows[0] ?? null;
  const [snapshot, setSnapshot] = useState<TeamSnapshot | null>(null);
  useEffect(() => {
    if (!first) return;
    let cancelled = false;
    api
      .getDashboard(first.league_id)
      .then((res) => {
        if (!cancelled) setSnapshot(res.team_snapshot);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [first]);
  if (!first || !snapshot) return null;
  const items: StatStripItem[] = [
    { glyph: "record", label: "Record", value: portfolioRecordText(snapshot) },
    { glyph: "power", label: TERMS.thisSeason, value: formatRank(snapshot.power_rank, snapshot.power_rank_tied) },
    { glyph: "franchise", label: TERMS.longTerm, value: formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied) },
  ];
  return (
    <AccentCard accent="var(--color-accent)" as="section" data-testid="portfolio-free-standing">
      <SectionHeading note={first.league_name ?? undefined}>{PORTFOLIO_FREE_HEADING}</SectionHeading>
      <StatStrip items={items} columns={3} />
      <div className="flex flex-col gap-1" data-testid="portfolio-locked-rows">
        <span className="flex items-center gap-2 text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {PORTFOLIO_LOCKED_HEADING}
          <NavProMarker />
        </span>
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {PORTFOLIO_LOCKED_ROWS.map((row) => (
            <li key={row} className="flex items-center gap-2" style={{ minHeight: "var(--touch-target-min)" }}>
              <span aria-hidden="true">&#128274;</span>
              {row}
            </li>
          ))}
        </ul>
      </div>
    </AccentCard>
  );
}

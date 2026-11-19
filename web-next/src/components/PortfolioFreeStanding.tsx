"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { NavProMarker } from "@/components/NavProMarker";
import { SampleLeagueLink } from "@/components/SampleLeagueBanner";
import { SectionHeading } from "@/components/SectionHeading";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { api, type TeamSnapshot } from "@/lib/api";
import { formatRank } from "@/lib/leagueRankingsPresentation";
import { PORTFOLIO_FREE_HEADING, PORTFOLIO_LOCKED_HEADING, PORTFOLIO_LOCKED_ROWS, portfolioRecordText } from "@/lib/portfolioFree";
import { TERMS } from "@/lib/terms";
import { useSavedLeagues } from "@/lib/useSavedLeagues";

/**
 * Portfolio's Free state: the first (only) saved league's real standing from the same Today snapshot, then the Pro part
 * locked and named. Renders nothing until the standing loads (the upsell card below is always the fallback); a failed load
 * shows a compact retry row instead of silently vanishing. A brand-new account with no saved league gets the connect / sample-league next step
 * (first-time-user audit 2026-11-17: it used to see only the Pro upsell and no way forward).
 */
export function PortfolioFreeStanding() {
  const { rows, status } = useSavedLeagues(true);
  const first = rows[0] ?? null;
  const [snapshot, setSnapshot] = useState<TeamSnapshot | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!first) return;
    let cancelled = false;
    setFailed(false);
    api
      .getDashboard(first.league_id)
      .then((res) => {
        if (!cancelled) setSnapshot(res.team_snapshot);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [first, attempt]);
  if (status === "ready" && !first) {
    return (
      <EmptyState title="No saved league yet" subtitle="Connect a league to see your record and rank here, or look around a sample league first.">
        <div className="mt-2 flex flex-col items-start gap-1">
          <ButtonLink href="/connect-league" size="sm">
            Connect a league
          </ButtonLink>
          <SampleLeagueLink />
        </div>
      </EmptyState>
    );
  }
  if (first && failed && !snapshot) return <ErrorState compact onRetry={() => setAttempt((n) => n + 1)} message="Could not load your standing" />;
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

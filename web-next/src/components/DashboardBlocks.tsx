"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

import type { BriefingItem, LeagueTeamRankingsResponse } from "@/lib/api";
import { ExpandRow } from "@/components/ui/ExpandRow";
import { AccentCard } from "@/components/AccentCard";
import { ToneBadge } from "@/components/ToneBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { CompactModule } from "@/components/ui/CompactModule";
import type { DashboardAttentionEntry } from "@/lib/dashboardLayout";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref, resolveGamePlanTargetPlayerId } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";

// Below-the-fold modules load as their own chunks, after the above-the-fold content has hydrated.
const GuessThePlayerCard = dynamic(() => import("@/components/GuessThePlayerCard").then((m) => m.GuessThePlayerCard), { loading: () => null });
const GuessThePlayerNameMatchCard = dynamic(() => import("@/components/GuessThePlayerNameMatchCard").then((m) => m.GuessThePlayerNameMatchCard), { loading: () => null });
const LeaguePulseCard = dynamic(() => import("@/components/LeaguePulseCard").then((m) => m.LeaguePulseCard), { loading: () => null });

/**
 * "Needs attention": a compact list of the few urgent items, each one line with
 * one link to where it is handled. Urgency is read only from existing fields
 * (lib/dashboardLayout.ts buildNeedsAttention); the full plan stays on GM Plan.
 * Renders nothing when nothing is urgent.
 */
/** Where a "Needs attention" entry opens (shared by the card and the status header's player rows). */
export function attentionEntryHref(entry: DashboardAttentionEntry<BriefingItem>, leagueId: string, leagueName: string): string {
  const id = encodeURIComponent(leagueId);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  if (entry.target === "matchup") return thisWeekHref("matchup", leagueId, leagueName);
  if (entry.target === "gm_plan" || !entry.item) return `/gm-plan/${id}${query}`;
  const route = GAME_PLAN_INTERNAL_ROUTES[entry.item.destination] ?? "gm-plan";
  return gamePlanTileHref(route, leagueId, leagueName, resolveGamePlanTargetPlayerId(entry.item));
}

export function DashboardNeedsAttention({
  entries,
  leagueId,
  leagueName,
}: {
  entries: DashboardAttentionEntry<BriefingItem>[];
  leagueId: string;
  leagueName: string;
}) {
  if (entries.length === 0) return null;
  const hrefFor = (entry: DashboardAttentionEntry<BriefingItem>): string => attentionEntryHref(entry, leagueId, leagueName);
  return (
    <section className="flex flex-col gap-3" aria-labelledby="needs-attention-heading" data-testid="dashboard-needs-attention">
      <SectionHeading id="needs-attention-heading">
        Needs attention
      </SectionHeading>
      <AccentCard accent="var(--color-danger)" compact>
        <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {entries.map((entry, index) => (
            <li key={`${entry.source}-${index}`} style={index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined}>
              <Link
                href={hrefFor(entry)}
                className="flex items-center gap-2 py-2.5"
                style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}
              >
                <span className="min-w-0 flex-1 flex flex-col items-start gap-1">
                  <ToneBadge label={entry.badge} color="var(--color-danger)" />
                  <span className="text-sm font-bold break-words">{entry.headline}</span>
                  <span
                    className="text-xs"
                    style={{
                      color: "var(--color-text-secondary)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical" as const,
                      overflow: "hidden",
                    }}
                  >
                    {entry.why}
                  </span>
                </span>
                <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </AccentCard>
    </section>
  );
}

/** Secondary modules (league activity, the mini-games, league type), one compact module, mounted only when opened. */
/**
 * "More" on Today, collapsed: league activity and the two mini-games, ONE line each (they are play, not decisions). A
 * line opens its full card. Below-the-fold, so each card loads as its own chunk. (The League type control lives on My Team's
 * league settings.) Mobile twin: components/DashboardBlocks.tsx.
 */
export function DashboardMore({ leagueId, leagueName, teamRankings }: { leagueId: string; leagueName: string; teamRankings?: Promise<LeagueTeamRankingsResponse> }) {
  return (
    <CompactModule
      id="today.more"
      title="More"
      testId="dashboard-more"
      tone="muted"
      parts={[
        { key: "a", text: "League activity" },
        { key: "g", text: "2 mini-games" },
      ]}
    >
      <ul className="m-0 flex list-none flex-col p-0 [&>li+li]:border-t [&>li+li]:border-[var(--color-border)]">
        <ExpandRow label="League activity" title="League activity" caption="Most active manager, streaks" testId="more-league-activity">
          <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} teamRankings={teamRankings} />
        </ExpandRow>
        <ExpandRow label="Guess the Player" title="Guess the Player" caption="Today's round" testId="more-guess-player">
          <GuessThePlayerCard leagueId={leagueId} leagueName={leagueName} />
        </ExpandRow>
        <ExpandRow label="Name match" title="Name match" caption="Match names to faces" testId="more-name-match">
          <GuessThePlayerNameMatchCard leagueId={leagueId} leagueName={leagueName} />
        </ExpandRow>
      </ul>
    </CompactModule>
  );
}

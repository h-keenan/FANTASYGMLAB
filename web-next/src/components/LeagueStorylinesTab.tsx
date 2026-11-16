"use client";


import { useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import type {
  HistoryAsset,
  StorylineLeader,
  StorylineTeam,
  StorylinesResponse,
} from "@/lib/api";





import { TeamAvatar } from "@/components/TeamAvatar";
import { AccentCard } from "@/components/AccentCard";
import {
  FILTER_TRADES,
  FILTER_WIRE,
  } from "@/lib/leagueRecapsPresentation";



import { ErrorState } from "@/components/ErrorState";
import { Money } from "@/components/Money";
import { formatMoney } from "@/lib/money";
import { AssetChip } from "@/components/LeagueHistoryTab";
import { SkeletonRegion, SkeletonModule } from "@/components/Skeleton";

function breakdownNote(breakdown: StorylineLeader["breakdown"]): string {
  if (!breakdown) return "";
  const bits: string[] = [];
  if (breakdown.trade) bits.push(`${breakdown.trade} trade${breakdown.trade !== 1 ? "s" : ""}`);
  if (breakdown.waiver) bits.push(`${breakdown.waiver} waiver${breakdown.waiver !== 1 ? "s" : ""}`);
  if (breakdown.free_agent) bits.push(`${breakdown.free_agent} FA add${breakdown.free_agent !== 1 ? "s" : ""}`);
  return bits.join(" · ");
}

function StorylineTeamLine({ team }: { team: StorylineTeam }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <TeamAvatar avatarUrl={team.avatar_url} size={28} />
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
          {team.team_name}
        </span>
        {team.owner_handle ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {team.owner_handle}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function StorylineCard({
  kicker,
  question,
  children,
  wide,
  route,
  onOpenHistory,
}: {
  kicker: string;
  question: string;
  children: ReactNode;
  wide?: boolean;
  route?: string;
  onOpenHistory?: (filter: string) => void;
}) {
  const style = { gridColumn: wide ? "1 / -1" : undefined };
  const body = (
    <>
      <span
        className="text-xs uppercase font-extrabold"
        style={{ color: "var(--color-information)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {kicker}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {question}
      </span>
      {children}
    </>
  );
  if (route && onOpenHistory) {
    return (
      <AccentCard accent="var(--color-information)" compact as="div" style={style}>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onOpenHistory(route)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") onOpenHistory(route);
          }}
          className="cursor-pointer grid gap-1"
        >
          {body}
        </div>
      </AccentCard>
    );
  }
  return (
    <AccentCard accent="var(--color-information)" compact style={style}>
      <div className="grid gap-1">{body}</div>
    </AccentCard>
  );
}

export function StorylinesTab({
  leagueId,
  data,
  setData,
  onOpenHistory,
}: {
  leagueId: string;
  data: StorylinesResponse | null;
  setData: (next: StorylinesResponse) => void;
  onOpenHistory: (filter: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (data) return;
    let cancelled = false;
    api
      .getLeagueStorylines(leagueId)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load league storylines.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId, data, retryToken]);

  if (!data && !error) {
    return (
      <SkeletonRegion label="league storylines" className="flex flex-col gap-3"><SkeletonModule /><SkeletonModule /></SkeletonRegion>
    );
  }
  if (error) {
    return (
      <ErrorState bare message={error} onRetry={() => { setError(null); setRetryToken((n) => n + 1); }} />
    );
  }
  if (!data) return null;

  const report = data.storylines;
  if (!report) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Storylines need a loaded league.
      </p>
    );
  }

  const cards: ReactNode[] = [];

  if (report.most_active) {
    const leader = report.most_active;
    const note = [
      leader.tied ? "Tied on activity count" : "",
      breakdownNote(leader.breakdown),
    ]
      .filter(Boolean)
      .join(" · ");
    cards.push(
      <StorylineCard key="most-active" kicker="Most Active" question="Who is driving league activity?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} move{leader.metric !== 1 ? "s" : ""}
        </span>
        {note ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {note}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.trade_market_leader) {
    const leader = report.trade_market_leader;
    cards.push(
      <StorylineCard key="trade-market" kicker="Trade Market" question="Who is driving the trade market?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} completed trade{leader.metric !== 1 ? "s" : ""}
        </span>
      </StorylineCard>,
    );
  }

  if (report.largest_trade) {
    const trade = report.largest_trade;
    cards.push(
      <StorylineCard
        key="biggest-trade"
        kicker="Biggest Trade"
        question="Which completed trade moved the most assets?"
        wide
        route={FILTER_TRADES}
        onOpenHistory={onOpenHistory}
      >
        <div className="flex flex-col gap-2">
          {trade.teams.slice(0, 3).map((team) => (
            <StorylineTeamLine key={team.roster_id || team.team_name} team={team} />
          ))}
        </div>
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {trade.players} player{trade.players !== 1 ? "s" : ""} · {trade.picks} pick
          {trade.picks !== 1 ? "s" : ""}
        </span>
        {trade.when ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {trade.when}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.biggest_faab) {
    const faab = report.biggest_faab;
    const player = "name" in faab.player ? (faab.player as HistoryAsset) : null;
    cards.push(
      <StorylineCard
        key="biggest-faab"
        kicker="Biggest FAAB"
        question="Who spent the most on a single claim?"
        route={FILTER_WIRE}
        onOpenHistory={onOpenHistory}
      >
        <StorylineTeamLine team={faab} />
        {player ? (
          <div className="flex flex-wrap gap-1">
            <AssetChip asset={player} />
          </div>
        ) : null}
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          <Money all>{formatMoney(faab.amount)}</Money>
        </span>
        {faab.when ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {faab.when}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.most_picks_acquired) {
    const leader = report.most_picks_acquired;
    cards.push(
      <StorylineCard key="most-picks" kicker="Most Picks Acquired" question="Who collected the most future picks?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} pick{leader.metric !== 1 ? "s" : ""} acquired
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Incoming picks from completed trades, not current ownership.
        </span>
      </StorylineCard>,
    );
  }

  if (report.roster_turnover) {
    const leader = report.roster_turnover;
    cards.push(
      <StorylineCard key="roster-turnover" kicker="Roster Turnover" question="Which roster changed the most player assets?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} player-asset change{leader.metric !== 1 ? "s" : ""}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Unique players added or dropped per move. Same-player add/drop counts once.
        </span>
      </StorylineCard>,
    );
  }

  if (report.quietest) {
    const leader = report.quietest;
    cards.push(
      <StorylineCard key="quietest" kicker="Quietest Desk" question="Who stayed out of the market?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} completed move{leader.metric !== 1 ? "s" : ""}
        </span>
      </StorylineCard>,
    );
  }

  if (report.busiest_week) {
    const busy = report.busiest_week;
    cards.push(
      <StorylineCard key="busiest-week" kicker="Busiest Week" question="When was the market loudest?">
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          Week {busy.week}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {busy.count} completed moves
        </span>
      </StorylineCard>,
    );
  }

  if (report.most_traded_player) {
    const traded = report.most_traded_player;
    cards.push(
      <StorylineCard key="most-traded-player" kicker="Most Moved Player" question="Which player changed hands the most?">
        <div className="flex flex-wrap gap-1">
          <AssetChip asset={traded.player} />
        </div>
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {traded.count} completed trades
        </span>
      </StorylineCard>,
    );
  }

  if (cards.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Not enough completed activity this season to form storylines.
      </p>
    );
  }

  const heading = report.season ? `${report.season} storylines` : "Season storylines";

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <span
          className="text-xs uppercase"
          style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          {heading}
        </span>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          What this season&apos;s activity says, not a grade of old deals.
        </p>
      </header>
      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))" }}>
        {cards}
      </div>
    </div>
  );
}


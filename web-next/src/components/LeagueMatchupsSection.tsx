"use client";

import Link from "next/link";
import { useState } from "react";

import { TeamNameLink } from "@/components/TeamNameLink";
import { CompactModule } from "@/components/ui/CompactModule";
import { ProgressFill } from "@/components/Motion";
import { Collapse } from "@/components/ui/Presence";
import { FreshnessLabel } from "@/components/ui/FreshnessLabel";
import { ViewSelect } from "@/components/ui/ViewSelect";
import { freshnessLabel as ageLabel } from "@/lib/liveScores";
import {
  defaultMatchupWeek,
  formatMatchupPoints,
  formatMatchupProjected,
  LEAGUE_MATCHUPS_TITLE,
  leagueMatchupsHidden,
  leagueMatchupsSummaryParts,
  leagueMatchupWeeks,
  matchupStateLabel,
  pairAriaLabel,
  pairTones,
  sideSubline,
  winPercent,
  type LeagueMatchupPairView,
  type LeagueMatchupSideView,
  type LeagueMatchupTone,
} from "@/lib/leagueMatchups";
import { useLeagueMatchups } from "@/lib/useLeagueMatchups";

/**
 * The League page's Matchups section: every pair of a week in a real Sleeper league as one compact card (both teams with
 * avatars and a VS chip, live points big with the projected total under them, a win-chance bar per side). Numbers come from the
 * same server computation as the Matchup page (GET .../matchups) and refresh on the live-poll rules while games are on.
 * Tap rules: a team name opens the shared team sheet (TeamNameLink); the card's "Details" row expands the owner handles,
 * projected finals and win chances. The Matchup route only renders YOUR pair, so only your card links to it ("Open my matchup").
 * Leader is green, trailing the muted tone, never red. Mobile twin: mobile/src/components/LeagueMatchupsSection.tsx.
 */

const TONE_COLOR: Record<LeagueMatchupTone, string> = {
  leader: "var(--color-success)",
  trailing: "var(--color-text-muted)",
  even: "var(--color-text-primary)",
};

function SideHead({ side, leagueId, leagueName, align }: { side: LeagueMatchupSideView; leagueId: string; leagueName: string; align: "start" | "end" }) {
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${align === "end" ? "items-end text-right" : "items-start text-left"}`}>
      <TeamNameLink
        leagueId={leagueId}
        leagueName={leagueName}
        rosterId={side.roster_id}
        name={side.team_name}
        avatarUrl={side.avatar_url}
        ownerName={side.owner_name}
        showAvatar
        avatarSize={28}
        ringColor={side.is_mine ? "var(--color-accent)" : undefined}
        className={`text-sm font-bold ${align === "end" ? "flex-row-reverse" : ""}`}
      />
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {sideSubline(side)}
      </span>
    </div>
  );
}

function SideScore({ side, tone, align }: { side: LeagueMatchupSideView; tone: LeagueMatchupTone; align: "start" | "end" }) {
  const proj = formatMatchupProjected(side.projected_total);
  return (
    <div className={`flex min-w-0 flex-col ${align === "end" ? "items-end" : "items-start"}`}>
      <span className="text-2xl font-extrabold tabular-nums" style={{ color: TONE_COLOR[tone] }} data-testid="league-matchup-points">
        {formatMatchupPoints(side.points)}
      </span>
      {proj ? (
        <span className="text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>
          {proj}
        </span>
      ) : null}
    </div>
  );
}

function MatchupCard({ pair, leagueId, leagueName }: { pair: LeagueMatchupPairView; leagueId: string; leagueName: string }) {
  const [open, setOpen] = useState(false);
  const [a, b] = pair.sides;
  const [toneA, toneB] = pairTones(pair);
  const modeled = winPercent(a.win_probability) !== null;
  const mine = a.is_mine || b.is_mine;
  const bodyId = `league-matchup-${pair.matchup_id}`;
  return (
    <li
      className="glass-surface flex flex-col gap-2 p-3"
      style={{ borderRadius: "var(--radius-card, 16px)", outline: mine ? "1px solid var(--color-accent)" : undefined }}
      aria-label={pairAriaLabel(pair)}
      data-testid="league-matchup-card"
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-2">
        <SideHead side={a} leagueId={leagueId} leagueName={leagueName} align="start" />
        <span
          className="mt-1 px-2 py-0.5 text-[0.6875rem] font-extrabold uppercase"
          style={{ borderRadius: "var(--radius-pill)", background: "var(--color-muted-soft)", color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          VS
        </span>
        <SideHead side={b} leagueId={leagueId} leagueName={leagueName} align="end" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <SideScore side={a} tone={toneA} align="start" />
        <SideScore side={b} tone={toneB} align="end" />
      </div>
      <div className="flex flex-col gap-1" data-testid="league-matchup-bar">
        <div className="grid grid-cols-2 gap-2" role="img" aria-label={modeled ? `${winPercent(a.win_probability)} percent to ${winPercent(b.win_probability)} percent` : "Win chance not modeled yet"}>
          {([[toneA, winPercent(a.win_probability)], [toneB, winPercent(b.win_probability)]] as const).map(([tone, pct], i) => (
            <div key={i} className="h-1.5 overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "var(--color-muted-soft)" }}>
              <ProgressFill percent={modeled ? pct : 0} color={TONE_COLOR[tone]} />
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs font-bold tabular-nums">
          <span style={{ color: TONE_COLOR[toneA] }}>{modeled ? `${winPercent(a.win_probability)}%` : "—"}</span>
          <span style={{ color: "var(--color-text-muted)" }}>{matchupStateLabel(pair.game_state)}</span>
          <span style={{ color: TONE_COLOR[toneB] }}>{modeled ? `${winPercent(b.win_probability)}%` : "—"}</span>
        </div>
      </div>
      <button
        type="button"
        className="flex w-full items-center justify-between text-xs font-bold"
        style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)", borderTop: "var(--border-width-default) solid var(--color-border)" }}
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((v) => !v)}
      >
        <span style={{ color: "var(--color-text-muted)" }}>Details</span>
        <span aria-hidden="true">{open ? "Hide" : "Show"}</span>
      </button>
      <Collapse open={open}>
        <div id={bodyId} className="flex flex-col gap-2 pb-1 text-xs">
          <div className="grid grid-cols-2 gap-2">
            {[a, b].map((s, i) => (
              <div key={s.roster_id} className={`flex min-w-0 flex-col gap-0.5 ${i === 1 ? "items-end text-right" : ""}`}>
                <span className="truncate font-bold" style={{ color: "var(--color-text-secondary)" }}>{s.owner_name ? `@${s.owner_name}` : "Manager"}</span>
                <span style={{ color: "var(--color-text-muted)" }}>{formatMatchupProjected(s.projected_total) ?? "No projection yet"}</span>
              </div>
            ))}
          </div>
          {mine ? (
            <Link href={`/matchup/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} className="font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)", display: "inline-flex", alignItems: "center" }}>
              Open my matchup
            </Link>
          ) : null}
        </div>
      </Collapse>
    </li>
  );
}

export function LeagueMatchupsSection({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const [week, setWeek] = useState<number | null>(null);
  const { data, error, loading, ageSeconds } = useLeagueMatchups(leagueId, week);
  if (leagueMatchupsHidden(data?.reason)) return null;
  const shownWeek = data?.week ?? defaultMatchupWeek(data?.current_week) ?? null;
  const pairs = data?.matchups ?? [];
  const parts = data ? leagueMatchupsSummaryParts(shownWeek, pairs) : error ? [{ key: "error", text: "Could not load", tone: "muted" as const }] : [];
  const weeks = leagueMatchupWeeks(data?.max_week ?? 0);
  return (
    <section data-testid="league-matchups">
      <CompactModule id="league.matchups" title={LEAGUE_MATCHUPS_TITLE} parts={parts} loading={!data && !error} defaultOpen>
        {weeks.length > 1 && shownWeek ? (
          <div className="flex items-center gap-2">
            {/* view-select-ok: weeks (up to 18) */}
            <ViewSelect
              label="Matchups week"
              className="min-w-0 flex-1"
              value={String(shownWeek)}
              options={weeks.map((w) => ({ value: String(w), label: `Wk ${w}` }))}
              onChange={(value) => setWeek(Number(value))}
            />
          </div>
        ) : null}
        <div style={{ opacity: loading && data ? 0.6 : 1 }}>
          {error && !data ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{error}</p>
          ) : pairs.length === 0 && data ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No matchups for this week yet.</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {pairs.map((pair) => (
                <MatchupCard key={String(pair.matchup_id)} pair={pair} leagueId={leagueId} leagueName={leagueName} />
              ))}
            </ul>
          )}
        </div>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {data?.live && ageSeconds != null ? ageLabel(ageSeconds) : ""}{data?.live && ageSeconds != null && data?.sleeper_data_as_of ? " · " : ""}
          <FreshnessLabel datasets={[]} report={null} leagueAsOf={data?.sleeper_data_as_of} />
        </p>
      </CompactModule>
    </section>
  );
}

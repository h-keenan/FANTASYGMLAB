"use client";

import { useEffect, useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  simFmtPts,
  simFmtRecord,
  simPlayoffRoundLabel,
  simPlayoffStatusLabel,
  simTeamNameMap,
  simTransactionText,
  type SimLeagueResponse,
  type SimRecapScore,
  type SimStandingRow,
} from "@/lib/simGame";

type View = "standings" | "scores" | "feed" | "teams";

export function SimStandingsList({ rows, regularWeeks, playoffTeams }: { rows: SimStandingRow[]; regularWeeks?: number; playoffTeams?: number }) {
  return (
    <ol className="flex flex-col gap-2" aria-label="Standings" data-reg-weeks={regularWeeks}>
      {rows.map((row, index) => (
        <li key={row.team_id}>
          <AccentCard accent={row.is_you ? "var(--color-accent)" : index < (playoffTeams ?? 0) ? "var(--color-success)" : "var(--color-border-strong)"} compact as="div">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2">
                <span className="text-sm font-bold w-5 shrink-0">{row.rank ?? index + 1}</span>
                <span className="text-sm font-semibold break-words min-w-0">
                  {row.name}
                  {row.is_you ? " (you)" : ""}
                </span>
              </span>
              <span className="flex items-center gap-2 shrink-0">
                {simPlayoffStatusLabel(row.playoff_status) ? (
                  <SimToneBadge label={simPlayoffStatusLabel(row.playoff_status)} tone={row.playoff_status === "out" || row.playoff_status === "eliminated" ? "muted" : "success"} />
                ) : null}
                <span className="text-sm font-bold">{simFmtRecord(row)}</span>
              </span>
            </div>
            <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              <span>{simFmtPts(row.pf)} PF · {simFmtPts(row.pa)} PA</span>
              {row.streak ? <span>{row.streak}</span> : null}
            </div>
          </AccentCard>
        </li>
      ))}
    </ol>
  );
}

function Scoreboard({ game, schedule, names }: { game: SimCtx["game"]; schedule: NonNullable<SimLeagueResponse["schedule"]>; names: Record<string, string> }) {
  const played = schedule.filter((w) => w.games.some((g) => g.home_pts != null));
  const [week, setWeek] = useState<number>(() => (played.length ? played[played.length - 1].week : Math.max(1, game.week)));
  const entry = schedule.find((w) => w.week === week);
  const label = entry?.kind === "playoff" ? simPlayoffRoundLabel(week, game.settings) : `Week ${week}`;
  const youId = game.you?.team_id;
  return (
    <section className="flex flex-col gap-2" aria-label="Scoreboard">
      <div className="flex items-center justify-between gap-2">
        <Button size="sm" variant="secondary" disabled={week <= 1} onClick={() => setWeek((w) => w - 1)}>Previous</Button>
        <span className="text-sm font-extrabold" aria-live="polite">{label} · Week {week}</span>
        <Button size="sm" variant="secondary" disabled={week >= schedule.length} onClick={() => setWeek((w) => w + 1)}>Next</Button>
      </div>
      {!entry || entry.games.length === 0 ? (
        <EmptyState title="No games" subtitle="Nothing is scheduled this week." />
      ) : (
        entry.games.map((g: SimRecapScore) => {
          const mine = g.home === youId || g.away === youId;
          const rows = [
            [g.home, g.home_pts],
            [g.away, g.away_pts],
          ] as const;
          return (
            <AccentCard key={`${g.home}-${g.away}`} accent={mine ? "var(--color-accent)" : "var(--color-border-strong)"} compact as="div">
              {rows.map(([id, pts]) => (
                <div key={id} className="flex justify-between gap-2 text-sm" style={{ fontWeight: g.winner === id ? 800 : 500, opacity: g.winner && g.winner !== id ? 0.7 : 1 }}>
                  <span className="break-words min-w-0">{names[id] ?? "Team"}{id === youId ? " (you)" : ""}</span>
                  <span>{pts == null ? "-" : simFmtPts(pts)}</span>
                </div>
              ))}
            </AccentCard>
          );
        })
      )}
    </section>
  );
}

/** Standings, scoreboard, transaction feed and AI-team scouting. */
export function SimLeagueTab({ ctx }: { ctx: SimCtx }) {
  const { gameId, game } = ctx;
  const [view, setView] = useState<View>("standings");
  const [league, setLeague] = useState<SimLeagueResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLeague(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setLeague(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  const names = useMemo(() => simTeamNameMap(league?.teams), [league?.teams]);

  if (failed) {
    return <EmptyState title="Could not load the league" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setFailed(false); setAttempt((n) => n + 1); }} />;
  }
  if (!league) return <SkeletonCard lines={6} />;

  return (
    <div className="flex flex-col gap-3">
      <PillRow
        ariaLabel="League view"
        variant="fill"
        options={[
          { label: "Standings", value: "standings" },
          { label: "Scores", value: "scores" },
          { label: "Feed", value: "feed" },
          { label: "Teams", value: "teams" },
        ]}
        active={view}
        onSelect={(value) => setView(value as View)}
      />
      {view === "standings" ? (
        <section className="flex flex-col gap-2">
          <SectionHeading note={`Top ${game.settings.playoff_teams} make the playoffs. Ties break on head-to-head, then points.`}>Standings</SectionHeading>
          <SimStandingsList rows={league.standings ?? []} playoffTeams={game.settings.playoff_teams} />
        </section>
      ) : null}
      {view === "scores" ? <Scoreboard game={game} schedule={league.schedule ?? []} names={names} /> : null}
      {view === "feed" ? (
        <section className="flex flex-col gap-2" aria-label="Transactions">
          <SectionHeading note="AI trades and waiver moves, newest first.">Around the league</SectionHeading>
          {(league.transactions ?? []).length === 0 ? (
            <EmptyState title="Quiet so far" subtitle="Moves show up here once the season gets going." />
          ) : (
            (league.transactions ?? []).map((tx, i) => (
              <AccentCard key={i} accent="var(--color-border-strong)" compact as="div">
                <div className="flex items-center gap-2">
                  {tx.week != null ? <ToneBadge label={`Week ${tx.week}`} color="var(--color-text-secondary)" size="xs" /> : null}
                  <ToneBadge label={String(tx.type ?? tx.kind ?? "move").replace(/_/g, " ")} color="var(--color-premium)" size="xs" />
                </div>
                <p className="text-sm">{simTransactionText(tx)}</p>
              </AccentCard>
            ))
          )}
        </section>
      ) : null}
      {view === "teams" ? (
        <section className="flex flex-col gap-2" aria-label="Scouting report">
          <SectionHeading note="Power rank is roster strength right now.">Scouting report</SectionHeading>
          {[...(league.teams ?? [])].sort((a, b) => a.power_rank - b.power_rank).map((team) => (
            <AccentCard key={team.team_id} accent={team.is_you ? "var(--color-accent)" : "var(--color-border-strong)"} compact as="div">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold break-words min-w-0">#{team.power_rank} {team.name}{team.is_you ? " (you)" : ""}</span>
                <ToneBadge label={team.persona.label} color="var(--color-accent)" size="xs" />
              </div>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{team.persona.blurb}</p>
              {team.avg_age != null ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Average age {team.avg_age.toFixed(1)}</p> : null}
            </AccentCard>
          ))}
        </section>
      ) : null}
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimPlayerChip, SimSectionTitle, SimSeeAll, SimSheet, SimTeamLink, SimToneBadge, simToneColor, simToneInk, useSimWide, type SimCtx } from "@/components/SimGameParts";
import { CountUp, MotionIn } from "@/components/Motion";
import { SimCrest } from "@/components/SimCrest";
import { SimLeaguePlayersView, SimLeagueTeamsView } from "@/components/SimLeagueWho";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simMatchupMargin, simMatchupStatus, simPreview, simScoreboardLabel } from "@/lib/simLayout";
import { useSimLeagueRosters } from "@/lib/useSimLeagueRosters";
import {
  simFmtPts,
  simFmtRecord,
  simPlayoffRoundLabel,
  simPlayoffStatusLabel,
  simPlayoffStatusTone,
  simStreakTone,
  simTransactionGlyph,
  simTransactionRoleTone,
  simTeamNameMap,
  simTransactionText,
  type SimLeagueResponse,
  type SimRecapScore,
  type SimStandingRow,
} from "@/lib/simGame";

type View = "standings" | "scores" | "feed" | "teams" | "players";

export function SimStandingsList({ rows, regularWeeks, playoffTeams }: { rows: SimStandingRow[]; regularWeeks?: number; playoffTeams?: number }) {
  const wide = useSimWide();
  if (!wide) {
    // Phone: one dense table-like row per team (rank, crest, name, streak, record) in a single card.
    return (
      <ol className="glass-surface flex flex-col px-2" aria-label="Standings" data-reg-weeks={regularWeeks}>
        {rows.map((row, index) => {
          const inPlayoffs = index < (playoffTeams ?? 0);
          const label = simPlayoffStatusLabel(row.playoff_status);
          return (
            <li
              key={row.team_id}
              className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto_auto] items-center gap-2"
              style={{
                borderBottom: index === (playoffTeams ?? 0) - 1 ? "2px dashed var(--color-success)" : "var(--border-width-default) solid var(--color-border)",
                background: row.is_you ? "var(--color-accent-soft)" : undefined,
              }}
            >
              <span className="text-xs font-extrabold tabular-nums" style={{ color: inPlayoffs ? "color-mix(in srgb, var(--color-success) 78%, var(--color-text-primary))" : "var(--color-text-secondary)" }}>{row.rank ?? index + 1}</span>
              <SimTeamLink teamId={row.team_id} name={row.name} isYou={row.is_you} size={22} bold={row.is_you} />
              <span className="text-xs font-bold tabular-nums" style={{ color: simToneInk(simStreakTone(row.streak ?? "")) }} title={label || undefined}>{row.streak ?? ""}</span>
              <span className="w-12 text-right text-sm font-bold tabular-nums">{simFmtRecord(row)}</span>
            </li>
          );
        })}
      </ol>
    );
  }
  return (
    <ol className="flex flex-col gap-2" aria-label="Standings" data-reg-weeks={regularWeeks}>
      {rows.map((row, index) => (
        <li key={row.team_id}>
          <AccentCard accent={row.is_you ? "var(--color-accent)" : index < (playoffTeams ?? 0) ? "var(--color-success)" : "var(--color-border-strong)"} compact as="div">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2">
                <span className="text-sm font-extrabold w-5 shrink-0 tabular-nums" style={{ color: index < (playoffTeams ?? 0) ? "var(--color-success)" : "var(--color-text-muted)" }}>{row.rank ?? index + 1}</span>
                <SimTeamLink teamId={row.team_id} name={row.name} isYou={row.is_you} size={28} />
              </span>
              <span className="flex items-center gap-2 shrink-0">
                {simPlayoffStatusLabel(row.playoff_status) ? (
                  <SimToneBadge label={simPlayoffStatusLabel(row.playoff_status)} tone={simPlayoffStatusTone(row.playoff_status)} />
                ) : null}
                <span className="text-sm font-bold">{simFmtRecord(row)}</span>
              </span>
            </div>
            <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              <span>{simFmtPts(row.pf)} PF · {simFmtPts(row.pa)} PA</span>
              {row.streak ? <span className="font-bold" style={{ color: simToneInk(simStreakTone(row.streak)) }}>{row.streak}</span> : null}
            </div>
          </AccentCard>
        </li>
      ))}
    </ol>
  );
}

/**
 * One matchup as a centered module: crest + name on each side, the two scores big in the middle (winner
 * emphasized, loser muted), a status dot + key (FINAL / UPCOMING) under them, my game highlighted. The
 * whole card is a button that opens the full matchup in a sheet. Mobile twin: mobile/src/components/SimGameLeague.tsx.
 */
export function SimScoreCard({ g, names, youId, onOpen }: { g: SimRecapScore; names: Record<string, string>; youId?: string; onOpen: () => void }) {
  const mine = g.home === youId || g.away === youId;
  const mineTone = !mine || !g.winner ? "accent" : g.winner === youId ? "success" : "danger";
  const status = simMatchupStatus(g);
  const side = (id: string, pts: number | null) => {
    const won = g.winner === id;
    return { id, pts, won, lost: Boolean(g.winner) && !won };
  };
  const left = side(g.home, g.home_pts);
  const right = side(g.away, g.away_pts);
  const team = (t: ReturnType<typeof side>) => (
    <span className="flex min-w-0 flex-col items-center gap-1 text-center" style={{ opacity: t.lost ? 0.7 : 1 }}>
      <SimCrest name={names[t.id] ?? "Team"} size={36} />
      <span className="text-xs leading-tight break-words" style={{ fontWeight: t.won ? 800 : 600, color: "var(--color-text-primary)" }}>{names[t.id] ?? "Team"}</span>
      {t.id === youId ? <ToneBadge label="YOU" color="var(--color-accent)" size="xs" /> : null}
    </span>
  );
  const score = (t: ReturnType<typeof side>) => (
    <span className="tabular-nums" style={{ fontSize: "1.25rem", fontWeight: t.won ? 900 : 600, color: t.won ? "var(--color-success)" : t.lost ? "var(--color-text-muted)" : "var(--color-text-primary)" }}>
      {t.pts == null ? "-" : <CountUp value={t.pts} />}
    </span>
  );
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full text-left"
      aria-label={`${names[g.home] ?? "Team"} ${left.pts == null ? "" : simFmtPts(left.pts)} versus ${names[g.away] ?? "Team"} ${right.pts == null ? "" : simFmtPts(right.pts)}. ${status.label}. Open matchup`}
      data-testid="sim-score-card"
    >
      <AccentCard accent={mine ? simToneColor(mineTone) : "var(--color-border-strong)"} compact as="div">
        <div className="grid items-center gap-2" style={{ gridTemplateColumns: "minmax(0,1fr) 9.5rem minmax(0,1fr)" }}>
          {team(left)}
          <span className="flex flex-col items-center gap-1">
            <span className="flex items-baseline gap-2">{score(left)}<span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>–</span>{score(right)}</span>
            <span className="inline-flex items-center gap-1 text-[0.6875rem] font-extrabold" style={{ color: status.tone === "success" ? "var(--color-success)" : "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
              <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
              {status.label}
            </span>
          </span>
          {team(right)}
        </div>
      </AccentCard>
    </button>
  );
}

function SimMatchupSheet({ g, names, youId, week, label, onClose }: { g: SimRecapScore; names: Record<string, string>; youId?: string; week: number; label: string; onClose: () => void }) {
  const status = simMatchupStatus(g);
  const rows = [
    [g.home, g.home_pts],
    [g.away, g.away_pts],
  ] as const;
  return (
    <SimSheet title={`${names[g.home] ?? "Team"} vs ${names[g.away] ?? "Team"}`} onClose={onClose}>
      <p className="pr-10 text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{label} · {status.label}</p>
      <div className="flex flex-col gap-3 pt-3" data-testid="sim-matchup-sheet">
        {rows.map(([id, pts]) => (
          <div key={id} className="flex items-center justify-between gap-3">
            <SimTeamLink teamId={id} name={names[id] ?? "Team"} isYou={id === youId} size={32} bold={g.winner === id} />
            <span className="tabular-nums text-2xl" style={{ fontWeight: g.winner === id ? 900 : 600, color: g.winner === id ? "var(--color-success)" : undefined }}>{pts == null ? "-" : simFmtPts(pts)}</span>
          </div>
        ))}
        <p className="text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>{simMatchupMargin(g, names)}</p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Week {week}. Tap a team for its scouting sheet.</p>
      </div>
    </SimSheet>
  );
}

function Scoreboard({ game, schedule, names }: { game: SimCtx["game"]; schedule: NonNullable<SimLeagueResponse["schedule"]>; names: Record<string, string> }) {
  const played = schedule.filter((w) => w.games.some((g) => g.home_pts != null));
  const [week, setWeek] = useState<number>(() => (played.length ? played[played.length - 1].week : Math.max(1, game.week)));
  const [open, setOpen] = useState<SimRecapScore | null>(null);
  const entry = schedule.find((w) => w.week === week);
  const roundLabel = entry?.kind === "playoff" ? simPlayoffRoundLabel(week, game.settings) : `Week ${week}`;
  const label = simScoreboardLabel(roundLabel, week);
  const youId = game.you?.team_id;
  return (
    <section className="flex flex-col gap-2" aria-label="Scoreboard">
      <div className="flex items-center justify-between gap-2">
        <Button size="sm" variant="secondary" disabled={week <= 1} onClick={() => setWeek((w) => w - 1)}>Previous</Button>
        <span className="text-sm font-extrabold" aria-live="polite">{label}</span>
        <Button size="sm" variant="secondary" disabled={week >= schedule.length} onClick={() => setWeek((w) => w + 1)}>Next</Button>
      </div>
      {!entry || entry.games.length === 0 ? (
        <EmptyState title="No games" subtitle="Nothing is scheduled this week." />
      ) : (
        // Changing the week sweeps a light band across the new scoreboard; the cards rise in a capped stagger.
        <div key={week} className="motion-sweep flex flex-col gap-2 rounded-xl">
          {entry.games.map((g: SimRecapScore, i) => (
            <MotionIn key={`${g.home}-${g.away}`} index={i} count={entry.games.length}>
              <SimScoreCard g={g} names={names} youId={youId} onOpen={() => setOpen(g)} />
            </MotionIn>
          ))}
        </div>
      )}
      {open ? <SimMatchupSheet g={open} names={names} youId={youId} week={week} label={label} onClose={() => setOpen(null)} /> : null}
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
  const [allMoves, setAllMoves] = useState(false);
  const [rosterAttempt, setRosterAttempt] = useState(0);
  // One request for every team's roster, only once Teams or Players is opened.
  const rosters = useSimLeagueRosters(gameId, ctx.tick, rosterAttempt, view === "teams" || view === "players");

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
          { label: "Standings", value: "standings", glyph: "standings" },
          { label: "Scores", value: "scores", glyph: "scores" },
          { label: "Feed", value: "feed", glyph: "feed" },
          { label: "Teams", value: "teams", glyph: "team" },
          { label: "Players", value: "players", glyph: "league" },
        ]}
        active={view}
        onSelect={(value) => setView(value as View)}
      />
      {view === "standings" ? (
        <section className="flex flex-col gap-2">
          <SimSectionTitle glyph="standings" tone="success" note={`Top ${game.settings.playoff_teams} make the playoffs. Ties break on ${game.settings.tiebreaker === "head_to_head" ? "head-to-head, then points" : "points for, then head-to-head"}.`}>Standings</SimSectionTitle>
          <SimStandingsList rows={league.standings ?? []} playoffTeams={game.settings.playoff_teams} />
        </section>
      ) : null}
      {view === "scores" ? <Scoreboard game={game} schedule={league.schedule ?? []} names={names} /> : null}
      {view === "feed" ? (
        <section className="flex flex-col gap-2" aria-label="Transactions">
          <SimSectionTitle glyph="league" tone="accent" note="AI trades and waiver moves, newest first.">Around the league</SimSectionTitle>
          {(league.transactions ?? []).length === 0 ? (
            <EmptyState title="Quiet so far" subtitle="Moves show up here once the season gets going." />
          ) : (
            simPreview(league.transactions ?? [], allMoves, 6).shown.map((tx, i) => (
              <AccentCard key={i} accent={simToneColor(simTransactionGlyph(tx).tone)} compact as="div">
                <div className="flex items-center gap-2">
                  {tx.team_id ? <SimTeamLink teamId={tx.team_id} name={names[tx.team_id] ?? "Team"} size={24} hideName /> : null}
                  <ReviewGlyphChip glyph={simTransactionGlyph(tx).glyph} tone={simTransactionGlyph(tx).tone} size={24} />
                  {tx.week != null ? <ToneBadge label={`Week ${tx.week}`} color="var(--color-text-secondary)" size="xs" /> : null}
                  <ToneBadge label={String(tx.type ?? tx.kind ?? "move").replace(/_/g, " ")} color={simToneColor(simTransactionGlyph(tx).tone)} size="xs" />
                </div>
                <p className="text-sm">{simTransactionText(tx)}</p>
                {(tx.players ?? []).length > 0 ? (
                  <ul className="flex flex-col gap-1" aria-label="Players in this move">
                    {tx.players!.map((p) => (
                      <li key={`${p.role}-${p.id}`} className="flex items-center gap-2">
                        <span className="w-10 shrink-0"><ToneBadge label={p.role} color={simToneColor(simTransactionRoleTone(p.role))} size="xs" /></span>
                        <SimPlayerChip player={p} size={28} />
                      </li>
                    ))}
                  </ul>
                ) : null}
              </AccentCard>
            ))
          )}
          <SimSeeAll hidden={simPreview(league.transactions ?? [], allMoves, 6).hidden} expanded={allMoves} onToggle={() => setAllMoves((v) => !v)} />
        </section>
      ) : null}
      {view === "teams" ? <SimLeagueTeamsView ctx={ctx} state={rosters} onRetry={() => setRosterAttempt((n) => n + 1)} /> : null}
      {view === "players" ? <SimLeaguePlayersView ctx={ctx} state={rosters} onRetry={() => setRosterAttempt((n) => n + 1)} /> : null}
    </div>
  );
}

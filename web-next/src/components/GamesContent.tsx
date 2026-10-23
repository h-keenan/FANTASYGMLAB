"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Input } from "@/components/Input";
import { RankingRow } from "@/components/LeagueRankingsContent";
import { PillRow } from "@/components/PillRow";
import { PlayerRow } from "@/components/PlayerRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import {
  api,
  type GamesPickemMatchup,
  type GamesPickemResponse,
  type GamesRosterPlayer,
  type GamesSeasonSimResponse,
  type GamesWhatIfResponse,
  type RankedPlayer,
} from "@/lib/api";
import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  PICKEM_PHASE_LABEL,
  pickemPhaseColor,
  recordLabel,
  seedChangeLabel,
  whatIfSummary,
  whatIfTone,
  withPick,
} from "@/lib/gamesPresentation";
import { formatRank, metricToneColor } from "@/lib/leagueRankingsPresentation";
import { matchPlayersByName } from "@/lib/playerSearch";

/**
 * Games: the Season Simulator (the shared playoff-odds Monte Carlo, plus a
 * Premium what-if) and a weekly Pick'em inside the user's own league. All
 * numbers come from modules/games.py and modules/playoff_simulator.py; nothing
 * is computed or invented here. Mirrors mobile's GamesScreen.
 */

const MAX_PLAYERS = 3;

type Tab = "sim" | "pickem";

export function GamesContent({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const [tab, setTab] = useState<Tab>("sim");
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {leagueName}
        </span>
        <h1 className="uppercase" style={{ font: "var(--font-page-title)", letterSpacing: "var(--letter-spacing-tight)" }}>
          Games
        </h1>
      </header>
      <PillRow
        fullWidth
        options={[
          { label: "Season Sim", value: "sim" },
          { label: "Pick'em", value: "pickem" },
        ]}
        active={tab}
        onSelect={(value) => setTab(value as Tab)}
      />
      {tab === "sim" ? <SeasonSimPanel leagueId={leagueId} /> : <PickemPanel leagueId={leagueId} />}
    </main>
  );
}

function ReasonState({ reason }: { reason: string }) {
  const router = useRouter();
  const goAccount = gamesReasonAction(reason) === "account";
  return (
    <EmptyState
      title={gamesReasonMessage(reason)}
      actionLabel={goAccount ? "Open Account" : "Back to Dashboard"}
      onAction={() => router.push(goAccount ? "/account" : "/")}
    />
  );
}

function Loading({ label }: { label: string }) {
  return (
    <p className="text-sm" style={{ color: "var(--color-text-muted)" }} role="status">
      {label}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Season Simulator
// ---------------------------------------------------------------------------

function SeasonSimPanel({ leagueId }: { leagueId: string }) {
  const [data, setData] = useState<GamesSeasonSimResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGamesSeasonSim(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the simulator.");
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!data) return <Loading label="Running the simulation…" />;
  if (data.reason || !data.my_team) return <ReasonState reason={data.reason || "unavailable"} />;

  const mine = data.my_team;
  const status = mine.clinched ? "Clinched" : mine.eliminated ? "Eliminated" : null;
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <SectionHeading
          kicker="Rest of season"
          note={
            data.weeks_remaining === 0
              ? "No games left. These are final results."
              : `${data.weeks_remaining ?? ""} weeks left, your real schedule and Roster Power.`
          }
        >
          Your odds
        </SectionHeading>
        <div className="glass-surface flex items-center justify-between gap-4 p-4">
          <div className="flex flex-col">
            <span className="text-4xl font-extrabold" style={{ color: metricToneColor(mine.playoff_probability) }}>
              {formatOdds(mine.playoff_probability)}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Playoff odds
            </span>
          </div>
          <div className="flex flex-col items-end gap-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            <span>
              Proj {mine.median_final_wins}-{mine.median_final_losses}
            </span>
            <span>Seed #{mine.median_seed}</span>
            {status ? <ToneBadge label={status} color={mine.clinched ? "var(--color-success)" : "var(--color-danger)"} /> : null}
          </div>
        </div>
      </section>

      <WhatIfSection leagueId={leagueId} data={data} />

      <section className="flex flex-col gap-3">
        <SectionHeading kicker="League" note="Same simulation for every team.">
          Playoff odds
        </SectionHeading>
        <div className="glass-surface flex flex-col">
          {data.teams.map((team, index) => (
            <RankingRow
              key={team.roster_id}
              rankLabel={formatRank(index + 1)}
              teamName={team.team_name}
              avatarUrl={team.avatar_url}
              ownerName={team.record_label}
              primaryMetric={formatOdds(team.playoff_probability)}
              metricLabel="Playoff odds"
              toneColor={metricToneColor(team.playoff_probability)}
              isCurrent={team.mine}
              firstPlace={index === 0}
              secondary={[`Seed #${team.median_seed}`]}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function WhatIfSection({ leagueId, data }: { leagueId: string; data: GamesSeasonSimResponse }) {
  const [drops, setDrops] = useState<string[]>([]);
  const [adds, setAdds] = useState<RankedPlayer[]>([]);
  const [pool, setPool] = useState<RankedPlayer[] | null>(null);
  const [search, setSearch] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<GamesWhatIfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadedPool = useRef(false);

  const rosterIds = useMemo(() => new Set(data.roster.map((p) => p.player_id)), [data.roster]);

  const loadPool = useCallback(() => {
    if (loadedPool.current) return;
    loadedPool.current = true;
    api
      .getLeagueRankings(leagueId)
      .then((response) => setPool(response.players ?? []))
      .catch(() => {
        loadedPool.current = false;
      });
  }, [leagueId]);

  const matches = useMemo(() => {
    if (!pool) return [];
    const taken = new Set(adds.map((p) => p.player_id));
    return matchPlayersByName(
      pool.filter((p) => !rosterIds.has(p.player_id) && !taken.has(p.player_id)),
      search,
    );
  }, [pool, adds, rosterIds, search]);

  if (!data.is_premium) {
    return (
      <PremiumUpsellCard
        bare
        kicker="What if"
        upsell={data.upsell}
        fallbackTitle="See how a move changes your season"
        fallbackBody="Add or drop players and see the change in your playoff odds before you make the move."
      />
    );
  }

  const toggleDrop = (id: string) =>
    setDrops((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : current.length < MAX_PLAYERS ? [...current, id] : current,
    );

  const run = () => {
    setRunning(true);
    setError(null);
    api
      .postGamesWhatIf(leagueId, { add: adds.map((p) => p.player_id), drop: drops })
      .then((response) => setResult(response))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not run the what-if."))
      .finally(() => setRunning(false));
  };

  const ready = adds.length > 0 || drops.length > 0;
  return (
    <section className="flex flex-col gap-3">
      <SectionHeading kicker="Premium" note={`Up to ${MAX_PLAYERS} players on each side.`}>
        What if
      </SectionHeading>

      <div className="glass-surface flex flex-col gap-1 p-4">
        <span className="text-xs font-bold uppercase" style={{ letterSpacing: "var(--letter-spacing-tight)" }}>
          Drop
        </span>
        {data.roster.map((player) => (
          <RosterPickRow key={player.player_id} player={player} selected={drops.includes(player.player_id)} onToggle={toggleDrop} />
        ))}
      </div>

      <div className="glass-surface flex flex-col gap-2 p-4">
        <span className="text-xs font-bold uppercase" style={{ letterSpacing: "var(--letter-spacing-tight)" }}>
          Add
        </span>
        {adds.map((player) => (
          <PlayerRow
            key={player.player_id}
            playerId={player.player_id}
            name={player.name ?? "Player"}
            position={player.position}
            tier={player.tier}
            injuryStatus={player.injury_status}
            trailing={
              <Button size="sm" variant="secondary" onClick={() => setAdds((c) => c.filter((p) => p.player_id !== player.player_id))}>
                Remove
              </Button>
            }
          >
            {player.team ?? ""}
          </PlayerRow>
        ))}
        {adds.length < MAX_PLAYERS ? (
          <>
            <Input
              aria-label="Search players to add"
              placeholder="Search players to add"
              value={search}
              onFocus={loadPool}
              onChange={(event) => {
                loadPool();
                setSearch(event.target.value);
              }}
            />
            {matches.map((player) => (
              <PlayerRow
                key={player.player_id}
                playerId={player.player_id}
                name={player.name ?? "Player"}
                position={player.position}
                tier={player.tier}
                injuryStatus={player.injury_status}
                trailing={
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setAdds((c) => [...c, player]);
                      setSearch("");
                    }}
                  >
                    Add
                  </Button>
                }
              >
                {player.team ?? ""}
              </PlayerRow>
            ))}
          </>
        ) : null}
      </div>

      <Button onClick={run} disabled={!ready || running} loading={running} className="self-start">
        Run what-if
      </Button>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      {result && !result.reason && result.baseline && result.scenario && result.change ? <WhatIfResult result={result} /> : null}
      {result?.reason ? <ReasonState reason={result.reason} /> : null}
    </section>
  );
}

function RosterPickRow({
  player,
  selected,
  onToggle,
}: {
  player: GamesRosterPlayer;
  selected: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <PlayerRow
      bordered
      playerId={player.player_id}
      name={player.name ?? "Player"}
      position={player.position}
      tier={player.tier}
      injuryStatus={player.injury_status}
      muted={!selected}
      trailing={
        <Button size="sm" variant={selected ? "primary" : "secondary"} aria-pressed={selected} onClick={() => onToggle(player.player_id)}>
          {selected ? "Dropping" : "Drop"}
        </Button>
      }
    >
      {player.team ?? ""}
    </PlayerRow>
  );
}

function WhatIfResult({ result }: { result: GamesWhatIfResponse }) {
  const change = result.change!;
  const tone = whatIfTone(change);
  const color = tone === "positive" ? "var(--color-success)" : tone === "negative" ? "var(--color-danger)" : "var(--color-text-muted)";
  return (
    <div className="glass-surface flex flex-col gap-3 p-4" data-testid="what-if-result">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {formatOdds(result.baseline!.playoff_probability)}
          </span>
          <span aria-hidden>→</span>
          <span className="text-2xl font-extrabold" style={{ color }}>
            {formatOdds(result.scenario!.playoff_probability)}
          </span>
        </div>
        <ToneBadge label={`${formatDelta(change.playoff_probability)} pts`} color={color} />
      </div>
      <p className="text-sm">{whatIfSummary(change)}</p>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Proj {result.scenario!.median_final_wins}-{result.scenario!.median_final_losses} · {seedChangeLabel(change.median_seed)}
      </p>
      {result.factors && result.factors.length > 0 ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          {result.factors.map((factor) => (
            <div key={factor.label} className="contents">
              <dt style={{ color: "var(--color-text-muted)" }}>{factor.label}</dt>
              <dd>{factor.detail}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pick'em
// ---------------------------------------------------------------------------

function PickemPanel({ leagueId }: { leagueId: string }) {
  const router = useRouter();
  const [data, setData] = useState<GamesPickemResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(
    (week?: number) => {
      api
        .getGamesPickem(leagueId, week)
        .then((result) => setData(result))
        .catch((err) => setError(err instanceof Error ? err.message : "Could not load Pick'em."));
    },
    [leagueId],
  );

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!data) return <Loading label="Loading Pick'em…" />;
  if (!data.available) {
    return (
      <EmptyState
        title="Pick'em is not open yet"
        subtitle="Check back soon."
        actionLabel="Back to Dashboard"
        onAction={() => router.push("/")}
      />
    );
  }
  if (data.reason || !data.matchups || data.week == null) return <ReasonState reason={data.reason || "unavailable"} />;

  const week = data.week;
  const phase = data.phase;
  const pick = (matchup: GamesPickemMatchup, rosterId: string) => {
    if (phase !== "open") return;
    setSaveError(null);
    setData((current) => (current && current.matchups ? { ...current, matchups: withPick(current.matchups, matchup.matchup_id, rosterId) } : current));
    api
      .postGamesPick(leagueId, { week, matchup_id: matchup.matchup_id, roster_id: rosterId })
      .then((response) => {
        if (!response.ok) {
          setSaveError(response.reason === "locked" ? "This week just locked." : "Could not save that pick.");
          load(week);
        }
      })
      .catch(() => {
        setSaveError("Could not save that pick.");
        load(week);
      });
  };

  const weeks = data.weeks ?? [];
  const index = weeks.indexOf(week);
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <SectionHeading kicker={`Season ${data.season ?? ""}`} note="Pick winners before the week starts. No money, just bragging rights.">
          Week {week}
        </SectionHeading>
        <div className="flex items-center justify-between gap-3">
          <Button size="sm" variant="secondary" disabled={index <= 0} onClick={() => load(weeks[index - 1])}>
            Prev
          </Button>
          <div className="flex items-center gap-2">
            <ToneBadge label={PICKEM_PHASE_LABEL[phase ?? "final"]} color={pickemPhaseColor(phase)} />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Your picks {recordLabel(data.season_record)}
            </span>
          </div>
          <Button size="sm" variant="secondary" disabled={index < 0 || index >= weeks.length - 1} onClick={() => load(weeks[index + 1])}>
            Next
          </Button>
        </div>
        {saveError ? (
          <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
            {saveError}
          </p>
        ) : null}
        {data.matchups.length === 0 ? (
          <EmptyState title="No matchups this week" />
        ) : (
          <div className="flex flex-col gap-3">
            {data.matchups.map((matchup) => (
              <MatchupPick key={matchup.matchup_id} matchup={matchup} phase={phase ?? "final"} onPick={pick} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <SectionHeading
          kicker="Season"
          note={data.leaderboard_scope === "you" ? "Showing your picks only." : "League members who made picks."}
        >
          Leaderboard
        </SectionHeading>
        {data.leaderboard && data.leaderboard.length > 0 ? (
          <div className="glass-surface flex flex-col">
            {data.leaderboard.map((row) => (
              <RankingRow
                key={row.roster_id}
                rankLabel={formatRank(row.rank)}
                teamName={row.team_name}
                avatarUrl={row.avatar_url}
                ownerName={row.owner_name}
                primaryMetric={`${row.correct}/${row.graded}`}
                metricLabel="Correct"
                toneColor={metricToneColor(row.accuracy)}
                isCurrent={row.mine}
                firstPlace={row.rank === 1}
                secondary={[`${row.accuracy}%`]}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No graded picks yet" subtitle="Standings start once a week you picked is final." />
        )}
      </section>
    </div>
  );
}

function MatchupPick({
  matchup,
  phase,
  onPick,
}: {
  matchup: GamesPickemMatchup;
  phase: string;
  onPick: (matchup: GamesPickemMatchup, rosterId: string) => void;
}) {
  const showPoints = phase !== "open";
  return (
    <article className="glass-surface flex flex-col gap-2 p-3" data-testid="pickem-matchup">
      <div className="grid grid-cols-2 gap-2">
        {matchup.teams.map((team) => {
          const picked = matchup.my_pick === team.roster_id;
          const won = matchup.winner_roster_id === team.roster_id;
          return (
            <button
              key={team.roster_id}
              type="button"
              disabled={phase !== "open"}
              aria-pressed={picked}
              onClick={() => onPick(matchup, team.roster_id)}
              className="flex flex-col items-center gap-1 p-3 min-h-[var(--touch-target-min)]"
              style={{
                border: `var(--border-width-default) solid ${picked ? "var(--color-accent)" : "var(--color-border)"}`,
                background: picked ? "var(--color-accent-soft)" : "transparent",
                opacity: phase !== "open" && !picked && !won ? 0.8 : 1,
              }}
            >
              <TeamAvatar avatarUrl={team.avatar_url} name={team.team_name} size={36} />
              <span className="text-sm font-bold text-center break-words">{team.team_name}</span>
              {showPoints ? (
                <span className="text-xs" style={{ color: won ? "var(--color-success)" : "var(--color-text-muted)" }}>
                  {team.points.toFixed(1)}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      {matchup.correct != null ? (
        <ToneBadge
          label={matchup.correct ? "Correct" : "Missed"}
          color={matchup.correct ? "var(--color-success)" : "var(--color-danger)"}
        />
      ) : null}
    </article>
  );
}

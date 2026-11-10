"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { OptionRadioGroup } from "@/components/OptionRadioGroup";
import { PageTitle } from "@/components/PageTitle";
import { PillRow } from "@/components/PillRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { Toggle } from "@/components/Toggle";
import { api, type LineupPlayer, type TeamRanking } from "@/lib/api";
import {
  DEFAULT_SIM_STRATEGY,
  SIM_DISCLAIMER,
  SIM_LABEL,
  SIM_MODE_OPTIONS,
  SIM_POSTURE_OPTIONS,
  isSimOffError,
  simCompareHeadline,
  simCompareRows,
  simDecisionKindLabel,
  simFormatPercent,
  simFormatPoints,
  simFormatRecord,
  simFormatSigned,
  simGate,
  simGradeTone,
  simLevelLabel,
  simNoteMessages,
  simPlayoffResultLabel,
  simPowerLabel,
  simReasonMessage,
  simRoundLabel,
  simStrategyEqual,
  simStrategySummary,
  simTeamNames,
  simTimeline,
  type SimMode,
  type SimResult,
  type SimStrategy,
  type SimTone,
  type SimUpsell,
  type SimWorld,
} from "@/lib/simPresentation";

type Phase =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "premium"; upsell: SimUpsell | null }
  | { kind: "setup" }
  | { kind: "running"; rerun: boolean }
  | { kind: "result" }
  | { kind: "error"; message: string };

type ResultTab = "summary" | "standings" | "playoffs" | "timeline" | "scouting";

const RESULT_TABS: { label: string; value: ResultTab }[] = [
  { label: "Summary", value: "summary" },
  { label: "Standings", value: "standings" },
  { label: "Playoffs", value: "playoffs" },
  { label: "Timeline", value: "timeline" },
  { label: "Scouting", value: "scouting" },
];

const TONE_COLOR: Record<SimTone, string> = {
  success: "var(--color-success)",
  accent: "var(--color-accent)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

function errorText(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null) {
    const e = error as { status?: number; code?: string; message?: string };
    if (e.status === 503 || e.code === "server_busy") return "The simulator is busy right now. Try again in a few seconds.";
    if (e.message) return e.message;
  }
  return fallback;
}

/** Strategy controls, shared by the first setup and the re-run editor. */
export function SimStrategyControls({
  strategy,
  onChange,
  roster,
  idPrefix,
}: {
  strategy: SimStrategy;
  onChange: (next: SimStrategy) => void;
  roster: LineupPlayer[];
  idPrefix: string;
}) {
  const protectedIds = new Set(strategy.protected_player_ids);
  function toggleProtected(playerId: string) {
    const next = new Set(protectedIds);
    if (next.has(playerId)) next.delete(playerId);
    else if (next.size < 50) next.add(playerId);
    onChange({ ...strategy, protected_player_ids: [...next] });
  }
  return (
    <div className="flex flex-col gap-4">
      <OptionRadioGroup
        id={`${idPrefix}-posture`}
        label="Your posture"
        options={SIM_POSTURE_OPTIONS.map((o) => ({ value: o.value, label: o.label, description: o.blurb }))}
        value={strategy.posture}
        onChange={(posture) => onChange({ ...strategy, posture })}
      />
      {(
        [
          ["trade_aggressiveness", "Trades", "How often your auto-GM looks for trades. Off means it never trades."],
          ["waiver_aggressiveness", "Waivers", "How hard your auto-GM works the waiver wire. Off ignores it."],
        ] as const
      ).map(([key, label, help]) => (
        <label key={key} className="flex flex-col gap-1">
          <span className="flex items-center justify-between text-sm font-semibold">
            <span>{label}</span>
            <span style={{ color: "var(--color-accent)" }}>{simLevelLabel(strategy[key])}</span>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.25}
            value={strategy[key]}
            aria-label={`${label} aggressiveness`}
            onChange={(event) => onChange({ ...strategy, [key]: Number(event.target.value) })}
            style={{ minHeight: "var(--touch-target-min)", accentColor: "var(--color-accent-strong)" }}
          />
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {help}
          </span>
        </label>
      ))}
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-semibold">Auto lineup</span>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {strategy.lineup_auto_set ? "Sets your best lineup every week." : "Set and forget: only fixes injuries."}
          </span>
        </span>
        <Toggle checked={strategy.lineup_auto_set} onChange={(lineup_auto_set) => onChange({ ...strategy, lineup_auto_set })} label="Auto lineup" />
      </div>
      <details>
        <summary className="text-sm font-semibold cursor-pointer" style={{ minHeight: "var(--touch-target-min)" }}>
          Protected players ({strategy.protected_player_ids.length})
        </summary>
        <p className="text-xs mb-2" style={{ color: "var(--color-text-secondary)" }}>
          Protected players are never traded or dropped.
        </p>
        {roster.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Your roster is not available to pick from right now.
          </p>
        ) : (
          <ul className="flex flex-col">
            {roster.map((player) => (
              <li key={player.player_id}>
                <label className="flex items-center gap-3 text-sm" style={{ minHeight: "var(--touch-target-min)" }}>
                  <input type="checkbox" checked={protectedIds.has(player.player_id)} onChange={() => toggleProtected(player.player_id)} />
                  <span>{player.name ?? player.player_id}</span>
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {player.position ?? ""}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  );
}

function SimBanner() {
  return (
    <div role="note" className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
      <ToneBadge label={SIM_LABEL} color="var(--color-accent)" size="xs" />
      <span>{SIM_DISCLAIMER}</span>
    </div>
  );
}

function ResultSkeleton() {
  return (
    <div className="flex flex-col gap-4" role="status" aria-label="Simulating the season">
      <SkeletonCard lines={4} />
      <SkeletonCard lines={3} />
      <SkeletonCard lines={5} />
    </div>
  );
}

function GradeHero({ result, teamName }: { result: SimResult; teamName: string }) {
  const tone = TONE_COLOR[simGradeTone(result.grade.letter)];
  const user = result.user;
  return (
    <AccentCard accent={tone} glow>
      <div className="flex items-center gap-4">
        <div
          aria-label={`Grade ${result.grade.letter}`}
          className="flex items-center justify-center font-extrabold"
          style={{ width: 88, height: 88, borderRadius: "var(--radius-pill)", color: tone, fontSize: "2.5rem", background: `color-mix(in srgb, ${tone} 15%, transparent)`, boxShadow: `inset 0 0 0 2px ${tone}` }}
        >
          {result.grade.letter}
        </div>
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            Simulated season grade
          </span>
          <span className="text-lg font-bold break-words">{teamName}</span>
          <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {simFormatRecord(user)}
            {user.seed ? `, seed ${user.seed}` : ""} · {simPlayoffResultLabel(user.playoff_result)}
          </span>
        </div>
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
        Graded on a curve: a typical manager is a C.
      </p>
      <ul className="flex flex-col gap-2">
        {result.grade.components.map((component) => (
          <li key={component.key} className="flex flex-col gap-1">
            <span className="flex justify-between text-xs">
              <span>{component.label}</span>
              <span>{Math.round(component.score)}</span>
            </span>
            <span aria-hidden="true" style={{ height: 6, borderRadius: 3, background: "var(--color-surface-muted)" }}>
              <span style={{ display: "block", height: 6, borderRadius: 3, width: `${Math.max(0, Math.min(100, component.score))}%`, background: tone }} />
            </span>
          </li>
        ))}
      </ul>
    </AccentCard>
  );
}

function TeamStats({ result }: { result: SimResult }) {
  const user = result.user;
  const luck = result.grade.summary.luck_wins;
  const stats: Array<[string, string]> = [
    ["Record", simFormatRecord(user)],
    ["Points for", simFormatPoints(user.pf)],
    ["Points against", simFormatPoints(user.pa)],
    ["Lineup efficiency", simFormatPercent(user.lineup_efficiency)],
    ["Expected wins", user.expected_wins === undefined ? "-" : user.expected_wins.toFixed(1)],
  ];
  return (
    <section className="flex flex-col gap-3" aria-labelledby="sim-team-stats">
      <SectionHeading id="sim-team-stats">Your team</SectionHeading>
      <div className="grid grid-cols-2 gap-2">
        {stats.map(([label, value]) => (
          <div key={label} className="glass-surface p-3 flex flex-col gap-1">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {label}
            </span>
            <span className="text-lg font-bold">{value}</span>
          </div>
        ))}
      </div>
      {typeof luck === "number" ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {Math.abs(luck) < 0.5 ? "Your record matched how you scored." : luck > 0 ? `You won about ${luck.toFixed(1)} more games than your scoring earned: a lucky season.` : `You won about ${Math.abs(luck).toFixed(1)} fewer games than your scoring earned: an unlucky season.`}
        </p>
      ) : null}
    </section>
  );
}

function Decisions({ result }: { result: SimResult }) {
  if (result.decisions_that_mattered.length === 0) return null;
  return (
    <section className="flex flex-col gap-3" aria-labelledby="sim-decisions">
      <SectionHeading id="sim-decisions" note="Each one is a what-if: the season replayed with that one move removed or flipped. Not a probability.">
        Decisions that mattered
      </SectionHeading>
      {result.decisions_that_mattered.map((decision, index) => {
        const helped = (decision.impact?.season_value ?? 0) >= 0;
        return (
          <AccentCard key={`${decision.kind}-${index}`} accent={helped ? "var(--color-success)" : "var(--color-warning)"} compact>
            <div className="flex items-center gap-2 flex-wrap">
              <ToneBadge label={simDecisionKindLabel(decision.kind)} color={helped ? "var(--color-success)" : "var(--color-warning)"} size="xs" />
              {decision.week ? <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Week {decision.week}</span> : null}
            </div>
            <p className="text-sm font-bold">{decision.title}</p>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{decision.detail}</p>
            {decision.impact && typeof decision.impact.points_per_game === "number" ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {simFormatSigned(decision.impact.points_per_game)} points per game
                {decision.impact.playoff_result_with && decision.impact.playoff_result_without
                  ? ` · ${simPlayoffResultLabel(decision.impact.playoff_result_with)} with it, ${simPlayoffResultLabel(decision.impact.playoff_result_without).toLowerCase()} without`
                  : ""}
              </p>
            ) : null}
          </AccentCard>
        );
      })}
    </section>
  );
}

function ComparePanel({ before, after }: { before: SimResult; after: SimResult }) {
  const rows = simCompareRows(before, after);
  return (
    <section className="flex flex-col gap-3" aria-labelledby="sim-compare">
      <SectionHeading id="sim-compare" note={`Before: ${simStrategySummary(before.strategy)}. After: ${simStrategySummary(after.strategy)}.`}>
        Strategy A/B
      </SectionHeading>
      <AccentCard accent="var(--color-accent)">
        <p className="text-sm font-semibold">{simCompareHeadline(before, after)}</p>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--color-text-muted)" }}>
              <th className="text-left font-normal text-xs" scope="col">&nbsp;</th>
              <th className="text-left font-normal text-xs" scope="col">Before</th>
              <th className="text-left font-normal text-xs" scope="col">After</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th className="text-left font-normal py-1 pr-2" scope="row">{row.label}</th>
                <td className="py-1 pr-2">{row.before}</td>
                <td className="py-1 font-bold" style={{ color: row.direction > 0 ? "var(--color-success)" : row.direction < 0 ? "var(--color-danger)" : undefined }}>
                  {row.after}
                  <span className="sr-only">{row.direction > 0 ? " (better)" : row.direction < 0 ? " (worse)" : ""}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </AccentCard>
    </section>
  );
}

function Standings({ result }: { result: SimResult }) {
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sim-standings">
      <SectionHeading id="sim-standings" note="Final regular-season order in the simulation.">Standings</SectionHeading>
      <ol className="flex flex-col gap-2">
        {result.standings.map((row, index) => (
          <li key={row.team_id}>
            <AccentCard accent={row.is_user ? "var(--color-accent)" : "var(--color-border-strong)"} compact>
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-bold" style={{ width: 20 }}>{index + 1}</span>
                  <span className="text-sm font-semibold break-words min-w-0">
                    {row.name}
                    {row.is_user ? " (you)" : ""}
                  </span>
                </span>
                <span className="text-sm font-bold shrink-0">{simFormatRecord(row)}</span>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                <span>
                  {simFormatPoints(row.pf)} PF · {simFormatPoints(row.pa)} PA
                </span>
                <span>{row.playoff_result === "champion" ? "Champion" : row.made_playoffs ? simPlayoffResultLabel(row.playoff_result) : "Missed playoffs"}</span>
              </div>
            </AccentCard>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Bracket({ result }: { result: SimResult }) {
  const names = simTeamNames(result);
  if (result.playoffs.length === 0) {
    return <EmptyState title="No playoffs to show" subtitle="This simulation has no playoff games." />;
  }
  return (
    <section className="flex flex-col gap-4" aria-labelledby="sim-bracket">
      <SectionHeading id="sim-bracket" note={result.champion ? `Champion: ${names[result.champion] ?? "Unknown"}` : undefined}>
        Playoff bracket
      </SectionHeading>
      {result.playoffs.map((round, index) => (
        <div key={round.round} className="flex flex-col gap-2">
          <h3 className="text-sm font-bold">
            {simRoundLabel(index, result.playoffs.length)} <span style={{ color: "var(--color-text-muted)" }}>· Week {round.week}</span>
          </h3>
          {round.games.map((game) => (
            <div key={`${game.home}-${game.away}`} className="glass-surface p-3 flex flex-col gap-1">
              {[
                [game.home, game.home_pts],
                [game.away, game.away_pts],
              ].map(([teamId, pts]) => (
                <div key={String(teamId)} className="flex justify-between text-sm" style={{ fontWeight: game.winner === teamId ? 800 : 400, opacity: game.winner === teamId ? 1 : 0.75 }}>
                  <span className="break-words min-w-0">{names[String(teamId)] ?? "Team"}</span>
                  <span>{simFormatPoints(Number(pts))}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

function Timeline({ result }: { result: SimResult }) {
  const [onlyMine, setOnlyMine] = useState(true);
  const names = useMemo(() => simTeamNames(result), [result]);
  const items = useMemo(() => simTimeline(result.events, names, { onlyUser: onlyMine }), [result, names, onlyMine]);
  return (
    <section className="flex flex-col gap-3" aria-labelledby="sim-timeline">
      <SectionHeading id="sim-timeline" note="Trades and pickups as the season played out.">Season timeline</SectionHeading>
      <PillRow
        ariaLabel="Timeline filter"
        options={[{ label: "Your moves", value: "mine" }, { label: "Whole league", value: "all" }]}
        active={onlyMine ? "mine" : "all"}
        onSelect={(value) => setOnlyMine(value === "mine")}
      />
      {items.length === 0 ? (
        <EmptyState title="No moves" subtitle={onlyMine ? "Your auto-GM made no trades or pickups. Raise trades or waivers and run again." : "No one made a move."} />
      ) : (
        <ol className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.key}>
              <AccentCard accent={item.involvesUser ? "var(--color-accent)" : "var(--color-border-strong)"} compact>
                <div className="flex items-center gap-2">
                  <ToneBadge label={`Week ${item.week}`} color="var(--color-text-secondary)" size="xs" />
                  <ToneBadge label={item.kind} color={item.kind === "trade" ? "var(--color-premium)" : "var(--color-opportunity)"} size="xs" />
                </div>
                <p className="text-sm font-semibold">{item.title}</p>
                <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{item.detail}</p>
              </AccentCard>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Scouting({ result }: { result: SimResult }) {
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sim-scouting">
      <SectionHeading id="sim-scouting" note="How each AI manager behaved in the simulation.">Scouting report</SectionHeading>
      <ul className="flex flex-col gap-2">
        {result.personas
          .filter((persona) => !persona.is_user)
          .map((persona) => (
            <li key={persona.team_id}>
              <AccentCard accent="var(--color-accent)" compact>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold break-words min-w-0">{persona.name}</span>
                  <ToneBadge label={persona.label ?? persona.persona_id} color="var(--color-accent)" size="xs" />
                </div>
                {persona.blurb ? <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{persona.blurb}</p> : null}
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {simPowerLabel(persona.power_percentile)}
                  {typeof persona.avg_age === "number" ? ` · average age ${persona.avg_age.toFixed(1)}` : ""}
                </p>
              </AccentCard>
            </li>
          ))}
      </ul>
    </section>
  );
}

export function FantasySimContent({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [worlds, setWorlds] = useState<SimWorld[]>([]);
  const [teams, setTeams] = useState<TeamRanking[]>([]);
  const [roster, setRoster] = useState<LineupPlayer[]>([]);
  const [mode, setMode] = useState<SimMode>("remaining");
  const [rosterId, setRosterId] = useState("");
  const [strategy, setStrategy] = useState<SimStrategy>(DEFAULT_SIM_STRATEGY);
  const [world, setWorld] = useState<SimWorld | null>(null);
  const [runs, setRuns] = useState<SimResult[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [teamName, setTeamName] = useState("Your team");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<ResultTab>("summary");
  const [attempt, setAttempt] = useState(0);

  const result = runs.length > 0 ? runs[runs.length - 1] : null;
  const previous = runs.length > 1 ? runs[runs.length - 2] : null;

  const refreshWorlds = useCallback(async () => {
    try {
      const list = await api.listSimWorlds();
      setWorlds(list.worlds ?? []);
    } catch {
      /* best-effort: the list only resumes older runs */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimStatus()
      .then((status) => {
        if (cancelled) return;
        const gate = simGate(status);
        if (gate.kind === "premium") setPhase({ kind: "premium", upsell: gate.upsell });
        else if (gate.kind === "unavailable") setPhase({ kind: "unavailable" });
        else setPhase({ kind: "setup" });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isSimOffError(error)) setPhase({ kind: "unavailable" });
        else setPhase({ kind: "error", message: errorText(error, "Could not load Fantasy Sim.") });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // Setup inputs are additive: neither may block the page.
  useEffect(() => {
    if (phase.kind !== "setup") return;
    let cancelled = false;
    api
      .listSimWorlds()
      .then((r) => {
        if (!cancelled) setWorlds(r.worlds ?? []);
      })
      .catch(() => {});
    api
      .getTeamRankings(leagueId)
      .then((r) => {
        if (!cancelled) setTeams(r.teams ?? []);
      })
      .catch(() => {});
    api
      .getMyTeam(leagueId)
      .then((r) => {
        if (!cancelled) setRoster([...(r.starters ?? []), ...(r.bench ?? [])]);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [phase.kind, leagueId]);

  async function finishWith(response: Awaited<ReturnType<typeof api.runSimWorld>>, append: boolean) {
    const gate = simGate(response);
    if (gate.kind === "premium") return setPhase({ kind: "premium", upsell: gate.upsell });
    if (response.reason || !response.result || !response.world) {
      setNotice(simReasonMessage(response.reason) || "The simulation did not finish. Try again.");
      return setPhase({ kind: append ? "result" : "setup" } as Phase);
    }
    setWorld(response.world);
    setRuns((current) => (append ? [...current, response.result as SimResult] : [response.result as SimResult]));
    setTab("summary");
    setEditing(false);
    setPhase({ kind: "result" });
  }

  async function run() {
    setNotice("");
    setPhase({ kind: "running", rerun: false });
    try {
      const created = await api.createSimWorld({ league_id: leagueId, mode, strategy, ...(rosterId ? { roster_id: rosterId } : {}) });
      const gate = simGate(created);
      if (gate.kind === "premium") return setPhase({ kind: "premium", upsell: gate.upsell });
      if (created.reason || !created.world) {
        setNotice(simReasonMessage(created.reason) || "Could not start the simulation.");
        if (created.reason === "world_limit_reached") void refreshWorlds();
        return setPhase({ kind: "setup" });
      }
      setNotes(created.notes ?? []);
      setTeamName(created.team?.name ?? "Your team");
      setRuns([]);
      await finishWith(await api.runSimWorld(created.world.id), false);
    } catch (error) {
      setNotice(errorText(error, "The simulation could not run. Try again."));
      setPhase({ kind: "setup" });
    }
  }

  async function rerun() {
    if (!world) return;
    setNotice("");
    setPhase({ kind: "running", rerun: true });
    try {
      const updated = await api.updateSimStrategy(world.id, strategy);
      if (updated.reason || !updated.world) {
        setNotice(simReasonMessage(updated.reason) || "Could not change the strategy.");
        return setPhase({ kind: "result" });
      }
      await finishWith(await api.runSimWorld(world.id), true);
    } catch (error) {
      setNotice(errorText(error, "The simulation could not run. Try again."));
      setPhase({ kind: "result" });
    }
  }

  async function openWorld(target: SimWorld) {
    setNotice("");
    setPhase({ kind: "running", rerun: false });
    try {
      const response = await api.getSimResult(target.id);
      if (response.reason || !response.result) {
        setNotice(simReasonMessage(response.reason) || "Could not open that simulation.");
        return setPhase({ kind: "setup" });
      }
      setWorld(response.world ?? target);
      setStrategy(response.result.strategy);
      setRuns([response.result]);
      setNotes([]);
      setTeamName(response.result.standings.find((row) => row.is_user)?.name ?? "Your team");
      setTab("summary");
      setPhase({ kind: "result" });
    } catch (error) {
      setNotice(errorText(error, "Could not open that simulation."));
      setPhase({ kind: "setup" });
    }
  }

  async function removeWorld(target: SimWorld) {
    try {
      await api.deleteSimWorld(target.id);
      setWorlds((current) => current.filter((w) => w.id !== target.id));
      setNotice("");
    } catch (error) {
      setNotice(errorText(error, "Could not delete that simulation."));
    }
  }

  if (phase.kind === "loading") {
    return (
      <main className="flex-1 flex flex-col gap-4 px-4 py-6 max-w-3xl w-full mx-auto">
        <PageTitle page="Fantasy Sim" />
        <ResultSkeleton />
      </main>
    );
  }
  if (phase.kind === "error") {
    return <ErrorState message={phase.message} onRetry={() => {
      setPhase({ kind: "loading" });
      setAttempt((n) => n + 1);
    }} />;
  }
  if (phase.kind === "premium") {
    return (
      <PremiumUpsellCard
        kicker="Fantasy Sim"
        leagueName={leagueName}
        upsell={phase.upsell}
        fallbackTitle="Play out your season before it happens"
        fallbackBody="Fantasy Sim is a Pro feature: set a strategy for your team, simulate the rest of the season against AI managers, and see your grade and the decisions that mattered. Start your free trial to unlock it."
      />
    );
  }
  if (phase.kind === "unavailable") {
    return (
      <main className="flex-1 flex flex-col gap-4 px-4 py-6 max-w-3xl w-full mx-auto">
        <PageTitle page="Fantasy Sim" />
        <EmptyState title="Fantasy Sim is coming soon" subtitle="Pick a strategy, play out the season, and see how you would grade. It is not switched on yet. Check back soon." />
      </main>
    );
  }

  const strategyChanged = world ? !simStrategyEqual(strategy, result?.strategy ?? strategy) : false;
  const noteLines = simNoteMessages(notes);

  return (
    <main className="flex-1 flex flex-col gap-5 px-4 py-6 max-w-3xl w-full mx-auto">
      <PageTitle page="Fantasy Sim" />
      <SimBanner />
      {notice ? (
        <p role="alert" className="text-sm" style={{ color: "var(--color-warning)" }}>
          {notice}
        </p>
      ) : null}

      {phase.kind === "setup" ? (
        <>
          <AccentCard accent="var(--color-accent)">
            <SectionHeading kicker={leagueName} note="Set a strategy for your team and play out the season against AI managers.">Set up your sim</SectionHeading>
            <OptionRadioGroup
              id="sim-mode"
              label="How much season"
              options={SIM_MODE_OPTIONS.map((o) => ({ value: o.value, label: o.label, description: o.blurb }))}
              value={mode}
              onChange={setMode}
            />
            {teams.length > 1 ? (
              <label className="flex flex-col gap-1 text-sm font-semibold">
                Play as
                <select
                  value={rosterId}
                  onChange={(event) => setRosterId(event.target.value)}
                  className="font-normal"
                  style={{ minHeight: "var(--touch-target-min)", background: "var(--color-surface)", color: "var(--color-text-primary)", border: "var(--border-width-default) solid var(--color-border-strong)", padding: "0 8px" }}
                >
                  <option value="">My team</option>
                  {teams.map((team) => (
                    <option key={team.roster_id} value={team.roster_id}>
                      {team.team_name ?? `Team ${team.roster_id}`}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <SimStrategyControls strategy={strategy} onChange={setStrategy} roster={roster} idPrefix="sim" />
            <Button onClick={run} fullWidth>
              Run simulation
            </Button>
          </AccentCard>
          {worlds.length > 0 ? (
            <section className="flex flex-col gap-2" aria-labelledby="sim-saved">
              <SectionHeading id="sim-saved">Your simulations</SectionHeading>
              <ul className="flex flex-col gap-2">
                {worlds.map((saved) => (
                  <li key={saved.id}>
                    <AccentCard accent="var(--color-border-strong)" compact>
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex flex-col min-w-0">
                          <span className="text-sm font-semibold break-words">{saved.league_name}</span>
                          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                            {saved.mode === "full" ? "Whole season" : "Rest of season"} · {simStrategySummary(saved.strategy)}
                          </span>
                        </span>
                        {saved.grade_letter ? <ToneBadge label={saved.grade_letter} color={TONE_COLOR[simGradeTone(saved.grade_letter)]} /> : null}
                      </div>
                      <div className="flex gap-2">
                        {saved.status !== "ready" || saved.grade_letter ? (
                          <Button size="sm" variant="secondary" onClick={() => openWorld(saved)}>
                            Open
                          </Button>
                        ) : null}
                        <Button size="sm" variant="ghost" onClick={() => removeWorld(saved)}>
                          Delete
                        </Button>
                      </div>
                    </AccentCard>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      ) : null}

      {phase.kind === "running" ? (
        <>
          <p className="text-sm font-semibold" role="status">
            Simulating the season…
          </p>
          <ResultSkeleton />
        </>
      ) : null}

      {phase.kind === "result" && result ? (
        <>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            Strategy: {simStrategySummary(result.strategy)}
          </p>
          <PillRow ariaLabel="Result sections" variant="scroll" options={RESULT_TABS} active={tab} onSelect={(value) => setTab(value as ResultTab)} />
          {tab === "summary" ? (
            <>
              <GradeHero result={result} teamName={teamName} />
              {previous ? <ComparePanel before={previous} after={result} /> : null}
              <TeamStats result={result} />
              <Decisions result={result} />
              {noteLines.length > 0 ? (
                <ul className="text-xs flex flex-col gap-1" style={{ color: "var(--color-text-muted)" }}>
                  {noteLines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
          {tab === "standings" ? <Standings result={result} /> : null}
          {tab === "playoffs" ? <Bracket result={result} /> : null}
          {tab === "timeline" ? <Timeline result={result} /> : null}
          {tab === "scouting" ? <Scouting result={result} /> : null}

          <AccentCard accent="var(--color-premium)">
            <SectionHeading kicker="What if" note="Change your strategy and run it again. The dice stay the same, so any difference is down to your choices.">Try a different strategy</SectionHeading>
            {editing ? (
              <>
                <SimStrategyControls strategy={strategy} onChange={setStrategy} roster={roster} idPrefix="sim-rerun" />
                <Button onClick={rerun} fullWidth disabled={!strategyChanged}>
                  Run again
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setEditing(true)} fullWidth>
                Change strategy
              </Button>
            )}
            <Button
              variant="ghost"
              onClick={() => {
                setPhase({ kind: "setup" });
                setRuns([]);
                setWorld(null);
              }}
            >
              Start a new simulation
            </Button>
          </AccentCard>
        </>
      ) : null}
    </main>
  );
}

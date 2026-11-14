"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { SimTeamLogo } from "@/components/SimTeamIdentity";
import { SimPlayerLine, SimSectionTitle, type SimCtx } from "@/components/SimGameParts";
import { SimTeamCard } from "@/components/SimTeamCard";
import { SkeletonCard } from "@/components/Skeleton";
import { simWindow, SIM_WINDOW_STEP } from "@/lib/simLayout";
import { simListStats } from "@/lib/simDraft";
import { simBlockEntryCount, simBlockNote, simRosterEntries, simRosterPositions, simTeamsByPower, type SimRosterPosFilter } from "@/lib/simLeagueRosters";
import type { SimLeagueRostersState } from "@/lib/useSimLeagueRosters";

function Loading({ state, onRetry }: { state: SimLeagueRostersState; onRetry: () => void }) {
  if (state.status === "error") {
    return <EmptyState title="Could not load the rosters" subtitle="Check your connection and try again." actionLabel="Try again" onAction={onRetry} />;
  }
  return <SkeletonCard lines={6} />;
}

/** Teams view: one glanceable card per team (record, top assets, needs and depth); tap a team for its full roster. */
export function SimLeagueTeamsView({ ctx, state, onRetry }: { ctx: SimCtx; state: SimLeagueRostersState; onRetry: () => void }) {
  if (state.status !== "ready") return <Loading state={state} onRetry={onRetry} />;
  return (
    <section className="flex flex-col gap-2" aria-label="Teams">
      <SimSectionTitle glyph="team" tone="accent" note="Who has who. Power rank is roster strength right now. Tap a team for its full roster.">Teams</SimSectionTitle>
      {simTeamsByPower(state.teams).map((team) => (
        <SimTeamCard key={team.team_id} team={team} onOpen={ctx.openTeam} />
      ))}
    </section>
  );
}

/**
 * Players view: find any rostered player and see who owns him (tap the owner to open that team), or browse the
 * league position by position (all QBs with owner and value). Reads the same single rosters payload.
 */
export function SimLeaguePlayersView({ ctx, state, onRetry }: { ctx: SimCtx; state: SimLeagueRostersState; onRetry: () => void }) {
  const [pos, setPos] = useState<SimRosterPosFilter>("ALL");
  const [onlyBlock, setOnlyBlock] = useState(false);
  const [text, setText] = useState("");
  const [visible, setVisible] = useState(SIM_WINDOW_STEP);
  const teams = state.status === "ready" ? state.teams : null;
  const entries = useMemo(() => (teams ? simRosterEntries(teams, pos, text, onlyBlock) : []), [teams, pos, text, onlyBlock]);
  const blockCount = useMemo(() => (teams ? simBlockEntryCount(teams) : 0), [teams]);
  const teamById = useMemo(() => new Map((teams ?? []).map((t) => [t.team_id, t])), [teams]);
  const positions = useMemo(() => (teams ? simRosterPositions(teams) : []), [teams]);
  if (!teams) return <Loading state={state} onRetry={onRetry} />;
  const { shown, remaining } = simWindow(entries, visible);
  return (
    <section className="flex flex-col gap-3" aria-label="League players">
      <SimSectionTitle glyph="league" tone="accent" note="Every rostered player and who owns him. Free agents are on the Players tab.">Find a player</SimSectionTitle>
      <Input
        type="search"
        inputMode="search"
        placeholder="Search by player name or NFL team"
        aria-label="Find a player"
        value={text}
        onChange={(event) => { setText(event.target.value); setVisible(SIM_WINDOW_STEP); }}
        className="w-full"
      />
      <PillRow
        ariaLabel="Position filter"
        variant="scroll"
        options={[{ label: "All", value: "ALL" }, ...positions.map((p) => ({ label: p, value: p })), ...(blockCount > 0 || onlyBlock ? [{ label: `On the block ${blockCount}`, value: "BLOCK" }] : [])]}
        active={onlyBlock ? "BLOCK" : pos}
        onSelect={(value) => {
          setOnlyBlock(value === "BLOCK");
          setPos(value === "BLOCK" ? "ALL" : (value as SimRosterPosFilter));
          setVisible(SIM_WINDOW_STEP);
        }}
      />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} aria-live="polite">
        {entries.length} {entries.length === 1 ? "player" : "players"}{onlyBlock ? " on a trade block" : pos === "ALL" ? "" : ` at ${pos}`}, best first
      </p>
      {entries.length === 0 ? (
        <EmptyState title="No one matches" subtitle="Try another name, or pick All positions. Free agents are on the Players tab." />
      ) : (
        <ul className="flex flex-col" aria-label="Rostered players">
          {shown.map(({ player, team }) => (
            <li key={player.id}>
              <SimPlayerLine
                player={player}
                onOpen={ctx.openPlayer}
                stats={simListStats(player, { adp: false })}
                tags={[{ key: "owner", label: team.is_you ? "Your team" : team.name, tone: team.is_you ? "accent" : undefined }]}
                extra={onlyBlock && player.block && !team.is_you ? <span className="text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="block-note">{simBlockNote(teamById.get(team.team_id) ?? { needs: [] }, player.block.why)}</span> : undefined}
                trailing={
                  <button
                    type="button"
                    className="tap-link inline-flex items-center justify-center"
                    style={{ width: 44, height: 44 }}
                    aria-label={`Owned by ${team.name}${team.is_you ? " (you)" : ""}. Open team`}
                    onClick={() => ctx.openTeam(team.team_id)}
                  >
                    <SimTeamLogo name={team.name} size="row" />
                  </button>
                }
              />
            </li>
          ))}
        </ul>
      )}
      {remaining > 0 ? (
        <Button variant="secondary" size="sm" onClick={() => setVisible((n) => n + SIM_WINDOW_STEP)}>
          Show {Math.min(remaining, SIM_WINDOW_STEP)} more
        </Button>
      ) : null}
    </section>
  );
}

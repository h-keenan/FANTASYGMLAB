"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { PositionBadge } from "@/components/PositionBadge";
import { SimTeamLogo } from "@/components/SimTeamIdentity";
import { SimGlyph } from "@/components/SimGlyph";
import { SimPlayerChip, SimPlayerLine, SimSectionTitle, SimSheet, SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SimTeamHistory } from "@/components/SimTeamHistory";
import { SkeletonCard } from "@/components/Skeleton";
import { TeamSheetFrame, TeamSheetOverview } from "@/components/TeamSheet";
import { teamSheetNextGameLine, type TeamSheetChip } from "@/lib/teamSheet";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simListStats } from "@/lib/simDraft";
import { simGroupBenchByPosition } from "@/lib/simLeagueRosters";
import {
  simFmtPts,
  simFmtRecord,
  simPlayoffStatusLabel,
  simSlotLabels,
  simSlotRepeatsPosition,
  simStrengthNeedLine,
  type SimTeamRosterResponse,
} from "@/lib/simGame";

const SIM_ROSTER_POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF"] as const;

/**
 * The scouting sheet for any team (GET /teams/{id}): record and rank, which
 * positions are strengths and needs, the lineup it will start, its full roster (starters, bench by position, IR, taxi) in the shared player rows, its
 * recent moves and a prefilled "Make an offer" (the trade tab opens with this team as the partner). Works for your own team too.
 */
export function SimTeamSheet({ ctx, teamId, onClose, onTrade }: { ctx: SimCtx; teamId: string; onClose: () => void; onTrade: (teamId: string) => void }) {
  const [data, setData] = useState<SimTeamRosterResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimGameTeam(ctx.gameId, teamId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason || !body.team) setFailed(true);
        else setData(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId, teamId, attempt]);

  const team = data?.team;
  const title = team ? `${team.name} scouting report` : "Team scouting report";
  return (
    <SimSheet title={title} onClose={onClose} labelledBy="sim-team-sheet-title">
      {failed ? (
        <div className="flex flex-col items-start gap-2 py-4">
          <p className="text-sm font-bold">Could not load this team.</p>
          <Button size="sm" variant="secondary" onClick={() => { setFailed(false); setAttempt((n) => n + 1); }}>Try again</Button>
        </div>
      ) : !data || !team ? (
        <div className="flex flex-col gap-3" aria-busy="true">
          <SkeletonCard lines={3} />
          <SkeletonCard lines={5} />
        </div>
      ) : (
        <TeamBody ctx={ctx} data={data} onTrade={onTrade} />
      )}
    </SimSheet>
  );
}

function TeamBody({ ctx, data, onTrade }: { ctx: SimCtx; data: SimTeamRosterResponse; onTrade: (teamId: string) => void }) {
  const team = data.team!;
  const record = team.record;
  const lineup = data.lineup ?? [];
  const labels = simSlotLabels(lineup);
  const started = new Set(lineup.map((s) => s.player?.id).filter(Boolean));
  const bench = (data.players ?? []).filter((p) => !started.has(p.id));
  const line = simStrengthNeedLine(data.strengths, data.needs);
  const status = record ? simPlayoffStatusLabel(record.playoff_status) : "";
  const tiles = [
    { label: "Record", value: record ? simFmtRecord(record) : "-" },
    { label: "Rank", value: record ? `#${record.rank}` : "-" },
    { label: "PF", value: record ? simFmtPts(record.pf) : "-" },
    { label: "Proj", value: simFmtPts(data.projected_total) },
  ];
  const chips: TeamSheetChip[] = [{ label: `Power #${team.power_rank}`, tone: "premium" }];
  if (status) chips.push({ label: status, tone: record?.playoff_status === "out" || record?.playoff_status === "eliminated" ? "muted" : "success" });
  return (
    <TeamSheetFrame
      id="sim-team"
      logo={<SimTeamLogo name={team.name} size="hero" label />}
      name={`${team.name}${team.is_you ? " (you)" : ""}`}
      nameTestId="team-sheet-name"
      tag={<ToneBadge label={team.persona.label} color="var(--color-accent)" size="xs" />}
      chips={chips}
      managedBy={team.owner}
      tabs={[
          {
            key: "overview",
            label: "Overview",
            render: () => (
              <TeamSheetOverview
                blurb={team.persona.blurb}
                tiles={tiles}
                streak={record?.streak}
                nextGame={data.next_game ? teamSheetNextGameLine({ week: data.next_game.week, opponent: data.next_game.opponent.name }) : ""}
                positions={data.positions ?? []}
                strengthsTitle={<SimSectionTitle glyph="spark" tone="accent" note={line || undefined}>Strengths and needs</SimSectionTitle>}
                injuries={
                  (data.injuries ?? []).length > 0 ? (
                    <section className="flex flex-col gap-1" aria-label="Injuries">
                      <SimSectionTitle glyph="injury" tone="danger">Injuries</SimSectionTitle>
                      {data.injuries!.map((p) => (
                        <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} trailing={<SimToneBadge label={`${p.out_weeks} wk`} tone="danger" />} />
                      ))}
                    </section>
                  ) : null
                }
              />
            ),
          },
          {
            key: "roster",
            label: "Roster",
            render: () => (
              <>
      <section className="flex flex-col gap-1" aria-label="Lineup">
        <SimSectionTitle glyph="team" tone="accent" note={`Projected ${simFmtPts(data.projected_total)} points this week`}>Lineup</SimSectionTitle>
        {lineup.map((slot, index) => (
          <div key={`${slot.slot}-${index}`} className="flex items-center gap-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
            <span className="w-12 shrink-0">
              <PositionBadge position={slot.slot} label={labels[index]} />
            </span>
            <div className="min-w-0 flex-1">
              {slot.player ? (
                <SimPlayerLine
                  player={slot.player}
                  hidePosition={simSlotRepeatsPosition(slot.slot, slot.player.pos)}
                  onOpen={ctx.openPlayer}
                  stats={simListStats(slot.player, { adp: false })}
                />
              ) : (
                <p className="py-3 text-xs" style={{ color: "var(--color-text-muted)" }}>Empty</p>
              )}
            </div>
          </div>
        ))}
      </section>

      {bench.length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="Bench">
          <SimSectionTitle glyph="bye" tone="muted" note={`${bench.length} on the bench, grouped by position`}>Bench</SimSectionTitle>
          {simGroupBenchByPosition(bench, SIM_ROSTER_POS_ORDER).map((group) => (
            <div key={group.pos} className="flex flex-col" role="group" aria-label={`${group.pos} bench`}>
              <p className="pt-1 text-xs font-extrabold" style={{ color: "var(--color-text-muted)" }}>{group.pos} · {group.players.length}</p>
              {group.players.map((p) => (
                <SimPlayerLine key={p.id} player={p} muted onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
              ))}
            </div>
          ))}
        </section>
      ) : null}

      {(data.ir ?? []).length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="Injured reserve">
          <SimSectionTitle glyph="injury" tone="danger" note="Not counted against the roster limit.">Injured reserve</SimSectionTitle>
          {data.ir!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
          ))}
        </section>
      ) : null}

      {(data.taxi ?? []).length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="Taxi squad">
          <SimSectionTitle glyph="spark" tone="accent" note="Young players stashed off the active roster.">Taxi squad</SimSectionTitle>
          {data.taxi!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
          ))}
        </section>
      ) : null}

              </>
            ),
          },
          {
            key: "trades",
            label: "Trades",
            render: () => (
              <>
      {(data.recent ?? []).length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Recent moves">
          <SimSectionTitle glyph="trade" tone="accent">Recent moves</SimSectionTitle>
          {data.recent!.map((m, i) => (
            <AccentCard key={i} accent="var(--color-border-strong)" compact as="div">
              <div className="flex items-center gap-2">
                <ToneBadge label={`Week ${m.week}`} color="var(--color-text-secondary)" size="xs" />
                <ToneBadge label={m.type.replace(/_/g, " ")} color="var(--color-premium)" size="xs" />
              </div>
              <p className="text-sm">{m.text}</p>
              <div className="flex flex-wrap gap-2">
                {m.players.map((p) => (
                  <SimPlayerChip key={`${p.role}-${p.id}`} player={p} size={24} />
                ))}
              </div>
            </AccentCard>
          ))}
        </section>
      ) : null}

      {!team.is_you ? (
        <div className="flex flex-col gap-1">
          <Button disabled={!data.trade?.open} onClick={() => onTrade(team.team_id)}>
            <span className="inline-flex items-center gap-2"><SimGlyph name="trade" size={14} />Make an offer to {team.name}</span>
          </Button>
          {!data.trade?.open ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Trades are closed right now.</p> : null}
        </div>
      ) : null}
              </>
            ),
          },
          { key: "history", label: "History", render: () => <SimTeamHistory gameId={ctx.gameId} teamId={team.team_id} /> },
      ]}
    />
  );
}

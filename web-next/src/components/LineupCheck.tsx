"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { IconRow } from "@/components/IconRow";
import { TeamNameLink } from "@/components/TeamNameLink";
import { SectionHeading } from "@/components/SectionHeading";
import { TeamAvatar } from "@/components/TeamAvatar";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { ToneBadge } from "@/components/ToneBadge";
import { ExpandRow, ExpandRowGroup } from "@/components/ui/ExpandRow";
import { api } from "@/lib/api";
import {
  flagText,
  flagTone,
  formatPoints,
  gapLabel,
  gapTone,
  lineupsReasonMessage,
  lineupsSummaryLine,
  setVsBestLine,
  swapLine,
  type CommissionerLineupsResponse,
  type LineupCheckTeam,
  type LineupTone,
} from "@/lib/commissionerLineups";

/**
 * Commissioner "Lineup check": every team's set lineup vs its best lineup this week, worst gap first. Each team is one
 * ExpandRow (avatar, name, set vs best, flag chips); tapping it opens the swaps that would fix it. Every number comes
 * from modules/commissioner_lineups.py (the Matchup engine's projections); nothing is computed here. A big gap is a
 * prompt to look, never a verdict, so tones are warning/muted, never red. Mobile twin: components/LineupCheck.tsx.
 */

const TONE_COLOR: Record<LineupTone, string> = {
  warning: "var(--color-warning)",
  success: "var(--color-success)",
  muted: "var(--color-text-muted)",
  information: "var(--color-information)",
};

function TeamRow({ team, leagueId, leagueName }: { team: LineupCheckTeam; leagueId?: string; leagueName?: string }) {
  const tone = gapTone(team);
  const label = `${team.team_name}, ${setVsBestLine(team)}`;
  return (
    <ExpandRow
      testId={`lineup-team-${team.roster_id}`}
      label={label}
      // team-tap-exempt: the whole row is one expand toggle; the team sheet opens from the "Open team" link inside it
      leading={<TeamAvatar avatarUrl={team.avatar_url} name={team.team_name} size={32} />}
      title={team.team_name}
      caption={setVsBestLine(team)}
      chips={
        <>
          {team.possible_tanking ? <ToneBadge label="Possible tanking" color={TONE_COLOR.warning} size="xs" /> : null}
          {team.flags.map((f, i) => (
            <ToneBadge key={`${f.kind}-${i}`} label={flagText(f)} color={TONE_COLOR[flagTone(f.kind)]} size="xs" />
          ))}
          {team.locked_count ? <ToneBadge label={`${team.locked_count} locked`} color={TONE_COLOR.muted} size="xs" /> : null}
        </>
      }
      action={<ToneBadge label={gapLabel(team)} color={TONE_COLOR[tone]} />}
    >
      <TeamNameLink leagueId={leagueId} leagueName={leagueName} rosterId={team.roster_id} name={team.team_name} showAvatar className="text-sm font-bold" />
      {team.swaps.length ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Swaps that fix it
          </span>
          {team.swaps.map((s, i) => (
            <IconRow key={`${s.slot}-${i}`} icon="arrow" color="var(--color-accent)">
              {swapLine(s)}
            </IconRow>
          ))}
        </div>
      ) : (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {team.gap != null && team.gap > 0
            ? "No swap is available: the players who would help are locked or not on the roster."
            : "Nothing to fix: the set lineup matches the best one."}
        </p>
      )}
      {team.starters.length ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Starters they set
          </span>
          {team.starters.map((s, i) => (
            <div key={`${s.player_id}-${i}`} className="flex items-center gap-2 text-sm">
              <PlayerAvatarSlot player={{ id: s.player_id, name: s.name ?? "Unknown player", position: s.position, team: s.team }} tier="row" />
              <span className="min-w-0 flex-1 truncate">
                <span style={{ color: "var(--color-text-muted)" }}>{s.slot ? `${s.slot} ` : ""}</span>
                {s.name ?? "Unknown player"}
              </span>
              {s.availability ? <ToneBadge label={s.availability === "bye" ? "Bye" : s.availability === "ir" ? "IR" : "Out"} color={TONE_COLOR[s.availability === "bye" ? "information" : "warning"]} size="xs" /> : null}
              {s.locked ? <ToneBadge label="Locked" color={TONE_COLOR.muted} size="xs" /> : null}
              <span className="tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
                {formatPoints(s.points)}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </ExpandRow>
  );
}

export function LineupCheckView({ data, leagueId, leagueName }: { data: CommissionerLineupsResponse; leagueId?: string; leagueName?: string }) {
  if (data.reason) return <EmptyState title="Nothing to check yet" subtitle={lineupsReasonMessage(data.reason)} />;
  return (
    <>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="lineup-summary">
        {lineupsSummaryLine(data)}
      </p>
      <ExpandRowGroup accent={TONE_COLOR.warning} testId="lineup-teams">
        {data.teams.map((t) => (
          <TeamRow key={t.roster_id} team={t} leagueId={leagueId} leagueName={leagueName} />
        ))}
      </ExpandRowGroup>
      {data.limits?.length ? (
        <details className="glass-surface p-4">
          <summary className="text-sm font-bold cursor-pointer" style={{ color: "var(--color-text-primary)" }}>
            What this can and can&rsquo;t tell you
          </summary>
          <div className="flex flex-col gap-2 mt-3">
            {data.limits.map((limit) => (
              <IconRow key={limit} icon="info" color="var(--color-text-muted)" textClassName="text-xs">
                {limit}
              </IconRow>
            ))}
          </div>
        </details>
      ) : null}
    </>
  );
}

/** Self-loading section for the Commissioner page. Renders nothing for a Free user (the integrity upsell above covers it). */
export function LineupCheck({ leagueId, leagueName, lens }: { leagueId: string; leagueName?: string; lens?: string }) {
  const [state, setState] = useState<{ key: string; data: CommissionerLineupsResponse | null; error: boolean }>({ key: "", data: null, error: false });
  const key = `${leagueId}|${lens ?? ""}`;
  useEffect(() => {
    let cancelled = false;
    api
      .getCommissionerLineups(leagueId, lens)
      .then((data) => !cancelled && setState({ key, data, error: false }))
      .catch(() => !cancelled && setState({ key, data: null, error: true }));
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, key]);
  if (state.key !== key) return null;
  if (state.error) return null;
  if (!state.data || state.data.is_premium === false) return null;
  return (
    <section className="flex flex-col gap-3" aria-label="Lineup check" data-testid="lineup-check">
      <SectionHeading note="Each team's set lineup vs its best lineup this week. A big gap is a prompt to look, not a verdict.">Lineup check</SectionHeading>
      <LineupCheckView data={state.data} leagueId={leagueId} leagueName={leagueName} />
    </section>
  );
}

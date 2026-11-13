"use client";

import { AccentCard } from "@/components/AccentCard";
import { PositionBadge } from "@/components/PositionBadge";
import { SimCrest } from "@/components/SimCrest";
import { simToneColor } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import type { SimLeagueRosterTeam } from "@/lib/simGame";
import { simTeamChips, simTeamRecordLine, simValueLabel } from "@/lib/simLeagueRosters";

/**
 * THE Fantasy Sim team card: who a team is and who it has, at a glance. Used by the League tab's Teams view and
 * the Trade tab's partner list (mobile twin: mobile/src/components/SimTeamCard.tsx). Crest, name, record and
 * rank, the team's top assets with their value, and what it needs vs where it is deep as position chips.
 * The whole card is one tap target (no nested buttons); `footer` is for non-interactive extras only.
 */
export function SimTeamCard({
  team,
  onOpen,
  selected = false,
  openLabel,
  compact = false,
  trailing,
}: {
  team: SimLeagueRosterTeam;
  onOpen?: (teamId: string) => void;
  selected?: boolean;
  openLabel?: string;
  /** Hide the top assets (the partner card once a partner is chosen). */
  compact?: boolean;
  trailing?: React.ReactNode;
}) {
  const chips = simTeamChips(team);
  const accent = selected || team.is_you ? "var(--color-accent)" : team.power_rank <= 3 ? "var(--color-success)" : "var(--color-border-strong)";
  const body = (
    <AccentCard accent={accent} compact as="div" data-testid="sim-team-card">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <SimCrest name={team.name} size={32} />
          <span className="flex min-w-0 flex-col text-left">
            <span className="break-words text-sm font-extrabold leading-tight">
              {team.name}
              {team.is_you ? " (you)" : ""}
            </span>
            <span className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{simTeamRecordLine(team)}</span>
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <ToneBadge label={`Power #${team.power_rank}`} color={team.power_rank <= 3 ? "var(--color-success)" : "var(--color-text-secondary)"} size="xs" />
          {trailing}
        </span>
      </div>
      {compact ? null : (
        <ul className="flex flex-col gap-1" aria-label={`${team.name} top assets`}>
          {team.top_assets.map((p) => (
            <li key={p.id} className="flex items-center gap-2 text-xs">
              <PositionBadge position={p.pos} />
              <span className="min-w-0 flex-1 truncate font-bold">{p.name}</span>
              <span className="shrink-0 tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                VAL <strong style={{ color: "var(--color-text-primary)" }}>{simValueLabel(p.value)}</strong>
              </span>
            </li>
          ))}
        </ul>
      )}
      {chips.length > 0 ? (
        <ul className="flex flex-wrap gap-1" aria-label="Needs and depth">
          {chips.map((c) => (
            <li key={c.key}>
              <ToneBadge label={c.label} color={simToneColor(c.tone === "danger" ? "danger" : "success")} size="xs" />
            </li>
          ))}
        </ul>
      ) : null}
    </AccentCard>
  );
  if (!onOpen) return body;
  return (
    <button
      type="button"
      className="block w-full text-left"
      style={{ minHeight: "var(--touch-target-min)" }}
      aria-pressed={selected || undefined}
      aria-label={openLabel ?? `${team.name}. Open roster`}
      onClick={() => onOpen(team.team_id)}
    >
      {body}
    </button>
  );
}

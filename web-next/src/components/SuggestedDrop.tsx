import { useState } from "react";
import type { DropPlayer, DropSuggestion, DroppablePlayers, NeedsModel, RosterOverflow } from "@/lib/api";
import { InfoTip } from "@/components/InfoTip";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import {
  dropActionLabel,
  overflowHeadline,
  lineupEffectText,
  needTierLabel,
  upgradeText,
  valueEffectText,
  weakestSlotText,
} from "@/lib/dropsPresentation";
import { PlayerName } from "@/components/PlayerName";

/**
 * Suggested drops (modules/drop_candidates.py), shared by the Waivers cards and
 * the Trade Analyzer's roster-full note. Everything shown is a server value:
 * the drop, why, the net effect on lineup points and value, and the
 * alternatives. Nothing is ranked or filtered here.
 */

function DropPlayerLine({
  player,
  lead,
  maxReasons = 3,
  swap = false,
  skipReasons,
}: {
  player: DropPlayer;
  lead?: string;
  maxReasons?: number;
  /** The effect is for the whole swap (add minus drop), so say so. */
  swap?: boolean;
  /** Reasons already shown on the main pick, so alternatives don't repeat them. */
  skipReasons?: string[];
}) {
  const effectText = [lineupEffectText(player.effect), valueEffectText(player.effect)].filter(Boolean).join(" · ");
  const effect = swap && effectText ? `Whole swap: ${effectText}` : effectText;
  const reasons = player.reasons.filter((reason) => !skipReasons?.includes(reason));
  const pills = effectPills(player.effect);
  return (
    <div className="flex flex-col gap-1" data-testid="drop-player">
      <span className="flex items-center gap-2 min-w-0">
        <PlayerAvatar playerId={player.player_id} size={32} />
        {lead ? (
          <span className="text-sm font-bold shrink-0" style={{ color: "var(--color-text-primary)" }}>
            {lead}{" "}
          </span>
        ) : null}
        <PlayerName name={player.name} className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
        <PositionBadge position={player.position} />
        <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          {[player.team, player.age ? Math.round(player.age) : null].filter(Boolean).join(" · ")}
        </span>
      </span>
      {reasons.length > 0 ? (
        <ul className="text-xs flex flex-col gap-0.5 pl-4 list-disc" style={{ color: "var(--color-text-secondary)" }}>
          {reasons.slice(0, maxReasons).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <span className="flex items-center gap-1.5 flex-wrap">
        <span className="sr-only">{effect}</span>
        {swap ? (
          <span className="text-[0.6875rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            Whole swap
          </span>
        ) : null}
        {pills.map((pill) => (
          <ToneBadge key={pill.label} label={pill.label} color={pill.color} title={pill.title} />
        ))}
      </span>
    </div>
  );
}

function dropBadge(suggestion: DropSuggestion) {
  const { drop } = suggestion;
  return drop != null
    ? { label: dropActionLabel(drop), color: "var(--color-danger)" }
    : suggestion.no_good_drop
      ? { label: "No good drop", color: "var(--color-warning)" }
      : suggestion.drop_required === false
        ? { label: "Spot open", color: "var(--color-success)" }
        : { label: "Roster", color: "var(--color-text-muted)" };
}

/** Compact pill text for the effect: "+7 pts / 9 wks" (full sentence in the details). */
function effectPills(effect: DropPlayer["effect"]): { label: string; color: string; title: string }[] {
  const pills: { label: string; color: string; title: string }[] = [];
  const pts = effect.lineup_points_ros;
  if (Math.abs(pts) < 0.5) {
    pills.push({ label: "No lineup change", color: "var(--color-text-muted)", title: lineupEffectText(effect) });
  } else {
    pills.push({
      label: `${pts > 0 ? "+" : "-"}${Math.abs(Math.round(pts))} pts / ${effect.weeks} wks`,
      color: pts > 0 ? "var(--color-success)" : "var(--color-danger)",
      title: lineupEffectText(effect),
    });
  }
  const value = valueEffectText(effect);
  if (value) {
    pills.push({ label: value, color: effect.value_delta > 0 ? "var(--color-success)" : "var(--color-danger)", title: value });
  }
  return pills;
}

type ReasonKind = "bench" | "injury" | "age" | "info";

function reasonKind(reason: string): ReasonKind {
  const r = reason.toLowerCase();
  if (/injur|\bir\b|out for|suspend/.test(r)) return "injury";
  if (/never start|bench|backup|depth|rotation|string|roster|snap|usage|role/.test(r)) return "bench";
  if (/\bage\b|\bold\b|years?|decline|aging/.test(r)) return "age";
  return "info";
}

const REASON_PATHS: Record<ReasonKind, string> = {
  bench: "M4 6h16M4 12h10M4 18h6",
  injury: "M12 5v14M5 12h14",
  age: "M12 7v5l3 2M12 3a9 9 0 100 18 9 9 0 000-18z",
  info: "M12 8h.01M11 12h1v5h1M12 3a9 9 0 100 18 9 9 0 000-18z",
};

function ReasonIcon({ kind }: { kind: ReasonKind }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      <path d={REASON_PATHS[kind]} />
    </svg>
  );
}

/** One player in the swap: headshot, name, position pill, team. */
function SwapTile({ side, player, name, playerId, position, team }: { side: "add" | "drop"; player?: DropPlayer; name: string; playerId: string; position: string; team?: string }) {
  const color = side === "add" ? "var(--color-success)" : "var(--color-danger)";
  const label = side === "add" ? "Add" : player?.action === "move_to_ir" ? "To IR" : "Drop";
  return (
    <div
      className="flex flex-col items-center gap-1 p-2 min-w-0 flex-1 text-center"
      data-testid={`swap-${side}`}
      style={{
        border: `var(--border-width-default) solid color-mix(in srgb, ${color} 55%, transparent)`,
        background: `color-mix(in srgb, ${color} 8%, transparent)`,
      }}
    >
      <ToneBadge label={label} color={color} size="xs" />
      <PlayerAvatar playerId={playerId} size={44} />
      <PlayerName name={name} className="text-sm font-bold leading-tight w-full" style={{ color: "var(--color-text-primary)" }} />
      <span className="flex items-center justify-center gap-1 flex-wrap">
        <PositionBadge position={position} />
        {team ? (
          <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
            {team}
            {player?.age ? ` · ${Math.round(player.age)}` : ""}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function SwapArrow() {
  return (
    <span className="shrink-0 flex items-center justify-center" aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 8h14M15 4l4 4-4 4M19 16H5M9 12l-4 4 4 4" />
      </svg>
    </span>
  );
}

/**
 * The swap itself, as a picture: ADD tile, arrow, DROP tile; effect as stat
 * pills; at most two icon reason chips (full reasons one tap away); and the
 * alternative cuts as avatar chips that swap the selection.
 */
function SwapBody({ suggestion, drop, alternatives }: { suggestion: DropSuggestion; drop: DropPlayer; alternatives: DropPlayer[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showWhy, setShowWhy] = useState(false);
  const pool: DropPlayer[] = [drop, ...alternatives];
  const selected = pool.find((p) => p.player_id === selectedId) ?? drop;
  const others = pool.filter((p) => p.player_id !== selected.player_id);
  const pills = effectPills(selected.effect);
  const effectSentence = [lineupEffectText(selected.effect), valueEffectText(selected.effect)].filter(Boolean).join(" · ");
  const chips = selected.reasons.slice(0, 2);
  return (
    <div className="flex flex-col gap-2">
      <p className="sr-only">
        {`Add ${suggestion.add.name}, ${selected.action === "move_to_ir" ? "move" : "drop"} ${selected.name}${selected.action === "move_to_ir" ? " to IR" : ""}`}
      </p>
      <div className="flex items-stretch gap-1.5">
        <SwapTile side="add" name={suggestion.add.name} playerId={suggestion.add.player_id} position={suggestion.add.position} />
        <SwapArrow />
        <SwapTile side="drop" player={selected} name={selected.name} playerId={selected.player_id} position={selected.position} team={selected.team} />
      </div>
      <div className="flex items-center gap-1.5 flex-wrap" data-testid="swap-effect" aria-label={`Whole swap: ${effectSentence}`}>
        <span className="text-[0.6875rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
          Swap
        </span>
        {pills.map((pill) => (
          <ToneBadge key={pill.label} label={pill.label} color={pill.color} title={pill.title} />
        ))}
      </div>
      {chips.length > 0 ? (
        <div className="flex items-center gap-1.5 flex-wrap" data-testid="swap-reasons">
          {chips.map((reason) => (
            <span
              key={reason}
              title={reason}
              className="inline-flex items-center gap-1 text-xs font-semibold min-w-0 max-w-full px-2 py-0.5"
              style={{ borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
            >
              <ReasonIcon kind={reasonKind(reason)} />
              <span className="truncate">{reason}</span>
            </span>
          ))}
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setShowWhy((v) => !v)}
        aria-expanded={showWhy}
        className="text-xs font-semibold self-start"
        style={{ background: "none", border: "none", padding: 0, color: "var(--color-accent)", cursor: "pointer", minHeight: "var(--touch-target-min)" }}
      >
        {showWhy ? "Hide details" : "Why this cut"}
      </button>
      {showWhy ? (
        <div className="flex flex-col gap-1" data-testid="swap-why">
          <DropPlayerLine player={selected} lead={selected === drop ? "Best cut:" : "Drop"} swap maxReasons={6} />
        </div>
      ) : null}
      {others.length > 0 ? (
        <div className="flex flex-col gap-1.5 pt-2" data-testid="swap-alternatives" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
          <span className="text-[0.6875rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            Or cut instead
          </span>
          <div className="flex gap-2 flex-wrap">
            {others.map((alt) => (
              <button
                key={alt.player_id}
                type="button"
                onClick={() => setSelectedId(alt.player_id === drop.player_id ? null : alt.player_id)}
                aria-label={`Cut ${alt.name} instead`}
                className="flex items-center gap-1.5 pr-2.5 py-0.5 pl-0.5 min-w-0"
                style={{
                  border: "var(--border-width-default) solid var(--color-border)",
                  borderRadius: "var(--radius-pill)",
                  background: "var(--color-surface-muted)",
                  cursor: "pointer",
                  minHeight: "var(--touch-target-min)",
                }}
              >
                <PlayerAvatar playerId={alt.player_id} size={28} />
                <PlayerName name={alt.name} className="text-xs font-bold max-w-[7.5rem]" style={{ color: "var(--color-text-primary)" }} />
                <PositionBadge position={alt.position} />
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** List rows: one line (badge + avatar + player name), the swap one tap away. The
 * top target shows the full block. */
function CompactSuggestedDrop({ suggestion }: { suggestion: DropSuggestion }) {
  const [open, setOpen] = useState(false);
  const { drop, alternatives } = suggestion;
  const badge = dropBadge(suggestion);
  return (
    <div className="flex flex-col gap-1.5" data-testid="suggested-drop-compact">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-2 text-left w-full"
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", minHeight: "var(--touch-target-min)" }}
      >
        <ToneBadge label={badge.label} color={badge.color} />
        {drop ? <PlayerAvatar playerId={drop.player_id} size={24} /> : null}
        <span className="text-sm font-bold flex-1 min-w-0 break-words flex items-center gap-1.5 flex-wrap" style={{ color: "var(--color-text-primary)" }}>
          {drop ? (
            <>
              {drop.name}
              <PositionBadge position={drop.position} />
            </>
          ) : suggestion.drop_required === false ? (
            "No drop needed"
          ) : null}
        </span>
        <span className="text-xs font-semibold shrink-0" style={{ color: "var(--color-accent)" }}>
          {open ? "Hide" : "Why"}
        </span>
      </button>
      {open ? (
        <div className="flex flex-col gap-2 pl-1" data-testid="suggested-drop-details">
          {drop ? (
            <SwapBody suggestion={suggestion} drop={drop} alternatives={alternatives} />
          ) : (
            <>
              <p className="text-xs font-semibold" style={{ color: "var(--color-text-secondary)" }}>
                {suggestion.why}
              </p>
              {suggestion.no_good_drop && suggestion.cheapest ? <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" /> : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function SuggestedDrop({ suggestion, compact = false }: { suggestion: DropSuggestion; compact?: boolean }) {
  if (compact) return <CompactSuggestedDrop suggestion={suggestion} />;
  const { drop, alternatives } = suggestion;
  const badge = dropBadge(suggestion);
  return (
    <div
      className="flex flex-col gap-2 p-3"
      data-testid="suggested-drop"
      style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-surface-2, transparent)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-xs font-extrabold uppercase"
          style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          Roster move
        </span>
        <ToneBadge label={badge.label} color={badge.color} />
      </div>
      {drop ? (
        <SwapBody suggestion={suggestion} drop={drop} alternatives={alternatives} />
      ) : (
        <>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {suggestion.why}
          </p>
          {suggestion.no_good_drop && suggestion.cheapest ? <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" /> : null}
        </>
      )}
    </div>
  );
}

/**
 * One group-level "Drop candidate" for a list whose rows all name the same cut (lib/waiversPresentation
 * sharedDropCandidate). One line (badge, avatar, name, position, "for N adds"), the why one tap away. Rows with a
 * different cut keep their own note.
 */
export function SharedDropNote({ drop, count }: { drop: DropPlayer; count: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1.5" data-testid="shared-drop-note">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-2 text-left w-full"
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", minHeight: "var(--touch-target-min)" }}
      >
        <ToneBadge label="Drop candidate" color="var(--color-danger)" />
        <PlayerAvatar playerId={drop.player_id} size={24} />
        <span className="text-sm font-bold flex-1 min-w-0 break-words flex items-center gap-1.5 flex-wrap" style={{ color: "var(--color-text-primary)" }}>
          {drop.name}
          <PositionBadge position={drop.position} />
          <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
            for {count} adds below
          </span>
        </span>
        <span className="text-xs font-semibold shrink-0" style={{ color: "var(--color-accent)" }}>
          {open ? "Hide" : "Why"}
        </span>
      </button>
      {open ? (
        <div className="pl-1" data-testid="shared-drop-details">
          <DropPlayerLine player={drop} maxReasons={6} />
        </div>
      ) : null}
    </div>
  );
}

const FREE_LOCK_NOTE = "more with Pro";

export function DroppablePlayersSection({ data }: { data: DroppablePlayers | null | undefined }) {
  if (!data) return null;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="droppable-heading" data-testid="droppable-players">
      <SectionHeading>
        <span id="droppable-heading">Players you could drop</span>
      </SectionHeading>
      {data.players.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Nobody on your roster is a free cut right now
          {data.protected_count > 0 ? ` (${data.protected_count} players are starters, high-value, needed depth or upside)` : ""}. If you add
          someone, their roster move shows the cheapest cut, or says there is no good one.
        </p>
      ) : (
        <div className="glass-surface flex flex-col gap-3 p-3">
          {data.players.map((player) => (
            <div key={player.player_id} className="flex flex-col gap-0.5">
              <DropPlayerLine player={player} lead={player.action === "move_to_ir" ? "Move to IR:" : undefined} />
              {player.named_for && player.named_for.length > 0 ? (
                <span className="text-xs font-semibold" style={{ color: "var(--color-accent)" }}>
                  The cut when you add {player.named_for.slice(0, 3).join(", ")}
                  {player.named_for.length > 3 ? ` +${player.named_for.length - 3}` : ""}
                </span>
              ) : null}
            </div>
          ))}
          {data.locked_count > 0 ? (
            <p className="text-xs" style={{ color: "var(--color-premium)" }}>
              +{data.locked_count} {FREE_LOCK_NOTE}
            </p>
          ) : null}
        </div>
      )}
      <InfoTip label="How drops are chosen">
        Lowest cost to your team first: players who never start, cost your lineup nothing if cut and have little value.
        Never suggested: starters, high-value assets, depth you need for byes and injuries, young upside for your team
        direction, hot players, and anyone you marked untouchable.
      </InfoTip>
    </section>
  );
}

/** The numbers behind the Team need stat, per position (the info sheet). */
export function NeedsBreakdown({ needs }: { needs: NeedsModel }) {
  return (
    <InfoTip label="How we read your needs">
      <div className="flex flex-col gap-2" data-testid="needs-breakdown">
        {needs.positions.map((position) => (
          <div key={position.position} className="flex flex-col gap-0.5">
            <span className="flex items-center gap-2 text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
              {position.position}
              <ToneBadge
                label={needTierLabel(position.tier)}
                color={
                  position.tier === "primary" || position.tier === "secondary"
                    ? "var(--color-warning)"
                    : position.tier === "watch"
                      ? "var(--color-accent)"
                      : "var(--color-success)"
                }
              />
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              Weakest slot {weakestSlotText(position)} · best free agent: {upgradeText(position)} · depth{" "}
              {position.healthy_count}/{position.required_depth}
            </span>
            {position.reasons.length > 0 ? (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {position.reasons.join("; ")}
              </span>
            ) : null}
          </div>
        ))}
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Ranks compare each starter slot with the same slot on every team in the league, using expected lineup points. The
          free agent line is the lineup points per week the best available player would add. Depth is healthy players vs
          starters plus one bye/injury cover.
        </span>
      </div>
    </InfoTip>
  );
}

/** "Roster full: you'd have to drop N" for a trade that overfills the roster (Analyzer verdict and Hub/Finder cards). */
export function RosterOverflowNote({ overflow, compact = false }: { overflow: RosterOverflow; compact?: boolean }) {
  const effect = overflow.effect ? [lineupEffectText(overflow.effect), valueEffectText(overflow.effect)].filter(Boolean).join(" · ") : "";
  return (
    <div
      className="flex flex-col gap-1.5 p-3"
      data-testid="roster-overflow"
      style={{ border: "var(--border-width-default) solid var(--color-warning)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-warning)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Roster full
        </span>
        <ToneBadge label={`${overflow.active_after}/${overflow.active_limit}`} color="var(--color-warning)" />
      </div>
      <p className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
        {overflowHeadline(overflow)}
      </p>
      {overflow.unavailable ? null : (
        <>
          {overflow.drops.map((drop) => (
            <DropPlayerLine key={drop.player_id} player={drop} maxReasons={compact ? 1 : 2} />
          ))}
          {effect ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Cost of the cuts, already in this result: {effect}
            </span>
          ) : null}
        </>
      )}
    </div>
  );
}

import { useState } from "react";
import type { DropPlayer, DropSuggestion, DroppablePlayers, NeedsModel } from "@/lib/api";
import { InfoTip } from "@/components/InfoTip";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import {
  dropActionLabel,
  lineupEffectText,
  needTierLabel,
  upgradeText,
  valueEffectText,
  weakestSlotText,
} from "@/lib/dropsPresentation";

/**
 * Suggested drops (modules/drop_candidates.py), shared by the Waivers cards and
 * the Trade Analyzer's roster-full note. Everything shown is a server value:
 * the drop, why, the net effect on lineup points and value, and the
 * alternatives. Nothing is ranked or filtered here.
 */

function DropPlayerLine({ player, lead, maxReasons = 3 }: { player: DropPlayer; lead?: string; maxReasons?: number }) {
  const effect = [lineupEffectText(player.effect), valueEffectText(player.effect)].filter(Boolean).join(" · ");
  return (
    <div className="flex flex-col gap-0.5" data-testid="drop-player">
      <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {lead ? `${lead} ` : ""}
        {player.name}{" "}
        <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          {player.position}
          {player.team ? ` · ${player.team}` : ""}
          {player.age ? ` · ${Math.round(player.age)}` : ""}
        </span>
      </span>
      {player.reasons.length > 0 ? (
        <ul className="text-xs flex flex-col gap-0.5 pl-4 list-disc" style={{ color: "var(--color-text-secondary)" }}>
          {player.reasons.slice(0, maxReasons).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {effect}
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

/** List rows: one line (badge + the full player name), details one tap away. The
 * top target shows the full block. */
function CompactSuggestedDrop({ suggestion }: { suggestion: DropSuggestion }) {
  const [open, setOpen] = useState(false);
  const { drop, alternatives } = suggestion;
  const badge = dropBadge(suggestion);
  const label = drop ? `${drop.name} · ${drop.position}` : suggestion.drop_required === false ? "No drop needed" : "";
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
        <span className="text-sm font-bold flex-1 min-w-0 break-words" style={{ color: "var(--color-text-primary)" }}>
          {label}
        </span>
        <span className="text-xs font-semibold shrink-0" style={{ color: "var(--color-accent)" }}>
          {open ? "Hide" : "Why"}
        </span>
      </button>
      {open ? (
        <div className="flex flex-col gap-2 pl-1" data-testid="suggested-drop-details">
          <p className="text-xs font-semibold" style={{ color: "var(--color-text-secondary)" }}>
            {drop ? `Add ${suggestion.add.name}, ${drop.action === "move_to_ir" ? "move" : "drop"} ${drop.name}${drop.action === "move_to_ir" ? " to IR" : ""}` : suggestion.why}
          </p>
          {drop ? <DropPlayerLine player={drop} /> : suggestion.no_good_drop && suggestion.cheapest ? <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" /> : null}
          {alternatives.length > 0 ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Or: {alternatives.map((alt) => alt.name).join(", ")}
            </span>
          ) : null}
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
        <>
          <p className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
            {`Add ${suggestion.add.name}, ${drop.action === "move_to_ir" ? "move" : "drop"} ${drop.name}${
              drop.action === "move_to_ir" ? " to IR" : ""
            }`}
          </p>
          <DropPlayerLine player={drop} />
          {alternatives.length > 0 ? (
            <div className="flex flex-col gap-1.5 pt-1" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
              <span className="text-[0.625rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                Or
              </span>
              {alternatives.map((alt) => (
                <DropPlayerLine key={alt.player_id} player={alt} maxReasons={1} />
              ))}
            </div>
          ) : null}
        </>
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

const FREE_LOCK_NOTE = "more with Premium";

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

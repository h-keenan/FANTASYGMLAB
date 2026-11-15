// Shared (web + mobile twin, byte-identical, import-free): the tap rule every player / pick template follows.
// A player (or pick) shown anywhere opens the shared quick view on tap. The templates (CompactPlayerCard,
// PlayerAccordionRow, TradeAssetCard, PlayerAvatarSlot) do that by default; a call site opts out ONLY with a
// `nonInteractive` reason string (a picker row that selects, a row already inside a link). See docs/ui-patterns.md,
// "Every player and pick is tappable".

export interface TapPlayer {
  id?: string | null;
  name: string;
}

/** A player can open the quick view when it has an id (generated rookies and sample rows without one stay plain). */
export function canOpenPlayer(player: TapPlayer | null | undefined): boolean {
  return Boolean(player && player.id != null && String(player.id).length > 0);
}

/** Screen-reader name of a player tap target. */
export function playerOpenLabel(name: string): string {
  return `Open ${name}`;
}

/** A `nonInteractive` opt-out must carry a real reason (a short sentence), never an empty string or a bare flag. */
export function isValidNonInteractiveReason(reason: unknown): reason is string {
  return typeof reason === "string" && reason.trim().length >= 12;
}

/** Minimum tap target (px) for any player / pick tap area. */
export const PLAYER_TAP_MIN = 44;

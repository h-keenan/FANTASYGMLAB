/**
 * THE Fantasy Sim manager label (coridian_: real-looking AI manager names are confusing). The engine generates a full
 * name ("Tessa Vance") and keeps it in the saved data; that never changes (old-save digests must stay put). Every surface
 * that prints a manager asks this formatter instead: an AI manager is "AI · Tessa" (first name only) with a bot mark, you
 * are "You", and a human manager (future public leagues) is their username with no bot mark.
 * Byte-identical web/mobile twin (guarded by scripts/check_lib_twins.mjs).
 */
export interface SimManagerLabel {
  /** What to print: "AI · Tessa", "You", or the human's username. */
  text: string;
  /** True for AI managers: the surface draws the small bot chip/icon beside the text. */
  isAi: boolean;
  /** The first name alone ("Tessa"), for compact slots that draw the bot mark themselves. */
  short: string;
}

export function simManagerLabel(
  owner: string | null | undefined,
  opts: { isYou?: boolean; human?: boolean } = {},
): SimManagerLabel | null {
  const full = (owner ?? "").replace(/\s+/g, " ").trim();
  if (opts.isYou) return { text: "You", isAi: false, short: "You" };
  if (!full) return null;
  if (opts.human) return { text: full, isAi: false, short: full };
  const first = full.split(" ")[0];
  return { text: `AI · ${first}`, isAi: true, short: first };
}

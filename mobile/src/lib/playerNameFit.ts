/**
 * The ONE name-fit ladder (owner rule, said five times: "the first letter of the first name and the whole surname if it
 * is ever truncated. Site-wide. No ifs, ands or buts."). A player name is NEVER ellipsized. When the full name does not
 * fit its box the renderer walks these stages in order until one fits:
 *
 *   0  full name                    "Jonathan Brisker"
 *   1  initial + whole surname      "J. Brisker"            (suffix kept: "M. Penix Jr.")
 *   2  same, one font step down     0.92em
 *   3  same, two font steps down    0.85em
 *   4  same, suffix dropped        "M. Harrison Jr." -> "M. Harrison" (only names with a Jr./III style suffix change)
 *   5  same, wrapped                the surname drops under the initial instead of being cut ("J." / "Brisker")
 *
 * Pure and dependency-free; byte-identical twin at mobile/src/lib/playerNameFit.ts (IDENTICAL in
 * scripts/check_lib_twins.mjs). Web `components/PlayerName.tsx` and app `components/PlayerName.tsx` measure and call
 * `playerNameStage`; nothing else may abbreviate or clip a person name (guarded by lib/playerNameTruncation.test.ts).
 */
import { shortPlayerName, splitPlayerName } from './playerNameDisplay.ts';

export type PlayerNameStage = {
  index: number;
  /** The text to show (full name or "J. Surname"). */
  text: string;
  /** Font-size multiplier (1 = the caller's own size). */
  scale: number;
  /** True only on the last stage: the line may wrap. Earlier stages are single-line. */
  wrap: boolean;
  /** True when `text` is the short form. */
  short: boolean;
};

export const PLAYER_NAME_SCALES = [1, 1, 0.92, 0.85, 0.85, 0.85] as const;
export const PLAYER_NAME_LAST_STAGE = PLAYER_NAME_SCALES.length - 1;

/** Stage `index` for `name`. A name that cannot shrink (mononym, team defense, "J. Cook") skips straight to wrap-safe scaling. */
export function playerNameStage(name: string | null | undefined, index: number): PlayerNameStage {
  const full = (name ?? "").replace(/\s+/g, " ").trim();
  const i = Math.max(0, Math.min(PLAYER_NAME_LAST_STAGE, Math.floor(index)));
  const short = i > 0;
  let text = short ? shortPlayerName(full) : full;
  // Stage 4 sheds a generational suffix before the name is allowed to wrap: "M. Harrison Jr." -> "M. Harrison".
  if (i === 4) {
    const { suffix } = splitPlayerName(full);
    if (suffix && text.endsWith(` ${suffix}`)) text = text.slice(0, -(suffix.length + 1));
  }
  return {
    index: i,
    text,
    scale: PLAYER_NAME_SCALES[i],
    wrap: i === PLAYER_NAME_LAST_STAGE,
    short: short && text !== full,
  };
}

/** Every stage, for tests and for twins that pre-measure. */
export function playerNameStages(name: string | null | undefined): PlayerNameStage[] {
  return PLAYER_NAME_SCALES.map((_, i) => playerNameStage(name, i));
}

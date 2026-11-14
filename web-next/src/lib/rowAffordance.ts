/**
 * Row affordance rule (coridian_: "if you tap anywhere on the module it takes you to the same page, so I don't
 * understand the arrow"). Import-free, byte-identical twin of mobile/src/lib/rowAffordance.ts.
 *
 *  1. A FULLY TAPPABLE row (or tile, or module) has NO chevron. The whole row is the affordance: it carries the link /
 *     button role, a visible press state (web: the global press rule + `.row-hit-scope:active` wash; app: PressableScale)
 *     and its accessible name says where it goes.
 *  2. A chevron is allowed ONLY for a separate secondary target: the row has its own action AND the chevron leads
 *     somewhere else (e.g. a bid row: tap = open the player, chevron = open the bid sheet). Never a second way to do the
 *     row's own action.
 *  3. Expand/collapse indicators (a +/- or a chevron that rotates) are state, not navigation, and are not covered here.
 *  4. The right edge of a row is ONE compact thing: a single number with a tiny caption (`ValueStat`), or one action.
 *     Never a labelled two-line block plus an arrow; that squeezed the name ("J. Bris...").
 */
export type RowAffordanceInput = {
  /** What tapping the row does (a destination key such as "player" or "league_recap"); null when the row is inert. */
  rowAction?: string | null;
  /** What a separate secondary control on the row does; null when there is none. */
  secondaryAction?: string | null;
};

export type RowAffordance = {
  /** The whole row is the hit target (stretch the hit area, press feedback). */
  wholeRow: boolean;
  /** Draw a chevron. True only for a secondary target that differs from the row's own action. */
  chevron: boolean;
};

export function rowAffordance({ rowAction = null, secondaryAction = null }: RowAffordanceInput): RowAffordance {
  const wholeRow = Boolean(rowAction);
  const chevron = Boolean(secondaryAction) && secondaryAction !== rowAction;
  return { wholeRow, chevron };
}

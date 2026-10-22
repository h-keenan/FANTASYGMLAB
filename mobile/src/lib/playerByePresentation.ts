/** Bye-week pills for the Player Detail header; same rules as web's PlayerHeroHeader. */
export function byePills(
  byeWeek: number | null | undefined,
  onByeThisWeek: boolean | null | undefined,
): { label: string | null; thisWeek: boolean } {
  if (byeWeek == null) return { label: null, thisWeek: false };
  return { label: `Bye: Wk ${byeWeek}`, thisWeek: onByeThisWeek === true };
}

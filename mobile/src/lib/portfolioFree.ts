/**
 * What a Free account sees on Portfolio instead of a pure upsell (first-time-user audit F9): its one saved league's real
 * standing, then the parts that need Pro, locked and named. Byte-identical twin (web PortfolioContent / app
 * PortfolioScreen), no imports. Gold stays on the Pro marker and the one Upgrade button; the standing itself is plain.
 */

/** The Pro part of Portfolio, as the locked rows under the free standing. */
export const PORTFOLIO_LOCKED_ROWS: readonly string[] = [
  "Every saved league side by side",
  "Your top need or opportunity in each league",
  "Player exposure across all your leagues",
];

export const PORTFOLIO_FREE_HEADING = "Your league";
export const PORTFOLIO_LOCKED_HEADING = "Unlock with Pro";

/** "7-3" or "7-3-1"; "—" when the record is not known. */
export function portfolioRecordText(s: { wins: number | null; losses: number | null; ties: number | null } | null | undefined): string {
  if (!s || s.wins == null || s.losses == null) return "—";
  return s.ties ? `${s.wins}-${s.losses}-${s.ties}` : `${s.wins}-${s.losses}`;
}

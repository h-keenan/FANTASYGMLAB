// The Free-tier gate card at the end of a Trade Hub board: ONE copy for web and the app (byte-identical twin, scripts/check_lib_twins.mjs).
// Web has no ad unlock, so it passes `adBonus = null` and the sentence just points at Pro; the app passes the per-ad bonus when ads can run.

export const TRADE_HUB_UPGRADE_LABEL = "Upgrade to Pro";

export function tradeHubGateTitle(hiddenCount: number): string {
  return `${hiddenCount} more trade ${hiddenCount === 1 ? "idea" : "ideas"} on this board`;
}

export function tradeHubGateBody(freeLimit: number, adBonus: number | null): string {
  return adBonus != null && adBonus > 0
    ? `Free shows the top ${freeLimit}. Watch a quick ad to reveal ${adBonus} more, or go Pro to unlock the full board.`
    : `Free shows the top ${freeLimit}. Go Pro to unlock the full board.`;
}

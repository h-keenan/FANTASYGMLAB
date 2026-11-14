import { PageTabBar } from "@/components/PageTabBar";

/**
 * The Trades family tab strip (Hub / Finder / Analyzer / History). Kept as the stable name the trade pages import;
 * the tabs, glyphs and routes now come from lib/pageFamilies.ts through the shared PageTabBar (sticky glass top tabs).
 * Mirrors app.py's TRADES_TAB_ROUTE_ORDER and mobile's TradesScreen tabs (lib/tradesTabs.test.ts).
 */
export function TradesTabBar({
  leagueId,
  leagueName,
  active,
}: {
  leagueId: string;
  leagueName: string;
  active: "trade_hub" | "trade_finder" | "trade_analyzer" | "trade_history";
}) {
  return <PageTabBar family="trades" active={active} leagueId={leagueId} leagueName={leagueName} />;
}

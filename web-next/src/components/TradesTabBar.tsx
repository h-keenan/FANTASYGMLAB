import { PillRow } from "@/components/PillRow";

/**
 * The Trade Hub / Trade Finder / Trade Analyzer tri-tab switcher — mirrors
 * app.py's TRADES_TAB_ROUTE_ORDER / TRADES_TAB_LABELS (the single segmented
 * control Streamlit shows above all three tabs, and mobile's
 * TradesScreen.tsx tab labels: Hub / Finder / Analyzer, pinned by lib/tradesTabs.test.ts). All
 * three tabs now have a real Next.js page (Trade Finder joined Trade Hub
 * and Trade Analyzer in Revision 17) — none of them deep-link out to
 * Streamlit anymore.
 *
 * Trade History is a pill in the same row, linking out to its own
 * league-independent page. The bar is sticky and compact.
 */
export function TradesTabBar({
  leagueId,
  leagueName,
  active,
}: {
  leagueId: string;
  leagueName: string;
  active: "trade_hub" | "trade_finder" | "trade_analyzer";
}) {
  const suffix = `?name=${encodeURIComponent(leagueName)}`;
  const id = encodeURIComponent(leagueId);
  // Short labels: the page <h1> carries the full name, and four pills have to
  // fit one phone-width row. Trade History is a destination pill in the same
  // row (it is not part of TRADES_TAB_ROUTE_ORDER) and is never "active" here.
  const tabs: { label: string; value: string; href: string }[] = [
    { value: "trade_hub", label: "Hub", href: `/trade-hub/${id}${suffix}` },
    { value: "trade_finder", label: "Finder", href: `/trade-finder/${id}${suffix}` },
    { value: "trade_analyzer", label: "Analyzer", href: `/trade-analyzer/${id}${suffix}` },
    { value: "trade_history", label: "History", href: "/trade-history" },
  ];

  return <PillRow sticky fullWidth ariaLabel="Trades section" options={tabs} active={active} />;
}

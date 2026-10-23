import Link from "next/link";
import { PillRow } from "@/components/PillRow";

/**
 * The Trade Hub / Trade Finder / Trade Analyzer tri-tab switcher — mirrors
 * app.py's TRADES_TAB_ROUTE_ORDER / TRADES_TAB_LABELS (the single segmented
 * control Streamlit shows above all three tabs, and mobile's
 * TradesScreen.tsx tab order: Trade Block / Search / Make a Trade). All
 * three tabs now have a real Next.js page (Trade Finder joined Trade Hub
 * and Trade Analyzer in Revision 17) — none of them deep-link out to
 * Streamlit anymore.
 *
 * Trade History (Revision 18) is a genuinely separate GM_TOOLS destination,
 * not a fourth tab in this segmented control — it isn't part of
 * TRADES_TAB_ROUTE_ORDER on Streamlit, and mobile's TradesScreen.tsx reaches
 * it via a small header icon beside the tabs (navigation.navigate to a
 * screen outside this tab group), not a fourth tab. The trailing link below
 * mirrors that same "beside, not inside" placement.
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
  const tabs: { key: "trade_hub" | "trade_finder" | "trade_analyzer"; label: string; href: string }[] = [
    { key: "trade_hub", label: "Trade Hub", href: `/trade-hub/${encodeURIComponent(leagueId)}${suffix}` },
    { key: "trade_finder", label: "Trade Finder", href: `/trade-finder/${encodeURIComponent(leagueId)}${suffix}` },
    { key: "trade_analyzer", label: "Trade Analyzer", href: `/trade-analyzer/${encodeURIComponent(leagueId)}${suffix}` },
  ];

  return (
    <div className="flex flex-col gap-2">
      <PillRow
        fullWidth
        ariaLabel="Trades section"
        options={tabs.map((tab) => ({ label: tab.label, value: tab.key, href: tab.href }))}
        active={active}
      />
      <Link href="/trade-history" className="text-xs font-bold uppercase self-end" style={{ color: "var(--color-accent)" }}>
        Trade History →
      </Link>
    </div>
  );
}

import Link from "next/link";

/**
 * The Trade Hub / Trade Finder / Trade Analyzer tri-tab switcher — mirrors
 * app.py's TRADES_TAB_ROUTE_ORDER / TRADES_TAB_LABELS (the single segmented
 * control Streamlit shows above all three tabs, and mobile's
 * TradesScreen.tsx tab order: Trade Block / Search / Make a Trade). All
 * three tabs now have a real Next.js page (Trade Finder joined Trade Hub
 * and Trade Analyzer in Revision 17) — none of them deep-link out to
 * Streamlit anymore.
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
    <div
      role="tablist"
      aria-label="Trades section"
      className="flex flex-wrap gap-0"
      style={{ border: "var(--border-width-default) solid var(--color-border)" }}
    >
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        const style = {
          letterSpacing: "0.03em",
          background: isActive ? "var(--color-information-soft)" : "var(--color-surface-muted)",
          color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
          boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
          border: "var(--border-width-default) solid var(--color-border)",
          marginLeft: "-1px",
        } as const;
        return (
          <Link
            key={tab.key}
            href={tab.href}
            role="tab"
            aria-selected={isActive}
            className="px-3 py-2 text-xs font-bold uppercase"
            style={style}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}

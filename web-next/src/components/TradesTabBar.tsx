import Link from "next/link";

import { streamlitPageUrl } from "@/lib/streamlitLink";

/**
 * The Trade Hub / Trade Finder / Trade Analyzer tri-tab switcher — mirrors
 * app.py's TRADES_TAB_ROUTE_ORDER / TRADES_TAB_LABELS (the single segmented
 * control Streamlit shows above all three tabs, and mobile's
 * TradesScreen.tsx tab order: Trade Block / Search / Make a Trade). Trade
 * Hub and Trade Analyzer each have a real Next.js page now; Trade Finder
 * (mobile's player-focused trade-block search) is still Streamlit-only, so
 * its tab deep-links out instead of routing internally — same split
 * GamePlanCard.tsx's INTERNAL_ROUTES already draws elsewhere on this site.
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
  const tabs: { key: "trade_hub" | "trade_finder" | "trade_analyzer"; label: string; href: string; internal: boolean }[] = [
    { key: "trade_hub", label: "Trade Hub", href: `/trade-hub/${encodeURIComponent(leagueId)}${suffix}`, internal: true },
    { key: "trade_finder", label: "Trade Finder", href: streamlitPageUrl("trade_finder"), internal: false },
    {
      key: "trade_analyzer",
      label: "Trade Analyzer",
      href: `/trade-analyzer/${encodeURIComponent(leagueId)}${suffix}`,
      internal: true,
    },
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
        return tab.internal ? (
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
        ) : (
          <a
            key={tab.key}
            href={tab.href}
            role="tab"
            aria-selected={isActive}
            className="px-3 py-2 text-xs font-bold uppercase"
            style={style}
          >
            {tab.label}
          </a>
        );
      })}
    </div>
  );
}

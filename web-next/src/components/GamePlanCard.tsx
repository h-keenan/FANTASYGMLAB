"use client";

import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { BriefingItemPlayers } from "@/components/BriefingItemPlayers";
import {
  GAME_PLAN_INTERNAL_ROUTES,
  formatGamePlanCategory,
  gamePlanTileHref,
  resolveGamePlanTargetPlayerId,
} from "@/lib/gamePlanPresentation";
import { destinationCtaLabel } from "@/lib/destinationLabels";

/**
 * Ports modules/daily_gm_briefing_ui.py's Today's Game Plan card: kicker
 * (category), headline, reason, an explicit "Open X" CTA. The visible
 * "Open" button is a real <Link> here instead of app.py's `[data-route]`
 * div-click-delegation hack (see Dashboard research notes) — normal React
 * navigation is simpler and was explicitly called out as the reason to do
 * this natively rather than port the mechanism.
 *
 * coridian_, 2026-10-18: "you can just put them all under watch and then
 * have the micro player card... to make this much simpler and more
 * streamlined" — every non-top_priority item (Watch/Waiver Opportunity/
 * League Movement) now renders through WatchListCard's grouped sections
 * instead of its own full GamePlanCard (see DashboardContent.tsx's
 * item-partitioning). This component is Top Priority's full card only now.
 */

export function GamePlanCard({
  item,
  leagueId,
  leagueName,
}: {
  item: BriefingItem;
  /** Trade Hub now has a real Next.js page (see app/trade-hub/[leagueId]) —
   * a card whose destination is "trade_hub" links there internally instead
   * of Streamlit's `?page=` router. Every other destination is still
   * Streamlit-only for this revision. */
  leagueId: string;
  leagueName: string;
}) {
  const internalRoute = GAME_PLAN_INTERNAL_ROUTES[item.destination] ?? "dashboard";
  const copy = useExperienceCopy();
  return (
    <AccentCard accent="var(--color-accent)">
      <span
        className="uppercase"
        style={{
          font: "var(--type-badge-size)",
          letterSpacing: "var(--letter-spacing-badge)",
          color: "var(--color-accent)",
        }}
      >
        {formatGamePlanCategory(item.category)}
      </span>
      <h3 style={{ font: "var(--font-card-title)" }}>{item.headline}</h3>
      <p
        className="text-sm"
        style={{
          color: "var(--color-text-secondary)",
          ...(copy.isBeginner
            ? {}
            : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const, overflow: "hidden" }),
        }}
      >
        {item.reason}
      </p>
      <BriefingItemPlayers item={item} sourceLabel="GM Plan" />
      <Link
        href={gamePlanTileHref(internalRoute, leagueId, leagueName, resolveGamePlanTargetPlayerId(item))}
        className="tap-link self-start text-sm font-bold"
        style={{ color: "var(--color-accent)" }}
      >
        {destinationCtaLabel(item.destination)} →
      </Link>
    </AccentCard>
  );
}

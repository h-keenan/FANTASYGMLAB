import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { BriefingItemPlayers } from "@/components/BriefingItemPlayers";
import { GAME_PLAN_INTERNAL_ROUTES, formatGamePlanCategory } from "@/lib/gamePlanPresentation";
import { destinationCtaLabel, streamlitPageUrl } from "@/lib/streamlitLink";

/**
 * coridian_, 2026-10-18: "With these modules and other modules similar to
 * it, you can just put them all under watch and then have the micro player
 * card and then underneath that micro player card you can have usage
 * trending down and then you can have another micro player card and then
 * under that it can say injured or whatever, stuff like that, to make this
 * much simpler and more streamlined."
 *
 * Every Today's Game Plan item EXCEPT Top Priority (Watch, Waiver
 * Opportunity, League Movement, ...) used to render as its own full
 * GamePlanCard — same border, padding, and CTA as the headline trade card,
 * for what's usually a one-line signal + one or two player chips. This
 * groups all of them into one card instead: a small section per item
 * (category label + headline + its own compact CTA), separated by a
 * hairline rather than a full card boundary each. Top Priority keeps its
 * own full-card treatment in GamePlanCard — it's the single highest-
 * priority recommendation and still needs the room.
 */
export function WatchListCard({
  items,
  leagueId,
  leagueName,
}: {
  items: BriefingItem[];
  leagueId: string;
  leagueName: string;
}) {
  if (items.length === 0) return null;
  return (
    <article className="glass-surface flex flex-col" style={{ overflow: "hidden" }}>
      {items.map((item, index) => {
        const internalRoute = GAME_PLAN_INTERNAL_ROUTES[item.destination];
        return (
          <div
            key={item.recommendation_id || item.headline}
            className="flex flex-col gap-1 px-3 py-2.5"
            style={index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined}
          >
            <div className="flex items-center justify-between gap-2">
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
              {internalRoute ? (
                <Link
                  href={`/${internalRoute}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
                  className="text-xs font-bold shrink-0"
                  style={{ color: "var(--color-accent)" }}
                >
                  {destinationCtaLabel(item.destination)} →
                </Link>
              ) : (
                <a
                  href={streamlitPageUrl(item.destination)}
                  className="text-xs font-bold shrink-0"
                  style={{ color: "var(--color-accent)" }}
                >
                  {destinationCtaLabel(item.destination)} →
                </a>
              )}
            </div>
            <h4 style={{ font: "var(--font-card-title)" }}>{item.headline}</h4>
            <p
              className="text-sm"
              style={{
                color: "var(--color-text-secondary)",
                display: "-webkit-box",
                WebkitLineClamp: 1,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {item.reason}
            </p>
            <BriefingItemPlayers item={item} sourceLabel="GM Plan" />
          </div>
        );
      })}
    </article>
  );
}

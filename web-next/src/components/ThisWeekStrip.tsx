
import Link from "next/link";

import type { ThisWeek } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { thisWeekHref, thisWeekToneColor } from "@/lib/thisWeek";
import { ButtonLink } from "@/components/Button";
import { SkeletonBlock } from "@/components/Skeleton";

/**
 * The Dashboard's "This week" strip: up to three moves (lineup, waivers,
 * hold or trade), each with a one-line why from the server
 * (modules/this_week.py). Offseason, pre-draft and not-ready leagues get one
 * next action instead. A row with no real data is simply not sent.
 */
export function ThisWeekStrip({
  data,
  leagueId,
  leagueName,
  tradePending = false,
}: {
  data: ThisWeek;
  leagueId: string;
  leagueName: string;
  /** The progressive first Dashboard pass has no trade verdict yet: reserve
   * the trade row's space so the full response fills it without a layout jump. */
  tradePending?: boolean;
}) {
  const nextAction = data.next_action;
  if (!nextAction && data.rows.length === 0) return null;
  return (
    <section className="flex flex-col gap-3" aria-labelledby="this-week-heading" data-fgl-this-week="true">
      <SectionHeading id="this-week-heading">{data.week ? `This week · Week ${data.week}` : "This week"}</SectionHeading>
      {nextAction ? (
        <AccentCard accent="var(--color-accent)" compact>
          <h3 className="text-sm font-bold">{nextAction.headline}</h3>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {nextAction.why}
          </p>
          <ThisWeekCta label={nextAction.cta_label} href={thisWeekHref(nextAction.route, leagueId, leagueName)} />
        </AccentCard>
      ) : (
        <AccentCard accent="var(--color-accent)" compact>
          <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {data.rows.map((row, index) => {
              const color = thisWeekToneColor(row.tone);
              const body = (
                <>
                  <ToneBadge label={row.status} color={color} />
                  <span className="min-w-0 flex-1 flex flex-col">
                    <span className="text-sm font-bold truncate">{row.headline}</span>
                    <span
                      className="text-xs"
                      style={{
                        color: "var(--color-text-secondary)",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {row.why}
                    </span>
                  </span>
                  {row.cta_label && row.route ? (
                    <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                      →
                    </span>
                  ) : null}
                </>
              );
              const rowStyle = index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined;
              return (
                <li key={row.key} style={rowStyle}>
                  {row.cta_label && row.route ? (
                    <Link
                      href={thisWeekHref(row.route, leagueId, leagueName, row.player_id)}
                      aria-label={row.cta_label}
                      className="flex items-center gap-2 py-2.5"
                      style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}
                    >
                      {body}
                    </Link>
                  ) : (
                    <div className="flex items-center gap-2 py-2.5" style={{ minHeight: 44 }}>
                      {body}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </AccentCard>
      )}
      {tradePending && !nextAction && !data.rows.some((row) => row.key === "trade") ? (
        <SkeletonBlock height={64} data-fgl-this-week-trade-pending="true" />
      ) : null}
    </section>
  );
}

/** A link that looks like the shared primary Button (Button renders a
 * <button>, and a button inside a link is invalid), same tokens and sizing. */
function ThisWeekCta({ label, href }: { label: string; href: string }) {
  return (
    <ButtonLink
      href={href}
      size="sm"
      className="mt-1"
    >
      {label}
    </ButtonLink>
  );
}

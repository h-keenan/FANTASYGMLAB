"use client";

import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { ToneBadge } from "@/components/ToneBadge";
import { SectionHeading } from "@/components/SectionHeading";
import type { DashboardAttentionEntry } from "@/lib/dashboardLayout";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref, resolveGamePlanTargetPlayerId } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";

/**
 * "Needs attention": a compact list of the few urgent items, each one line with
 * one link to where it is handled. Urgency is read only from existing fields
 * (lib/dashboardLayout.ts buildNeedsAttention); the full plan stays on GM Plan.
 * Renders nothing when nothing is urgent.
 */
/** Where a "Needs attention" entry opens (shared by the card and the status header's player rows). */
export function attentionEntryHref(entry: DashboardAttentionEntry<BriefingItem>, leagueId: string, leagueName: string): string {
  const id = encodeURIComponent(leagueId);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  if (entry.target === "matchup") return thisWeekHref("matchup", leagueId, leagueName);
  if (entry.target === "gm_plan" || !entry.item) return `/gm-plan/${id}${query}`;
  const route = GAME_PLAN_INTERNAL_ROUTES[entry.item.destination] ?? "gm-plan";
  return gamePlanTileHref(route, leagueId, leagueName, resolveGamePlanTargetPlayerId(entry.item));
}

export function DashboardNeedsAttention({
  entries,
  leagueId,
  leagueName,
}: {
  entries: DashboardAttentionEntry<BriefingItem>[];
  leagueId: string;
  leagueName: string;
}) {
  if (entries.length === 0) return null;
  const hrefFor = (entry: DashboardAttentionEntry<BriefingItem>): string => attentionEntryHref(entry, leagueId, leagueName);
  return (
    <section className="flex flex-col gap-3" aria-labelledby="needs-attention-heading" data-testid="dashboard-needs-attention">
      <SectionHeading id="needs-attention-heading">
        Needs attention
      </SectionHeading>
      <AccentCard accent="var(--color-danger)" compact>
        <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {entries.map((entry, index) => (
            <li key={`${entry.source}-${index}`} style={index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined}>
              <Link
                href={hrefFor(entry)}
                className="flex items-center gap-2 py-2.5"
                style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}
              >
                <span className="min-w-0 flex-1 flex flex-col items-start gap-1">
                  <ToneBadge label={entry.badge} color="var(--color-danger)" />
                  <span className="text-sm font-bold break-words">{entry.headline}</span>
                  <span
                    className="text-xs"
                    style={{
                      color: "var(--color-text-secondary)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical" as const,
                      overflow: "hidden",
                    }}
                  >
                    {entry.why}
                  </span>
                </span>
                <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </AccentCard>
    </section>
  );
}

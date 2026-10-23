"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { importedPlatformLabel, notAvailableMessage } from "@/lib/leaguePlatform";

/**
 * Shown in place of a league page an ESPN league can't feed yet (see
 * lib/leaguePlatform.ts). Says so plainly and points at the pages that do
 * work, instead of loading a Sleeper-only page that would error or show
 * empty data.
 */
export function EspnUnavailableState({ leagueId }: { leagueId: string }) {
  const leagueName = useSearchParams()?.get("name") || "This league";
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const encodedId = encodeURIComponent(leagueId);
  const links = [
    { label: "My Team", href: `/my-team/${encodedId}${query}` },
    { label: "Trade Analyzer", href: `/trade-analyzer/${encodedId}${query}` },
    { label: "Players", href: `/players/${encodedId}${query}` },
    { label: "League Rankings", href: `/league-rankings/${encodedId}${query}` },
  ];
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 px-4 py-12 text-center">
      <div className="glass-surface w-full max-w-sm flex flex-col gap-3 p-5">
        <h1 style={{ font: "var(--font-card-title)" }}>{notAvailableMessage(leagueId)}</h1>
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {leagueName} is {importedPlatformLabel(leagueId) === "ESPN" ? "an" : "a"} {importedPlatformLabel(leagueId) || "ESPN"} league. This page needs league data FantasyDesk can only read from Sleeper so far.
          These pages work for it now:
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {links.map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="px-3 py-2 text-sm font-bold"
              style={{
                background: "var(--color-accent-strong)",
                color: "var(--color-brand-mark-ink)",
                fontWeight: "var(--font-weight-button)",
              }}
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}

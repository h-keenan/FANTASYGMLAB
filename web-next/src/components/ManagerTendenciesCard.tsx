"use client";

import { ButtonLink } from "@/components/Button";
import { useEffect, useState } from "react";

import { trackUse } from "@/lib/analytics";
import type { ManagerTendenciesSummaryResponse } from "@/lib/api";
import { findManagerRow, headlineChips, loadLeagueTendencies } from "@/lib/managerTendencies";

/**
 * Compact "How this manager trades" read for a trade partner: 2-3 chips from
 * the league tendencies summary (one cached request per league). Free users
 * get a one-line Premium link; no readable signals renders nothing.
 */
export function ManagerTendenciesCard({
  leagueId,
  rosterId,
  teamName,
}: {
  leagueId?: string;
  rosterId?: string | number;
  teamName?: string;
}) {
  const [data, setData] = useState<ManagerTendenciesSummaryResponse | null>(null);

  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    loadLeagueTendencies(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const row = data?.is_premium ? findManagerRow(data, { rosterId, teamName }) : null;
  const chips = headlineChips(row?.headline);
  const state = !data ? null : !data.is_premium ? "locked" : chips.length > 0 ? "chips" : null;
  useEffect(() => {
    if (state === "chips") trackUse("manager_tendencies", "viewed", { leagueId, tier: "pro" });
    else if (state === "locked") trackUse("manager_tendencies", "gate_seen", { leagueId, tier: "free" });
  }, [state, leagueId]);

  if (!data) return null;
  if (!data.is_premium) {
    return (
      <ButtonLink
        href="/premium"
        variant="premium"
        size="sm"
        onClick={() => trackUse("manager_tendencies", "upsell_tapped", { leagueId, tier: "free" })}
      >
        How this manager trades · Premium →
      </ButtonLink>
    );
  }
  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="How this manager trades">
      <span
        className="text-xs uppercase font-bold"
        style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        Trades
      </span>
      {chips.map((chip) => (
        <span
          key={chip}
          className="px-1.5 py-0.5 text-xs font-bold"
          style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
        >
          {chip}
        </span>
      ))}
    </div>
  );
}

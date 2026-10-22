"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { StatStrip } from "@/components/StatStrip";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type GuillotineResponse } from "@/lib/api";
import { guillotineView } from "@/lib/guillotine";

/** Fetches guillotine status for a league; null while loading, on error, or for normal leagues. */
export function useGuillotine(leagueId: string | undefined, lens: string = "Dynasty"): GuillotineResponse | null {
  const [data, setData] = useState<GuillotineResponse | null>(null);
  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    api
      .getGuillotine(leagueId, lens)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        /* the card renders nothing on failure */
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens]);
  return data;
}

const GLYPHS = ["record", "power", "franchise", "starter"] as const;

/** Survival card for guillotine leagues (replaces win probability). */
export function GuillotineCard({ data }: { data: GuillotineResponse | null }) {
  const view = guillotineView(data);
  if (!view) return null;
  const color = view.badge.tone === "success" ? "var(--color-success)" : "var(--color-danger)";
  return (
    <AccentCard accent={color} as="section" compact>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)" }}>
          Guillotine
        </span>
        <ToneBadge label={view.badge.label} color={color} />
      </div>
      <StatStrip
        columns={view.items.length > 3 ? 4 : 3}
        items={view.items.map((item, i) => ({ ...item, glyph: GLYPHS[i] }))}
      />
    </AccentCard>
  );
}

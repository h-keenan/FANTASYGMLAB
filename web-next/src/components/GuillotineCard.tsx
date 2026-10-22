"use client";

import { useEffect, useState } from "react";

import { PillRow } from "@/components/PillRow";
import { AccentCard } from "@/components/AccentCard";
import { StatStrip } from "@/components/StatStrip";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type GuillotineResponse } from "@/lib/api";
import { guillotineView } from "@/lib/guillotine";

/** Fetches guillotine status for a league; null while loading, on error, or for normal leagues. */
export function useGuillotine(leagueId: string | undefined, lens: string = "Dynasty"): GuillotineResponse | null {
  return useGuillotineState(leagueId, lens).data;
}

export function useGuillotineState(leagueId: string | undefined, lens: string = "Dynasty") {
  const [data, setData] = useState<GuillotineResponse | null>(null);
  const [nonce, setNonce] = useState(0);
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
  }, [leagueId, lens, nonce]);
  return { data, reload: () => setNonce((n) => n + 1) };
}

const TYPE_OPTIONS = [
  { label: "Auto", value: "auto" },
  { label: "Guillotine", value: "guillotine" },
  { label: "Standard", value: "standard" },
];

/** Manual league-type override (Auto / Guillotine / Standard). Hidden until status has loaded. */
export function LeagueTypeControl({
  leagueId,
  data,
  onChanged,
}: {
  leagueId: string;
  data: GuillotineResponse | null;
  onChanged: () => void;
}) {
  const [saving, setSaving] = useState(false);
  if (!data || !data.ok || data.league_type_override === undefined) return null;
  const select = (value: string) => {
    if (saving) return;
    setSaving(true);
    api
      .setLeagueType(leagueId, value as "guillotine" | "standard" | "auto")
      .then(onChanged)
      .catch(() => {})
      .finally(() => setSaving(false));
  };
  return (
    <section className="flex flex-col gap-1" aria-label="League type">
      <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
        League type
      </span>
      <PillRow options={TYPE_OPTIONS} active={data.league_type_override ?? "auto"} onSelect={select} />
    </section>
  );
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

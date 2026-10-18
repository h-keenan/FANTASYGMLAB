"use client";

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";

import { SUB_RATING_DISPLAY } from "@/lib/playerQuickViewPresentation";

type RadarRatings = Partial<Record<(typeof SUB_RATING_DISPLAY)[number]["key"], number | null>>;

/**
 * Market/Opportunity/Scarcity/Role/Durability as a 5-axis radar chart —
 * ports modules/player_quick_view.py's model_radar_chart_html (coridian_:
 * "it needs to be one of those multi-axis graphs where it shows the
 * multiple strengths of different attributes... like they have in RPGs").
 * Same SUB_RATING_DISPLAY 0-99 values SubRatingRow already renders as
 * chips — this is a second, visual representation of the identical real
 * numbers, not a new metric.
 *
 * Renders nothing unless all 5 ratings are present — a radar polygon needs
 * a real point on every axis to be an honest shape; a missing factor
 * plotted as 0 would read as "worst," not "no confident read," which is
 * exactly the fabrication this app's valuation code refuses to do
 * elsewhere (see OvrGauge's own docstring for the same principle). The
 * chip row stays the fallback for a player without a full Model read on
 * every factor — same split the Python source makes.
 */
export function ModelRadarChart({ model }: { model: RadarRatings }) {
  const data = SUB_RATING_DISPLAY.map(({ key, abbr }) => ({ abbr, value: model[key] }));
  if (data.some((point) => point.value == null)) return null;

  return (
    <div style={{ width: "100%", maxWidth: "15rem", height: 220, margin: "0 auto" }} aria-hidden="true">
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="var(--color-border)" />
          <PolarAngleAxis
            dataKey="abbr"
            tick={{ fill: "var(--color-text-muted)", fontSize: 10, fontWeight: 700 }}
          />
          <Radar
            dataKey="value"
            stroke="var(--color-accent-strong)"
            fill="var(--color-accent-strong)"
            fillOpacity={0.28}
            strokeWidth={1.5}
            dot={{ r: 2.5, fill: "var(--color-accent-strong)", strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
      {/* Visually-hidden text equivalent of the Python version's
          role="img" aria-label — recharts' SVG output isn't labeled the
          same way, so the chart itself stays aria-hidden above and this
          carries the accessible description instead. */}
      <span className="sr-only">
        Model attributes: {data.map((point) => `${point.abbr} ${point.value}`).join(", ")}
      </span>
    </div>
  );
}

import type { BriefingItem } from "@/lib/api";
import { destinationCtaLabel, streamlitPageUrl } from "@/lib/streamlitLink";
import { positionColorVar } from "@/lib/playerPresentation";

/**
 * Ports modules/daily_gm_briefing_ui.py's Today's Game Plan card: kicker
 * (category), headline, reason, an explicit "Open X" CTA. The visible
 * "Open" button is a real <Link> here instead of app.py's `[data-route]`
 * div-click-delegation hack (see Dashboard research notes) — normal React
 * navigation is simpler and was explicitly called out as the reason to do
 * this natively rather than port the mechanism.
 */
/** Backend categories are snake_case tokens (e.g. "top_priority") — title-case
 * them for display, matching Streamlit's kicker labels (Top Priority / Watch /
 * Waiver Opportunity / League Movement). */
function formatCategory(category: string): string {
  return category
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function GamePlanCard({ item }: { item: BriefingItem }) {
  const positionVar = positionColorVar(item.route_player_position);

  return (
    <article
      className="flex flex-col gap-2 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <span
        className="uppercase"
        style={{
          font: "var(--type-badge-size)",
          letterSpacing: "var(--letter-spacing-badge)",
          color: "var(--color-accent)",
        }}
      >
        {formatCategory(item.category)}
      </span>
      <h3 style={{ font: "var(--font-card-title)" }}>{item.headline}</h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {item.reason}
      </p>
      {item.route_player_name ? (
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {positionVar ? (
            <span
              className="px-1.5 py-0.5 font-bold"
              style={{ background: `var(${positionVar})`, color: "var(--color-brand-mark-ink)" }}
            >
              {item.route_player_position}
            </span>
          ) : null}
          <span>{item.route_player_name}</span>
          {item.route_player_team ? <span>· {item.route_player_team}</span> : null}
        </div>
      ) : null}
      <a
        href={streamlitPageUrl(item.destination)}
        className="self-start text-sm font-bold mt-1"
        style={{ color: "var(--color-accent)" }}
      >
        {destinationCtaLabel(item.destination)} →
      </a>
    </article>
  );
}

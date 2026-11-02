import type { UsageProfile } from "@/lib/api";
import {
  formatUsageDelta,
  formatUsageValue,
  hasUsageContent,
  usageDataNote,
} from "@/lib/usageProfilePresentation";

/** Usage block shared by Player Quick View and the full profile: rolling
 * last-4 / last-8 usage against the player's earlier games, role flags in plain
 * English, and the nflverse (CC BY 4.0) credit the data requires. Everything
 * shown is decided server-side (modules/usage_trends.py); mobile renders the
 * same payload in UsageBlock.tsx. */
export function PlayerUsageBlock({ profile }: { profile: UsageProfile | null | undefined }) {
  if (!hasUsageContent(profile)) return null;
  const note = profile.status === "ok" || profile.status === "building_sample" || profile.status === "low_usage" ? usageDataNote(profile) : null;
  return (
    <section className="pqv-usage" aria-labelledby="pqv-usage-heading" data-testid="usage-block">
      <h3 id="pqv-usage-heading">Usage</h3>
      {profile.status === "unavailable" ? (
        <p className="pqv-usage-note" role="status">
          Usage trends could not be calculated right now.
        </p>
      ) : null}
      {profile.flags.map((flag) => (
        <div key={flag.key} className={`pqv-usage-flag pqv-usage-flag--${flag.tone}`}>
          <span className={`pqv-chip pqv-chip--${flag.tone === "positive" ? "positive" : "danger"}`}>{flag.label}</span>
          <p>{flag.explanation}</p>
        </div>
      ))}
      {profile.flags.length === 0 && profile.status_note ? <p className="pqv-usage-note">{profile.status_note}</p> : null}
      {profile.metrics.length > 0 ? (
        <div className="pqv-usage-table" role="table" aria-label="Rolling usage">
          <div className="pqv-usage-row pqv-usage-row--head" role="row">
            <span role="columnheader">Metric</span>
            <span role="columnheader">Last 4</span>
            <span role="columnheader">Last 8</span>
            <span role="columnheader">Season</span>
          </div>
          {profile.metrics.map((metric) => (
            <div key={metric.key} className="pqv-usage-row" role="row">
              <span role="rowheader" className="pqv-usage-label">
                {metric.label}
                {metric.delta_last4_vs_prior != null ? (
                  <small className={`pqv-usage-delta pqv-usage-delta--${metric.direction}`}>
                    {formatUsageDelta(metric)} vs earlier
                  </small>
                ) : null}
              </span>
              <span role="cell">{formatUsageValue(metric, metric.last4)}</span>
              <span role="cell">{formatUsageValue(metric, metric.last8)}</span>
              <span role="cell">{formatUsageValue(metric, metric.season)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {note ? <p className="pqv-usage-note">{note}</p> : null}
      {profile.not_available?.length ? (
        <p className="pqv-usage-note">
          Not shown: {profile.not_available.map((item) => item.label).join(", ")}. No free data source we can use in a paid
          app publishes it.
        </p>
      ) : null}
      {profile.attribution ? (
        <p className="pqv-usage-credit" data-testid="usage-credit">
          <a href={profile.attribution.url} target="_blank" rel="noopener noreferrer">
            {profile.attribution.text}
          </a>
        </p>
      ) : null}
    </section>
  );
}

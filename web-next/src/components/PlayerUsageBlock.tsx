import { StatRowsCard } from "@/components/StatRows";
import type { UsageProfile } from "@/lib/api";
import { poolCaption, usageRows } from "@/lib/statRowsPresentation";
import { hasUsageContent, usageDataNote } from "@/lib/usageProfilePresentation";

/** Usage card shared by Player Quick View and the full profile: the role flag in
 * plain English, then the five usage numbers as the same percentile rows every
 * other stat uses (tap for the Percentile Explorer), each with its last-4 trend.
 * Everything is decided server-side (modules/usage_trends.py); mobile renders the
 * same payload in UsageBlock.tsx. */
export function PlayerUsageBlock({
  profile,
  position,
  playerId,
}: {
  profile: UsageProfile | null | undefined;
  position?: string | null;
  playerId?: string;
}) {
  if (!hasUsageContent(profile)) return null;
  const rows = usageRows(profile, position);
  const showNote = profile.status === "ok" || profile.status === "building_sample" || profile.status === "low_usage";
  const note = showNote ? usageDataNote(profile) : null;
  return (
    <div data-testid="usage-block">
      <StatRowsCard title="Usage" caption={rows.some((row) => row.percentile != null) && poolCaption(position, profile.season) ? `Percentile ${poolCaption(position, profile.season)}` : null} rows={rows} playerId={playerId} collapseAfter={5}>
        {profile.status === "unavailable" ? (
          <p className="sr-note" role="status">
            Usage trends could not be calculated right now.
          </p>
        ) : null}
        {profile.flags.map((flag) => (
          <div key={flag.key} className={`sr-flag sr-flag--${flag.tone}`}>
            <span className={`pqv-chip pqv-chip--${flag.tone === "positive" ? "positive" : "danger"}`}>{flag.label}</span>
            <p>{flag.explanation}</p>
          </div>
        ))}
        {profile.flags.length === 0 && profile.status_note ? <p className="sr-note">{profile.status_note}</p> : null}
      </StatRowsCard>
      {note ? <p className="sr-note sr-note--out">{note}</p> : null}
      {profile.not_available?.length ? (
        <p className="sr-note sr-note--out">
          Not shown: {profile.not_available.map((item) => item.label).join(", ")}. No free data source we can use in a paid app
          publishes it.
        </p>
      ) : null}
      {profile.attribution ? (
        <p className="sr-credit" data-testid="usage-credit">
          <a href={profile.attribution.url} target="_blank" rel="noopener noreferrer">
            {profile.attribution.text}
          </a>
        </p>
      ) : null}
    </div>
  );
}

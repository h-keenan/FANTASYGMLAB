import { ToneBadge } from "@/components/ToneBadge";
import type { MatchupWeatherNote, PlayerWeekWeather, WeatherStatus } from "@/lib/api";

const BADGE: Record<WeatherStatus, string> = {
  outdoor: "Weather",
  retractable: "Roof?",
  dome: "Dome",
  unavailable: "No data",
};

/**
 * Labeled status line stating WHY a projection is what it is weather-wise:
 * "Weather: heavy rain, 18 mph wind (outdoor) \u2192 passing outlook \u22126%",
 * "Dome: no weather effect", "Weather unavailable: no adjustment". Renders
 * nothing when there is no weather block. Mirrors
 * mobile/src/components/WeatherReasonChip.tsx.
 */
export function WeatherStatusLine({
  status,
  label,
  applied,
  player,
}: {
  status: WeatherStatus | null;
  label: string;
  applied: boolean;
  player?: string | null;
}) {
  const color = applied ? "var(--color-warning)" : "var(--color-information)";
  return (
    <li className="flex items-start gap-1.5 min-w-0">
      <ToneBadge label={BADGE[status ?? "outdoor"]} color={color} size="xs" />
      <span className="text-xs break-words min-w-0" style={{ color: "var(--color-text-secondary)" }}>
        {player ? `${player}: ` : ""}
        {label}
      </span>
    </li>
  );
}

export function WeatherReasonChip({ notes }: { notes: MatchupWeatherNote[] | null | undefined }) {
  if (!notes || notes.length === 0) return null;
  return (
    <ul className="flex flex-col gap-0.5 min-w-0" data-testid="weather-reason">
      {notes.map((note) => (
        <WeatherStatusLine key={`${note.role}-${note.player ?? ""}`} {...note} />
      ))}
    </ul>
  );
}

/** Single-projection variant (schedule rows). */
export function ProjectionWeatherChip({ weather }: { weather: PlayerWeekWeather | null | undefined }) {
  if (!weather) return null;
  return (
    <ul className="flex flex-col gap-0.5 min-w-0" data-testid="weather-reason">
      <WeatherStatusLine status={weather.status} label={weather.label} applied={weather.applied} />
    </ul>
  );
}

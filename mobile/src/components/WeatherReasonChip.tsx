import React from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import ToneBadge from './ToneBadge';
import type { MatchupWeatherNote, PlayerWeekWeather, WeatherStatus } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';

const BADGE: Record<WeatherStatus, string> = {
  outdoor: 'Weather',
  retractable: 'Roof?',
  dome: 'Dome',
  unavailable: 'No data',
  loading: 'Loading',
};

function StatusLine({
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
  const { colors } = useThemeMode();
  return (
    <View style={styles.row}>
      <ToneBadge label={BADGE[status ?? 'outdoor']} color={applied ? colors.warning : colors.accent} size="xs" />
      <AppText style={[styles.text, { color: colors.textSecondary }]}>
        {player ? `${player}: ` : ''}
        {label}
      </AppText>
    </View>
  );
}

/**
 * Labeled status stating WHY a projection is what it is weather-wise
 * ("Dome: no weather effect", "Weather unavailable: no adjustment", ...).
 * Renders nothing without a weather block. Mirrors web-next's WeatherReasonChip.
 */
export default function WeatherReasonChip({ notes }: { notes: MatchupWeatherNote[] | null | undefined }) {
  if (!notes || notes.length === 0) return null;
  return (
    <View style={styles.list} testID="weather-reason">
      {notes.map((note) => (
        <StatusLine key={`${note.role}-${note.player ?? ''}`} {...note} />
      ))}
    </View>
  );
}

/** Single-projection variant (schedule rows). */
export function ProjectionWeatherChip({ weather }: { weather: PlayerWeekWeather | null | undefined }) {
  if (!weather) return null;
  return (
    <View style={styles.list} testID="weather-reason">
      <StatusLine status={weather.status} label={weather.label} applied={weather.applied} />
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 2, marginTop: 2 },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
  text: { flex: 1, fontSize: 12, minWidth: 0 },
});

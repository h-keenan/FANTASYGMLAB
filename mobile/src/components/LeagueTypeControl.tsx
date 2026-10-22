import React, { useState } from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import SegmentedTabBar from './SegmentedTabBar';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type GuillotineResponse } from '../lib/api';

type LeagueType = 'auto' | 'guillotine' | 'standard';

const OPTIONS: Array<{ key: LeagueType; label: string }> = [
  { key: 'auto', label: 'Auto' },
  { key: 'guillotine', label: 'Guillotine' },
  { key: 'standard', label: 'Standard' },
];

/** Manual league-type override (Auto / Guillotine / Standard). Hidden until status has loaded. */
export default function LeagueTypeControl({
  leagueId,
  data,
  onChanged,
}: {
  leagueId: string;
  data: GuillotineResponse | null | undefined;
  onChanged: () => void;
}) {
  const { colors } = useThemeMode();
  const [saving, setSaving] = useState(false);
  if (!data || !data.ok || data.league_type_override === undefined) return null;
  const select = (key: LeagueType) => {
    if (saving) return;
    setSaving(true);
    api
      .setLeagueType(leagueId, key)
      .then(onChanged)
      .catch(() => {})
      .finally(() => setSaving(false));
  };
  return (
    <View style={{ gap: 6 }}>
      <AppText style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>League type</AppText>
      <SegmentedTabBar options={OPTIONS} active={data.league_type_override ?? 'auto'} onChange={select} />
    </View>
  );
}

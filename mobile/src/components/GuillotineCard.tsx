import React from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import StatStrip from './StatStrip';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { GuillotineResponse } from '../lib/api';
import { guillotineView } from '../lib/guillotine';

/** Survival card for guillotine leagues (replaces win probability). Renders nothing otherwise. */
export default function GuillotineCard({ data }: { data: GuillotineResponse | null | undefined }) {
  const { colors } = useThemeMode();
  const view = guillotineView(data);
  if (!view) return null;
  const color = view.badge.tone === 'success' ? colors.successBright : colors.danger;
  return (
    <AccentCard accent={color} compact>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <AppText style={{ fontSize: 11, fontWeight: '800', color: colors.textTertiary, textTransform: 'uppercase' }}>
          Guillotine
        </AppText>
        <ToneBadge label={view.badge.label} color={color} />
      </View>
      <StatStrip items={view.items} fullWidth />
    </AccentCard>
  );
}

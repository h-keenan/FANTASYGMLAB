import React from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import { SimSheet } from './SimGameParts';
import type { PickTapRef } from './PlayerOpenContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { simParsePickId } from '../lib/simGame';

/**
 * The pick detail every tapped pick opens inside Fantasy Sim (trade offers, the builder, the block, the team sheet).
 * Twin of web components/SimPickSheet.tsx.
 */
export function SimPickSheet({ pick, onClose }: { pick: PickTapRef; onClose: () => void }) {
  const { colors } = useThemeMode();
  const parsed = simParsePickId(pick.id);
  return (
    <SimSheet title={pick.label} onClose={onClose}>
      <View style={{ gap: 8 }} testID="sim-pick-detail">
        {parsed ? (
          <AppText style={{ fontSize: 14, color: colors.textPrimary }}>
            <AppText style={{ fontWeight: '800' }}>Round {parsed.round}</AppText> of the {parsed.season} draft.
          </AppText>
        ) : null}
        {pick.detail ? <AppText style={{ fontSize: 14, color: colors.textSecondary }}>{pick.detail}</AppText> : null}
        <AppText style={{ fontSize: 12, color: colors.textTertiary }}>
          A pick turns into a rookie when its draft runs. Early picks are the valuable ones; the slot is set by the final standings of the season before.
        </AppText>
      </View>
    </SimSheet>
  );
}

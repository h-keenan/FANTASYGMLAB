import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimStoryEntry } from '../lib/simGame';
import { simStoryGroups, simStorySummaryParts, simStoryToneKey, simStoryWhen } from '../lib/simStory';
import { spacing, type ThemeColors } from '../theme';

/**
 * "What is this guy's story?" in a Fantasy Sim player's quick view: a plain-language timeline per season (his depth slot
 * and why he moved, injuries and games missed, trades, big seasons and busts), derived on the server from the game's
 * event log. Open by default so the answer is on screen. Twin of web's SimPlayerStory.
 */
export function SimPlayerStory({ story }: { story: readonly SimStoryEntry[] | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const parts = simStorySummaryParts(story);
  if (parts.length === 0) return null;
  const tone = { success: colors.success, danger: colors.danger, muted: colors.textTertiary } as const;
  return (
    <CompactModule id="simpqv.story" title="Story" label="Player story" parts={parts} tone="accent" defaultOpen testID="sim-player-story">
      <View style={styles.stack}>
        {simStoryGroups(story).map((group) => (
          <View key={group.key} style={styles.group} accessibilityLabel={group.label}>
            <AppText style={styles.heading}>{group.label}</AppText>
            {group.entries.map((e, i) => (
              <View key={i} style={styles.line} testID="sim-story-line">
                <AppText style={styles.when}>{simStoryWhen(e)}</AppText>
                <AppText style={[styles.text, e.kind === 'season' ? styles.strong : null, e.tone === 'neutral' ? null : { color: tone[simStoryToneKey(e.tone)] }]}>{e.text}</AppText>
              </View>
            ))}
          </View>
        ))}
      </View>
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md },
    group: { gap: 4 },
    heading: { fontSize: 12, fontWeight: '800', color: colors.textSecondary },
    line: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
    when: { width: 64, fontSize: 12, color: colors.textTertiary, fontVariant: ['tabular-nums'] },
    text: { flex: 1, fontSize: 14, color: colors.textPrimary },
    strong: { fontWeight: '800' },
  });
}

export default SimPlayerStory;

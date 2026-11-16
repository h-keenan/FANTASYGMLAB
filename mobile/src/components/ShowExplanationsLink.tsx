import React, { useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { useExperienceLevel } from '../context/ExperienceLevelContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { PLAIN_COPY } from '../lib/experienceCopy';
import type { ThemeColors } from '../theme';

/**
 * "Show explanations": the in-context way back for someone who chose Veteran and then wants a term explained. Writes
 * the same preference as More > Explanations (`setLevel('beginner')`). Renders nothing once the level is already a
 * beginner one. Twin of web-next's components/ShowExplanationsLink.tsx.
 */
export default function ShowExplanationsLink() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { level, setLevel } = useExperienceLevel();
  const [done, setDone] = useState(false);
  if (done) return <AppText style={styles.done}>{PLAIN_COPY.showExplanationsDone}</AppText>;
  if (level === 'beginner' || level === 'new_to_fantasy') return null;
  return (
    <PressableScale
      accessibilityRole="button"
      onPress={() => {
        setLevel('beginner');
        setDone(true);
      }}
      style={styles.link}
      testID="show-explanations"
    >
      <AppText style={styles.linkText}>{PLAIN_COPY.showExplanationsAction}</AppText>
    </PressableScale>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    link: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    linkText: { fontSize: 14.5, fontWeight: '700', color: colors.accent, textDecorationLine: 'underline' },
    done: { fontSize: 13.5, color: colors.textTertiary },
  });
}

import React from 'react';
import { type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import { useThemeMode } from '../context/ThemeModeContext';
import type { BeginnerHelpKey } from '../lib/experienceCopy';
import { typography } from '../theme';

/**
 * Plain-language helper line for a beginner (onboarding experience level),
 * mirroring web-next's BeginnerHelp. Renders nothing for advanced or unset
 * accounts, so a screen can drop it next to a term without its own
 * conditional. Pass `term` for a fixed BEGINNER_HELP entry, or `text` for a
 * value already resolved via the same copy helpers (copy.verdictHelp(), ...).
 */
export default function BeginnerHelp({
  term,
  text,
  style,
}: {
  term?: BeginnerHelpKey;
  text?: string | null;
  style?: StyleProp<TextStyle>;
}) {
  const copy = useExperienceCopy();
  const { colors } = useThemeMode();
  const resolved = text !== undefined ? (copy.isBeginner ? text : null) : term ? copy.help(term) : null;
  if (!resolved) return null;
  return (
    <AppText style={[typography.caption, { color: colors.textTertiary, lineHeight: 15 }, style]}>{resolved}</AppText>
  );
}

import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useState } from 'react';
import { Pressable, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import { useThemeMode } from '../context/ThemeModeContext';
import type { BeginnerHelpKey } from '../lib/experienceCopy';
import { typography } from '../theme';

const SEEN_PREFIX = 'fd-help-seen:';

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
  seenOnce = false,
}: {
  term?: BeginnerHelpKey;
  text?: string | null;
  style?: StyleProp<TextStyle>;
  /** First-visit line: shows a "Got it" that hides this exact line for good (same fd-help-seen: key as web). */
  seenOnce?: boolean;
}) {
  const copy = useExperienceCopy();
  const { colors } = useThemeMode();
  const resolved = text !== undefined ? (copy.showsHelp ? text : null) : term ? copy.help(term) : null;
  // null = storage not read yet (render nothing so a seen line never flashes).
  const [seen, setSeen] = useState<boolean | null>(seenOnce ? null : false);
  useEffect(() => {
    if (!seenOnce || !resolved) return;
    let cancelled = false;
    AsyncStorage.getItem(SEEN_PREFIX + resolved)
      .then((raw) => {
        if (!cancelled) setSeen(raw === '1');
      })
      .catch(() => {
        if (!cancelled) setSeen(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seenOnce, resolved]);
  if (!resolved || seen !== false) return null;
  const text_ = (
    <AppText style={[typography.caption, { color: colors.textTertiary, lineHeight: 15 }, style]}>{resolved}</AppText>
  );
  if (!seenOnce) return text_;
  return (
    <>
      {text_}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Got it, hide this explanation"
        hitSlop={8}
        onPress={() => {
          setSeen(true);
          AsyncStorage.setItem(SEEN_PREFIX + resolved, '1').catch(() => {});
        }}
        style={{ minHeight: 44, justifyContent: 'center' }}
      >
        <AppText style={[typography.caption, { color: colors.accent, fontWeight: '700' }]}>Got it</AppText>
      </Pressable>
    </>
  );
}

import React, { useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { Sheet } from './Sheet';
import ShowExplanationsLink from './ShowExplanationsLink';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { trackUse } from '../lib/analytics';
import { GLOSSARY, type GlossaryKey } from '../lib/glossary';
import { whyEntry, type WhyMetricId } from '../lib/tapForWhyContent';
import { spacing, type ThemeColors } from '../theme';

export type InfoMarkLegendItem = { label: string; color: string; description: string };

export type InfoMarkProps = {
  /** REQUIRED name of what the "?" explains ("this matchup", "Roster Power"). Accessible name is "About <label>"; it is also the sheet heading unless `title` is set. */
  label: string;
  title?: string;
  /** Plain sentences (nullish entries are dropped). */
  lines?: ReadonlyArray<string | null | undefined>;
  /** Registry entries (lib/tapForWhyContent.ts), one block per metric. */
  metrics?: readonly WhyMetricId[];
  /** Glossary terms (lib/glossary.ts) as definitions. */
  glossary?: readonly GlossaryKey[];
  /** Coloured term/definition rows. */
  legend?: readonly InfoMarkLegendItem[];
  /** Free-form body after the structured content. */
  children?: ReactNode;
  /** Render only for accounts that show beginner help (experience level), still through this same "?". */
  beginnerOnly?: boolean;
  testID?: string;
};

/**
 * Twin of web-next's components/ui/InfoMark.tsx: THE "?" (UI audit batch A). Inline directly after the label or heading it
 * explains (MetricCard `labelAccessory`, a module title row, ScreenHeader `info`), never its own row, never over text. 18pt glyph box
 * with a 12pt glyph (font floor) and a 44pt hit area from hitSlop, so the layout does not grow. At most one per module: several terms
 * go in one sheet through `lines` / `metrics` / `glossary` / `legend`. Retired: ScreenInfoNote, GlossaryNote, BeginnerHelp paragraphs
 * (scripts/check_info_mark_usage.mjs keeps them gone).
 */
export default function InfoMark({ label, title, lines, metrics, glossary, legend, children, beginnerOnly = false, testID }: InfoMarkProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const copy = useExperienceCopy();
  const [open, setOpen] = useState(false);
  if (beginnerOnly && !copy.showsHelp) return null;
  const sentences = (lines ?? []).filter((line): line is string => Boolean(line));
  const hasContent = sentences.length > 0 || (metrics?.length ?? 0) > 0 || (glossary?.length ?? 0) > 0 || (legend?.length ?? 0) > 0 || children != null;
  if (!hasContent) return null;
  const multiBlock = (metrics?.length ?? 0) + (glossary?.length ?? 0) + (legend?.length ?? 0) > 1;
  return (
    <>
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={`About ${label}`}
        accessibilityHint="Opens a short explanation"
        accessibilityState={{ expanded: open }}
        hitSlop={13}
        onPress={() => {
          setOpen(true);
          trackUse('info_mark', 'opened');
        }}
        style={styles.mark}
        testID={testID ?? 'info-mark'}
      >
        <AppText style={styles.glyph} allowFontScaling={false}>
          ?
        </AppText>
      </PressableScale>
      <Sheet open={open} onClose={() => setOpen(false)} title={title ?? label} size="sm" testID={testID ? `${testID}-sheet` : undefined}>
        <View style={styles.body}>
          {sentences.map((line) => (
            <AppText key={line} style={styles.sentence}>
              {line}
            </AppText>
          ))}
          {(metrics ?? []).map((id) => {
            const entry = whyEntry(id);
            return (
              <View key={id} style={styles.term}>
                {multiBlock || sentences.length > 0 ? <AppText style={styles.termTitle}>{entry.title}</AppText> : null}
                {entry.sentences.map((sentence) => (
                  <AppText key={sentence} style={styles.sentence}>
                    {sentence}
                  </AppText>
                ))}
              </View>
            );
          })}
          {(glossary ?? []).map((key) => (
            <View key={key} style={styles.term}>
              <AppText style={styles.termTitle}>{GLOSSARY[key].label}</AppText>
              <AppText style={styles.sentence}>{GLOSSARY[key].definition}</AppText>
            </View>
          ))}
          {(legend ?? []).map((item) => (
            <View key={item.label} style={styles.term}>
              <AppText style={[styles.termTitle, { color: item.color }]}>{item.label}</AppText>
              <AppText style={styles.sentence}>{item.description}</AppText>
            </View>
          ))}
          {children != null ? <View>{children}</View> : null}
          <ShowExplanationsLink />
        </View>
      </Sheet>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    mark: { width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center', marginLeft: 6, flexShrink: 0 },
    glyph: { fontSize: 13, lineHeight: 16, fontWeight: '800', color: colors.textTertiary, includeFontPadding: false, textAlign: 'center' },
    body: { gap: spacing.md },
    term: { gap: 2 },
    termTitle: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    sentence: { fontSize: 15, lineHeight: 22, color: colors.textSecondary },
  });
}

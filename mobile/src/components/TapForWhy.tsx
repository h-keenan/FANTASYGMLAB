import React, { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import PressableScale from './PressableScale';

import AppText from './AppText';
import { Sheet } from './Sheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { trackUse } from '../lib/analytics';
import { whyEntry, whyTriggerLabel, type WhyMetricId } from '../lib/tapForWhyContent';
import { spacing, type ThemeColors } from '../theme';

const TapForWhyOffContext = createContext(false);

/** Turns every TapForWhy underneath into plain, untappable content (Fantasy Sim's trade window: a stat pill must never open a sheet over the trade). Twin of web's TapForWhyOff. */
export function TapForWhyOff({ children }: { children: ReactNode }) {
  return <TapForWhyOffContext.Provider value>{children}</TapForWhyOffContext.Provider>;
}

export type TapForWhyProps = {
  /** Registry key (lib/tapForWhyContent.ts), the same table web uses. */
  metric: WhyMetricId;
  /** The thing being explained, rendered unchanged. */
  children: ReactNode;
  /** What a screen reader hears: "Why: Value 82". Default: "Why: <entry title>". */
  spoken?: string;
  /** Layout hint, same names as web. Only changes the pressed treatment's shape. */
  variant?: 'inline' | 'chip' | 'tile';
  title?: string;
  /** Mini chart or detail under the explanation. Rendered only while the sheet is open. */
  chart?: ReactNode;
  /** Extra plain sentences for this instance, after the registry copy. */
  extra?: readonly string[];
  /** Shows the registry's "learn more" link when set (the caller owns navigation, so it can close its own modal first). */
  onLearnMore?: () => void;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/**
 * Twin of web-next's components/ui/TapForWhy.tsx. Makes any number, chip,
 * badge or grade tappable: the child renders unchanged inside a button
 * (44pt hit area via hitSlop, so the layout does not grow), with a pressed
 * state and no resting decoration, and opens a small Sheet with the
 * registry's 1-3 sentences, an optional chart slot and a learn-more link.
 * Fires a `why_<metric>` usage event.
 */
export default function TapForWhy({ metric, children, spoken, variant = 'inline', title, chart, extra, onLearnMore, style, testID }: TapForWhyProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const off = useContext(TapForWhyOffContext);
  const entry = whyEntry(metric);
  const sentences = [...entry.sentences, ...(extra ?? [])];
  if (off) return <>{children}</>;
  return (
    <>
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={whyTriggerLabel(metric, spoken)}
        accessibilityHint="Opens a short explanation"
        accessibilityState={{ expanded: open }}
        hitSlop={10}
        onPress={() => {
          setOpen(true);
          trackUse(`why_${metric}`, 'opened');
        }}
        style={[variant === 'tile' && styles.tile, style]}
        testID={testID}
      >
        {children}
      </PressableScale>
      <Sheet open={open} onClose={() => setOpen(false)} title={title ?? entry.title} size="sm" testID={testID ? `${testID}-sheet` : undefined}>
        <View style={styles.body}>
          {sentences.map((sentence) => (
            <AppText key={sentence} style={styles.sentence}>
              {sentence}
            </AppText>
          ))}
          {chart ? <View style={styles.chart}>{chart}</View> : null}
          {onLearnMore && entry.learnMoreHref ? (
            <PressableScale
              accessibilityRole="link"
              onPress={() => {
                setOpen(false);
                onLearnMore();
              }}
              style={styles.learn}
            >
              <AppText style={styles.learnText}>{entry.learnMoreLabel ?? 'Learn more'}</AppText>
            </PressableScale>
          ) : null}
        </View>
      </Sheet>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    tile: { alignSelf: 'stretch' },
    body: { gap: spacing.md },
    sentence: { fontSize: 15, lineHeight: 22, color: colors.textSecondary },
    chart: { paddingVertical: spacing.sm },
    learn: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    learnText: { fontSize: 14.5, fontWeight: '700', color: colors.accent },
  });
}

import React, { useMemo, useState, type ReactNode } from 'react';
import { LetterGrade } from './LetterGrade';
import { simGradeIndex, type SimGradeLetter } from '../lib/simGrade';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { RecapCardModel, RecapCardRow, RecapTone } from '../lib/recapCard';
import { spacing, type ThemeColors } from '../theme';

/**
 * THE recap card (mirrors web-next/src/components/ui/RecapCard.tsx): a glass card with the page kicker, an optional
 * grade/finish badge and three label/value rows; extra rows open under "More". Used on the recap story pages and the
 * Season in Review stats. The badge uses the accent, never gold.
 */
function toneColor(tone: RecapTone | undefined, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    default: return colors.textPrimary;
  }
}

function Row({ row, extra }: { row: RecapCardRow; extra?: ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.row} testID="recap-card-row">
      <View style={styles.rowTop}>
        <AppText style={styles.label}>{row.label}</AppText>
        <AppText style={[styles.value, { color: toneColor(row.tone, colors) }]}>{row.value}</AppText>
      </View>
      {row.sub ? <AppText style={styles.sub}>{row.sub}</AppText> : null}
      {extra}
    </View>
  );
}

export default function RecapCard({ model, extras, testID = 'recap-card' }: { model: RecapCardModel; /** Extra node under a row, by row key (a player chip). */ extras?: Record<string, ReactNode>; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  return (
    <AccentCard accent={colors.accent} compact>
      <View testID={testID} style={styles.stack}>
        <View style={styles.head}>
          <AppText style={styles.kicker}>{model.kicker}</AppText>
          {model.badge && simGradeIndex(model.badge) >= 0 ? (
            <LetterGrade grade={{ grade: model.badge as SimGradeLetter }} size="sm" />
          ) : model.badge ? (
            <View style={styles.badge} testID="recap-card-badge">
              <AppText style={styles.badgeText}>{model.badge}</AppText>
            </View>
          ) : null}
        </View>
        <View style={styles.stack}>
          {model.rows.map((row) => (
            <Row key={row.key} row={row} extra={extras?.[row.key]} />
          ))}
        </View>
        {model.more.length > 0 ? (
          <>
            <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen(!open)} style={styles.moreBtn}>
              <AppText style={styles.moreText}>{open ? 'Less' : `More (${model.more.length})`}</AppText>
            </Pressable>
            {open ? (
              <View style={[styles.stack, styles.moreBody]}>
                {model.more.map((row) => (
                  <Row key={row.key} row={row} extra={extras?.[row.key]} />
                ))}
              </View>
            ) : null}
          </>
        ) : null}
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.sm },
    head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.accent },
    badge: { minWidth: 36, height: 30, paddingHorizontal: 8, alignItems: 'center', justifyContent: 'center', borderRadius: 15, borderWidth: 1.5, borderColor: colors.accent, backgroundColor: colors.accentMuted },
    badgeText: { fontSize: 14, fontWeight: '800', color: colors.accent },
    row: { gap: 4 },
    rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    label: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    value: { flexShrink: 1, textAlign: 'right', fontSize: 14, fontWeight: '800' },
    sub: { textAlign: 'right', fontSize: 12.5, color: colors.textTertiary },
    moreBtn: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    moreText: { fontSize: 13, fontWeight: '700', color: colors.accent },
    moreBody: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 },
  });
}

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, typography, type ThemeColors } from '../theme';

export interface ContentSection {
  title: string;
  paragraphs: string[];
  bullets: string[];
}

/**
 * A handful of bullets in the source content already read as a
 * "label — description" or "Label (44%): description" pair (Privacy's
 * account-action bullets, the FAQ's Q — A pairs, How We Evaluate's weighted
 * factor list). Bolding the lead-in makes those scannable the way a metric
 * label/value pair is (Magna Carta §10/§26) without touching a single word
 * of the copy — this only ever changes *which existing characters* render
 * bold, never the characters themselves.
 *
 * Deliberately conservative so it never misfires on a plain sentence that
 * happens to contain a colon or dash: a "label:" lead-in only counts within
 * the first 70 characters (every real label in the content is well under
 * that — "Availability (applied on top, not a weight):" is the longest at
 * 44), and a "label —" lead-in only counts if it's short (<=40 chars) or
 * ends in "?" (an FAQ question) — long asides like "...related tools — not
 * identical answers." fall through untouched and render as plain text.
 */
function splitBulletLeadIn(text: string): { lead: string; sep: string; rest: string } | null {
  const colonIdx = text.indexOf(': ');
  if (colonIdx > 0 && colonIdx <= 70) {
    return { lead: text.slice(0, colonIdx), sep: ': ', rest: text.slice(colonIdx + 2) };
  }
  const dashIdx = text.indexOf(' — ');
  if (dashIdx > 0) {
    const lead = text.slice(0, dashIdx);
    if (lead.length <= 40 || lead.endsWith('?')) {
      return { lead, sep: ' — ', rest: text.slice(dashIdx + 3) };
    }
  }
  return null;
}

/** Shared renderer for static prose pages (Legal, How We Evaluate) that
 * ship as generator-backed JSON — see scripts/export_legal_content.py and
 * scripts/export_methodology_content.py. */
export default function ContentSections({ sections }: { sections: ContentSection[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
      {sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <AppText style={styles.sectionTitle}>{section.title}</AppText>
          {section.paragraphs.map((paragraph) => (
            <AppText key={paragraph} style={styles.paragraph}>
              {paragraph}
            </AppText>
          ))}
          {section.bullets.map((bullet) => {
            const split = splitBulletLeadIn(bullet);
            return (
              <View key={bullet} style={styles.bulletRow}>
                <AppText style={styles.bulletMark}>{'•'}</AppText>
                <AppText style={styles.bulletText}>
                  {split ? (
                    <>
                      <AppText style={styles.bulletLead}>{split.lead}</AppText>
                      {split.sep}
                      {split.rest}
                    </>
                  ) : (
                    bullet
                  )}
                </AppText>
              </View>
            );
          })}
        </View>
      ))}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { marginBottom: spacing.xl },
    sectionTitle: {
      fontSize: 17,
      fontWeight: '700',
      color: colors.textPrimary,
      marginBottom: spacing.sm,
    },
    paragraph: {
      ...typography.body,
      color: colors.textPrimary,
      lineHeight: 23,
      marginBottom: spacing.sm,
    },
    bulletRow: { flexDirection: 'row', marginBottom: spacing.sm, paddingLeft: spacing.xs },
    bulletMark: { color: colors.textSecondary, marginRight: spacing.sm },
    bulletText: { flex: 1, ...typography.body, color: colors.textPrimary, lineHeight: 22 },
    bulletLead: { fontWeight: '700' },
  });
}

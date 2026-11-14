import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import BrandMark from './BrandMark';
import { Sheet } from './Sheet';
import TabIcon from './TabIcon';
import { useThemeMode } from '../context/ThemeModeContext';
import { activeBottomTab, bottomTabBadgeText, simGameBottomTabs, simOrbAriaLabel, SIM_NAV_META } from '../lib/bottomNav';
import { requestOrbSearch } from '../lib/orbEvents';
import type { SimTab } from '../lib/simGameFlow';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The Fantasy Sim's own navigation orb. Replaces the global GM orb inside the
 * game: same brand mark, but it names the page you are on and carries a badge
 * for pending trade offers. One tap opens the game navigator (Home, Team,
 * Players, Trades, League, More) with the current page marked, plus search,
 * All games and a way back to the app home. Mirrors web-next's SimGameOrb;
 * the screen places it in the action bar's one row (Sim to | orb | Advance), and the menu rows reuse the More sheet look (tinted glyph over label + subtitle).
 */
export default function SimGameOrb({
  tab,
  offseason,
  inbox,
  onTab,
  onMore,
  onHub,
  onAppHome,
}: {
  tab: SimTab;
  offseason: boolean;
  inbox: number;
  onTab: (tab: SimTab) => void;
  onMore: () => void;
  onHub: () => void;
  onAppHome: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const tabs = simGameBottomTabs({ offseason, inbox });
  const current = activeBottomTab(tabs, tab);
  const currentTab = tabs.find((t) => t.key === current) ?? tabs[0];
  const badge = bottomTabBadgeText(inbox);
  const close = () => setOpen(false);
  const toneColor = (key: string) => colors[SIM_NAV_META[key]?.tone ?? 'accent'];

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={simOrbAriaLabel(currentTab.label, inbox)}
        accessibilityHint="Opens the game navigator"
        style={styles.orb}
        hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
        testID="sim-game-orb"
      >
        <BrandMark width={22} height={15} />
        <AppText style={styles.label} importantForAccessibility="no" accessibilityElementsHidden>{currentTab.label}</AppText>
        {badge ? (
          <View style={[styles.badge, styles.orbBadge]} testID="sim-game-orb-badge" importantForAccessibility="no" accessibilityElementsHidden>
            <AppText style={styles.badgeText}>{badge}</AppText>
          </View>
        ) : null}
      </Pressable>
      <Sheet open={open} onClose={close} title="Fantasy Sim" description="Jump to any page of this game.">
        <View style={styles.list} accessibilityLabel="Game pages">
          {tabs.map((t) => {
            const count = bottomTabBadgeText(t.badge);
            const isCurrent = t.key === current;
            return (
              <Pressable
                key={t.key}
                onPress={() => {
                  close();
                  onTab(t.key as SimTab);
                }}
                accessibilityRole="button"
                accessibilityState={{ selected: isCurrent }}
                accessibilityLabel={isCurrent ? `${t.label}, current page` : t.badge ? `${t.label}, ${t.badge} new` : t.label}
                style={[styles.row, isCurrent && styles.rowCurrent]}
              >
                <TabIcon name={t.glyph} color={toneColor(t.key)} size={22} />
                <View style={styles.rowText}>
                  <AppText style={[styles.rowLabel, isCurrent && { color: colors.accent }]}>{t.label}</AppText>
                  <AppText style={styles.rowSub} numberOfLines={1}>{SIM_NAV_META[t.key]?.subtitle}</AppText>
                </View>
                {count ? (
                  <View style={styles.badge} importantForAccessibility="no" accessibilityElementsHidden>
                    <AppText style={styles.badgeText}>{count}</AppText>
                  </View>
                ) : null}
              </Pressable>
            );
          })}
          <Pressable
            onPress={() => {
              close();
              onMore();
            }}
            accessibilityRole="button"
            accessibilityLabel="More: rules, reset the week, or leave this game"
            style={styles.row}
          >
            <TabIcon name="more" color={colors.accent} size={22} />
            <View style={styles.rowText}>
              <AppText style={styles.rowLabel}>More</AppText>
              <AppText style={styles.rowSub} numberOfLines={1}>{SIM_NAV_META.more.subtitle}</AppText>
            </View>
          </Pressable>
        </View>
        <View style={styles.footer}>
          <Pressable
            onPress={() => {
              close();
              setTimeout(requestOrbSearch, 250);
            }}
            accessibilityRole="button"
            accessibilityLabel="Search players and pages"
            style={styles.row}
          >
            <Ionicons name="search-outline" size={22} color={colors.accent} />
            <AppText style={styles.rowLabel}>Search players and pages</AppText>
          </Pressable>
          <Pressable
            onPress={() => {
              close();
              onHub();
            }}
            accessibilityRole="button"
            accessibilityLabel="All games"
            style={styles.row}
          >
            <TabIcon name="league" color={colors.premium} size={22} />
            <AppText style={styles.rowLabel}>All games</AppText>
          </Pressable>
          <Pressable
            onPress={() => {
              close();
              onAppHome();
            }}
            accessibilityRole="button"
            accessibilityLabel="Back to FantasyDesk home"
            style={styles.row}
          >
            <TabIcon name="home" color={colors.accent} size={22} />
            <AppText style={styles.rowLabel}>Back to FantasyDesk home</AppText>
          </Pressable>
        </View>
      </Sheet>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    orb: {
      width: 48,
      height: 48,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 1,
      borderRadius: 24,
      borderWidth: 1.5,
      borderColor: colors.accent,
      backgroundColor: colors.backgroundElevated,
    },
    label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.2, textTransform: 'uppercase', color: colors.accent },
    badge: {
      minWidth: 18,
      height: 18,
      paddingHorizontal: 5,
      borderRadius: 9,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.accent,
    },
    badgeText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
    orbBadge: { position: 'absolute', top: -4, right: -4 },
    list: { gap: spacing.xs },
    footer: { marginTop: spacing.sm, paddingTop: spacing.sm, gap: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    row: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.md, borderRadius: radii.md },
    rowCurrent: { backgroundColor: colors.glassInset },
    rowText: { flex: 1, minWidth: 0 },
    rowSub: { fontSize: 12, color: colors.textTertiary },
    rowLabel: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  });
}

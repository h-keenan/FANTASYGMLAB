import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import PressableScale from './PressableScale';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';
import { StackActions } from '@react-navigation/routers';

import { navigationRef, switchLeagueKeepingScreen } from '../navigation/navigationRef';
import { setLastLeague } from '../lib/lastLeague';
import { maskShowcaseFields } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { filterLeagues, SWITCHER_SEARCH_FROM } from '../lib/appHeader';
import LeagueCrest from './LeagueCrest';
import ErrorState from './ErrorState';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';

interface SavedLeagueRow {
  id: string;
  league_id: string;
  league_name: string;
}

/**
 * coridian_: "the league switcher should be built into the header as well" —
 * switching leagues used to require opening GM Orb's full menu just to reach
 * its "Switch League" section at the bottom. Same saved_leagues query and
 * switchToLeague behavior as GmOrb (switchLeagueKeepingScreen: stay on this
 * screen with the new league, like web's swapLeagueIdInPath), just surfaced
 * as its own compact header control so it's reachable without a detour
 * through the orb.
 *
 * The sheet ends with "Add a league" (tap-depth audit #4, web's switcher
 * already has one), which opens Home's existing Add League sheet; a free
 * account at its league cap gets that sheet's existing upgrade lock instead.
 * Because of that row the button now shows from one saved league up (it
 * used to need two); still hidden with zero.
 */
export default function LeagueSwitcherHeaderButton({
  leagueId,
  leagueName,
}: {
  leagueId: string;
  leagueName: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    supabase
      .from('saved_leagues')
      .select('id, league_id, league_name')
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) {
          setFailed(true);
          return;
        }
        setFailed(false);
        if (data) setSavedLeagues(maskShowcaseFields(data as SavedLeagueRow[]));
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (savedLeagues.length < 1 && !failed) return null;
  // UI pass 7 (web twin: LeagueSwitcherSheet): the current league first, search from 6 leagues, names wrap (never ellipsized).
  const shownLeagues = filterLeagues(savedLeagues, query, leagueId);

  const switchToLeague = (row: SavedLeagueRow) => {
    setOpen(false);
    const target = { leagueId: row.league_id, leagueName: row.league_name || 'League' };
    void setLastLeague(target);
    switchLeagueKeepingScreen(target, leagueId);
  };

  return (
    <>
      <PressableScale style={styles.button} onPress={() => setOpen(true)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Switch league">
        <Ionicons name="swap-vertical" size={18} color={colors.textPrimary} />
      </PressableScale>
      <SheetModal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <SwipeDismissCard style={styles.sheet} onDismiss={() => setOpen(false)}>
            <AppText style={styles.title}>Your leagues</AppText>
            {savedLeagues.length >= SWITCHER_SEARCH_FROM ? (
              <TextInput
                style={styles.search}
                placeholder={`Search ${savedLeagues.length} leagues`}
                placeholderTextColor={colors.textTertiary}
                value={query}
                onChangeText={setQuery}
                accessibilityLabel="Search leagues"
                autoCorrect={false}
              />
            ) : null}
            {failed ? (
              <ErrorState compact title="Your other leagues didn't load" onRetry={() => setAttempt((n) => n + 1)} />
            ) : null}
            <SheetScrollView style={styles.list}>
              {shownLeagues.map((row) => {
                const active = row.league_id === leagueId;
                return (
                  <PressableScale
                    key={row.id}
                    style={styles.optionRow}
                    onPress={() => switchToLeague(row)}
                    disabled={active}
                  >
                    <View style={styles.optionIcon}>
                      <LeagueCrest leagueId={row.league_id} name={row.league_name} size={34} />
                    </View>
                    <View style={styles.optionBody}>
                      <AppText style={[styles.optionText, active && styles.optionTextActive]}>{row.league_name || row.league_id}</AppText>
                      {active ? <AppText style={styles.optionSub}>Current league</AppText> : null}
                    </View>
                    {active ? <Ionicons name="checkmark" size={18} color={colors.accent} /> : null}
                  </PressableScale>
                );
              })}
            </SheetScrollView>
            <PressableScale
              style={styles.addRow}
              onPress={() => {
                setOpen(false);
                if (navigationRef.isReady()) {
                  navigationRef.dispatch(StackActions.popTo('Home', { openAddLeague: true }));
                }
              }}
              accessibilityRole="button"
              accessibilityLabel="Add a league"
            >
              <Ionicons name="add" size={18} color={colors.accentOnTint} style={styles.optionIcon} />
              <AppText style={[styles.optionText, styles.optionTextActive]}>Add a league</AppText>
            </PressableScale>
            <PressableScale
              style={styles.addRow}
              onPress={() => {
                setOpen(false);
                if (navigationRef.isReady()) navigationRef.dispatch(StackActions.push('SampleLeague'));
              }}
              accessibilityRole="button"
              accessibilityLabel="Try the sample league"
            >
              <Ionicons name="star-outline" size={18} color={colors.textSecondary} style={styles.optionIcon} />
              <AppText style={styles.optionText}>Try the sample league</AppText>
            </PressableScale>
          </SwipeDismissCard>
        </Pressable>
      </SheetModal>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    button: {
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.pill,
      width: 40,
      height: 40,
    },
    backdrop: {
      flex: 1,
      backgroundColor: scrim,
      justifyContent: 'flex-end',
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      padding: spacing.lg,
      maxHeight: '60%',
    },
    title: { fontSize: 17, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
    list: { flexGrow: 0 },
    optionRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: spacing.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    optionIcon: { marginRight: spacing.sm },
    optionBody: { flex: 1, minWidth: 0 },
    optionSub: { fontSize: 12.5, color: colors.textTertiary },
    search: { borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, fontSize: 16, color: colors.textPrimary, marginBottom: spacing.sm },
    addRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.sm, marginTop: spacing.xs },
    optionText: { fontSize: 16.5, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
    // accentOnTint: plain accent measures only 4.02:1 against this sheet's
    // backgroundElevated surface on light mode, under AA (color-system
    // audit, 2026-09-25).
    optionTextActive: { color: colors.accentOnTint },
  });
}

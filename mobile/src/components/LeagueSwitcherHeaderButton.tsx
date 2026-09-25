import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';
import { StackActions } from '@react-navigation/routers';

import { navigationRef } from '../navigation/navigationRef';
import { setLastLeague } from '../lib/lastLeague';
import { maskShowcaseFields } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

interface SavedLeagueRow {
  id: string;
  league_id: string;
  league_name: string;
}

/**
 * coridian_: "the league switcher should be built into the header as well" —
 * switching leagues used to require opening GM Orb's full menu just to reach
 * its "Switch League" section at the bottom. Same saved_leagues query and
 * switchToLeague behavior as GmOrb (popTo LeagueDetail with the new league's
 * params), just surfaced as its own compact header control so it's reachable
 * without a detour through the orb. Hidden entirely for an account with one
 * or zero saved leagues — nothing to switch to.
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

  useEffect(() => {
    let cancelled = false;
    supabase
      .from('saved_leagues')
      .select('id, league_id, league_name')
      .then(({ data }) => {
        if (!cancelled && data) setSavedLeagues(maskShowcaseFields(data as SavedLeagueRow[]));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (savedLeagues.length < 2) return null;

  const switchToLeague = (row: SavedLeagueRow) => {
    setOpen(false);
    const target = { leagueId: row.league_id, leagueName: row.league_name || 'League' };
    void setLastLeague(target);
    if (navigationRef.isReady()) {
      navigationRef.dispatch(StackActions.popTo('LeagueDetail', target));
    }
  };

  return (
    <>
      <TouchableOpacity style={styles.button} onPress={() => setOpen(true)} hitSlop={8}>
        <Ionicons name="swap-vertical" size={14} color={colors.textPrimary} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <AppText style={styles.title}>Switch League</AppText>
            <ScrollView style={styles.list}>
              {savedLeagues.map((row) => {
                const active = row.league_id === leagueId;
                return (
                  <TouchableOpacity
                    key={row.id}
                    style={styles.optionRow}
                    onPress={() => switchToLeague(row)}
                    disabled={active}
                  >
                    <Ionicons
                      name={active ? 'radio-button-on' : 'radio-button-off'}
                      size={18}
                      color={active ? colors.accent : colors.textTertiary}
                      style={styles.optionIcon}
                    />
                    <AppText style={[styles.optionText, active && styles.optionTextActive]} numberOfLines={1}>
                      {row.league_name || row.league_id}
                    </AppText>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
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
      width: 28,
      height: 28,
    },
    backdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.6)',
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
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
    list: { flexGrow: 0 },
    optionRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: spacing.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    optionIcon: { marginRight: spacing.sm },
    optionText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
    // accentOnTint: plain accent measures only 4.02:1 against this sheet's
    // backgroundElevated surface on light mode, under AA (color-system
    // audit, 2026-09-25).
    optionTextActive: { color: colors.accentOnTint },
  });
}

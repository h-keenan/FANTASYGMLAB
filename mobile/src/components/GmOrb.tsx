import React, { useEffect, useState } from 'react';
import {
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { currentLeagueContext, navigationRef } from '../navigation/navigationRef';
import { setLastLeague } from '../lib/lastLeague';
import { supabase } from '../lib/supabase';
import { colors, radii, spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

interface Destination {
  label: string;
  route: string;
  icon: IconName;
  needsLeague?: boolean;
}

const LEAGUE_DESTINATIONS: Destination[] = [
  { label: 'League Overview', route: 'LeagueDetail', icon: 'grid-outline', needsLeague: true },
  { label: 'Next Move', route: 'Dashboard', icon: 'flash-outline', needsLeague: true },
  { label: 'Players', route: 'Players', icon: 'people-outline', needsLeague: true },
  { label: 'GM Targets', route: 'GmTargets', icon: 'bookmark-outline', needsLeague: true },
  { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', needsLeague: true },
  { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline', needsLeague: true },
  { label: 'Trade Analyzer', route: 'TradeAnalyzer', icon: 'git-compare-outline', needsLeague: true },
  { label: 'Trade Calculator', route: 'TradeCalculator', icon: 'calculator-outline', needsLeague: true },
  { label: 'Recap', route: 'Recap', icon: 'newspaper-outline', needsLeague: true },
  { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline', needsLeague: true },
];

const GENERAL_DESTINATIONS: Destination[] = [
  { label: 'Home', route: 'Home', icon: 'home-outline' },
  { label: 'News', route: 'News', icon: 'globe-outline' },
  { label: 'Premium', route: 'Paywall', icon: 'star-outline' },
  { label: 'More', route: 'More', icon: 'ellipsis-horizontal-outline' },
];

interface SavedLeagueRow {
  id: string;
  league_id: string;
  league_name: string;
}

/**
 * The floating "GM" brand-mark button + destination sheet — the mobile
 * counterpart to the web app's gm_orb_floating_trigger/render_mobile_destination_sheet
 * (modules/brand_identity.py, app.py). Rendered once, globally, so every
 * screen gets the same always-available navigation affordance instead of
 * each screen inventing its own per-page tool row.
 */
export default function GmOrb() {
  const [open, setOpen] = useState(false);
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);
  const insets = useSafeAreaInsets();
  const league = open ? currentLeagueContext() : null;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    supabase
      .from('saved_leagues')
      .select('id, league_id, league_name')
      .then(({ data }) => {
        if (!cancelled && data) setSavedLeagues(data as SavedLeagueRow[]);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const go = (destination: Destination) => {
    setOpen(false);
    if (!navigationRef.isReady()) return;
    // Destinations are a data-driven list (not a single statically-known
    // route), so this dispatches dynamically rather than through the
    // strongly-typed `navigate` overloads.
    const navigate = navigationRef.navigate as (name: string, params?: object) => void;
    if (destination.needsLeague) {
      if (!league) return;
      navigate(destination.route, league);
    } else {
      navigate(destination.route);
    }
  };

  const switchToLeague = (row: SavedLeagueRow) => {
    setOpen(false);
    const target = { leagueId: row.league_id, leagueName: row.league_name || 'League' };
    void setLastLeague(target);
    if (navigationRef.isReady()) {
      (navigationRef.navigate as (name: string, params?: object) => void)('LeagueDetail', target);
    }
  };

  return (
    <>
      <TouchableOpacity
        style={[styles.orb, { bottom: insets.bottom + spacing.lg }]}
        onPress={() => setOpen(true)}
        accessibilityLabel="Open GM menu"
        activeOpacity={0.85}
      >
        <Image source={require('../../assets/icon.png')} style={styles.orbImage} />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.sheetHandle} />
            <Text style={styles.sheetKicker}>FantasyGM Lab</Text>
            <Text style={styles.sheetTitle}>Where to go</Text>

            <ScrollView contentContainerStyle={styles.sheetContent}>
              {league ? (
                <>
                  <Text style={styles.sectionLabel}>{league.leagueName}</Text>
                  {LEAGUE_DESTINATIONS.map((destination) => (
                    <TouchableOpacity
                      key={destination.route}
                      style={styles.row}
                      onPress={() => go(destination)}
                    >
                      <Ionicons name={destination.icon} size={18} color={colors.accent} style={styles.rowIcon} />
                      <Text style={styles.rowText}>{destination.label}</Text>
                    </TouchableOpacity>
                  ))}
                </>
              ) : (
                <Text style={styles.sectionNote}>
                  Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
                </Text>
              )}

              {savedLeagues.length > 1 ? (
                <>
                  <Text style={styles.sectionLabel}>Switch League</Text>
                  {savedLeagues.map((row) => (
                    <TouchableOpacity key={row.id} style={styles.row} onPress={() => switchToLeague(row)}>
                      <Ionicons
                        name={row.league_id === league?.leagueId ? 'radio-button-on' : 'radio-button-off'}
                        size={18}
                        color={row.league_id === league?.leagueId ? colors.accent : colors.textTertiary}
                        style={styles.rowIcon}
                      />
                      <Text style={styles.rowText} numberOfLines={1}>
                        {row.league_name || row.league_id}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </>
              ) : null}

              <Text style={styles.sectionLabel}>General</Text>
              {GENERAL_DESTINATIONS.map((destination) => (
                <TouchableOpacity key={destination.route} style={styles.row} onPress={() => go(destination)}>
                  <Ionicons name={destination.icon} size={18} color={colors.textSecondary} style={styles.rowIcon} />
                  <Text style={styles.rowText}>{destination.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TouchableOpacity style={styles.closeButton} onPress={() => setOpen(false)}>
              <Text style={styles.closeButtonText}>Close</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const ORB_SIZE = 56;

const styles = StyleSheet.create({
  orb: {
    position: 'absolute',
    left: spacing.lg,
    width: ORB_SIZE,
    height: ORB_SIZE,
    borderRadius: radii.lg,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.borderStrong,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 8,
  },
  orbImage: { width: ORB_SIZE, height: ORB_SIZE },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.backgroundElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.xl,
    maxHeight: '75%',
    borderWidth: 1,
    borderColor: colors.border,
    borderBottomWidth: 0,
  },
  sheetHandle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  sheetKicker: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.accent,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  sheetTitle: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
  sheetContent: { paddingBottom: spacing.md },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  sectionNote: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowIcon: { marginRight: spacing.sm },
  rowText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  closeButton: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  closeButtonText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
});

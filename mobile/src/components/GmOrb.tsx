import React, { useState } from 'react';
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

import { currentLeagueContext, navigationRef } from '../navigation/navigationRef';
import { colors, radii, spacing } from '../theme';

interface Destination {
  label: string;
  route: string;
  needsLeague?: boolean;
}

const LEAGUE_DESTINATIONS: Destination[] = [
  { label: 'League Overview', route: 'LeagueDetail', needsLeague: true },
  { label: 'Players', route: 'Players', needsLeague: true },
  { label: 'GM Targets', route: 'GmTargets', needsLeague: true },
  { label: 'Waivers', route: 'Waivers', needsLeague: true },
  { label: 'Trade Analyzer', route: 'TradeAnalyzer', needsLeague: true },
  { label: 'Trade Calculator', route: 'TradeCalculator', needsLeague: true },
  { label: 'Recap', route: 'Recap', needsLeague: true },
  { label: 'Alerts', route: 'Alerts', needsLeague: true },
];

const GENERAL_DESTINATIONS: Destination[] = [
  { label: 'Home', route: 'Home' },
  { label: 'News', route: 'News' },
  { label: 'Premium', route: 'Paywall' },
  { label: 'More', route: 'More' },
];

/**
 * The floating "GM" brand-mark button + destination sheet — the mobile
 * counterpart to the web app's gm_orb_floating_trigger/render_mobile_destination_sheet
 * (modules/brand_identity.py, app.py). Rendered once, globally, so every
 * screen gets the same always-available navigation affordance instead of
 * each screen inventing its own per-page tool row.
 */
export default function GmOrb() {
  const [open, setOpen] = useState(false);
  const insets = useSafeAreaInsets();
  const league = open ? currentLeagueContext() : null;

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
                      <Text style={styles.rowText}>{destination.label}</Text>
                    </TouchableOpacity>
                  ))}
                </>
              ) : (
                <Text style={styles.sectionNote}>
                  Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
                </Text>
              )}

              <Text style={styles.sectionLabel}>General</Text>
              {GENERAL_DESTINATIONS.map((destination) => (
                <TouchableOpacity key={destination.route} style={styles.row} onPress={() => go(destination)}>
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
    right: spacing.lg,
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
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  closeButton: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  closeButtonText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
});

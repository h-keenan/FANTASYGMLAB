import React, { forwardRef, useEffect, useMemo, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import QRCode from 'react-native-qrcode-svg';

import type { PortfolioLeague, PortfolioTopAsset } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 640;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const QR_SIZE = 60;
// Cap matches RecapShareCard's own MAX_STORIES idea — a compact per-league
// strip stays scannable at a glance instead of turning into a scroll-free
// list that has to shrink type to fit everything.
const MAX_LEAGUES = 5;
// Safety net only — NOT the fix. See TradeShareCard's identical comment:
// the real fix is waiting for PlayerAvatar's onLoadSettle below.
const AVATAR_READY_TIMEOUT_MS = 4000;

function recordLabel(league: PortfolioLeague): string {
  if (league.wins == null && league.losses == null) return '';
  const base = `${league.wins ?? 0}-${league.losses ?? 0}`;
  return league.ties ? `${base}-${league.ties}` : base;
}

/**
 * The best honest cross-league standing claim this user can make right now,
 * computed purely from each league's own `power_rank` (no new ranking
 * math) — coridian_-approved headline for the Portfolio share card. Prefers
 * an outright #1 count; falls back to a top-3 count when there isn't one,
 * and to a plain league count when the caller has neither (e.g. every
 * league is mid-pack).
 */
export function portfolioHeadlineStat(leagues: PortfolioLeague[]): string {
  const ranked = leagues.filter((league) => league.power_rank != null);
  const firstPlaceCount = ranked.filter((league) => league.power_rank === 1).length;
  if (firstPlaceCount > 0) {
    return `#1 in ${firstPlaceCount} of ${leagues.length} league${leagues.length === 1 ? '' : 's'}`;
  }
  const topThreeCount = ranked.filter((league) => (league.power_rank ?? Infinity) <= 3).length;
  if (topThreeCount > 0) {
    return `Top 3 finish in ${topThreeCount} league${topThreeCount === 1 ? '' : 's'}`;
  }
  return `Managing ${leagues.length} league${leagues.length === 1 ? '' : 's'}`;
}

/**
 * The single highest-value-score player across every one of this user's
 * rosters — each league's `top_asset` is already the top of that league's
 * roster (modules.dashboard_engine.build_league_summary), so this is just a
 * max over N already-computed values, not a new valuation pass.
 */
export function portfolioStandoutAsset(leagues: PortfolioLeague[]): PortfolioTopAsset | null {
  let best: PortfolioTopAsset | null = null;
  for (const league of leagues) {
    const asset = league.top_asset;
    if (!asset) continue;
    if (!best || (asset.score ?? -Infinity) > (best.score ?? -Infinity)) {
      best = asset;
    }
  }
  return best;
}

function LeagueStripRow({ league }: { league: PortfolioLeague }) {
  const record = recordLabel(league);
  const isChampion = league.power_rank === 1;
  const rankColor = isChampion ? colors.premium : colors.accent;
  return (
    <View style={styles.stripRow}>
      <View style={styles.stripTextGroup}>
        <AppText style={styles.stripLeagueName} numberOfLines={1}>
          {league.league_name}
        </AppText>
        <View style={styles.stripMetaRow}>
          {record ? <AppText style={styles.stripMeta}>{record}</AppText> : null}
          {league.archetype_label ? (
            <View style={styles.archetypeChip}>
              <AppText style={styles.archetypeChipText} numberOfLines={1}>
                {league.archetype_label}
              </AppText>
            </View>
          ) : null}
        </View>
      </View>
      {league.power_rank != null ? (
        <View style={[styles.rankPill, isChampion && styles.rankPillFirst, { borderColor: `${rankColor}80` }]}>
          <AppText style={[styles.rankValue, { color: rankColor }]}>
            {league.power_rank_tied ? `T-${league.power_rank}` : `#${league.power_rank}`}
          </AppText>
        </View>
      ) : null}
    </View>
  );
}

/**
 * The literal graphic that gets captured + shared — a third instance of the
 * same branded-share-card pattern as TradeShareCard/RecapShareCard (logo +
 * wordmark header, hairline dividers, "SCAN TO TRY" QR + tagline footer),
 * built from the same PortfolioLeague[] the Portfolio screen already shows.
 * Rendered at a fixed 360x640 logical size so react-native-view-shot's
 * capture produces a consistent image regardless of device.
 *
 * `onReadyChange` reports whether the standout asset's headshot has settled
 * (loaded, failed, or there is no standout asset to load) — same contract
 * as TradeShareCard's identical prop, for the same reason: captureRef does
 * not wait for in-flight PlayerAvatar loads.
 */
const PortfolioShareCard = forwardRef<View, {
  leagues: PortfolioLeague[];
  onReadyChange?: (ready: boolean) => void;
}>(({ leagues, onReadyChange }, ref) => {
  const shown = leagues.slice(0, MAX_LEAGUES);
  const headline = portfolioHeadlineStat(leagues);
  const standout = useMemo(() => portfolioStandoutAsset(leagues), [leagues]);

  const [avatarSettled, setAvatarSettled] = useState(false);
  const standoutPlayerId = standout?.player_id ?? null;

  // Re-arm the timeout safety net whenever the standout asset itself changes.
  const [forceReady, setForceReady] = useState(false);
  useEffect(() => {
    setAvatarSettled(false);
    setForceReady(false);
    const timer = setTimeout(() => setForceReady(true), AVATAR_READY_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [standoutPlayerId]);

  const ready = !standoutPlayerId || avatarSettled || forceReady;
  useEffect(() => {
    onReadyChange?.(ready);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  return (
    <View ref={ref} collapsable={false} style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.brandRow}>
          <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
          <AppText style={styles.brandWord}>
            FANTASY<AppText style={styles.brandWordAccent}>GM</AppText> LAB
          </AppText>
        </View>
        <AppText style={styles.kickerRight}>YOUR PORTFOLIO</AppText>
      </View>

      <View style={styles.hairline} />

      <AppText style={styles.headline}>{headline}</AppText>
      <AppText style={styles.headlineSub}>Across every saved league</AppText>

      <View style={styles.hairline} />

      <AppText style={styles.sectionLabel}>YOUR LEAGUES</AppText>
      <View style={styles.stripGroup}>
        {shown.map((league) => (
          <LeagueStripRow key={league.league_id} league={league} />
        ))}
      </View>

      {standout ? (
        <>
          <View style={styles.hairline} />
          <View style={styles.standoutRow}>
            <PlayerAvatar
              playerId={standout.player_id}
              size={36}
              tier={standout.tier}
              onLoadSettle={() => setAvatarSettled(true)}
            />
            <View style={styles.standoutTextGroup}>
              <AppText style={styles.standoutLabel}>MOST VALUABLE ASSET</AppText>
              <PlayerNameText name={standout.name ?? 'Unknown'} style={styles.standoutName} />
            </View>
          </View>
        </>
      ) : null}

      <View style={styles.qrRow}>
        <View style={styles.qrTextGroup}>
          <AppText style={styles.qrKicker}>SCAN TO TRY</AppText>
          <AppText style={styles.qrTitle}>FantasyGM Lab</AppText>
          <AppText style={styles.qrSubtitle}>Real trade grades, waiver signal, and a Trade Hub built for dynasty.</AppText>
        </View>
        <View style={styles.qrWrap}>
          <QRCode
            value={SHARE_QR_URL}
            size={QR_SIZE}
            color={colors.background}
            backgroundColor="#fff"
            logo={require('../../assets/icon.png')}
            logoSize={QR_SIZE * 0.28}
            logoBorderRadius={4}
            logoBackgroundColor="#fff"
            ecl="H"
          />
        </View>
      </View>

      <View style={styles.footer}>
        <AppText style={styles.footerText}>
          <AppText style={{ color: colors.accent }}>PLAN. </AppText>
          <AppText style={{ color: colors.premium }}>PROJECT. </AppText>
          <AppText style={{ color: colors.danger }}>WIN.</AppText>
        </AppText>
      </View>
    </View>
  );
});
PortfolioShareCard.displayName = 'PortfolioShareCard';

export default PortfolioShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    backgroundColor: colors.background,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  brandMark: { width: 28, height: 28, borderRadius: 8 },
  brandWord: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, letterSpacing: 0.5 },
  brandWordAccent: { color: colors.accent },
  kickerRight: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  headline: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.xs },
  headlineSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.6, marginTop: spacing.xs },
  stripGroup: { gap: spacing.sm, marginTop: spacing.sm },
  stripRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  stripTextGroup: { flex: 1 },
  stripLeagueName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
  stripMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  stripMeta: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  archetypeChip: {
    backgroundColor: `${colors.violet}26`,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 1,
    maxWidth: 140,
  },
  archetypeChipText: { fontSize: 9, fontWeight: '700', color: colors.violet, letterSpacing: 0.2 },
  rankPill: {
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    alignItems: 'center',
    minWidth: 40,
  },
  rankPillFirst: { backgroundColor: `${colors.premium}1F` },
  rankValue: { fontSize: 13, fontWeight: '700' },
  standoutRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 2 },
  standoutTextGroup: { flex: 1 },
  standoutLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
  standoutName: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: 1 },
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    // 'auto' (not a fixed value) — same trick TradeShareCard/RecapShareCard
    // use so flexbox fills whatever room is left in the fixed-height card
    // regardless of how many leagues/rows this particular portfolio shows.
    marginTop: 'auto',
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    gap: spacing.md,
  },
  qrTextGroup: { flex: 1 },
  qrKicker: { fontSize: 9, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
  qrTitle: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
  qrSubtitle: { fontSize: 10, color: colors.textSecondary, lineHeight: 13, marginTop: 2 },
  qrWrap: {
    padding: 6,
    backgroundColor: '#fff',
    borderRadius: radii.sm,
  },
  footer: { marginTop: 'auto', alignItems: 'center', paddingTop: spacing.sm },
  footerText: { fontSize: 12, fontWeight: '700', letterSpacing: 1.5 },
});

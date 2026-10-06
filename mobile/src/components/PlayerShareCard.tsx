import React, { forwardRef, useEffect, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import QRCode from 'react-native-qrcode-svg';

import CircularProgressRing from './CircularProgressRing';
import PlayerAvatar from './PlayerAvatar';
import SubRatingRow from './SubRatingRow';
import TierBadge from './TierBadge';
import type { SubRating } from '../lib/subRatings';
import { colors, radii, spacing } from '../theme';
import { resolvePlayerTier } from '../lib/playerTier';
import { percentileColor } from '../lib/percentile';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 540;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const QR_SIZE = 60;
// Same safety net as TradeShareCard's AVATAR_READY_TIMEOUT_MS — not the
// fix, just a floor so a single hung headshot request can't leave the
// share button stuck forever. See that component's comment for the real
// fix (waiting for PlayerAvatar's onLoadSettle below).
const AVATAR_READY_TIMEOUT_MS = 4000;

/**
 * The literal graphic that gets captured + shared — a single-player "trading
 * card": portrait, OVR ring, tier pill, and the Model tab's sub-rating chip
 * row as the card's headline attributes (a Madden Ultimate Team card's
 * portrait + OVR + position + color-coded sub-attributes, per coridian_'s
 * brief). Built from the exact same tier/rating/sub-rating data
 * PlayerHero/ModelSection already render on-screen — never a second
 * computation. Structured identically to TradeShareCard (fixed logical
 * size, dark-palette-always `colors` import rather than useThemeMode, same
 * QR + tagline footer) so the two share surfaces read as one family and so
 * react-native-view-shot's capture produces a consistent image regardless
 * of device or the viewer's light/dark setting.
 *
 * `onReadyChange` reports whether the portrait headshot has settled
 * (loaded, failed, or had no id to load) — see PlayerAvatar's onLoadSettle
 * doc comment for why a capturer needs this. Fires synchronously
 * false->true->false as props change, so a caller (the share modal) should
 * treat the latest value as the source of truth, not a one-shot event.
 */
const PlayerShareCard = forwardRef<View, {
  playerId: string;
  tier?: string | null;
  name: string;
  position?: string | null;
  team?: string | null;
  overallRating: number | null;
  subRatings: SubRating[];
  onReadyChange?: (ready: boolean) => void;
}>(({ playerId, tier, name, position, team, overallRating, subRatings, onReadyChange }, ref) => {
  const tierIdentity = resolvePlayerTier(tier, true);
  const ringColor = overallRating !== null ? percentileColor(overallRating, colors) : colors.accent;

  const [avatarSettled, setAvatarSettled] = useState(false);
  useEffect(() => {
    setAvatarSettled(false);
  }, [playerId]);

  const [forceReady, setForceReady] = useState(false);
  useEffect(() => {
    setForceReady(false);
    const timer = setTimeout(() => setForceReady(true), AVATAR_READY_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [playerId]);

  const ready = avatarSettled || forceReady;
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
        <TierBadge storedTier={tier} size="md" />
      </View>

      <View style={styles.hairline} />

      <View style={styles.portraitRow}>
        <View style={styles.avatarWrap}>
          <View style={[styles.glow, { backgroundColor: tierIdentity.color }]} />
          <PlayerAvatar
            playerId={playerId}
            size={128}
            tier={tier}
            style={styles.avatar}
            onLoadSettle={() => setAvatarSettled(true)}
          />
        </View>
        {overallRating !== null ? (
          <CircularProgressRing
            percent={overallRating}
            size={76}
            strokeWidth={7}
            valueLabel={String(overallRating)}
            valueFontScale={0.36}
            color={ringColor}
            label="OVR"
          />
        ) : null}
      </View>

      <AppText style={styles.name} numberOfLines={2}>
        {name}
      </AppText>
      <View style={styles.metaRow}>
        {position ? (
          <View style={styles.positionPill}>
            <AppText style={styles.positionPillText}>{position}</AppText>
          </View>
        ) : null}
        {team ? <AppText style={styles.team}>{team}</AppText> : null}
      </View>

      <View style={styles.hairline} />

      <AppText style={styles.attributesLabel}>Headline Attributes</AppText>
      <SubRatingRow ratings={subRatings} size="md" />

      <View style={styles.qrRow}>
        <View style={styles.qrTextGroup}>
          <AppText style={styles.qrKicker}>SCAN TO TRY</AppText>
          <AppText style={styles.qrTitle}>FantasyGM Lab</AppText>
          <AppText style={styles.qrSubtitle}>Real player grades, model breakdowns, and a dynasty engine built for GMs.</AppText>
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
PlayerShareCard.displayName = 'PlayerShareCard';

export default PlayerShareCard;
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
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  portraitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  avatarWrap: { alignItems: 'center', justifyContent: 'center' },
  glow: {
    position: 'absolute',
    width: 160,
    height: 160,
    borderRadius: 80,
    opacity: 0.22,
  },
  avatar: {
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  name: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, lineHeight: 27, marginTop: spacing.md },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 4 },
  positionPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  positionPillText: { fontSize: 11, fontWeight: '800', color: colors.textPrimary, letterSpacing: 0.3 },
  team: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
  attributesLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: spacing.sm,
  },
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    // 'auto' (not a fixed value) — same trick TradeShareCard's qrRow/footer
    // use — so flexbox splits whatever vertical room is left in the fixed-
    // height card evenly across the two gaps instead of dumping it all
    // into one gap right above the footer.
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
  footer: { marginTop: 'auto', alignItems: 'center' },
  footerText: { fontSize: 12, fontWeight: '700', letterSpacing: 1.5 },
});

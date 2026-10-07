import React, { forwardRef, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import ShareCardChrome, { CARD_HEIGHT, CARD_WIDTH } from './ShareCardChrome';
import PlayerAvatar from './PlayerAvatar';
import SubRatingRow from './SubRatingRow';
import TierBadge from './TierBadge';
import type { SubRating } from '../lib/subRatings';
import { colors, radii, spacing } from '../theme';
import { resolvePlayerTier } from '../lib/playerTier';
import { percentileColor } from '../lib/percentile';
import CircularProgressRing from './CircularProgressRing';

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
 * computation. Header/QR/footer chrome comes from the shared
 * ShareCardChrome (see that file) so this and every other share card read
 * as one family and so react-native-view-shot's capture produces a
 * consistent image regardless of device or the viewer's light/dark setting.
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
    <ShareCardChrome
      ref={ref}
      headerRight={<TierBadge storedTier={tier} size="md" />}
      qrSubtitle="Real player grades, model breakdowns, and a dynasty engine built for GMs."
    >
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
    </ShareCardChrome>
  );
});
PlayerShareCard.displayName = 'PlayerShareCard';

export default PlayerShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
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
});

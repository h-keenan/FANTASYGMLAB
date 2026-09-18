import React, { forwardRef } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';

import type { RankedPlayer, TradeVerdict } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 540;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const QR_SIZE = 60;

const HEADLINE_META: Record<TradeVerdict['tone'], { headline: string; color: string }> = {
  accept: { headline: 'TRADE ACCEPTED', color: colors.accent },
  counter: { headline: 'COUNTER THIS TRADE', color: colors.premium },
  decline: { headline: 'TRADE DECLINED', color: colors.danger },
  fair: { headline: 'FAIR TRADE', color: colors.textSecondary },
};

function AssetLine({ player }: { player: RankedPlayer }) {
  return (
    <View style={styles.assetLine}>
      <PlayerAvatar playerId={player.player_id} size={32} tier={player.tier} style={styles.assetAvatar} />
      <View style={styles.assetTextGroup}>
        <Text style={styles.assetName} numberOfLines={1}>
          {player.name ?? 'Unknown'}
        </Text>
        <View style={styles.assetMetaRow}>
          <PositionBadge position={player.position} />
          <Text style={styles.assetMeta} numberOfLines={1}>
            {player.team}
          </Text>
        </View>
      </View>
    </View>
  );
}

/**
 * The literal graphic that gets captured + shared — a wireframe port of the
 * FGL brand style sheet's "Share Card Example" panel (logo + wordmark, big
 * value-change number, send/receive breakdown, "why this works", tagline
 * footer), built from the same TradeVerdict data the on-screen card shows.
 * Rendered at a fixed 360x450 logical size so react-native-view-shot's
 * capture produces a consistent image regardless of device.
 */
const TradeShareCard = forwardRef<View, {
  leagueName: string;
  verdict: TradeVerdict;
  sendPlayers: RankedPlayer[];
  receivePlayers: RankedPlayer[];
}>(({ leagueName, verdict, sendPlayers, receivePlayers }, ref) => {
  const meta = HEADLINE_META[verdict.tone];
  const gain = verdict.value_delta;
  const gainColor = gain > 0 ? colors.successBright : gain < 0 ? colors.danger : colors.textSecondary;
  const gainLabel = `${gain > 0 ? '+' : ''}${gain.toLocaleString()}`;

  return (
    <View ref={ref} collapsable={false} style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.brandRow}>
          <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
          <View>
            <Text style={styles.brandWord}>
              FANTASY<Text style={styles.brandWordAccent}>GM</Text> LAB
            </Text>
          </View>
        </View>
        <Text style={styles.leagueName} numberOfLines={1}>
          {leagueName.toUpperCase()}
        </Text>
      </View>

      <View style={styles.hairline} />

      <Text style={[styles.headline, { color: meta.color }]}>{meta.headline}</Text>
      <View style={styles.bandRow}>
        <View style={[styles.bandChip, { backgroundColor: `${meta.color}26` }]}>
          <Text style={[styles.bandChipText, { color: meta.color }]}>{verdict.band}</Text>
        </View>
        <Text style={styles.confidenceText}>{verdict.confidence} confidence</Text>
      </View>

      <Text style={[styles.gainValue, { color: gainColor }]}>{gainLabel}</Text>
      <Text style={styles.gainLabel}>Value Change</Text>

      <View style={styles.hairline} />

      <View style={styles.exchangeRow}>
        <View style={styles.exchangeSide}>
          <Text style={styles.exchangeKicker}>YOU SEND</Text>
          {sendPlayers.slice(0, 3).map((player) => (
            <AssetLine key={player.player_id} player={player} />
          ))}
        </View>
        <View style={styles.exchangeSide}>
          <Text style={styles.exchangeKicker}>YOU RECEIVE</Text>
          {receivePlayers.slice(0, 3).map((player) => (
            <AssetLine key={player.player_id} player={player} />
          ))}
        </View>
      </View>

      <View style={styles.hairline} />

      <Text style={styles.whyLabel}>Why this works</Text>
      <Text style={styles.whyText} numberOfLines={6}>
        {verdict.rationale}
      </Text>

      <View style={styles.qrRow}>
        <View style={styles.qrTextGroup}>
          <Text style={styles.qrKicker}>SCAN TO TRY</Text>
          <Text style={styles.qrTitle}>FantasyGM Lab</Text>
          <Text style={styles.qrSubtitle}>Real trade grades, waiver signal, and a Trade Hub built for dynasty.</Text>
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
        <Text style={styles.footerText}>
          <Text style={{ color: colors.accent }}>PLAN. </Text>
          <Text style={{ color: colors.premium }}>PROJECT. </Text>
          <Text style={{ color: colors.danger }}>WIN.</Text>
        </Text>
      </View>
    </View>
  );
});
TradeShareCard.displayName = 'TradeShareCard';

export default TradeShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    backgroundColor: colors.background,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  brandMark: { width: 28, height: 28, borderRadius: 8 },
  brandWord: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, letterSpacing: 0.5 },
  brandWordAccent: { color: colors.accent },
  leagueName: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6, maxWidth: 120 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  headline: { fontSize: 20, fontWeight: '800', letterSpacing: 0.5, marginTop: spacing.xs },
  bandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 6 },
  bandChip: { borderRadius: radii.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  bandChipText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.4, textTransform: 'uppercase' },
  confidenceText: { fontSize: 11, color: colors.textSecondary },
  gainValue: { fontSize: 40, fontWeight: '800', letterSpacing: -1, marginTop: spacing.md },
  gainLabel: { fontSize: 12, color: colors.textSecondary, marginTop: -2 },
  exchangeRow: { flexDirection: 'row', gap: spacing.md },
  exchangeSide: { flex: 1, gap: 6 },
  exchangeKicker: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5, marginBottom: 2 },
  assetLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  assetAvatar: {},
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 12, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 10, color: colors.textSecondary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  whyLabel: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
  whyText: { fontSize: 11, color: colors.textSecondary, lineHeight: 15, marginTop: 2 },
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.lg,
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
  footer: { marginTop: spacing.md, alignItems: 'center' },
  footerText: { fontSize: 12, fontWeight: '700', letterSpacing: 1.5 },
});

import React, { forwardRef, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle } from 'react-native-svg';
import AppText from './AppText';

import type { DraftPickAsset, RankedPlayer, TradeVerdict } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import { confidenceLevelFor } from './ConfidenceMeter';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';
import PositionBadge from './PositionBadge';
import ShareCardChrome, { CARD_WIDTH, ShareConfidenceBars, ShareGlass } from './ShareCardChrome';
import TeamAvatar from './TeamAvatar';
import { buildPartnerPitch, type PitchAsset } from '../lib/tradePitch';
import { formatTradeGain } from '../lib/liveDraft';
import { LOW_CONFIDENCE_NOTE, TRADE_SHARE_COPY } from '../lib/tradeShareCopy';
import { overallRatingColor } from '../lib/percentile';

const CARD_HEIGHT = 620;
// Safety net only — NOT the fix. If some avatar never fires onLoad/onError
// (e.g. a hung request), don't leave the share button stuck forever. The
// real fix is waiting for PlayerAvatar's onLoadSettle below.
const AVATAR_READY_TIMEOUT_MS = 4000;
const MAX_ROWS = 3;
const WARNING = '#F59E0B';

/** Verdict word color by band, same fairness-band tones as web's share card
 * (favorable green, fair neutral, overpay warm, major overpay red). */
function bandColor(band: string, fallback: string): string {
  const key = band.trim().toLowerCase();
  if (key === 'favorable') return colors.successBright;
  if (key === 'fair') return colors.textPrimary;
  if (key === 'slight overpay') return '#F59E0B';
  if (key === 'major overpay') return colors.danger;
  return fallback;
}

const HEADLINE_COLOR: Record<TradeVerdict['tone'], string> = {
  accept: colors.accent,
  counter: colors.premium,
  decline: colors.danger,
  fair: colors.textPrimary,
  // Trade Hub's own suggestions — nobody has accepted or declined anything.
  idea: colors.accent,
};

type Side = 'send' | 'get';
const SIDE_COLOR: Record<Side, string> = { send: colors.danger, get: colors.success };
const SIDE_TINT: Record<Side, string> = { send: colors.dangerMuted, get: colors.successMuted };

/** Fixed-dark OVR ring (OvrGauge's look: tinted arc over a surface disc).
 * Not CircularProgressRing/OvrGauge: those read the live theme, and an
 * exported share image must look the same on every device and in light mode. */
function ShareOvrRing({ rating, size = 28 }: { rating: number | null | undefined; size?: number }) {
  if (rating == null || !Number.isFinite(rating)) return null;
  const clamped = Math.max(0, Math.min(99, Math.round(rating)));
  const tint = overallRatingColor(clamped, colors);
  const stroke = Math.max(2.5, size * 0.11);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.border} strokeWidth={stroke} fill={colors.surface} />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={tint}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * c} ${c}`}
          rotation={-90}
          origin={`${size / 2}, ${size / 2}`}
        />
      </Svg>
      <AppText style={{ fontSize: size * 0.36, fontWeight: '900', color: tint }}>{clamped}</AppText>
    </View>
  );
}

function AssetRow({
  player,
  side,
  trackKey,
  onAvatarSettle,
}: {
  player: RankedPlayer;
  side: Side;
  trackKey: string;
  onAvatarSettle: (key: string) => void;
}) {
  const meta = [player.team, player.age ? `Age ${player.age}` : null].filter(Boolean).join(' \u00b7 ');
  return (
    <View style={[styles.assetRow, { backgroundColor: SIDE_TINT[side], borderColor: `${SIDE_COLOR[side]}59` }]}>
      <PlayerAvatar
        playerId={player.player_id}
        size={34}
        tier={player.tier}
        onLoadSettle={() => onAvatarSettle(trackKey)}
      />
      <View style={styles.assetTextGroup}>
        <PlayerNameText name={player.name ?? 'Unknown'} style={styles.assetName} />
        <View style={styles.assetMetaRow}>
          <PositionBadge position={player.position} />
          <AppText style={styles.assetMeta} numberOfLines={1}>
            {meta}
          </AppText>
        </View>
      </View>
      <View style={styles.assetRight}>
        <ShareOvrRing rating={player.overall_rating} />
        {player.score != null ? <AppText style={styles.assetValue}>{Math.round(player.score).toLocaleString('en-US')}</AppText> : null}
      </View>
    </View>
  );
}

const playerPitchAsset = (p: RankedPlayer): PitchAsset => ({ kind: 'player', name: p.name, position: p.position, score: p.score });
const pickPitchAsset = (p: DraftPickAsset): PitchAsset => ({ kind: 'pick', score: p.score, season: p.season, round: p.round });
const sumScores = (players: RankedPlayer[], picks: DraftPickAsset[]) =>
  [...players.map((p) => p.score), ...picks.map((p) => p.score)].reduce<number>((s, v) => s + (Number(v) || 0), 0);

function ExchangePanel({
  label,
  side,
  total,
  players,
  picks = [],
  keyPrefix,
  onAvatarSettle,
}: {
  label: string;
  side: Side;
  total?: number;
  players: RankedPlayer[];
  picks?: DraftPickAsset[];
  keyPrefix: string;
  onAvatarSettle: (key: string) => void;
}) {
  const shown = players.slice(0, MAX_ROWS);
  const shownPicks = picks.slice(0, Math.max(0, MAX_ROWS - shown.length));
  const hidden = players.length + picks.length - shown.length - shownPicks.length;
  return (
    <View style={styles.panel}>
      <View style={styles.panelHead}>
        <View style={[styles.dot, { backgroundColor: SIDE_COLOR[side] }]} />
        <AppText style={styles.panelLabel}>{label.toUpperCase()}</AppText>
        {total != null ? <AppText style={styles.panelTotal}>{Math.round(total).toLocaleString('en-US')}</AppText> : null}
      </View>
      {/* Rows share the column height, so a short side fills the same space as a long one. */}
      <View style={styles.panelRows}>
        {shown.map((player, i) => (
          <AssetRow
            key={`${player.player_id}-${i}`}
            player={player}
            side={side}
            trackKey={`${keyPrefix}-${player.player_id ?? i}`}
            onAvatarSettle={onAvatarSettle}
          />
        ))}
        {shownPicks.map((pick) => (
          <View key={pick.pick_id} style={[styles.assetRow, { backgroundColor: SIDE_TINT[side], borderColor: `${SIDE_COLOR[side]}59` }]}>
            <View style={styles.pickBadge}>
              <AppText style={styles.pickBadgeText}>{pick.round ? `R${pick.round}` : 'PK'}</AppText>
            </View>
            <View style={styles.assetTextGroup}>
              <AppText style={styles.assetName} numberOfLines={2}>
                {[pick.season, pick.round ? `Round ${pick.round}` : ''].filter(Boolean).join(' ') || pick.label || 'Draft pick'}
              </AppText>
              <AppText style={styles.assetMeta}>Draft pick</AppText>
            </View>
            {pick.score != null ? <AppText style={styles.assetValue}>{Math.round(pick.score).toLocaleString('en-US')}</AppText> : null}
          </View>
        ))}
      </View>
      {hidden > 0 ? <AppText style={styles.more}>{`+${hidden} more`}</AppText> : null}
    </View>
  );
}

/**
 * The literal graphic that gets captured + shared, laid out like web-next's
 * trade share card (lib/shareCard/tradeCard) and the in-app Trade Hub card:
 * header, YOU SEND (red) / YOU GET (green) columns, the verdict chip + Balance
 * line + confidence meter, WHY, and the
 * shared ShareCardChrome footer. Built from the same TradeVerdict data the
 * on-screen card shows. Rendered at a fixed 360x620 logical size so
 * react-native-view-shot's capture is consistent across devices.
 *
 * `onReadyChange` reports whether every rendered player headshot has
 * settled (loaded, failed, or had no id to load) — see PlayerAvatar's
 * onLoadSettle doc comment for why a capturer needs this. It fires
 * synchronously false→true→false as props change, so a caller (the share
 * modal) should treat the latest value as the source of truth, not a
 * one-shot event.
 *
 * `sendTotal`/`receiveTotal` are the engine's own per-side value totals
 * (Trade Hub's send_score/receive_score); omitted when the caller doesn't
 * have them, so the card never sums a partial (pick-less) player list.
 * `myTeamName` falls back to "You".
 */
const TradeShareCard = forwardRef<View, {
  leagueName: string;
  verdict: TradeVerdict;
  sendPlayers: RankedPlayer[];
  receivePlayers: RankedPlayer[];
  partnerTeamName?: string;
  partnerTeamAvatarUrl?: string | null;
  myTeamName?: string;
  sendTotal?: number;
  receiveTotal?: number;
  /** Draft picks on each side (Trade Analyzer). Listed after the players. */
  sendPicks?: DraftPickAsset[];
  receivePicks?: DraftPickAsset[];
  /** Trade Analyzer card: a pitch to the partner instead of verdict/edge/why. */
  pitchMode?: boolean;
  onReadyChange?: (ready: boolean) => void;
}>(({ leagueName, verdict, sendPlayers, receivePlayers, partnerTeamName, partnerTeamAvatarUrl, myTeamName, sendTotal, receiveTotal, sendPicks = [], receivePicks = [], pitchMode, onReadyChange }, ref) => {
  const me = myTeamName?.trim() || 'You';
  const partner = partnerTeamName?.trim() || 'Partner';
  const gain = verdict.value_delta;
  const band = verdict.band?.trim() || '';
  const pitch = pitchMode
    ? buildPartnerPitch(
        [...sendPlayers.map(playerPitchAsset), ...sendPicks.map(pickPitchAsset)],
        [...receivePlayers.map(playerPitchAsset), ...receivePicks.map(pickPitchAsset)],
        partnerTeamName,
      )
    : null;
  // Analyzer totals come from the assets themselves (players + picks).
  const sendSum = sendTotal ?? (pitchMode ? sumScores(sendPlayers, sendPicks) : undefined);
  const receiveSum = receiveTotal ?? (pitchMode ? sumScores(receivePlayers, receivePicks) : undefined);
  const verdictColor = bandColor(band, HEADLINE_COLOR[verdict.tone]);
  const balanceColor = gain > 0 ? colors.success : gain < 0 ? colors.danger : colors.textSecondary;
  const lowConfidence = (verdict.confidence || '').trim().toLowerCase().startsWith('low');
  const sendShown = sendPlayers.slice(0, MAX_ROWS);
  const receiveShown = receivePlayers.slice(0, MAX_ROWS);
  const trackedKeys = useMemo(
    () => [
      ...sendShown.map((p, i) => `send-${p.player_id ?? i}`),
      ...receiveShown.map((p, i) => `receive-${p.player_id ?? i}`),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sendShown.map((p) => p.player_id).join(','), receiveShown.map((p) => p.player_id).join(',')],
  );
  const trackedSignature = trackedKeys.join('|');

  const [settledKeys, setSettledKeys] = useState<Set<string>>(new Set());
  const handleAvatarSettle = React.useCallback((key: string) => {
    setSettledKeys((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
  }, []);
  const allSettled = trackedKeys.every((k) => settledKeys.has(k));

  // Re-arm the timeout safety net whenever the actual trade content changes.
  const [forceReady, setForceReady] = useState(false);
  useEffect(() => {
    setForceReady(false);
    const timer = setTimeout(() => setForceReady(true), AVATAR_READY_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [trackedSignature]);

  const ready = allSettled || forceReady;
  useEffect(() => {
    onReadyChange?.(ready);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  const confidenceLabel = (verdict.confidence || '').trim();
  const why = (verdict.rationale || '').trim();

  return (
    <ShareCardChrome
      ref={ref}
      kind="Trade"
      height={CARD_HEIGHT}
      headerRight={
        <AppText style={styles.leagueName} numberOfLines={1}>
          {leagueName.toUpperCase()}
        </AppText>
      }
    >
      <View style={styles.matchup}>
        <TeamAvatar avatarId={null} size={20} />
        <AppText style={styles.matchupName} numberOfLines={1}>
          {me}
        </AppText>
        <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
        <TeamAvatar avatarId={partnerTeamAvatarUrl} size={20} />
        <AppText style={styles.matchupName} numberOfLines={1}>
          {partner}
        </AppText>
      </View>

      <View style={styles.panelsRow}>
        <ExchangePanel
          label={pitchMode ? TRADE_SHARE_COPY.pitchSend : TRADE_SHARE_COPY.send}
          side="send"
          total={sendSum}
          players={sendPlayers}
          picks={sendPicks}
          keyPrefix="send"
          onAvatarSettle={handleAvatarSettle}
        />
        <ExchangePanel
          label={pitchMode ? TRADE_SHARE_COPY.pitchGet : TRADE_SHARE_COPY.get}
          side="get"
          total={receiveSum}
          players={receivePlayers}
          picks={receivePicks}
          keyPrefix="receive"
          onAvatarSettle={handleAvatarSettle}
        />
      </View>

      {pitch ? (
        <ShareGlass style={styles.verdictBlock}>
          <AppText style={styles.pitchHeadline} numberOfLines={2} adjustsFontSizeToFit>
            {pitch.headline}
          </AppText>
          {pitch.lines.length ? <AppText style={styles.whyLabel}>WHY IT WORKS FOR YOU</AppText> : null}
          {pitch.lines.map((line) => (
            <AppText key={line} style={styles.pitchLine} numberOfLines={1}>{`\u2022 ${line}`}</AppText>
          ))}
        </ShareGlass>
      ) : (
      <ShareGlass style={styles.verdictBlock}>
        {band ? (
          <View style={[styles.bandChip, { borderColor: verdictColor, backgroundColor: `${verdictColor}1F` }]}>
            <AppText style={[styles.bandChipText, { color: verdictColor }]} numberOfLines={1}>
              {band.toUpperCase()}
            </AppText>
          </View>
        ) : null}
        <View style={styles.balanceRow}>
          <AppText style={styles.balanceLabel}>{TRADE_SHARE_COPY.balance.toUpperCase()}</AppText>
          <AppText style={[styles.balanceValue, { color: balanceColor }]}>{formatTradeGain(gain)}</AppText>
        </View>
        {confidenceLabel ? (
          <View style={styles.meterWrap}>
            <ShareConfidenceBars
              level={confidenceLevelFor(confidenceLabel)}
              label={`${confidenceLabel.replace(/ confidence$/i, '')} confidence`}
            />
          </View>
        ) : null}
        {lowConfidence ? <AppText style={styles.lowNote}>{LOW_CONFIDENCE_NOTE}</AppText> : null}
      </ShareGlass>
      )}

      {why && !pitch ? (
        <ShareGlass style={styles.whyBlock}>
          <AppText style={styles.whyLabel}>WHY</AppText>
          <AppText style={styles.whyText} numberOfLines={5}>
            {why}
          </AppText>
        </ShareGlass>
      ) : null}
    </ShareCardChrome>
  );
});
TradeShareCard.displayName = 'TradeShareCard';

export default TradeShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  leagueName: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6, maxWidth: 120 },
  pitchHeadline: { fontSize: 22, fontWeight: '900', letterSpacing: -0.3, color: colors.textPrimary },
  pitchLine: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pickBadge: { width: 34, height: 34, borderRadius: radii.sm, alignItems: 'center', justifyContent: 'center', backgroundColor: `${colors.accent}22`, borderWidth: 1, borderColor: `${colors.accent}80` },
  pickBadgeText: { fontSize: 11, fontWeight: '800', color: colors.accent },
  matchup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 2 },
  matchupName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
  panelsRow: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm, alignItems: 'stretch' },
  panel: { flex: 1, gap: 6 },
  panelHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  panelLabel: { fontSize: 9, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1.4 },
  panelTotal: { flex: 1, textAlign: 'right', fontSize: 16, fontWeight: '800', color: colors.textSecondary },
  panelRows: { flex: 1, gap: 6 },
  assetRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 6,
    paddingVertical: 4,
    minHeight: 46,
    borderRadius: radii.sm,
    borderWidth: 1,
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 11, fontWeight: '800', color: colors.textPrimary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  assetMeta: { fontSize: 9, color: colors.textTertiary, flexShrink: 1 },
  assetRight: { alignItems: 'center', gap: 1 },
  assetValue: { fontSize: 9, fontWeight: '800', color: colors.textPrimary },
  more: { fontSize: 10, fontWeight: '700', color: colors.textTertiary },
  verdictBlock: { marginTop: spacing.md, padding: spacing.md, gap: 6, borderColor: `${colors.accent}66` },
  bandChip: { alignSelf: 'flex-start', borderWidth: 1.5, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 3 },
  bandChipText: { fontSize: 15, fontWeight: '900', letterSpacing: 1.2 },
  balanceRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  balanceLabel: { fontSize: 10, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1.4 },
  balanceValue: { fontSize: 28, fontWeight: '900', letterSpacing: -0.5 },
  lowNote: { fontSize: 10, fontWeight: '600', color: WARNING },
  meterWrap: { marginTop: 2 },
  whyBlock: { marginTop: spacing.sm, padding: spacing.md, gap: 3 },
  whyLabel: { fontSize: 10, fontWeight: '800', color: colors.accent, letterSpacing: 2 },
  whyText: { fontSize: 11, color: colors.textSecondary, lineHeight: 15 },
});

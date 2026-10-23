import React, { forwardRef, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from './AppText';

import type { RankedPlayer, TradeVerdict } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import { confidenceLevelFor } from './ConfidenceMeter';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';
import PositionBadge from './PositionBadge';
import ShareCardChrome, { CARD_WIDTH, ShareConfidenceBars, ShareGlass } from './ShareCardChrome';
import TeamAvatar from './TeamAvatar';
import { analyzerHeadline, partnerForLine } from '../lib/tradeShareLabels';

const CARD_HEIGHT = 620;
// Safety net only — NOT the fix. If some avatar never fires onLoad/onError
// (e.g. a hung request), don't leave the share button stuck forever. The
// real fix is waiting for PlayerAvatar's onLoadSettle below.
const AVATAR_READY_TIMEOUT_MS = 4000;
const MAX_ROWS = 3;

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

function AssetRow({
  player,
  trackKey,
  onAvatarSettle,
}: {
  player: RankedPlayer;
  trackKey: string;
  onAvatarSettle: (key: string) => void;
}) {
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar
        playerId={player.player_id}
        size={30}
        tier={player.tier}
        onLoadSettle={() => onAvatarSettle(trackKey)}
      />
      <View style={styles.assetTextGroup}>
        <PlayerNameText name={player.name ?? 'Unknown'} style={styles.assetName} />
        <View style={styles.assetMetaRow}>
          <PositionBadge position={player.position} />
          <AppText style={styles.assetMeta} numberOfLines={1}>
            {player.team}
          </AppText>
        </View>
      </View>
    </View>
  );
}

function ReceivesPanel({
  teamName,
  avatarId,
  accent,
  total,
  players,
  keyPrefix,
  onAvatarSettle,
}: {
  teamName: string;
  avatarId?: string | null;
  accent: string;
  total?: number;
  players: RankedPlayer[];
  keyPrefix: string;
  onAvatarSettle: (key: string) => void;
}) {
  const shown = players.slice(0, MAX_ROWS);
  const hidden = players.length - shown.length;
  return (
    <ShareGlass style={[styles.panel, { borderColor: `${accent}8C` }]}>
      <View style={styles.panelHead}>
        <TeamAvatar avatarId={avatarId} size={22} />
        <AppText style={[styles.panelTeam, { color: accent }]} numberOfLines={1}>
          {teamName.toUpperCase()}
        </AppText>
      </View>
      <View style={styles.panelTotalRow}>
        <AppText style={styles.panelReceives}>RECEIVES</AppText>
        {total != null ? <AppText style={styles.panelTotal}>{Math.round(total).toLocaleString('en-US')}</AppText> : null}
      </View>
      {shown.map((player, i) => (
        <AssetRow
          key={`${player.player_id}-${i}`}
          player={player}
          trackKey={`${keyPrefix}-${player.player_id ?? i}`}
          onAvatarSettle={onAvatarSettle}
        />
      ))}
      {hidden > 0 ? <AppText style={styles.more}>{`+${hidden} more`}</AppText> : null}
    </ShareGlass>
  );
}

/**
 * The literal graphic that gets captured + shared, laid out like web-next's
 * trade share card (lib/shareCard/tradeCard): header, two RECEIVES panels
 * with swap arrows, the verdict word + edge + confidence meter, WHY, and the
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
  /** Trade Analyzer card: grade word as the headline + "For <partner>" line. */
  analyzer?: boolean;
  onReadyChange?: (ready: boolean) => void;
}>(({ leagueName, verdict, sendPlayers, receivePlayers, partnerTeamName, partnerTeamAvatarUrl, myTeamName, sendTotal, receiveTotal, analyzer, onReadyChange }, ref) => {
  const me = myTeamName?.trim() || 'You';
  const partner = partnerTeamName?.trim() || 'Partner';
  const gain = verdict.value_delta;
  const band = verdict.band?.trim() || '';
  const headline = (analyzer ? analyzerHeadline(verdict.ui_verdict) : null) || band;
  const forLine = analyzer ? partnerForLine(partnerTeamName) : null;
  const verdictColor = bandColor(band, HEADLINE_COLOR[verdict.tone]);
  const edge =
    gain === 0
      ? { text: 'Even value', color: colors.textSecondary }
      : gain > 0
        ? { text: `Edge: ${me} +${Math.round(gain).toLocaleString('en-US')}`, color: colors.successBright }
        : { text: `Edge: ${partner} +${Math.round(Math.abs(gain)).toLocaleString('en-US')}`, color: colors.danger };

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
      {forLine ? (
        <AppText style={styles.forLine} numberOfLines={1}>
          {forLine.toUpperCase()}
        </AppText>
      ) : null}
      <View style={styles.matchup}>
        <AppText style={styles.matchupName} numberOfLines={1}>
          {me}
        </AppText>
        <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
        <AppText style={styles.matchupName} numberOfLines={1}>
          {partner}
        </AppText>
      </View>

      <View style={styles.panelsRow}>
        <ReceivesPanel
          teamName={me}
          accent={colors.accent}
          total={receiveTotal}
          players={receivePlayers}
          keyPrefix="receive"
          onAvatarSettle={handleAvatarSettle}
        />
        <ReceivesPanel
          teamName={partner}
          avatarId={partnerTeamAvatarUrl}
          accent={colors.premium}
          total={sendTotal}
          players={sendPlayers}
          keyPrefix="send"
          onAvatarSettle={handleAvatarSettle}
        />
        <View style={styles.swapDisc} pointerEvents="none">
          <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
        </View>
      </View>

      <ShareGlass style={styles.verdictBlock}>
        <AppText style={[styles.verdictWord, { color: verdictColor }]} numberOfLines={1} adjustsFontSizeToFit>
          {headline || 'Trade idea'}
        </AppText>
        <AppText style={[styles.edge, { color: edge.color }]} numberOfLines={1}>
          {edge.text}
        </AppText>
        {confidenceLabel ? (
          <View style={styles.meterWrap}>
            <ShareConfidenceBars
              level={confidenceLevelFor(confidenceLabel)}
              label={`${confidenceLabel.replace(/ confidence$/i, '')} confidence`}
            />
          </View>
        ) : null}
      </ShareGlass>

      {why ? (
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
  forLine: { fontSize: 10, fontWeight: '800', color: colors.accent, letterSpacing: 1.6, marginTop: 2 },
  matchup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 2 },
  matchupName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
  panelsRow: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm },
  panel: { flex: 1, padding: spacing.sm, gap: 6, borderWidth: 1.5 },
  panelHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  panelTeam: { flex: 1, fontSize: 11, fontWeight: '800', letterSpacing: 0.2 },
  panelTotalRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  panelReceives: { fontSize: 8, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1.6 },
  panelTotal: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
  assetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    padding: 4,
    borderRadius: radii.sm,
    backgroundColor: 'rgba(255,255,255,0.045)',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 11, fontWeight: '700', color: colors.textPrimary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 1 },
  assetMeta: { fontSize: 10, color: colors.textSecondary },
  more: { fontSize: 10, fontWeight: '700', color: colors.textTertiary },
  swapDisc: {
    position: 'absolute',
    alignSelf: 'center',
    left: '50%',
    top: '38%',
    marginLeft: -15,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: `${colors.accent}80`,
  },
  verdictBlock: { marginTop: spacing.md, padding: spacing.md, gap: 4, borderColor: `${colors.accent}66` },
  verdictWord: { fontSize: 30, fontWeight: '900', letterSpacing: -0.5 },
  edge: { fontSize: 14, fontWeight: '800' },
  meterWrap: { marginTop: 4 },
  whyBlock: { marginTop: spacing.sm, padding: spacing.md, gap: 3 },
  whyLabel: { fontSize: 10, fontWeight: '800', color: colors.accent, letterSpacing: 2 },
  whyText: { fontSize: 11, color: colors.textSecondary, lineHeight: 15 },
});

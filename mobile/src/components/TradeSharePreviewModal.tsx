import React, { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';
import { Ionicons } from '@expo/vector-icons';

import { api, type RankedPlayer, type TradeVerdict } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import TradeShareCard, { CARD_HEIGHT, CARD_WIDTH } from './TradeShareCard';

const PREVIEW_SCALE = 0.82;

interface Props {
  visible: boolean;
  onClose: () => void;
  leagueId: string;
  leagueName: string;
  partnerTeamName?: string;
  verdict: TradeVerdict;
  sendPlayers: RankedPlayer[];
  receivePlayers: RankedPlayer[];
}

/** Preview + share sheet for the real branded trade PNG, plus a fallback plain-text share. */
export default function TradeSharePreviewModal({
  visible,
  onClose,
  leagueId,
  leagueName,
  partnerTeamName,
  verdict,
  sendPlayers,
  receivePlayers,
}: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);

  // Best-effort: a share sheet dismissed without sending still gets recorded
  // (the later "did this happen?" prompt already has a "Didn't send" answer
  // for exactly this ambiguity — most share APIs don't reliably report
  // completion, so recording optimistically beats not asking at all).
  const recordShare = () => {
    void api
      .recordTradeShare(leagueId, {
        partnerTeamName,
        send: sendPlayers.map((p) => ({ name: p.name ?? 'Unknown', position: p.position ?? '' })),
        receive: receivePlayers.map((p) => ({ name: p.name ?? 'Unknown', position: p.position ?? '' })),
        valueEdgeLabel: verdict.band,
      })
      .catch(() => {});
  };

  const onShareImage = async () => {
    if (!cardRef.current) return;
    setCapturing(true);
    try {
      const uri = await captureRef(cardRef, {
        format: 'png',
        quality: 1,
        result: 'tmpfile',
        width: CARD_WIDTH * 3,
        height: CARD_HEIGHT * 3,
      });
      const canShare = await Sharing.isAvailableAsync();
      if (canShare) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share trade' });
        recordShare();
      }
    } catch {
      // Fall through silently — the text-share fallback below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    const sendNames = sendPlayers.map((p) => p.name ?? 'Unknown').join(', ') || 'Nothing';
    const receiveNames = receivePlayers.map((p) => p.name ?? 'Unknown').join(', ') || 'Nothing';
    const lines = [
      `${leagueName} trade — ${verdict.band} (${verdict.confidence})`,
      '',
      `You send: ${sendNames}`,
      `You receive: ${receiveNames}`,
      '',
      verdict.rationale,
      '',
      `Value: ${verdict.value_summary}`,
      `Roster fit: ${verdict.roster_summary}`,
      `Strategy fit: ${verdict.strategy_summary}`,
      `Risk: ${verdict.risk_summary}`,
      verdict.counter_guidance ? `Counter guidance: ${verdict.counter_guidance}` : '',
      '',
      'Analyzed with FantasyGM Lab',
    ].filter(Boolean);
    Share.share({ message: lines.join('\n') })
      .then(recordShare)
      .catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <AppText style={styles.title}>Share this trade</AppText>
          <View style={styles.previewWrap}>
            <View style={styles.previewScaled}>
              <TradeShareCard
                ref={cardRef}
                leagueName={leagueName}
                verdict={verdict}
                sendPlayers={sendPlayers}
                receivePlayers={receivePlayers}
              />
            </View>
          </View>
          <TouchableOpacity style={styles.primaryButton} onPress={onShareImage} disabled={capturing}>
            {capturing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="image-outline" size={16} color="#fff" />
                <AppText style={styles.primaryButtonText}>Share image</AppText>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={onShareText}>
            <AppText style={styles.secondaryButtonText}>Share as text instead</AppText>
          </TouchableOpacity>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <AppText style={styles.closeButtonText}>Cancel</AppText>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  sheet: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
  // The card renders at its real CARD_WIDTH/CARD_HEIGHT (react-native-view-shot
  // captures it full-resolution via cardRef), then gets visually shrunk to fit
  // the modal. A bare `transform: scale` doesn't shrink the LAYOUT box though —
  // it only shrinks what's drawn inside it — so the wrapper below is sized to
  // the post-scale dimensions and clips the now-oversized layout box down to
  // exactly that size, with the scale anchored at its top-left corner instead
  // of the default center (so it shrinks into the wrapper's corner, not out
  // past all four edges). That replaces a `marginVertical: -45` hand-tuned
  // fudge factor that didn't quite match the real overflow.
  previewWrap: {
    width: CARD_WIDTH * PREVIEW_SCALE,
    height: CARD_HEIGHT * PREVIEW_SCALE,
    overflow: 'hidden',
  },
  previewScaled: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    transform: [{ scale: PREVIEW_SCALE }],
    transformOrigin: '0 0',
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    width: '100%',
    marginTop: spacing.md,
  },
  primaryButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  secondaryButton: { paddingVertical: spacing.sm, marginTop: spacing.xs },
  secondaryButtonText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  closeButton: { paddingVertical: spacing.sm },
  closeButtonText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}

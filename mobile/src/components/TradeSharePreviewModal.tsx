import React, { useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Share, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';
import { Ionicons } from '@expo/vector-icons';

import type { RankedPlayer, TradeVerdict } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import TradeShareCard, { CARD_HEIGHT, CARD_WIDTH } from './TradeShareCard';

interface Props {
  visible: boolean;
  onClose: () => void;
  leagueName: string;
  verdict: TradeVerdict;
  sendPlayers: RankedPlayer[];
  receivePlayers: RankedPlayer[];
}

/** Preview + share sheet for the real branded trade PNG, plus a fallback plain-text share. */
export default function TradeSharePreviewModal({
  visible,
  onClose,
  leagueName,
  verdict,
  sendPlayers,
  receivePlayers,
}: Props) {
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);

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
    Share.share({ message: lines.join('\n') }).catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>Share this trade</Text>
          <View style={styles.previewWrap}>
            <TradeShareCard
              ref={cardRef}
              leagueName={leagueName}
              verdict={verdict}
              sendPlayers={sendPlayers}
              receivePlayers={receivePlayers}
            />
          </View>
          <TouchableOpacity style={styles.primaryButton} onPress={onShareImage} disabled={capturing}>
            {capturing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="image-outline" size={16} color="#fff" />
                <Text style={styles.primaryButtonText}>Share image</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={onShareText}>
            <Text style={styles.secondaryButtonText}>Share as text instead</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeButtonText}>Cancel</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
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
    borderColor: colors.border,
    padding: spacing.lg,
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
  previewWrap: {
    transform: [{ scale: 0.82 }],
    marginVertical: -45,
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

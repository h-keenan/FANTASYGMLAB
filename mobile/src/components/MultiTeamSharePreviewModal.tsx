import React, { useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, Share, StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';

import AppText from './AppText';
import Button from './Button';
import MultiTeamTradeShareCard, { multiShareCardHeight } from './MultiTeamTradeShareCard';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import { CARD_WIDTH } from './ShareCardChrome';
import { trackUse } from '../lib/analytics';
import { buildShareText, type ShareModel } from '../lib/multiTeamTrade';
import { shareLink } from '../lib/shareLinks';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

const PREVIEW_SCALE = 0.7;

/**
 * Preview + share sheet for the multi-team trade PITCH picture. This is the
 * share surface (persuasion framed, for the other managers), separate from
 * the private analysis on screen. Same flow as TradeSharePreviewModal:
 * capture the real card with view-shot, with a plain-text fallback.
 */
export default function MultiTeamSharePreviewModal({
  visible,
  onClose,
  leagueId,
  leagueName,
  model,
}: {
  visible: boolean;
  onClose: () => void;
  leagueId: string;
  leagueName: string;
  model: ShareModel;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);
  const height = multiShareCardHeight(model);

  const recordShare = () => trackUse('share_card', 'shared', { leagueId, props: { item_kind: 'multi_team_trade' } });

  const onShareImage = async () => {
    if (!cardRef.current) return;
    setCapturing(true);
    try {
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      const uri = await captureRef(cardRef, { format: 'png', quality: 1, result: 'tmpfile', width: CARD_WIDTH * 3, height: height * 3 });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share trade' });
        recordShare();
      }
    } catch {
      // The text share below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    Share.share({ message: [buildShareText(model, leagueName), '', shareLink('trade')].join('\n') })
      .then(recordShare)
      .catch(() => {});
  };

  return (
    <SheetModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose}>
          <AppText style={styles.title}>Pitch this trade</AppText>
          <ScrollView style={styles.previewScroll} contentContainerStyle={styles.previewContent}>
            <View style={{ width: CARD_WIDTH * PREVIEW_SCALE, height: height * PREVIEW_SCALE, overflow: 'hidden' }}>
              <View style={{ width: CARD_WIDTH, height, transform: [{ scale: PREVIEW_SCALE }], transformOrigin: '0 0' }}>
                <MultiTeamTradeShareCard ref={cardRef} model={model} leagueName={leagueName} />
              </View>
            </View>
          </ScrollView>
          <AppText style={styles.note}>Written for the other managers. It shows every team&apos;s real value change.</AppText>
          <Button label="Share image" onPress={onShareImage} loading={capturing} style={styles.primary} />
          <PressableScale style={styles.secondary} onPress={onShareText} accessibilityRole="button">
            <AppText style={styles.secondaryText}>Share as text instead</AppText>
          </PressableScale>
          <PressableScale style={styles.close} onPress={onClose} accessibilityRole="button">
            <AppText style={styles.closeText}>Cancel</AppText>
          </PressableScale>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      alignItems: 'center',
      width: '100%',
      maxWidth: 400,
      maxHeight: '92%',
    },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
    previewScroll: { flexGrow: 0, maxHeight: 420 },
    previewContent: { alignItems: 'center' },
    note: { fontSize: 12, color: colors.textSecondary, textAlign: 'center', marginTop: spacing.sm },
    primary: { width: '100%', marginTop: spacing.md },
    secondary: { paddingVertical: spacing.sm, marginTop: spacing.xs },
    secondaryText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
    close: { paddingVertical: spacing.sm },
    closeText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}

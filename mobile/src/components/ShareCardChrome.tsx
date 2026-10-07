import React, { forwardRef } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import QRCode from 'react-native-qrcode-svg';

import { colors, radii, spacing } from '../theme';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 540;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const QR_SIZE = 60;

/**
 * Shared chrome for every branded share-card PNG: the FGL logo/wordmark
 * header (with an optional per-card right-side slot — a TierBadge, a
 * "HEAD-TO-HEAD" label, a league name, etc.), the hairline divider under it,
 * the "SCAN TO TRY" QR + tagline footer row, and the PLAN./PROJECT./WIN.
 * footer line. Pulled out of PlayerShareCard (the original single-player
 * share card) so every share surface renders the exact same header/QR/
 * footer markup instead of each card re-implementing its own copy of it —
 * same "shared primitive, page/card supplies the content" convention the
 * rest of the app uses for list rows (see UI_HIERARCHY_DIRECTIVE.md §9-10).
 *
 * Always uses the fixed dark `colors` palette (never useThemeMode) and a
 * fixed CARD_WIDTH/CARD_HEIGHT logical size, same as every exported share
 * graphic — the captured PNG must look identical regardless of the
 * viewer's light/dark setting or device. `children` is the card-specific
 * content; it sits between the header hairline and the QR row, whose
 * `marginTop: 'auto'` pins it (and the footer) to the bottom of the fixed-
 * height card regardless of how tall the content is.
 */
const ShareCardChrome = forwardRef<
  View,
  {
    headerRight?: React.ReactNode;
    qrSubtitle: string;
    children: React.ReactNode;
  }
>(({ headerRight, qrSubtitle, children }, ref) => {
  return (
    <View ref={ref} collapsable={false} style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.brandRow}>
          <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
          <AppText style={styles.brandWord}>
            FANTASY<AppText style={styles.brandWordAccent}>GM</AppText> LAB
          </AppText>
        </View>
        {headerRight}
      </View>

      <View style={styles.hairline} />

      {children}

      <View style={styles.qrRow}>
        <View style={styles.qrTextGroup}>
          <AppText style={styles.qrKicker}>SCAN TO TRY</AppText>
          <AppText style={styles.qrTitle}>FantasyGM Lab</AppText>
          <AppText style={styles.qrSubtitle}>{qrSubtitle}</AppText>
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
ShareCardChrome.displayName = 'ShareCardChrome';

export default ShareCardChrome;
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
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    // 'auto' (not a fixed value) — same trick every pre-existing share card
    // used locally — so flexbox splits whatever vertical room is left in
    // the fixed-height card between this and the footer below, instead of
    // dumping it all into one gap right above the footer.
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

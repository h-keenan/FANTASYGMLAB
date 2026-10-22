import React, { forwardRef } from 'react';
import { Image, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import AppText from './AppText';
import QRCode from 'react-native-qrcode-svg';

import { colors, radii, spacing } from '../theme';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 540;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const SHARE_DOMAIN = 'fantasygmlab.com';
const QR_SIZE = 52;
/** assets/share-lockup-white.png is web-next's public/share-card/lockup-white.png
 * (the real FantasyDesk mark + wordmark, white), 1102x160. */
const LOCKUP_HEIGHT = 20;
const LOCKUP_WIDTH = Math.round(LOCKUP_HEIGHT * (1102 / 160));

/**
 * Glass panel for exported share graphics: the same translucent raised
 * surface + hairline rim as web's `.glass-surface` share cards, drawn from
 * the fixed dark palette (never useThemeMode, and no live blur, so the
 * captured PNG is identical on every device and in light mode). Every share
 * card builds its panels from this instead of restyling its own.
 */
export function ShareGlass({ style, children }: { style?: StyleProp<ViewStyle>; children?: React.ReactNode }) {
  return <View style={[styles.glass, style]}>{children}</View>;
}

/** 1-3 segment confidence meter, fixed palette (see ConfidenceMeter for the
 * in-app, themed twin). Level 1 = low, 2 = medium, 3 = high. */
export function ShareConfidenceBars({ level, label }: { level: number; label: string }) {
  const color = level >= 3 ? colors.successBright : level === 2 ? colors.premium : '#F59E0B';
  return (
    <View style={styles.meter}>
      <View style={styles.meterBars}>
        {[1, 2, 3].map((n) => (
          <View
            key={n}
            style={[styles.meterBar, { height: 5 + n * 3, backgroundColor: n <= level ? color : colors.borderStrong }]}
          />
        ))}
      </View>
      <AppText style={styles.meterLabel}>{label.toUpperCase()}</AppText>
    </View>
  );
}

/**
 * Shared chrome for every branded share-card PNG: the FantasyDesk lockup
 * header (with an optional `kind` kicker under it, e.g. "TRADE", and an
 * optional per-card right-side slot — a TierBadge, a league name, etc.), the
 * glass QR footer ("fantasygmlab.com / Scan to try FantasyDesk") and the
 * PLAN./PROJECT./WIN. tagline. Every share surface (player, compare, trade,
 * portfolio, recap) renders this exact header/footer so they read as one
 * family — same "shared primitive, card supplies the content" convention the
 * rest of the app uses for list rows (see UI_HIERARCHY_DIRECTIVE.md §9-10),
 * and the same layout as web-next's lib/shareCard frame.
 *
 * Always uses the fixed dark `colors` palette (never useThemeMode) and a
 * fixed CARD_WIDTH x `height` logical size, same as every exported share
 * graphic — the captured PNG must look identical regardless of the viewer's
 * light/dark setting or device. `children` is the card-specific content; the
 * QR row's `marginTop: 'auto'` pins it to the bottom of the fixed-height
 * card regardless of how tall the content is.
 */
const ShareCardChrome = forwardRef<
  View,
  {
    kind?: string;
    headerRight?: React.ReactNode;
    height?: number;
    children: React.ReactNode;
  }
>(({ kind, headerRight, height = CARD_HEIGHT, children }, ref) => {
  return (
    <View ref={ref} collapsable={false} style={[styles.card, { height }]}>
      <View style={styles.headerRow}>
        <View>
          <Image
            // eslint-disable-next-line @typescript-eslint/no-require-imports
            source={require('../../assets/share-lockup-white.png')}
            style={styles.lockup}
            resizeMode="contain"
            accessibilityLabel="FantasyDesk"
          />
          {kind ? <AppText style={styles.kind}>{kind.toUpperCase()}</AppText> : null}
        </View>
        {headerRight}
      </View>

      <View style={styles.hairline} />

      {children}

      <ShareGlass style={styles.qrRow}>
        <View style={styles.qrWrap}>
          <QRCode value={SHARE_QR_URL} size={QR_SIZE} color={colors.background} backgroundColor="#fff" ecl="M" />
        </View>
        <View style={styles.qrTextGroup}>
          <AppText style={styles.qrDomain}>{SHARE_DOMAIN}</AppText>
          <AppText style={styles.qrSubtitle}>Scan to try FantasyDesk</AppText>
        </View>
        <View style={styles.tagline}>
          <AppText style={[styles.taglineText, { color: colors.accent }]}>PLAN.</AppText>
          <AppText style={[styles.taglineText, { color: colors.premium }]}>PROJECT.</AppText>
          <AppText style={[styles.taglineText, { color: colors.danger }]}>WIN.</AppText>
        </View>
      </ShareGlass>
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
  glass: {
    backgroundColor: 'rgba(38,44,52,0.78)',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
    borderTopColor: 'rgba(255,255,255,0.22)',
  },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  lockup: { width: LOCKUP_WIDTH, height: LOCKUP_HEIGHT },
  kind: { fontSize: 9, fontWeight: '800', color: colors.accent, letterSpacing: 3, marginTop: 4 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 'auto',
    padding: spacing.sm,
    gap: spacing.md,
  },
  qrTextGroup: { flex: 1 },
  qrDomain: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
  qrSubtitle: { fontSize: 10, color: colors.textSecondary, marginTop: 2 },
  qrWrap: { padding: 4, backgroundColor: '#fff', borderRadius: radii.sm },
  tagline: { alignItems: 'flex-end' },
  taglineText: { fontSize: 9, fontWeight: '800', letterSpacing: 1.2, lineHeight: 11 },
  meter: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  meterBars: { flexDirection: 'row', alignItems: 'flex-end', gap: 2 },
  meterBar: { width: 4, borderRadius: 1 },
  meterLabel: { fontSize: 9, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 },
});

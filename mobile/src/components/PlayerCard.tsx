import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, TouchableOpacity, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  ReduceMotion,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import OverallRatingBadge from './OverallRatingBadge';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { bestAvailableCardVisual } from '../lib/bestAvailableCardVisual';
import type { PlayerCardBackStat } from '../lib/playerCardBackStats';
import { positionRankPrestige } from '../lib/positionRankPrestige';
import { glowShadow, gradients, lightGradients, motion, radii, shadows, spacing, type ThemeColors } from '../theme';

export type { PlayerCardBackStat };

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export interface PlayerCardProps {
  playerId: string | null | undefined;
  name: string | null | undefined;
  position?: string | null;
  /** Raw stored tier (e.g. "Elite") — drives the avatar ring color only;
   * a human-readable tier label belongs in `backStats` (see
   * lib/playerCardBackStats.ts for the Trade Hub mapping). */
  tier?: string | null;
  overallRating?: number | null;
  /** League-wide/pool position rank (never team-roster-relative — see
   * lib/positionRankPrestige.ts). Top-5 gets the prestige glow border;
   * everyone else (or omitted) gets the plain card. */
  positionRank?: number | null;
  /** Short injury status (e.g. "Questionable"). Drives a small persistent
   * dot on the front-face avatar so an injury is never fully hidden behind
   * a flip — the full status text belongs in `backStats`. Falsy = healthy. */
  injuryLabel?: string | null;
  /** Back-face stat rows — the caller supplies these from data it already
   * has for this player; PlayerCard never fetches or invents fields. */
  backStats?: PlayerCardBackStat[];
  /** Optional longer free-text line shown above the stat rows on the back
   * face (e.g. a role/opportunity rationale sentence). */
  backNote?: string | null;
  /** Called when the user activates the "view full profile" affordance —
   * wire this to `navigation.navigate('PlayerDetail', ...)` at the call
   * site. Omit to hide the affordance entirely (e.g. a pick has none). */
  onOpenDetail?: () => void;
  /** Explicit square size in px — omit to size from the parent's own width
   * via `aspectRatio: 1` (e.g. a flex:1 column), the more common case. */
  size?: number;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * Shared, reusable, flippable compact player card.
 *
 * coridian_ (Discord, this pass, circling Trade Hub's "YOU SEND" card):
 * "I want to make the compact player card, similar to this... I believe
 * this module or pill is littered throughout the app. We need to use many
 * of the components and badges from this. Make it more square, incorporate
 * the prestige around the border, and put an overall in the top right
 * corner and the name in the bottom, and then whenever you tap on it, the
 * card flips... you see other pertinent stats very quickly, and then we'd
 * have to incorporate a way for you to open up the PQV."
 *
 * The front face is the same visual language `WaiversScreen.tsx`'s
 * `BestAvailableCard` / `LeagueDetailScreen.tsx`'s `WaiverSuggestionCard`
 * already established (square card, prestige-tier glow border via
 * `bestAvailableCardVisual`/`positionRankPrestige`, OVR top-right, name
 * bottom-center dominant per UI_HIERARCHY_DIRECTIVE.md §11) — generalized
 * here rather than re-invented, and NOT yet adopted by those two screens
 * (explicitly deferred to a follow-up pass product-owner wants to review
 * first). What's new here is the flip: tapping the card rotates it on the
 * Y axis (react-native-reanimated, already a dependency — no new animation
 * library) to reveal a back face of `backStats` the caller supplies, plus
 * a "view full profile" affordance into PlayerDetailScreen (the "PQV").
 *
 * Accessibility: the whole card is one accessible element (front-face
 * summary as its label, a hint describing the flip) — VoiceOver/TalkBack's
 * default double-tap action already triggers the flip, so no screen-reader
 * user is required to find a visually-tiny target to do that. The "view
 * full profile" affordance is additionally exposed as a custom
 * accessibility action ("View full player profile") on that same element,
 * so reaching PlayerDetail never requires first performing the flip
 * gesture — see this component's end-of-file note for why this wasn't
 * verified against a real screen reader.
 */
export default function PlayerCard({
  playerId,
  name,
  position,
  tier,
  overallRating,
  positionRank,
  injuryLabel,
  backStats = [],
  backNote,
  onOpenDetail,
  size,
  style,
  testID,
}: PlayerCardProps) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const prestige = positionRankPrestige(positionRank, isDark);
  const visual = bestAvailableCardVisual(prestige.tier);

  const flip = useSharedValue(0); // 0 = front resting, 1 = back resting
  const pressScale = useSharedValue(1);
  const [flipped, setFlipped] = useState(false);

  const toggleFlip = () => {
    const next = !flipped;
    setFlipped(next);
    // `reduceMotion: ReduceMotion.System` makes reanimated itself consult
    // the OS "reduce motion" setting and jump straight to the end value
    // when it's on, instead of this component polling/duplicating that
    // check — see react-native-reanimated's ReduceMotion docs.
    flip.value = withTiming(next ? 1 : 0, {
      duration: motion.easeOutQuintMs,
      easing: Easing.out(Easing.cubic),
      reduceMotion: ReduceMotion.System,
    });
  };

  const frontAnimatedStyle = useAnimatedStyle(() => {
    const rotateY = interpolate(flip.value, [0, 1], [0, 180]);
    return {
      transform: [{ rotateY: `${rotateY}deg` }],
      opacity: flip.value > 0.5 ? 0 : 1,
    };
  });
  const backAnimatedStyle = useAnimatedStyle(() => {
    const rotateY = interpolate(flip.value, [0, 1], [180, 360]);
    return {
      transform: [{ rotateY: `${rotateY}deg` }],
      opacity: flip.value > 0.5 ? 1 : 0,
    };
  });
  const pressAnimatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: pressScale.value }] }));

  const metaBits = [name ?? 'Unknown player', position, overallRating != null ? `${Math.round(overallRating)} overall` : null]
    .filter(Boolean)
    .join(', ');
  const accessibilityLabel = injuryLabel ? `${metaBits}, ${injuryLabel}` : metaBits;

  const rimColors = prestige.color ? ([prestige.color, prestige.color] as const) : isDark ? gradients.accent : lightGradients.accent;
  const rimShadow = prestige.color ? glowShadow(prestige.color) : shadows.orbGlow;

  const pressable = (
    <AnimatedPressable
      testID={testID}
      onPress={toggleFlip}
      onPressIn={() => {
        pressScale.value = withSpring(0.97, motion.pressSpring);
      }}
      onPressOut={() => {
        pressScale.value = withSpring(1, motion.pressSpring);
      }}
      style={[styles.pressable, visual.glow && styles.pressableGlowInner, pressAnimatedStyle]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={flipped ? 'Flips back to show the summary side' : 'Flips to show more stats'}
      accessibilityActions={onOpenDetail ? [{ name: 'viewProfile', label: 'View full player profile' }] : undefined}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'viewProfile') onOpenDetail?.();
      }}
    >
      <View style={styles.faceStack}>
        <Animated.View style={[styles.face, frontAnimatedStyle]}>
          <View style={styles.topRow}>
            {visual.prestigeLabel ? (
              <AppText style={[styles.prestigeLabel, { color: prestige.color ?? colors.textTertiary }]}>
                {visual.prestigeLabel}
              </AppText>
            ) : (
              <View />
            )}
            <OverallRatingBadge rating={overallRating} positionRank={positionRank} />
          </View>
          <View style={styles.avatarWrap}>
            <PlayerAvatar playerId={playerId} size={36} tier={tier} />
            {injuryLabel ? <View style={[styles.injuryDot, { backgroundColor: colors.danger }]} /> : null}
          </View>
          <View style={styles.positionBadgeWrap}>
            <PositionBadge position={position} size="sm" />
          </View>
          <PlayerNameText name={name ?? 'Unknown player'} style={styles.name} />
        </Animated.View>

        <Animated.View style={[styles.face, styles.backFace, backAnimatedStyle]}>
          <View style={styles.backHeaderRow}>
            <PlayerNameText name={name ?? 'Unknown player'} style={styles.backName} />
            <PositionBadge position={position} size="sm" />
          </View>
          {backNote ? (
            <AppText style={styles.backNote} numberOfLines={3}>
              {backNote}
            </AppText>
          ) : null}
          <View style={styles.backStatsList}>
            {backStats.length > 0 ? (
              backStats.map((stat) => (
                <View key={stat.key} style={styles.backStatRow}>
                  <AppText style={styles.backStatLabel} numberOfLines={1}>
                    {stat.label}
                  </AppText>
                  <AppText style={[styles.backStatValue, { color: toneColor(stat.tone, colors) }]} numberOfLines={1}>
                    {stat.value}
                  </AppText>
                </View>
              ))
            ) : !backNote ? (
              <AppText style={styles.backEmpty}>No additional stats yet.</AppText>
            ) : null}
          </View>
        </Animated.View>
      </View>

      {/* Persistent "view full profile" affordance — reachable regardless
          of flip state (see component doc comment). Hidden from the
          accessibility tree on both platforms since the outer card already
          exposes the exact same action via `accessibilityActions` above;
          this stays a plain touch target for sighted/pointer users. */}
      {onOpenDetail ? (
        <TouchableOpacity
          onPress={(event) => {
            event.stopPropagation?.();
            onOpenDetail();
          }}
          style={styles.detailButton}
          hitSlop={8}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          <Ionicons name="open-outline" size={13} color={colors.textPrimary} />
        </TouchableOpacity>
      ) : null}
    </AnimatedPressable>
  );

  return (
    <View style={[styles.aspectWrapper, size ? { width: size } : null, style]}>
      {visual.glow ? (
        <LinearGradient colors={rimColors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.glowRim, rimShadow]}>
          {pressable}
        </LinearGradient>
      ) : (
        pressable
      )}
    </View>
  );
}

function toneColor(tone: PlayerCardBackStat['tone'], colors: ThemeColors): string {
  switch (tone) {
    case 'positive':
      return colors.success;
    case 'negative':
      return colors.danger;
    case 'warning':
      return colors.premium;
    default:
      return colors.textPrimary;
  }
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    aspectWrapper: { width: '100%', aspectRatio: 1 },
    glowRim: { flex: 1, borderRadius: radii.md, padding: 1.5 },
    pressable: {
      flex: 1,
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      ...shadows.resting,
    },
    pressableGlowInner: { borderWidth: 0 },
    // The parent of the two rotating faces gets the 3D perspective; the
    // faces themselves only ever set their own rotateY — RN doesn't merge
    // `transform` arrays across a parent/child style boundary, so this
    // can't collide with either face's animated transform.
    faceStack: { flex: 1, transform: [{ perspective: 1000 }] },
    face: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backfaceVisibility: 'hidden',
      padding: spacing.sm,
      alignItems: 'center',
    },
    backFace: { justifyContent: 'flex-start' },
    topRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      alignSelf: 'stretch',
      minHeight: 14,
      marginBottom: spacing.xs,
    },
    prestigeLabel: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
    avatarWrap: { marginTop: spacing.xs },
    injuryDot: {
      position: 'absolute',
      right: -2,
      bottom: -2,
      width: 10,
      height: 10,
      borderRadius: 5,
      borderWidth: 1.5,
      borderColor: colors.surface,
    },
    positionBadgeWrap: { marginTop: spacing.xs },
    // Most visually dominant text on the card (UI_HIERARCHY_DIRECTIVE.md
    // §11 — player identity must outrank badges/chips), bottom-anchored via
    // `justifyContent` on the front face's own flex layout.
    name: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, marginTop: 'auto', textAlign: 'center' },
    backHeaderRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      alignSelf: 'stretch',
      gap: spacing.xs,
    },
    backName: { flex: 1, fontSize: 13, fontWeight: '800', color: colors.textPrimary },
    backNote: {
      alignSelf: 'stretch',
      fontSize: 10.5,
      color: colors.textSecondary,
      lineHeight: 14,
      marginTop: spacing.xs,
    },
    backStatsList: { alignSelf: 'stretch', marginTop: spacing.xs, gap: 3 },
    backStatRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: spacing.xs },
    backStatLabel: { fontSize: 9.5, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.3 },
    backStatValue: { fontSize: 11, fontWeight: '700', flexShrink: 1, textAlign: 'right' },
    backEmpty: { fontSize: 10.5, color: colors.textTertiary, marginTop: spacing.xs },
    detailButton: {
      position: 'absolute',
      left: 4,
      bottom: 4,
      width: 22,
      height: 22,
      borderRadius: 11,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.backgroundElevated,
    },
  });
}

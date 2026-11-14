import React, { useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import PlayerIdentityRow from './PlayerIdentityRow';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  statusAttentionAria,
  statusHeaderModel,
  type StatusAttentionItem,
  type StatusHeaderModel,
  type StatusMiniStat,
  type StatusRing,
  type StatusTone,
} from '../lib/statusHeader';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * THE players-first status header (docs/ui-patterns.md, "StatusHeader"; twin of web-next/src/components/ui/StatusHeader.tsx):
 * status ring + up to three mini stats, a short "Needs your attention" list of player rows (the shared
 * PlayerIdentityRow, so every row has an avatar), then the one primary action in cyan, then optional CompactModules
 * (`children`). The page hands it a StatusHeaderModel built by lib/statusHeader.ts. Gold is never used here.
 *
 * Navigation: the shared model carries web hrefs; on the app the page puts a route NAME in `href` (e.g. "Matchup") and
 * handles it in `onOpen(href)`.
 */

function toneColor(tone: StatusTone | undefined, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return colors.textPrimary;
  }
}

export function StatusRingMark({ ring, size = 54 }: { ring: StatusRing; size?: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const center = size / 2;
  return (
    <View style={{ width: size, height: size }} accessible accessibilityRole="image" accessibilityLabel={ring.label} testID="status-ring">
      <Svg width={size} height={size}>
        <Circle cx={center} cy={center} r={r} fill="none" stroke={colors.border} strokeWidth={stroke} />
        {ring.pct != null ? (
          <Circle
            cx={center}
            cy={center}
            r={r}
            fill="none"
            stroke={toneColor(ring.tone, colors)}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${(c * ring.pct) / 100} ${c}`}
            rotation={-90}
            originX={center}
            originY={center}
          />
        ) : null}
      </Svg>
      <View style={[StyleSheet.absoluteFillObject, styles.ringCenter]} pointerEvents="none">
        <AppText style={styles.ringText} numberOfLines={1} adjustsFontSizeToFit>
          {ring.center}
        </AppText>
      </View>
    </View>
  );
}

function MiniStat({ stat, onOpen }: { stat: StatusMiniStat; onOpen?: (href: string) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const body = (
    <>
      <AppText style={styles.statLabel} numberOfLines={1}>
        {stat.label}
      </AppText>
      <AppText style={[styles.statValue, { color: toneColor(stat.tone, colors) }]} numberOfLines={1} adjustsFontSizeToFit>
        {stat.value}
      </AppText>
    </>
  );
  if (stat.href && onOpen) {
    const href = stat.href;
    return (
      <Pressable accessibilityRole="link" accessibilityLabel={`${stat.label}: ${stat.value}`} onPress={() => onOpen(href)} style={styles.stat} testID={`status-stat-${stat.key}`}>
        {body}
      </Pressable>
    );
  }
  return (
    <View style={styles.stat} accessible accessibilityLabel={`${stat.label}: ${stat.value}`} testID={`status-stat-${stat.key}`}>
      {body}
    </View>
  );
}

function AttentionRow({ item, first, onOpen }: { item: StatusAttentionItem; first: boolean; onOpen?: (href: string) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const href = item.href;
  const hasDetail = Boolean(item.detail);
  const trailingValue = item.grade ?? item.stat?.value ?? null;
  const trailingCaption = item.grade ? 'GRADE' : item.stat?.label ?? null;
  const row = (
    <PlayerIdentityRow
      playerId={item.playerId}
      name={item.name}
      position={item.position}
      team={item.team}
      tier={item.tier}
      injuryLabel={item.injuryStatus}
      contextLine={item.meta}
      trailingValue={trailingValue}
      trailingCaption={trailingCaption}
      trailingTone={item.grade || item.stat?.tone === 'success' ? 'accent' : undefined}
      chevron={!hasDetail && Boolean(href && onOpen)}
      onPress={hasDetail ? () => setOpen(!open) : href && onOpen ? () => onOpen(href) : undefined}
      style={styles.rowFlex}
    />
  );
  return (
    <View style={[styles.attentionRow, !first && styles.attentionDivider]} testID="status-attention-row" accessibilityLabel={hasDetail ? `${statusAttentionAria(item)}. ${open ? 'Collapse' : 'Expand'}` : statusAttentionAria(item)} accessibilityState={hasDetail ? { expanded: open } : undefined}>
      <View style={styles.rowMain}>{row}</View>
      {hasDetail && open ? (
        <View style={styles.detail}>
          <AppText style={styles.detailText}>{item.detail}</AppText>
          {href && onOpen ? (
            <Pressable accessibilityRole="link" onPress={() => onOpen(href)} style={styles.openLink}>
              <AppText style={styles.link}>Open →</AppText>
            </Pressable>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

export default function StatusHeader({
  model: raw,
  attentionTitle = 'Needs your attention',
  badge,
  headerHref,
  onOpen,
  onAction,
  actionLoading = false,
  testID = 'status-header',
  children,
}: {
  model: StatusHeaderModel;
  attentionTitle?: string;
  /** A small pill beside the kicker (archetype, status). */
  badge?: ReactNode;
  /** Makes the ring + headline block tappable (Today: the matchup). */
  headerHref?: string;
  /** Opens an `href` (a route name on the app). */
  onOpen?: (href: string) => void;
  /** Handles a primary action that has an `actionKey` instead of an href (the sim switches tabs). */
  onAction?: (actionKey: string) => void;
  actionLoading?: boolean;
  testID?: string;
  /** CompactModules that follow the header. */
  children?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const model = statusHeaderModel(raw);
  const primary = model.primary;
  const top = (
    <>
      {model.ring ? <StatusRingMark ring={model.ring} /> : null}
      <View style={styles.topText}>
        <View style={styles.kickerRow}>
          <AppText style={styles.kicker}>{model.kicker}</AppText>
          {badge}
        </View>
        <AppText style={styles.headline} testID="status-headline">
          {model.headline}
        </AppText>
        {model.context ? (
          <AppText style={styles.context} testID="status-context">
            {model.context}
          </AppText>
        ) : null}
      </View>
    </>
  );
  return (
    <View style={styles.block} testID={testID}>
      <AccentCard accent={colors.accent}>
        {headerHref && onOpen ? (
          <Pressable
            accessibilityRole="link"
            accessibilityLabel={[model.kicker, model.headline, model.context].filter(Boolean).join('. ')}
            onPress={() => onOpen(headerHref)}
            style={styles.top}
          >
            {top}
          </Pressable>
        ) : (
          <View style={styles.top}>{top}</View>
        )}
        {model.stats.length > 0 ? (
          <View style={styles.stats} testID="status-stats">
            {model.stats.map((stat) => (
              <MiniStat key={stat.key} stat={stat} onOpen={onOpen} />
            ))}
          </View>
        ) : null}
        {model.attention.length > 0 ? (
          <View testID="status-attention">
            <AppText style={styles.kickerMuted}>{attentionTitle}</AppText>
            {model.attention.map((item, index) => (
              <AttentionRow key={item.key} item={item} first={index === 0} onOpen={onOpen} />
            ))}
          </View>
        ) : null}
        {primary ? (
          <Button
            label={primary.label}
            variant="primary"
            loading={actionLoading}
            onPress={() => {
              if (primary.href) onOpen?.(primary.href);
              else if (primary.actionKey) onAction?.(primary.actionKey);
            }}
          />
        ) : null}
      </AccentCard>
      {children}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    block: { gap: spacing.md },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 44 },
    topText: { flex: 1, minWidth: 0, gap: 2 },
    kickerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.accent },
    kickerMuted: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary, textTransform: 'uppercase' },
    headline: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    context: { fontSize: 13.5, color: colors.textSecondary },
    ringCenter: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8 },
    ringText: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    stats: { flexDirection: 'row', gap: spacing.sm },
    stat: {
      flex: 1,
      minWidth: 0,
      minHeight: 44,
      justifyContent: 'center',
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.xs,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    statLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    statValue: { fontSize: 16, fontWeight: '800' },
    attentionRow: { minHeight: 44 },
    attentionDivider: { borderTopWidth: 1, borderTopColor: colors.border },
    rowMain: { flexDirection: 'row' },
    rowFlex: { flex: 1, minWidth: 0 },
    detail: { gap: spacing.xs, paddingBottom: spacing.sm },
    detailText: { fontSize: 13.5, color: colors.textSecondary },
    openLink: { minHeight: 44, justifyContent: 'center' },
    link: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
  });
}

import React, { useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import SimGlyph from './SimGlyph';
import { SimFold, createSimStyles } from './SimGameParts';
import ToneBadge from './ToneBadge';
import TrophyIcon from './TrophyIcon';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simAchievementColor,
  simAchievementDate,
  simAchievementGlyph,
  simAchievementGroups,
  simAchievementLine,
  simAchievementProgressPct,
  simAchievementRarityLabel,
  simAchievementsParts,
  type SimAchievement,
  type SimAchievementsPayload,
  type SimTrophyRow,
} from '../lib/simAchievements';

/** The lib names web CSS tokens; the app resolves the same semantic tokens from its theme. */
export function useAchievementColor() {
  const { colors } = useThemeMode();
  return (a: Pick<SimAchievement, 'rarity' | 'tone' | 'unlocked'>): string => {
    const token = simAchievementColor(a);
    if (token.includes('premium')) return colors.premium;
    if (token.includes('danger')) return colors.danger;
    if (token.includes('success')) return colors.success;
    if (token.includes('accent')) return colors.accent;
    return colors.textTertiary;
  };
}

/** The round badge: a rarity-coloured ring around the glyph (muted while locked). Decorative; the row carries the name. */
export function SimAchievementBadge({ a, size = 36 }: { a: Pick<SimAchievement, 'icon' | 'rarity' | 'tone' | 'unlocked'>; size?: number }) {
  const colorOf = useAchievementColor();
  const color = colorOf(a);
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      testID="achievement-badge"
      style={{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: color + (a.unlocked ? 'B3' : '59'), backgroundColor: a.unlocked ? color + '24' : 'transparent', opacity: a.unlocked ? 1 : 0.8 }}
    >
      <SimGlyph name={simAchievementGlyph(a.icon)} color={color} size={Math.round(size * 0.5)} />
    </View>
  );
}

function Row({ a }: { a: SimAchievement }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const colorOf = useAchievementColor();
  const [open, setOpen] = useState(false);
  const color = colorOf(a);
  const pct = simAchievementProgressPct(a.progress);
  return (
    <View>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${a.name}, ${simAchievementRarityLabel(a.rarity)}, ${a.unlocked ? simAchievementDate(a) || 'unlocked' : a.progress?.text ?? 'locked'}`}
        testID="achievement-row"
        style={{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, paddingVertical: 6 }}
      >
        <SimAchievementBadge a={a} />
        <View style={{ flex: 1, minWidth: 0 }}>
          <AppText numberOfLines={1} style={[common.bodyStrong, { color: a.unlocked ? colors.textPrimary : colors.textSecondary }]}>{a.name}</AppText>
          <AppText numberOfLines={1} style={common.muted}>{a.unlocked ? simAchievementDate(a) : a.progress ? a.progress.text : 'Locked'}</AppText>
        </View>
        <ToneBadge label={simAchievementRarityLabel(a.rarity)} color={a.unlocked ? color : colors.textTertiary} size="xs" />
      </Pressable>
      {!a.unlocked && a.progress ? (
        <View style={{ marginLeft: 48, height: 4, borderRadius: 2, overflow: 'hidden', backgroundColor: colors.border }} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: pct }}>
          <View style={{ width: `${pct}%`, height: 4, backgroundColor: color, opacity: 0.8 }} />
        </View>
      ) : null}
      {open ? (
        <AppText style={[common.muted, { marginLeft: 48, marginBottom: 8, color: colors.textSecondary }]} testID="achievement-detail">
          {simAchievementLine(a)}
          {a.unlocked && a.player ? ` (${a.player.name})` : ''}
        </AppText>
      ) : null}
    </View>
  );
}

/**
 * The Achievements CompactModule (Home, the offseason review and the final Season in Review). Twin of web's SimAchievementsModule:
 * renders only what the server's `achievements` payload says.
 */
export function SimAchievementsModule({ payload, seasonNo, id = 'home.achievements', openOnPhone = false }: { payload: SimAchievementsPayload | null | undefined; seasonNo?: number | null; id?: string; openOnPhone?: boolean }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (!payload || !Array.isArray(payload.items)) return null;
  const groups = simAchievementGroups(payload, seasonNo);
  return (
    <SimFold id={id} glyph="trophy" tone="warning" title="Achievements" parts={simAchievementsParts(payload)} openOnPhone={openOnPhone} testID="sim-achievements">
      {groups.length === 0 ? (
        <AppText style={common.muted}>Nothing earned yet. Win a few, stack a streak, chase a title.</AppText>
      ) : (
        <View style={{ gap: 12 }}>
          {groups.map((g) => (
            <View key={`${g.key}-${g.title}`} accessibilityLabel={g.title}>
              <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase' }]}>{g.title}</AppText>
              {g.items.map((a) => <Row key={a.id} a={a} />)}
            </View>
          ))}
        </View>
      )}
    </SimFold>
  );
}

/** A team's champion trophies, newest first (team history). Gold: a title is the premium meaning here. */
export function SimTrophyRow({ rows }: { rows: SimTrophyRow[] }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (rows.length === 0) return null;
  return (
    <View style={[common.wrapRow, { gap: 8 }]} accessibilityLabel="Championship trophies" testID="sim-trophy-row">
      {rows.map((r) => (
        <AccentCard key={r.label} accent={colors.premium} compact>
          <View style={[common.row, { gap: 8 }]}>
            <TrophyIcon size={28} color={colors.premium} />
            <View>
              <AppText style={common.bodyStrong}>{r.label}</AppText>
              <AppText style={common.muted}>{r.record}</AppText>
            </View>
          </View>
        </AccentCard>
      ))}
    </View>
  );
}

/** Compact badge chips (your team page, a player's History tab). */
export function SimBadgeChips({ items, label = 'Achievements' }: { items: SimAchievement[]; label?: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (items.length === 0) return null;
  return (
    <View style={[common.wrapRow, { gap: 8 }]} accessibilityLabel={label} testID="sim-badge-chips">
      {items.map((a) => (
        <View key={a.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingRight: 10, borderRadius: 999, backgroundColor: colors.border + '55' }}>
          <SimAchievementBadge a={a} size={28} />
          <AppText style={[common.bodyStrong, { fontSize: 12 }]}>
            {a.name} <AppText style={common.muted}>{a.season_label}</AppText>
          </AppText>
        </View>
      ))}
    </View>
  );
}

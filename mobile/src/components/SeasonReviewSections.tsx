import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Line, Path } from 'react-native-svg';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import { SimPlayerChip as BaseChip, createSimStyles, simToneColor } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimPlayerRef } from '../lib/simGame';
import type {
  ReviewCard,
  ReviewGameRow,
  ReviewGlyph,
  ReviewLeaderGroup,
  ReviewPathStep,
  ReviewPlayer,
  ReviewSection,
  ReviewStat,
  ReviewTone,
} from '../lib/simReview';
import { radii, spacing } from '../theme';

/**
 * The data-driven Season in Review body (twin of web's SeasonReviewSections):
 * renders a typed `ReviewSection[]` so the sim's final grade page and the
 * future real-league yearly summary share one set of cards. Theme tokens only.
 */

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export const REVIEW_ICON: Record<ReviewGlyph, IconName> = {
  lineup: 'clipboard-outline',
  waiver: 'add-circle-outline',
  trade: 'swap-horizontal',
  draft: 'ticket-outline',
  injury: 'medkit-outline',
  boom: 'trending-up',
  bust: 'trending-down',
  game: 'stopwatch-outline',
  trophy: 'trophy-outline',
  rank: 'analytics-outline',
  leader: 'bar-chart-outline',
  stats: 'stats-chart-outline',
  path: 'flag-outline',
};

const ROLE_BADGE: Record<string, { label: string; tone: ReviewTone }> = {
  get: { label: 'Got', tone: 'success' },
  give: { label: 'Sent', tone: 'danger' },
  add: { label: 'Added', tone: 'success' },
  drop: { label: 'Dropped', tone: 'danger' },
  pick: { label: 'Pick', tone: 'accent' },
  hurt: { label: 'Hurt', tone: 'danger' },
  bench: { label: 'Benched', tone: 'warning' },
  started: { label: 'Started', tone: 'muted' },
  boom: { label: 'Boom', tone: 'success' },
  bust: { label: 'Bust', tone: 'danger' },
};

function SimPlayerChip({ player, size }: { player: ReviewPlayer; size?: number }) {
  return <BaseChip player={player as unknown as SimPlayerRef} size={size} />;
}

export function ReviewGlyphChip({ glyph, tone, size = 28 }: { glyph: ReviewGlyph; tone: ReviewTone; size?: number }) {
  const { colors } = useThemeMode();
  const color = simToneColor(tone, colors);
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: `${color}26` }}
    >
      <Ionicons name={REVIEW_ICON[glyph]} size={Math.round(size * 0.58)} color={color} />
    </View>
  );
}

export function ReviewDeltaText({ text, tone, small = false }: { text: string; tone: ReviewTone; small?: boolean }) {
  const { colors } = useThemeMode();
  return <AppText style={{ fontSize: small ? 14 : 18, fontWeight: '800', color: simToneColor(tone, colors) }}>{text}</AppText>;
}

export function ReviewCardView({ card }: { card: ReviewCard }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const color = simToneColor(card.tone, colors);
  return (
    <AccentCard accent={color} compact>
      <View style={styles.cardHead}>
        <ReviewGlyphChip glyph={card.glyph} tone={card.tone} />
        <View style={common.grow}>
          <AppText style={[styles.kind, { color }]}>{card.label}</AppText>
          <AppText style={common.bodyStrong}>{card.headline}</AppText>
        </View>
        <View style={styles.end}>
          {card.delta ? <ReviewDeltaText text={card.delta.text} tone={card.delta.tone} /> : null}
          {card.chip ? <ToneBadge label={card.chip.label} color={simToneColor(card.chip.tone, colors)} size="xs" /> : null}
        </View>
      </View>
      {card.players.slice(0, 4).map((p, i) => {
        const role = p.role ? ROLE_BADGE[p.role] : undefined;
        return (
          <View key={`${p.id}-${i}`} style={common.rowBetween}>
            <View style={common.grow}>
              <SimPlayerChip player={p} />
            </View>
            {role ? <ToneBadge label={role.label} color={simToneColor(role.tone, colors)} size="xs" /> : null}
          </View>
        );
      })}
      {card.detail ? <AppText style={common.small}>{card.detail}</AppText> : null}
    </AccentCard>
  );
}

function StatTile({ stat }: { stat: ReviewStat }) {
  const { colors } = useThemeMode();
  const color = stat.tone === 'muted' ? colors.textPrimary : simToneColor(stat.tone, colors);
  return (
    <View style={[styles.tile, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <AppText style={[styles.kind, { color: colors.textTertiary }]}>{stat.label}</AppText>
      <AppText style={[styles.tileValue, { color }]}>{stat.value}</AppText>
      {stat.sub ? <AppText style={{ fontSize: 12, color: colors.textTertiary }}>{stat.sub}</AppText> : null}
      {stat.player ? <SimPlayerChip player={stat.player} size={28} /> : null}
    </View>
  );
}

const STEP_TONE: Record<ReviewPathStep['result'], ReviewTone> = { win: 'success', loss: 'danger', bye: 'warning' };

function PathView({ steps, caption }: { steps: ReviewPathStep[]; caption?: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <View style={common.tight}>
      {caption ? <AppText style={common.muted}>{caption}</AppText> : null}
      {steps.map((s, i) => {
        const tone = STEP_TONE[s.result];
        const color = simToneColor(tone, colors);
        return (
          <View key={i} style={styles.step}>
            <View style={styles.rail}>
              <ReviewGlyphChip glyph={s.result === 'win' ? 'trophy' : s.result === 'bye' ? 'path' : 'bust'} tone={tone} />
              {i < steps.length - 1 ? <View style={[styles.railLine, { backgroundColor: colors.borderStrong }]} /> : null}
            </View>
            <View style={[common.rowBetween, styles.stepBody]}>
              <View style={common.grow}>
                <AppText style={common.bodyStrong}>{s.label}</AppText>
                {s.sub ? <AppText style={common.small}>{s.sub}</AppText> : null}
              </View>
              <View style={styles.end}>
                {s.score ? <AppText style={[common.bodyStrong, { color }]}>{s.score}</AppText> : null}
                <ToneBadge label={s.result === 'win' ? 'Won' : s.result === 'loss' ? 'Lost' : 'Bye'} color={color} size="xs" />
              </View>
            </View>
          </View>
        );
      })}
    </View>
  );
}

function JourneyView({ points, teams }: { points: { label: string; rank: number; sub?: string }[]; teams: number }) {
  const { colors } = useThemeMode();
  const w = 300;
  const h = 96;
  const pad = 14;
  const x = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(1, points.length - 1);
  const y = (rank: number) => pad + ((rank - 1) * (h - 2 * pad)) / Math.max(1, teams - 1);
  const best = Math.min(...points.map((p) => p.rank));
  const worst = Math.max(...points.map((p) => p.rank));
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(p.rank).toFixed(1)}`).join(' ');
  const last = points[points.length - 1];
  return (
    <View style={[styles.tile, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View accessible accessibilityRole="image" accessibilityLabel={`Standings rank by week, best ${best}, worst ${worst}, finished ${last.rank}`} style={{ aspectRatio: w / h }}>
        <Svg width="100%" height="100%" viewBox={`0 0 ${w} ${h}`}>
          <Line x1={pad} x2={w - pad} y1={y(1)} y2={y(1)} stroke={colors.border} strokeDasharray="3 4" />
          <Path d={d} fill="none" stroke={colors.accent} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
          {points.map((p, i) => (
            <Circle key={i} cx={x(i)} cy={y(p.rank)} r={p.rank === best ? 4.5 : 3} fill={p.rank === best ? colors.success : p.rank === worst ? colors.danger : colors.accent} />
          ))}
        </Svg>
      </View>
      <View style={styles.journeyLabels}>
        <AppText style={{ fontSize: 12, color: colors.textTertiary }}>{points[0].label}: #{points[0].rank}</AppText>
        <AppText style={{ fontSize: 12, color: colors.textTertiary }}>
          <AppText style={{ fontSize: 12, color: colors.success }}>Peak #{best}</AppText> · <AppText style={{ fontSize: 12, color: colors.danger }}>Low #{worst}</AppText>
        </AppText>
        <AppText style={{ fontSize: 12, color: colors.textTertiary }}>{last.label}: #{last.rank}</AppText>
      </View>
    </View>
  );
}

function LeaderGroup({ group }: { group: ReviewLeaderGroup }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <View style={[styles.tile, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={common.row}>
        {group.pos ? <PositionBadge position={group.pos} /> : null}
        <AppText style={[styles.kind, { color: colors.textTertiary }]}>{group.pos ? 'Leaders' : group.title}</AppText>
      </View>
      {group.rows.map((r, i) => (
        <View key={`${r.player.id}-${i}`} style={[common.row, i ? common.divider : null, styles.leaderRow]}>
          <AppText style={[styles.rankNum, { color: i === 0 ? colors.premium : colors.textTertiary }]}>{i + 1}</AppText>
          <View style={common.grow}>
            <SimPlayerChip player={r.player} size={28} />
          </View>
          <View style={styles.end}>
            <AppText style={[common.bodyStrong, r.highlight ? { color: colors.accent } : null]}>{r.value}</AppText>
            {r.sub ? <AppText style={{ fontSize: 12, color: colors.textTertiary }} numberOfLines={1}>{r.sub}</AppText> : null}
          </View>
        </View>
      ))}
    </View>
  );
}

function GameRow({ row }: { row: ReviewGameRow }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <AccentCard accent={row.tone === 'muted' ? colors.borderStrong : simToneColor(row.tone, colors)} compact>
      <View style={common.rowBetween}>
        <AppText style={[common.bodyStrong, common.grow]}>{row.label}</AppText>
        <AppText style={common.bodyStrong}>{row.score}</AppText>
      </View>
      <View style={common.rowBetween}>
        <AppText style={common.small}>{row.sub}</AppText>
        {row.chip ? <ToneBadge label={row.chip.label} color={simToneColor(row.chip.tone, colors)} size="xs" /> : null}
      </View>
    </AccentCard>
  );
}

function SectionBody({ section }: { section: ReviewSection }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  switch (section.kind) {
    case 'stats':
      return <View style={styles.grid}>{section.items.map((s, i) => <View key={i} style={styles.half}><StatTile stat={s} /></View>)}</View>;
    case 'cards':
      return <View style={common.stack}>{section.cards.map((c) => <ReviewCardView key={c.id} card={c} />)}</View>;
    case 'path':
      return <PathView steps={section.steps} caption={section.caption} />;
    case 'journey':
      return <JourneyView points={section.points} teams={section.teams} />;
    case 'leaders':
      return <View style={common.stack}>{section.groups.map((g, i) => <LeaderGroup key={`${g.title}-${i}`} group={g} />)}</View>;
    case 'games':
      return <View style={common.stack}>{section.rows.map((r, i) => <GameRow key={i} row={r} />)}</View>;
  }
}

export function SeasonReviewSections({ sections }: { sections: readonly ReviewSection[] }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <>
      {sections.map((section) => (
        <View key={section.id} style={common.stack} testID={`review-section-${section.id}`}>
          <SectionHeading title={section.title} icon={REVIEW_ICON[section.glyph]} caption={section.note} />
          <SectionBody section={section} />
        </View>
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  kind: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase' },
  end: { alignItems: 'flex-end', gap: 4 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  half: { width: '48%', flexGrow: 1 },
  tile: { borderWidth: 1, borderRadius: radii.lg, padding: spacing.md, gap: 2 },
  tileValue: { fontSize: 22, fontWeight: '800' },
  step: { flexDirection: 'row', gap: spacing.sm },
  rail: { width: 28, alignItems: 'center' },
  railLine: { width: 2, flex: 1, minHeight: 12 },
  stepBody: { flex: 1, paddingBottom: spacing.md, alignItems: 'flex-start' },
  journeyLabels: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
  leaderRow: { paddingVertical: spacing.xs },
  rankNum: { width: 16, fontSize: 12, fontWeight: '800' },
});

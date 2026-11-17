import { swipeLockProps } from './swipeLock';
import React, { useMemo, useState, type ReactNode } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import PlayerAvatar from './PlayerAvatar';
import PlayerAccordionRow, { usePlayerAccordion } from './PlayerAccordionRow';
import PlayerName from './PlayerName';
import ToneBadge from './ToneBadge';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  buildNewsDigest,
  newsHeadlineChip,
  newsLeaguePreview,
  type DigestItem,
  type NewsDigestRow,
  type NewsFilterKey,
  type NewsStripPlayer,
  type NewsVerdictTone,
} from '../lib/newsDigest';
import { stubPlayer } from '../lib/playerQuickView';
import { spacing, type ThemeColors } from '../theme';

/**
 * The roster-first News digest, native twin of web-next/src/components/NewsDigest.tsx (logic: lib/newsDigest.ts, a
 * byte-identical twin). Your players' items first as shared PlayerAccordionRows (avatar, "J. Surname", headline, verdict
 * chip; tap to expand "what it means"), a PFP strip that filters to one player, and the league-wide feed as a collapsed
 * CompactModule whose body is `feed`.
 */

const SLOT_LABEL = { starter: 'Starter', bench: 'Bench', taxi: 'Taxi', ir: 'IR' } as const;

function ago(ts: number | null): string {
  if (!ts) return '';
  const seconds = Date.now() / 1000 - ts;
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function toneColor(tone: NewsVerdictTone, colors: ThemeColors): string {
  return tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : colors.accent;
}

function RosterStrip({ players, active, onPick }: { players: NewsStripPlayer[]; active: string | null; onPick: (key: string | null) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <CompactModule id="news.roster" title={`Your roster · ${players.length} with news`} label="Your roster" parts={[{ key: 'count', text: `${players.length} with news`, tone: 'muted' }]} defaultOpen={active != null} testID="news-strip">
      <ScrollView horizontal {...swipeLockProps} showsHorizontalScrollIndicator={false} contentContainerStyle={styles.stripRow}>
        {players.map((p) => {
          const on = p.key === active;
          return (
            <Pressable
              key={p.key}
              accessibilityRole="button"
              accessibilityState={{ selected: on }}
              accessibilityLabel={`${p.name}, ${p.count} ${p.count === 1 ? 'item' : 'items'}`}
              onPress={() => onPick(on ? null : p.key)}
              style={styles.chip}
            >
              <View style={[styles.avatarWrap, on && { borderColor: colors.accent }]}>
                <PlayerAvatar playerId={p.id} tier={p.tier} size={44} fallbackLabel={p.name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2)} />
                {p.unread ? <View style={[styles.dot, { backgroundColor: colors.accent, borderColor: colors.background }]} /> : null}
              </View>
              <PlayerName name={p.name} style={[styles.chipName, on && { color: colors.accent }]} />
            </Pressable>
          );
        })}
      </ScrollView>
    </CompactModule>
  );
}

function DigestRow({ row, acc }: { row: NewsDigestRow; acc: ReturnType<typeof usePlayerAccordion> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  const { item, verdict } = row;
  const slot = item.roster_relationship;
  const time = ago(item.published_ts);
  const meta: { key: string; text: string; tone?: 'success' }[] = [];
  if (slot) meta.push({ key: 'slot', text: SLOT_LABEL[slot], tone: slot === 'starter' ? 'success' : undefined });
  if (item.source) meta.push({ key: 'src', text: item.source });
  if (time) meta.push({ key: 'time', text: time });
  const name = item.matched_player ?? 'Player';
  return (
    <PlayerAccordionRow
      mode="desk"
      player={{ id: item.matched_player_id ?? null, name, position: item.matched_player_position ?? null, team: item.matched_player_team ?? null, tier: item.matched_player_tier ?? null }}
      open={acc.isOpen(row.key)}
      onToggle={() => acc.toggle(row.key)}
      metaParts={meta}
      headline={item.title}
      trailingAction={<ToneBadge label={verdict.label} color={toneColor(verdict.tone, colors)} size="xs" />}
      onOpenProfile={
        item.matched_player_id
          ? () => openPlayer(stubPlayer({ player_id: item.matched_player_id as string, name, position: item.matched_player_position, team: item.matched_player_team }), { sourceLabel: 'News' })
          : undefined
      }
      testID="news-row"
    >
      <View style={styles.tight}>
        <AppText style={styles.kicker}>What it means</AppText>
        <AppText style={styles.body}>{row.impact}</AppText>
        {item.summary ? <AppText style={styles.muted}>{item.summary}</AppText> : null}
        {item.link ? (
          <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(item.link as string)} style={styles.link}>
            <AppText style={[styles.body, { color: colors.accent, fontWeight: '700' }]}>Read the article</AppText>
          </Pressable>
        ) : null}
      </View>
    </PlayerAccordionRow>
  );
}

export default function NewsDigest({
  alerts,
  general,
  reasonNote,
  feed,
  filter,
}: {
  alerts: readonly DigestItem[];
  general: readonly DigestItem[];
  /** Why there is no roster news (no league linked, empty roster), shown instead of an empty list. */
  reasonNote?: string | null;
  /** The league-wide feed body for the given (filtered) items. */
  feed: (items: DigestItem[]) => ReactNode;
  /** The News type filter, picked in the page's one control row. */
  filter: NewsFilterKey;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [playerKey, setPlayerKey] = useState<string | null>(null);
  const acc = usePlayerAccordion();
  const digest = useMemo(() => buildNewsDigest({ alerts, general, filter, playerKey }), [alerts, general, filter, playerKey]);
  const chip = newsHeadlineChip(digest);
  const hasRoster = alerts.length > 0;
  const preview = newsLeaguePreview(digest.league);
  const picked = digest.strip.find((p) => p.key === playerKey);
  return (
    <View style={styles.stack} testID="news-digest">
      {digest.strip.length > 0 ? <RosterStrip players={digest.strip} active={playerKey} onPick={setPlayerKey} /> : null}
      {digest.rows.length > 0 ? (
        <View style={styles.between}>
          <AppText style={styles.kicker}>{picked ? `${picked.name} · ${digest.rows.length} ${digest.rows.length === 1 ? 'item' : 'items'}` : `Your players · ${digest.rows.length}`}</AppText>
          {chip ? <ToneBadge label={chip} color={colors.accent} size="xs" /> : null}
        </View>
      ) : null}
      {digest.rows.length > 0 ? (
        <View>{digest.rows.map((row) => <DigestRow key={row.key} row={row} acc={acc} />)}</View>
      ) : (
        <AppText style={styles.muted} testID="news-roster-empty">
          {reasonNote ?? (hasRoster ? 'No news on your players for this filter.' : 'No news on your players right now.')}
        </AppText>
      )}
      {digest.league.length > 0 ? (
        <CompactModule
          id="news.league"
          title={`Around the NFL · ${digest.league.length}`}
          label="Around the NFL"
          parts={[preview ? { key: 'preview', text: preview, tone: 'muted' } : null]}
          defaultOpen={digest.rows.length === 0}
          summaryWhenCollapsed
          testID="news-league-module"
        >
          {feed(digest.league)}
        </CompactModule>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md },
    tight: { gap: spacing.xs },
    between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.textTertiary },
    body: { fontSize: 14.5, lineHeight: 20, color: colors.textSecondary },
    muted: { fontSize: 13.5, lineHeight: 19, color: colors.textTertiary },
    link: { minHeight: 44, justifyContent: 'center' },
    stripRow: { gap: spacing.sm, paddingBottom: spacing.xs },
    chip: { width: 68, alignItems: 'center', gap: 4, minHeight: 44 },
    avatarWrap: { borderRadius: 30, borderWidth: 2, borderColor: 'transparent', padding: 1 },
    dot: { position: 'absolute', top: -1, right: -1, width: 11, height: 11, borderRadius: 6, borderWidth: 2 },
    chipName: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textAlign: 'center' },
  });
}

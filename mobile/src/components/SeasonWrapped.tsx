import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Share, StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Line, Polyline, Text as SvgText } from 'react-native-svg';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';

import AppText from './AppText';
import Button from './Button';
import PlayerAvatar from './PlayerAvatar';
import { CARD_WIDTH } from './ShareCardChrome';
import WrappedShareCard, { WRAPPED_SHARE_HEIGHT } from './WrappedShareCard';
import { useThemeMode } from '../context/ThemeModeContext';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { radii, spacing, type ThemeColors } from '../theme';
import {
  normalizeWrappedDeck,
  wrappedGradeTone,
  wrappedPlayerLine,
  wrappedShareModel,
  wrappedShareText,
  wrappedShortName,
  wrappedView,
  type WrappedBlock,
  type WrappedCard,
  type WrappedDeck,
  type WrappedPlayer,
  type WrappedShareModel,
  type WrappedTone,
} from '../lib/wrapped';


function toneColor(colors: ThemeColors, tone: WrappedTone): string {
  return tone === 'good' ? colors.success : tone === 'warm' ? colors.warning : colors.textSecondary;
}

function Face({ player, size = 44 }: { player: WrappedPlayer; size?: number }) {
  return <PlayerAvatar playerId={player.headshot_id} name={player.name} position={player.pos} team={player.team} size={size} />;
}

function Chip({ label, tone, colors }: { label: string; tone: WrappedTone; colors: ThemeColors }) {
  const color = toneColor(colors, tone);
  return (
    <View style={{ borderWidth: 1, borderColor: color, borderRadius: radii.pill, paddingHorizontal: 10, paddingVertical: 3, backgroundColor: colors.surface, alignSelf: 'flex-start' }}>
      <AppText style={{ color, fontSize: 12, fontWeight: '700' }}>{label}</AppText>
    </View>
  );
}

function CardBody({ card, colors, styles, onUnlock }: { card: WrappedCard; colors: ThemeColors; styles: ReturnType<typeof createStyles>; onUnlock: () => void }) {
  const view = wrappedView(card);
  const Rows = ({ rows }: { rows: { label: string; value: string }[] }) =>
    rows.length ? (
      <View style={styles.rows}>
        {rows.map((r) => (
          <View key={r.label} style={styles.row}>
            <AppText style={styles.rowLabel}>{r.label.toUpperCase()}</AppText>
            <AppText style={styles.rowValue}>{r.value}</AppText>
          </View>
        ))}
      </View>
    ) : null;
  const Head = ({ p, size = 44 }: { p: WrappedPlayer; size?: number }) => (
    <View style={styles.headRow}>
      <Face player={p} size={size} />
      <View style={{ flex: 1 }}>
        <AppText style={styles.name}>{wrappedShortName(p.name)}</AppText>
        <AppText style={styles.muted}>{[p.pos, p.team].filter(Boolean).join(' · ')}</AppText>
      </View>
    </View>
  );
  const Block = ({ b }: { b: WrappedBlock }) => (
    <View style={[styles.panel, { flex: 1 }]}>
      <View style={styles.rowBetween}>
        <AppText style={styles.rowLabel}>{b.label.toUpperCase()}</AppText>
        {b.badge ? <Chip label={b.badge} tone={b.tone} colors={colors} /> : null}
      </View>
      <AppText style={[styles.heroSmall, { fontSize: card.id === 'close' ? 34 : 52 }]}>
        {b.hero}
        {b.unit ? <AppText style={styles.unit}> {b.unit}</AppText> : null}
      </AppText>
      {b.sub ? <AppText style={styles.muted}>{b.sub}</AppText> : null}
    </View>
  );
  switch (view.kind) {
    case 'locked':
      return (
        <View style={[styles.panel, styles.locked]} testID="wrapped-locked">
          <View style={styles.lockDisc}><Ionicons name="lock-closed" size={16} color={colors.premium} /></View>
          <AppText style={styles.proTag}>PRO</AppText>
          <AppText style={[styles.name, { textAlign: 'center' }]}>{view.teaser}</AppText>
          <View style={styles.bar} />
          <View style={[styles.bar, { width: '66%' }]} />
          <Button label="Unlock with Pro" variant="premium" onPress={onUnlock} style={{ alignSelf: 'stretch' }} />
        </View>
      );
    case 'hero':
      return (
        <View style={styles.panel} testID={`wrapped-${card.id}`}>
          {view.player ? <Head p={view.player} /> : null}
          <View style={styles.center}>
            <AppText style={[styles.hero, { fontSize: view.hero.length > 6 ? 44 : 60 }]}>
              {view.hero}
              {view.unit ? <AppText style={styles.unit}> {view.unit}</AppText> : null}
            </AppText>
            {view.chip ? <Chip label={view.chip} tone={view.chipTone} colors={colors} /> : null}
          </View>
          <Rows rows={view.rows} />
          {view.second ? (
            <View style={[styles.headRow, styles.rows]}>
              <Face player={view.second} size={32} />
              <View style={{ flex: 1 }}>
                <AppText style={styles.nameSmall}>{wrappedShortName(view.second.name)}</AppText>
                <AppText style={styles.muted}>{view.secondLabel} · {view.second.pos} · {view.second.team}</AppText>
              </View>
            </View>
          ) : null}
          {view.foot ? <AppText style={[styles.muted, { textAlign: 'center' }]}>{view.foot}</AppText> : null}
        </View>
      );
    case 'blocks':
      return (
        <View style={{ gap: spacing.md }} testID={`wrapped-${card.id}`}>
          <View style={{ flexDirection: card.id === 'close' && view.blocks.length > 1 ? 'row' : 'column', gap: spacing.md }}>
            {view.blocks.map((b) => <Block key={b.label} b={b} />)}
          </View>
          {view.rows.length || view.miss ? (
            <View style={styles.panel}>
              <Rows rows={view.rows} />
              {view.miss ? (
                <View style={styles.headRow}>
                  <Face player={view.miss} size={36} />
                  <View style={{ flex: 1 }}>
                    <AppText style={styles.rowLabel}>BIGGEST MISS</AppText>
                    <AppText style={styles.nameSmall}>{wrappedPlayerLine(view.miss)}</AppText>
                    {view.missLine ? <AppText style={styles.muted}>{view.missLine}</AppText> : null}
                  </View>
                </View>
              ) : null}
            </View>
          ) : null}
        </View>
      );
    case 'dots':
      return (
        <View style={{ gap: spacing.md }} testID="wrapped-consistency">
          {view.items.map((item, i) => (
            <View key={item.player.id} style={styles.panel}>
              <AppText style={styles.rowLabel}>{i === 0 ? 'MR. CONSISTENT' : 'ROLLERCOASTER'}</AppText>
              <View style={styles.rowBetween}>
                <Head p={item.player} size={36} />
                <Chip label={item.tally} tone="neutral" colors={colors} />
              </View>
              <View style={styles.dots}>
                {item.beat.map((b, k) => (
                  <View key={k} style={[styles.dot, { backgroundColor: b ? colors.accent : 'transparent' }]} />
                ))}
              </View>
              <AppText style={styles.muted}>{item.caption}</AppText>
            </View>
          ))}
        </View>
      );
    case 'trades':
      return (
        <View style={{ gap: spacing.md }} testID="wrapped-trades">
          {view.sides.map((s, i) => (
            <View key={i} style={styles.panel}>
              <View style={styles.rowBetween}>
                <AppText style={styles.rowLabel}>{`${i === 0 ? 'BEST TRADE' : 'WORST TRADE'} · WK ${s.week}`}</AppText>
                <Chip label={s.grade} tone={wrappedGradeTone(s.grade)} colors={colors} />
              </View>
              {[...s.got.map((p) => ({ p, tag: 'Got' })), ...s.sent.map((p) => ({ p, tag: 'Gave' }))].map(({ p, tag }) => (
                <View key={`${tag}${p.id}`} style={styles.headRow}>
                  <Face player={p} size={28} />
                  <AppText style={styles.nameSmall}>{wrappedShortName(p.name)}</AppText>
                  <AppText style={styles.muted}>{tag} · {p.pos} · {p.team}</AppText>
                </View>
              ))}
              <AppText style={[styles.netPill, { color: i === 0 ? colors.success : colors.textSecondary }]}>{s.net}</AppText>
            </View>
          ))}
        </View>
      );
    case 'luck':
      return (
        <View style={styles.panel} testID="wrapped-luck">
          {[{ label: view.actualLabel, value: view.actual, color: colors.textTertiary }, { label: view.expectedLabel, value: view.expected, color: colors.accent }].map((bar) => (
            <View key={bar.label} style={{ gap: 6 }}>
              <View style={styles.rowBetween}>
                <AppText style={styles.muted}>{bar.label}</AppText>
                <AppText style={styles.rowValue}>{Number.isInteger(bar.value) ? String(bar.value) : bar.value.toFixed(1)}</AppText>
              </View>
              <View style={styles.track}><View style={{ height: 8, borderRadius: 4, width: `${Math.min(100, (bar.value / view.max) * 100)}%`, backgroundColor: bar.color }} /></View>
            </View>
          ))}
          <View style={styles.center}><Chip label={view.chip} tone="neutral" colors={colors} /></View>
        </View>
      );
    case 'journey': {
      const w = 300;
      const h = 130;
      const step = view.ranks.length > 1 ? w / (view.ranks.length - 1) : w;
      const y = (r: number) => 8 + ((r - 1) / Math.max(1, view.teams - 1)) * (h - 16);
      const pts = view.ranks.map((r, i) => `${(i * step).toFixed(1)},${y(r).toFixed(1)}`).join(' ');
      const best = view.ranks.indexOf(Math.min(...view.ranks));
      return (
        <View style={styles.panel} testID="wrapped-journey">
          <Svg viewBox={`-6 0 ${w + 12} ${h}`} width="100%" height={150} accessibilityLabel="League rank after each week">
            {[1, Math.ceil(view.teams / 2), view.teams].map((r) => (
              <React.Fragment key={r}>
                <Line x1={-6} x2={w + 6} y1={y(r)} y2={y(r)} stroke={colors.border} strokeDasharray="3 4" />
                <SvgText x={-4} y={y(r) - 3} fontSize={9} fill={colors.textTertiary}>{r === 1 ? '1st' : `${r}th`}</SvgText>
              </React.Fragment>
            ))}
            <Polyline points={pts} fill="none" stroke={colors.accent} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
            {best >= 0 ? <Circle cx={best * step} cy={y(view.ranks[best])} r={4.5} fill={colors.success} /> : null}
            <Circle cx={(view.ranks.length - 1) * step} cy={y(view.ranks[view.ranks.length - 1])} r={4.5} fill={colors.accent} />
          </Svg>
          <AppText style={[styles.muted, { textAlign: 'center' }]}>{view.note}</AppText>
        </View>
      );
    }
    case 'grade':
      return (
        <View style={[styles.panel, styles.center]} testID="wrapped-grade">
          <View style={[styles.gradeDisc, { borderColor: toneColor(colors, wrappedGradeTone(view.overall)) }]}>
            <AppText style={[styles.gradeLetter, { color: toneColor(colors, wrappedGradeTone(view.overall)) }]}>{view.overall}</AppText>
          </View>
          <AppText style={styles.muted}>Overall</AppText>
          <View style={[styles.rows, { alignSelf: 'stretch' }]}>
            {view.subs.map((s) => (
              <View key={s.label} style={styles.row}>
                <AppText style={styles.rowLabel}>{s.label.toUpperCase()}</AppText>
                <Chip label={s.letter} tone={wrappedGradeTone(s.letter)} colors={colors} />
              </View>
            ))}
          </View>
        </View>
      );
    case 'persona':
      return (
        <View style={[styles.panel, styles.center]} testID="wrapped-persona">
          <View style={styles.lockDisc}><Ionicons name={view.glyph === 'check' ? 'checkmark' : view.glyph === 'target' ? 'locate' : view.glyph === 'clock' ? 'time' : 'swap-horizontal'} size={26} color={colors.accent} /></View>
          <AppText style={styles.personaName}>{view.name}</AppText>
          {view.lines.map((l) => <AppText key={l} style={styles.muted}>{l}</AppText>)}
          {view.runnerUp ? <Chip label={view.runnerUp} tone="neutral" colors={colors} /> : null}
        </View>
      );
  }
}

/** The full-screen story: tap the sides to move, X to close. */
export function SeasonWrapped({ deck, visible, onClose }: { deck: WrappedDeck; visible: boolean; onClose: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [index, setIndex] = useState(0);
  const [sharing, setSharing] = useState(false);
  const shareRef = useRef<View>(null);
  const last = deck.cards.length - 1;
  const card = deck.cards[Math.min(index, last)];
  const locked = card.locked || !card.data;
  const model = useMemo(() => wrappedShareModel(card, deck), [card, deck]);
  const go = (d: number) => setIndex((i) => Math.max(0, Math.min(last, i + d)));
  const onUnlock = () => {
    onClose();
    navigation.navigate('Paywall');
  };
  const onShare = async () => {
    setSharing(true);
    try {
      const uri = await captureRef(shareRef, { format: 'png', quality: 1, result: 'tmpfile', width: CARD_WIDTH * 3, height: WRAPPED_SHARE_HEIGHT * 3 });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share this card' });
        return;
      }
      throw new Error('sharing unavailable');
    } catch {
      Share.share({ message: wrappedShareText(model) }).catch(() => {});
    } finally {
      setSharing(false);
    }
  };
  return (
    <Modal visible={visible} animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.screen} testID="season-wrapped">
        <View style={styles.top}>
          <View style={styles.segments}>
            {deck.cards.map((c, i) => (
              <View key={c.id} style={[styles.segment, { backgroundColor: i <= index ? colors.accent : colors.backgroundElevated }]} />
            ))}
          </View>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" style={styles.close}>
            <Ionicons name="close" size={18} color={colors.textPrimary} />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={styles.body}>
          <View style={{ gap: 4 }}>
            <AppText style={styles.eyebrow}>{(card.id === 'intro' ? deck.season_label : card.eyebrow).toUpperCase()}</AppText>
            <AppText style={styles.title}>{card.title}</AppText>
            {card.sub ? <AppText style={styles.sub}>{card.sub}</AppText> : null}
          </View>
          <View style={{ marginVertical: spacing.lg }}>
            <CardBody card={card} colors={colors} styles={styles} onUnlock={onUnlock} />
          </View>
        </ScrollView>
        <Pressable style={[styles.tap, { left: 0 }]} onPress={() => go(-1)} accessibilityLabel="Previous card" />
        <Pressable style={[styles.tap, { right: 0 }]} onPress={() => go(1)} accessibilityLabel="Next card" />
        <View style={styles.footer}>
          {locked ? null : <Button label="Share this card" variant="accentOutline" onPress={onShare} loading={sharing} />}
        </View>
        {locked ? null : <WrappedShareCard model={model} shareRef={shareRef} />}
      </View>
    </Modal>
  );
}

/** A button that loads a deck and opens the story. `load` resolves the /wrapped body's deck (or null: nothing to wrap yet). */
export function SeasonWrappedLauncher({ label, load, variant = 'accentOutline' }: { label: string; load: () => Promise<unknown>; variant?: 'primary' | 'secondary' | 'accentOutline' }) {
  const { colors } = useThemeMode();
  const [deck, setDeck] = useState<WrappedDeck | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const open = async () => {
    setBusy(true);
    setNote(null);
    try {
      const parsed = normalizeWrappedDeck(await load());
      if (parsed) setDeck(parsed);
      else setNote('Nothing to wrap yet. Play a few more weeks.');
    } catch {
      setNote('Could not load your wrapped. Try again.');
    } finally {
      setBusy(false);
    }
  };
  const close = useCallback(() => setDeck(null), []);
  return (
    <View style={{ gap: 4 }}>
      <Button label={label} variant={variant} onPress={open} loading={busy} />
      {note ? <AppText style={{ color: colors.textTertiary, fontSize: 12 }}>{note}</AppText> : null}
      {deck ? <SeasonWrapped deck={deck} visible onClose={close} /> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: colors.background, paddingTop: 54 },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg },
    segments: { flex: 1, flexDirection: 'row', gap: 4 },
    segment: { flex: 1, height: 4, borderRadius: 2 },
    close: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
    body: { flexGrow: 1, padding: spacing.lg, justifyContent: 'center' },
    eyebrow: { fontSize: 12, fontWeight: '800', letterSpacing: 1.2, color: colors.textTertiary },
    title: { fontSize: 30, fontWeight: '800', color: colors.textPrimary, lineHeight: 34 },
    sub: { fontSize: 14, color: colors.textSecondary },
    tap: { position: 'absolute', top: 110, bottom: 90, width: '25%' },
    footer: { padding: spacing.lg, paddingBottom: 34 },
    panel: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.lg, padding: spacing.lg, gap: spacing.md },
    locked: { alignItems: 'center', borderColor: colors.premium },
    lockDisc: { width: 56, height: 56, borderRadius: 28, borderWidth: 1, borderColor: colors.accent, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentMuted },
    proTag: { fontSize: 12, fontWeight: '800', letterSpacing: 1.2, color: colors.premium },
    bar: { height: 8, borderRadius: 4, backgroundColor: colors.backgroundElevated, alignSelf: 'stretch' },
    center: { alignItems: 'center', gap: spacing.sm },
    hero: { fontWeight: '800', color: colors.textPrimary },
    heroSmall: { fontWeight: '800', color: colors.textPrimary },
    unit: { fontSize: 15, fontWeight: '700', color: colors.textTertiary },
    name: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    nameSmall: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 12, color: colors.textTertiary },
    headRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    rows: { gap: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md },
    row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.md },
    rowLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 1, color: colors.textTertiary },
    rowValue: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, flexShrink: 1, textAlign: 'right' },
    dots: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
    dot: { width: 12, height: 12, borderRadius: 6, borderWidth: 2, borderColor: colors.accent },
    netPill: { textAlign: 'center', fontSize: 12, fontWeight: '700', backgroundColor: colors.backgroundElevated, borderRadius: radii.pill, paddingVertical: 4, overflow: 'hidden' },
    track: { height: 8, borderRadius: 4, backgroundColor: colors.backgroundElevated },
    gradeDisc: { width: 68, height: 68, borderRadius: 34, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
    gradeLetter: { fontSize: 30, fontWeight: '800' },
    personaName: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, textAlign: 'center' },
  });
}

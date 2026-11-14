import React, { useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import FairnessMeterRow from './FairnessMeterRow';
import { MotionIn } from './Motion';
import { animateRowExpand } from './PlayerAccordionRow';
import { TradeAssetCard, type TradeCardAsset } from './TradeCompactCard';
import { useThemeMode } from '../context/ThemeModeContext';
import { fairnessMeter, type FairnessMeter, type PlayerMode } from '../lib/playerAnatomy';
import { tradeScaleCount, tradeScaleMissing, tradeScalePhase } from '../lib/tradeScale';
import { radii, spacing, type ThemeColors } from '../theme';

export type TradeScaleSide = 'give' | 'get';

function Column({ side, label, assets, mode, max, editing, addHint, onAdd, onRemove, styles, colors }: {
  side: TradeScaleSide;
  label: string;
  assets: TradeCardAsset[];
  mode: PlayerMode;
  max?: number | null;
  editing: boolean;
  addHint?: string;
  onAdd: (side: TradeScaleSide) => void;
  onRemove?: (side: TradeScaleSide, key: string) => void;
  styles: ReturnType<typeof createStyles>;
  colors: ThemeColors;
}) {
  const full = Boolean(max && assets.length >= max);
  return (
    <View style={styles.column} testID={`scale-${side}`}>
      <View style={styles.head}>
        <View style={[styles.dot, { backgroundColor: side === 'give' ? colors.danger : colors.success }]} />
        <AppText style={styles.kicker}>{label} {tradeScaleCount(assets.length, max)}</AppText>
      </View>
      {assets.map((a, i) => (
        <MotionIn key={a.key} index={i} count={assets.length}>
          <View style={styles.assetRow} testID="scale-asset">
            <View style={styles.assetMain}>
              <TradeAssetCard asset={a} mode={mode} />
            </View>
            {editing && onRemove ? (
              <Pressable accessibilityRole="button" accessibilityLabel={`Remove ${a.player?.name ?? a.pickLabel ?? 'asset'}`} onPress={() => { animateRowExpand(); onRemove(side, a.key); }} style={styles.remove} hitSlop={6}>
                <AppText style={styles.removeText}>×</AppText>
              </Pressable>
            ) : null}
          </View>
        </MotionIn>
      ))}
      {editing && !full ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={assets.length ? `${label}: add more` : `${label}: add players or picks${addHint ? ` (${addHint})` : ''}`}
          onPress={() => onAdd(side)}
          style={[styles.add, { minHeight: assets.length ? 44 : 64 }]}
          testID={`scale-add-${side}`}
        >
          <AppText style={styles.addPlus}>+</AppText>
          {assets.length === 0 && addHint ? <AppText style={styles.addHint}>{addHint}</AppText> : null}
        </Pressable>
      ) : null}
    </View>
  );
}

/**
 * The trade builder's "two-column scale" (coridian_ pick, ui-pass-3 topic 3 V1): Give and Get side by side as compact
 * player cards, the fairness meter under them updating live, "+" opens the picker sheet, a card opens the player peek,
 * and once both sides are filled the verdict replaces the add buttons with Send / Tweak. `mode="sim"` passes its own
 * plain-word `meter`. Twin of web-next ui/TradeScale.tsx; model: lib/tradeScale.ts.
 */
export default function TradeScale({
  give, get, mode = 'desk', giveLabel = 'You send', getLabel = 'You get', max, meter, netValue, addHint, onAdd, onRemove,
  verdict, onSend, canSend = true, sending = false, sendLabel = 'Send offer', footer, buildingAction, testID = 'trade-scale',
}: {
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  giveLabel?: string;
  getLabel?: string;
  max?: number | null;
  meter?: FairnessMeter;
  netValue?: number | null;
  addHint?: { give?: string; get?: string };
  onAdd: (side: TradeScaleSide) => void;
  onRemove?: (side: TradeScaleSide, key: string) => void;
  verdict?: ReactNode;
  onSend?: () => void;
  canSend?: boolean;
  sending?: boolean;
  sendLabel?: string;
  footer?: ReactNode;
  buildingAction?: ReactNode;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [tweaking, setTweaking] = useState(false);
  const phase = tradeScalePhase({ giveCount: give.length, getCount: get.length, tweaking });
  const editing = phase !== 'review';
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const missing = tradeScaleMissing(give.length, get.length);
  const live = meter ?? fairnessMeter(sum(give), sum(get), mode, netValue);
  const shown: FairnessMeter = missing ? { position: 0.5, edge: 0, label: missing, description: missing, tone: 'muted' } : live;
  const setTweak = (v: boolean) => { animateRowExpand(); setTweaking(v); };
  return (
    <View style={styles.wrap} testID={testID} accessibilityLabel="Trade">
      <View style={styles.columns}>
        <Column side="give" label={giveLabel} assets={give} mode={mode} max={max} editing={editing} addHint={addHint?.give} onAdd={onAdd} onRemove={onRemove} styles={styles} colors={colors} />
        <Column side="get" label={getLabel} assets={get} mode={mode} max={max} editing={editing} addHint={addHint?.get} onAdd={onAdd} onRemove={onRemove} styles={styles} colors={colors} />
      </View>
      <View style={styles.meterCard}>
        <FairnessMeterRow meter={shown} />
        {footer}
      </View>
      {(phase === 'building' || phase === 'empty') && buildingAction ? <View style={{ gap: spacing.sm }} testID="scale-building-action">{buildingAction}</View> : null}
      {phase === 'review' || phase === 'tweak' ? (
        <MotionIn key={phase}>
          <View style={{ gap: spacing.sm }} testID="scale-actions">
            {phase === 'review' ? verdict : null}
            <View style={styles.actions}>
              {phase === 'review' ? (
                <>
                  {onSend ? <Button label={sendLabel} loading={sending} disabled={!canSend} onPress={onSend} /> : null}
                  <Button label="Tweak" variant="secondary" onPress={() => setTweak(true)} />
                </>
              ) : (
                <Button label="Review" variant="secondary" onPress={() => setTweak(false)} />
              )}
            </View>
          </View>
        </MotionIn>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    columns: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start' },
    column: { flex: 1, minWidth: 0, gap: 4, padding: spacing.sm, backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.tile },
    head: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    dot: { width: 6, height: 6, borderRadius: 3 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    assetRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
    assetMain: { flex: 1, minWidth: 0 },
    remove: { width: 32, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    removeText: { fontSize: 18, fontWeight: '700', color: colors.textTertiary },
    add: { alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderStyle: 'dashed', borderColor: colors.accent, borderRadius: radii.md },
    addPlus: { fontSize: 16, fontWeight: '800', color: colors.accent },
    addHint: { fontSize: 12, fontWeight: '700', color: colors.textTertiary, textAlign: 'center', paddingHorizontal: 4 },
    meterCard: { gap: 4, padding: spacing.sm, backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.tile },
    actions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
  });
}

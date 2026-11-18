import React, { useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import CompactModule from './CompactModule';
import { Collapse } from './Presence';
import ExchangeSide from './ExchangeSide';
import PlayerAvatar from './PlayerAvatar';
import PressableScale from './PressableScale';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { GmPlanOutlookItem, GmPlanTradeItem, PresentationAsset } from '../lib/api';
import { abbreviatePlayerName } from '../lib/formatPlayerName';
import type { PlanStep } from '../lib/gmPlanPlan';
import { tradeIdeaGainPhrase, tradeIdeaNamesText } from '../lib/tradeIdeaSummary';
import { deltaBand } from '../lib/verdictTone';
import { spacing, type ThemeColors } from '../theme';

type Person = { id: string | null; name: string; position?: string; team?: string };

function players(assets: PresentationAsset[] | undefined, fallbackId: string, fallbackName: string): Person[] {
  const found = (assets ?? []).filter((a) => a.asset_type === 'player' && a.name).map((a) => ({ id: a.player_id ?? null, name: a.name!, position: a.position, team: a.team }));
  return found.length > 0 ? found : fallbackName ? [{ id: fallbackId || null, name: fallbackName }] : [];
}

export function tradeAvatarPeople(item: GmPlanTradeItem): Person[] {
  return [
    ...players(item.send_assets, item.my_player_id, item.my_player).slice(0, 1),
    ...players(item.receive_assets, item.their_player_id, item.their_player).slice(0, 1),
  ];
}

export function Avatars({ people, size = 28 }: { people: Person[]; size?: number }) {
  return (
    <View style={styles.avatars}>
      {people.map((p, i) => (
        <View key={`${p.id ?? p.name}-${i}`} style={{ marginLeft: i === 0 ? 0 : -8 }}>
          <PlayerAvatar playerId={p.id} name={p.name} position={p.position} team={p.team} size={size} />
        </View>
      ))}
    </View>
  );
}

/** One trade idea inside a step: a compact row that opens on tap (web twin: GmPlanSteps.tsx TradeRow). */
function TradeRow({ item, onViewDetails }: { item: GmPlanTradeItem; onViewDetails: () => void }) {
  const { colors } = useThemeMode();
  const s = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const gain = item.trade_gain;
  const sendNames = players(item.send_assets, item.my_player_id, item.my_player).map((p) => abbreviatePlayerName(p.name));
  const getNames = players(item.receive_assets, item.their_player_id, item.their_player).map((p) => abbreviatePlayerName(p.name));
  const gainColor = gain != null && deltaBand(gain) === 'good' ? colors.success : colors.textTertiary;
  return (
    <View style={s.row} testID="plan-trade-row">
      <PressableScale
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${item.partner_team_name || 'Trade idea'}: ${tradeIdeaNamesText(sendNames)} for ${tradeIdeaNamesText(getNames)}`}
        style={s.rowHead}
        onPress={() => setOpen(!open)}
      >
        <Avatars people={tradeAvatarPeople(item)} />
        <View style={s.rowText}>
          <AppText style={s.partner} numberOfLines={1}>
            {(item.partner_team_name || 'Trade idea').toUpperCase()}
          </AppText>
          <AppText style={s.swap}>
            {tradeIdeaNamesText(sendNames)} for {tradeIdeaNamesText(getNames)}
          </AppText>
          <View style={s.badges}>
            {gain != null ? <ToneBadge size="xs" label={tradeIdeaGainPhrase(gain)} color={gainColor} /> : null}
            {item.trade_confidence_label ? <ToneBadge size="xs" label={item.trade_confidence_label} color={colors.accent} /> : null}
          </View>
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} />
      </PressableScale>
      <Collapse open={open}>
        <View style={s.detail}>
          {(item.send_assets?.length ?? 0) > 0 || (item.receive_assets?.length ?? 0) > 0 ? (
            <>
              <ExchangeSide side="send" assets={item.send_assets ?? []} />
              <ExchangeSide side="get" assets={item.receive_assets ?? []} />
            </>
          ) : null}
          <View style={s.detailFoot}>
            <AppText style={s.why}>{item.rationale || item.trade_confidence_label}</AppText>
            <Button variant="accentOutline" size="sm" label="View details" onPress={onViewDetails} />
          </View>
        </View>
      </Collapse>
    </View>
  );
}

/** One Team Outlook fact (handshake item 7): avatars, label and headline, the reasons on tap. Web twin: OutlookRow. */
export function OutlookRow({ item }: { item: GmPlanOutlookItem }) {
  const { colors } = useThemeMode();
  const s = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const tone = { success: colors.success, muted: colors.textTertiary, accent: colors.accent }[item.tone] ?? colors.accent;
  const people = item.players.map((p) => ({ id: p.player_id || null, name: p.name, position: p.position, team: p.team }));
  return (
    <View style={s.row} testID="plan-outlook-row">
      <PressableScale
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${item.label}: ${item.headline}`}
        style={s.rowHead}
        onPress={() => setOpen(!open)}
      >
        {people.length > 0 ? <Avatars people={people} /> : null}
        <View style={s.rowText}>
          <AppText style={[s.partner, { color: tone }]} numberOfLines={1}>
            {item.label.toUpperCase()}
          </AppText>
          <AppText style={s.swap}>{item.headline}</AppText>
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textTertiary} />
      </PressableScale>
      <Collapse open={open}>
        <View style={s.detail}>
          {item.why.map((line) => (
            <AppText key={line} style={s.why}>
              {'\u2022 '}
              {line}
            </AppText>
          ))}
        </View>
      </Collapse>
    </View>
  );
}

function StepNumber({ n }: { n: number }) {
  const { colors } = useThemeMode();
  const s = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={s.num}>
      <AppText style={s.numText}>{n}</AppText>
    </View>
  );
}

/** The numbered action steps (GM Plan Overview, concept C). Web twin: components/GmPlanSteps.tsx. */
export default function PlanSteps({
  steps,
  tradeItems,
  onViewDetails,
  renderArea,
  tradeEmpty,
}: {
  steps: PlanStep[];
  tradeItems: GmPlanTradeItem[];
  onViewDetails: () => void;
  renderArea: (areaKey: string) => ReactNode;
  tradeEmpty?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const chipColor = { accent: colors.accent, success: colors.success, muted: colors.textTertiary } as const;
  return (
    <>
      {steps.map((step, i) => {
        const body =
          step.kind === 'trades' ? (
            tradeItems.length === 0 ? (
              tradeEmpty
            ) : (
              <View>
                {tradeItems.map((item, idx) => (
                  <TradeRow key={`${item.my_player_id}-${item.their_player_id}-${idx}`} item={item} onViewDetails={onViewDetails} />
                ))}
              </View>
            )
          ) : step.kind === 'area' && step.areaKey ? (
            renderArea(step.areaKey)
          ) : undefined;
        return (
          <CompactModule
            key={step.key}
            id={`gmplan.step.${step.key}`}
            persist={false}
            defaultOpen={i === 0 && step.kind === 'trades'}
            testID={`plan-step-${step.key}`}
            title={
              <View style={styles.titleRow}>
                <StepNumber n={i + 1} />
                <AppText style={styles.titleText}>{step.title.toUpperCase()}</AppText>
              </View>
            }
            label={step.title}
            parts={[{ key: 's', text: step.summary }]}
            action={step.chip ? <ToneBadge size="xs" label={step.chip.label} color={chipColor[step.chip.tone]} /> : undefined}
            preview={
              step.kind === 'trades' && tradeItems.length > 0 ? (
                <View style={styles.preview}>
                  <Avatars people={tradeItems.slice(0, 3).flatMap((t) => tradeAvatarPeople(t).slice(1))} />
                </View>
              ) : undefined
            }
          >
            {body}
          </CompactModule>
        );
      })}
    </>
  );
}

const styles = StyleSheet.create({
  avatars: { flexDirection: 'row', alignItems: 'center' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  titleText: { fontSize: 12, fontWeight: '800', letterSpacing: 0.5 },
  preview: { paddingTop: spacing.xs },
});

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    rowHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm, minHeight: 44 },
    rowText: { flex: 1, minWidth: 0, gap: 4 },
    partner: { fontSize: 12, fontWeight: '800', letterSpacing: 0.5, color: colors.textTertiary },
    swap: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
    badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
    detail: { gap: spacing.sm, paddingBottom: spacing.sm },
    detailFoot: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: spacing.md },
    why: { flex: 1, fontSize: 12, color: colors.textSecondary },
    num: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: `${colors.accent}2E` },
    numText: { fontSize: 12, fontWeight: '800', color: colors.accent },
  });
}

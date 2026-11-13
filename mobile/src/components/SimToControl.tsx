import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Switch, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ConfirmInPlace from './ConfirmInPlace';
import { SkeletonCard } from './SkeletonBlock';
import { SimStandingsList } from './SimGameLeague';
import { SimSectionTitle, SimSheet, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import type { SimToOption, SimToResponse } from '../lib/simGame';
import { simToCanForce, simToFixLabel, simToFixTab, simToHeadline, simToRecordLine, simToWeekLine } from '../lib/simTo';
import { spacing } from '../theme';

export interface SimToRequest {
  option: SimToOption;
  autoSet: boolean;
  forceFirst?: boolean;
}

/**
 * The "Sim to..." chooser: only the milestones that make sense for the stage the game is in (the server decides), and the
 * optional "auto-set my lineup each week" toggle (off by default). One tap runs the whole thing as a single request.
 * Twin of web's SimToSheet.
 */
export function SimToSheet({ ctx, onClose, onRun }: { ctx: SimCtx; onClose: () => void; onRun: (request: SimToRequest) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [options, setOptions] = useState<SimToOption[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [autoSet, setAutoSet] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .getSimToOptions(ctx.gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setOptions(body.options ?? []);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId, ctx.game.week, ctx.tick]);
  return (
    <SimSheet title="Sim to..." onClose={onClose}>
      <View style={common.stack} testID="sim-to-sheet">
        <AppText style={common.small}>Play several weeks at once. It stops early when you have something to decide.</AppText>
        {failed ? (
          <AppText style={common.bodyStrong}>Could not load the options. Try again in a moment.</AppText>
        ) : !options ? (
          <SkeletonCard rows={3} />
        ) : options.length === 0 ? (
          <AppText style={common.small}>There is nothing to simulate right now.</AppText>
        ) : (
          options.map((o) => (
            <Button
              key={`${o.id}-${o.weeks ?? 0}`}
              label={o.label}
              variant="secondary"
              onPress={() => {
                onClose();
                onRun({ option: o, autoSet });
              }}
            />
          ))
        )}
        <View style={[common.rowBetween, { minHeight: 48 }]}>
          <View style={common.grow}>
            <AppText style={common.bodyStrong}>Auto-set my lineup each week</AppText>
            <AppText style={common.muted}>Plays your best healthy lineup before every week. Off: it stops when a starter is out or on a bye.</AppText>
          </View>
          <Switch value={autoSet} onValueChange={setAutoSet} accessibilityLabel="Auto-set my lineup each week" />
        </View>
      </View>
    </SimSheet>
  );
}

/** The skipped weeks at a glance: record, rank, each result, injuries, claims, standings; the stop reason with its fix; undo. */
export function SimToResultView({
  result,
  onClose,
  onTab,
  onForce,
  onUndo,
  onGoPro,
}: {
  result: SimToResponse;
  onClose: () => void;
  onTab: (tab: 'team' | 'trades') => void;
  onForce: () => void;
  onUndo: () => Promise<boolean>;
  onGoPro: () => void;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(), []);
  const played = result.weeks_played ?? 0;
  const s = result.summary;
  const stop = result.stopped ?? null;
  const fixLabel = stop ? simToFixLabel(stop) : null;
  return (
    <View style={common.stack} testID="sim-to-result">
      <SimSectionTitle glyph="matchup" title={simToHeadline(played, s)} caption={s ? simToRecordLine(s) : undefined} />
      {stop ? (
        <AccentCard accent={colors.warning} compact>
          <AppText style={common.bodyStrong} accessibilityRole="alert" testID="sim-to-stop">
            {stop.message}
          </AppText>
          <View style={common.wrapRow}>
            {fixLabel ? (
              <Button
                size="sm"
                label={fixLabel}
                onPress={() => {
                  if (stop.fix === 'premium') onGoPro();
                  else {
                    const tab = simToFixTab(stop);
                    if (tab) onTab(tab);
                    onClose();
                  }
                }}
              />
            ) : null}
            {played === 0 && simToCanForce(stop) ? <Button size="sm" variant="secondary" label="Sim anyway" onPress={onForce} /> : null}
          </View>
        </AccentCard>
      ) : null}
      {s ? (
        <>
          <View style={styles.tiles}>
            <Tile label="Record" value={s.record.after ?? '-'} />
            <Tile label="Rank" value={s.rank.after != null ? `#${s.rank.after}` : '-'} />
            <Tile label="Points" value={`+${s.pf.toFixed(1)}`} />
          </View>
          <View accessibilityLabel="Results">
            {s.weeks.map((w) => (
              <View key={w.week} style={[common.rowBetween, common.divider, { minHeight: 40 }]}>
                <View style={common.row}>
                  <SimToneBadge label={w.kind === 'playoff' ? `Rd ${w.round ?? ''}`.trim() : `Wk ${w.week}`} tone="muted" />
                  <AppText style={[common.bodyStrong, { color: w.result === 'w' ? colors.success : w.result === 'l' ? colors.danger : colors.textPrimary }]}>{simToWeekLine(w)}</AppText>
                </View>
                {w.auto_filled.length > 0 ? <AppText style={common.muted}>auto-filled {w.auto_filled.join(', ')}</AppText> : null}
              </View>
            ))}
          </View>
          {s.injuries.length > 0 ? (
            <AccentCard accent={simToneColor('danger', colors)} compact>
              <AppText style={common.bodyStrong}>Injuries to your team</AppText>
              {s.injuries.map((i, k) => (
                <AppText key={k} style={common.small}>
                  Week {i.week}: {i.player.name} ({i.player.pos}), out {i.weeks} week{i.weeks === 1 ? '' : 's'}
                </AppText>
              ))}
            </AccentCard>
          ) : null}
          {s.claims.length > 0 ? (
            <AccentCard accent={colors.accent} compact>
              <AppText style={common.bodyStrong}>Waiver claims</AppText>
              {s.claims.map((c, k) => (
                <AppText key={k} style={common.small}>
                  Week {c.week}: {c.ok === false ? 'missed' : 'added'} {c.add?.name ?? 'a player'}
                  {c.drop ? `, dropped ${c.drop.name}` : ''}
                </AppText>
              ))}
            </AccentCard>
          ) : null}
          {s.ai_trades > 0 ? (
            <AppText style={common.muted}>
              {s.ai_trades} trade{s.ai_trades === 1 ? '' : 's'} around the league. See the Feed for who moved.
            </AppText>
          ) : null}
          {s.champion ? <AppText style={common.bodyStrong}>The season is over. {s.standings.find((r) => r.team_id === s.champion)?.name ?? 'A team'} are the champions.</AppText> : null}
          <SimStandingsList rows={s.standings} />
        </>
      ) : null}
      <View style={common.wrapRow}>
        <Button label="Continue" onPress={onClose} />
        {played > 0 && result.from_seq != null ? <ConfirmInPlace label="Undo this sim" buttonVariant="secondary" size="sm" onConfirm={onUndo} /> : null}
      </View>
    </View>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(), []);
  return (
    <View style={[styles.tile, { borderColor: colors.glassBorder, backgroundColor: colors.glassInset }]}>
      <AppText style={common.muted}>{label}</AppText>
      <AppText style={common.bodyStrong}>{value}</AppText>
    </View>
  );
}

function createStyles() {
  return StyleSheet.create({
    tiles: { flexDirection: 'row', gap: spacing.sm },
    tile: { flex: 1, alignItems: 'center', paddingVertical: spacing.sm, borderRadius: 12, borderWidth: 1 },
  });
}

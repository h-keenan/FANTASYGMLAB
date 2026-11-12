import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import SimCrest from './SimCrest';
import { SkeletonCard } from './SkeletonBlock';
import { SimPlayerChip, SimPlayerLine, SimSectionTitle, SimSheet, SimStat, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simFmtPts,
  simFmtRecord,
  simLevelLabel,
  simLevelTone,
  simPlayoffStatusLabel,
  simSlotLabels,
  simSlotRepeatsPosition,
  simStrengthNeedLine,
  type SimTeamRosterResponse,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

/**
 * The scouting sheet for any team (GET /teams/{id}): record and rank, which
 * positions are strengths and needs, the lineup it will start, its injuries,
 * its recent moves and a way to open a trade. Works for your own team too.
 * Mirrors web-next's SimTeamSheet.
 */
export function SimTeamSheet({ ctx, teamId, onClose, onTrade }: { ctx: SimCtx; teamId: string; onClose: () => void; onTrade: (teamId: string) => void }) {
  const [data, setData] = useState<SimTeamRosterResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimGameTeam(ctx.gameId, teamId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason || !body.team) setFailed(true);
        else setData(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId, teamId, attempt]);

  return (
    <SimSheet title={data?.team ? `${data.team.name} scouting report` : 'Team scouting report'} onClose={onClose}>
      {failed ? (
        <ErrorState title="Team did not load" message="Check your connection and try again." onRetry={() => { setFailed(false); setAttempt((n) => n + 1); }} />
      ) : !data?.team ? (
        <SkeletonCard rows={4} />
      ) : (
        <TeamBody ctx={ctx} data={data} onTrade={onTrade} />
      )}
    </SimSheet>
  );
}

function TeamBody({ ctx, data, onTrade }: { ctx: SimCtx; data: SimTeamRosterResponse; onTrade: (teamId: string) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const team = data.team!;
  const record = team.record;
  const lineup = data.lineup ?? [];
  const labels = simSlotLabels(lineup);
  const started = new Set(lineup.map((s) => s.player?.id).filter(Boolean));
  const bench = (data.players ?? []).filter((p) => !started.has(p.id));
  const line = simStrengthNeedLine(data.strengths, data.needs);
  const status = record ? simPlayoffStatusLabel(record.playoff_status) : '';
  return (
    <View style={common.stack}>
      <View style={common.row}>
        <SimCrest name={team.name} size={56} label />
        <View style={common.grow}>
          <AppText style={common.title} testID="team-sheet-name">
            {team.name}
            {team.is_you ? ' (you)' : ''}
          </AppText>
          <View style={common.wrapRow}>
            <ToneBadge label={team.persona.label} color={colors.accent} size="xs" />
            <ToneBadge label={`Power #${team.power_rank}`} color={colors.premium} size="xs" />
            {status ? <SimToneBadge label={status} tone={record?.playoff_status === 'out' || record?.playoff_status === 'eliminated' ? 'muted' : 'success'} /> : null}
          </View>
          {team.owner ? <AppText style={common.muted}>Managed by {team.owner}</AppText> : null}
        </View>
      </View>
      <AppText style={common.small}>{team.persona.blurb}</AppText>

      <View style={styles.facts}>
        <Fact label="Record" value={record ? simFmtRecord(record) : '-'} />
        <Fact label="Rank" value={record ? `#${record.rank}` : '-'} />
        <Fact label="PF" value={record ? simFmtPts(record.pf) : '-'} />
        <Fact label="Proj" value={simFmtPts(data.projected_total)} />
      </View>
      {record?.streak || data.next_game ? (
        <AppText style={common.small}>
          {record?.streak ? <AppText style={{ fontWeight: '800', color: record.streak.startsWith('W') ? colors.success : colors.danger }}>Streak {record.streak}</AppText> : null}
          {record?.streak && data.next_game ? ' · ' : ''}
          {data.next_game ? `Week ${data.next_game.week} vs ${data.next_game.opponent.name}` : ''}
        </AppText>
      ) : null}

      <SimSectionTitle glyph="spark" title="Strengths and needs" caption={line || undefined} />
      <View style={styles.grid}>
        {(data.positions ?? []).map((p) => (
          <View key={p.pos} style={styles.gridCell}>
            <AccentCard accent={simToneColor(simLevelTone(p.level), colors)} compact>
              <View style={{ gap: 4, alignItems: 'flex-start' }}>
                <PositionBadge position={p.pos} />
                <AppText style={{ fontSize: 12.5, fontWeight: '800', color: simToneColor(simLevelTone(p.level), colors) }}>{simLevelLabel(p.level)}</AppText>
              </View>
              <AppText style={common.small}>
                #{p.rank} of {p.teams} · depth {p.depth}
              </AppText>
            </AccentCard>
          </View>
        ))}
      </View>

      {(data.injuries ?? []).length > 0 ? (
        <View style={common.tight}>
          <SimSectionTitle glyph="injury" tone="danger" title="Injuries" />
          {data.injuries!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} trailing={<SimToneBadge label={`${p.out_weeks} wk`} tone="danger" />} />
          ))}
        </View>
      ) : null}

      <View style={common.tight}>
        <SimSectionTitle glyph="team" title="Lineup" caption={`Projected ${simFmtPts(data.projected_total)} points this week`} />
        {lineup.map((slot, index) => (
          <View key={`${slot.slot}-${index}`} style={[common.row, common.divider]}>
            <View style={common.slotCol}>
              <PositionBadge position={slot.slot} label={labels[index]} />
            </View>
            <View style={common.grow}>
              {slot.player ? (
                <SimPlayerLine
                  player={slot.player}
                  hidePosition={simSlotRepeatsPosition(slot.slot, slot.player.pos)}
                  onOpen={ctx.openPlayer}
                  trailing={<SimStat label="Proj" value={simFmtPts(slot.player.projection)} />}
                />
              ) : (
                <AppText style={[common.muted, { paddingVertical: spacing.md }]}>Empty</AppText>
              )}
            </View>
          </View>
        ))}
      </View>

      {bench.length > 0 ? (
        <View style={common.tight}>
          <SimSectionTitle glyph="bye" tone="muted" title="Bench" />
          {bench.map((p) => (
            <SimPlayerLine key={p.id} player={p} muted onOpen={ctx.openPlayer} trailing={<SimStat label="Proj" value={simFmtPts(p.projection)} />} />
          ))}
        </View>
      ) : null}

      {(data.recent ?? []).length > 0 ? (
        <View style={common.stack}>
          <SimSectionTitle glyph="trade" title="Recent moves" />
          {data.recent!.map((m, i) => (
            <AccentCard key={i} accent={colors.borderStrong} compact>
              <View style={common.row}>
                <ToneBadge label={`Week ${m.week}`} color={colors.textSecondary} size="xs" />
                <ToneBadge label={m.type.replace(/_/g, ' ')} color={colors.premium} size="xs" />
              </View>
              <AppText style={common.body}>{m.text}</AppText>
              {m.players.map((p) => (
                <SimPlayerChip key={`${p.role}-${p.id}`} player={p} size={24} />
              ))}
            </AccentCard>
          ))}
        </View>
      ) : null}

      {!team.is_you ? (
        <View style={common.tight}>
          <Button label={`Trade with ${team.name}`} disabled={!data.trade?.open} onPress={() => onTrade(team.team_id)} />
          {!data.trade?.open ? <AppText style={common.muted}>Trades are closed right now.</AppText> : null}
        </View>
      ) : null}
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.fact}>
      <AppText style={styles.factLabel}>{label}</AppText>
      <AppText style={styles.factValue}>{value}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    facts: { flexDirection: 'row', gap: spacing.sm },
    fact: { flex: 1, alignItems: 'center', paddingVertical: spacing.sm, borderRadius: 12, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glassInset },
    factLabel: { fontSize: 12, color: colors.textTertiary },
    factValue: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    gridCell: { flexBasis: '31%', flexGrow: 1 },
  });
}

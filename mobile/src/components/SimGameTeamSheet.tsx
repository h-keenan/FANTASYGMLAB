import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import { SimTeamLogo } from './SimTeamIdentity';
import { SimTeamHistory } from './SimTeamHistory';
import { SkeletonCard } from './SkeletonBlock';
import Tabs from './Tabs';
import { SimPlayerChip, SimPlayerLine, SimSectionTitle, SimSheet, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simListStats } from '../lib/simDraft';
import { simGroupBenchByPosition } from '../lib/simLeagueRosters';
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

const SIM_ROSTER_POS_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'] as const;

/**
 * The scouting sheet for any team (GET /teams/{id}): record and rank, which
 * positions are strengths and needs, the lineup it will start, its full roster (starters, bench by position, IR, taxi) in the shared player rows, its
 * recent moves and a prefilled "Make an offer". Works for your own team too.
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
        <SimTeamLogo name={team.name} size='hero' label />
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
      <Tabs
        id="sim-team"
        tabs={[
          {
            key: 'overview',
            label: 'Overview',
            render: () => (
              <>
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
        <View style={common.tight} accessibilityLabel="Injuries">
          <SimSectionTitle glyph="injury" tone="danger" title="Injuries" />
          {data.injuries!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} trailing={<SimToneBadge label={`${p.out_weeks} wk`} tone="danger" />} />
          ))}
        </View>
      ) : null}
              </>
            ),
          },
          {
            key: 'roster',
            label: 'Roster',
            render: () => (
              <>
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
                  stats={simListStats(slot.player, { adp: false })}
                />
              ) : (
                <AppText style={[common.muted, { paddingVertical: spacing.md }]}>Empty</AppText>
              )}
            </View>
          </View>
        ))}
      </View>

      {bench.length > 0 ? (
        <View style={common.tight} accessibilityLabel="Bench">
          <SimSectionTitle glyph="bye" tone="muted" title="Bench" caption={`${bench.length} on the bench, grouped by position`} />
          {simGroupBenchByPosition(bench, SIM_ROSTER_POS_ORDER).map((group) => (
            <View key={group.pos} accessibilityLabel={`${group.pos} bench`}>
              <AppText style={[common.muted, { fontWeight: '800', paddingTop: spacing.xs }]}>
                {group.pos} · {group.players.length}
              </AppText>
              {group.players.map((p) => (
                <SimPlayerLine key={p.id} player={p} muted onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
              ))}
            </View>
          ))}
        </View>
      ) : null}

      {(data.ir ?? []).length > 0 ? (
        <View style={common.tight} accessibilityLabel="Injured reserve">
          <SimSectionTitle glyph="injury" tone="danger" title="Injured reserve" caption="Not counted against the roster limit." />
          {data.ir!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
          ))}
        </View>
      ) : null}

      {(data.taxi ?? []).length > 0 ? (
        <View style={common.tight} accessibilityLabel="Taxi squad">
          <SimSectionTitle glyph="spark" title="Taxi squad" caption="Young players stashed off the active roster." />
          {data.taxi!.map((p) => (
            <SimPlayerLine key={p.id} player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} />
          ))}
        </View>
      ) : null}

              </>
            ),
          },
          {
            key: 'trades',
            label: 'Trades',
            render: () => (
              <>
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
          <Button label={`Make an offer to ${team.name}`} disabled={!data.trade?.open} onPress={() => onTrade(team.team_id)} />
          {!data.trade?.open ? <AppText style={common.muted}>Trades are closed right now.</AppText> : null}
        </View>
      ) : null}
              </>
            ),
          },
          { key: 'history', label: 'History', render: () => <SimTeamHistory gameId={ctx.gameId} teamId={team.team_id} /> },
        ]}
      />
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

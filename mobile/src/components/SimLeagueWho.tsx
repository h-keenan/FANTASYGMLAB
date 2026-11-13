import React, { useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import Input from './Input';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import SimCrest from './SimCrest';
import { SimPlayerLine, SimSectionTitle, createSimStyles, type SimCtx } from './SimGameParts';
import SimTeamCard from './SimTeamCard';
import { useThemeMode } from '../context/ThemeModeContext';
import { SIM_WINDOW_STEP, simWindow } from '../lib/simLayout';
import { simListStats } from '../lib/simDraft';
import { simRosterEntries, simRosterPositions, simTeamsByPower, type SimRosterPosFilter } from '../lib/simLeagueRosters';
import type { SimLeagueRostersState } from '../lib/useSimLeagueRosters';

function Loading({ state, onRetry }: { state: SimLeagueRostersState; onRetry: () => void }) {
  if (state.status === 'error') return <ErrorState title="The rosters did not load" message="Check your connection and try again." onRetry={onRetry} />;
  return <SkeletonCard rows={6} />;
}

/** Teams view: one glanceable card per team (record, top assets, needs and depth); tap a team for its full roster. */
export function SimLeagueTeamsView({ ctx, state, onRetry }: { ctx: SimCtx; state: SimLeagueRostersState; onRetry: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (state.status !== 'ready') return <Loading state={state} onRetry={onRetry} />;
  return (
    <View style={common.stack} accessibilityLabel="Teams">
      <SimSectionTitle glyph="team" title="Teams" caption="Who has who. Power rank is roster strength right now. Tap a team for its full roster." />
      {simTeamsByPower(state.teams).map((team) => (
        <SimTeamCard key={team.team_id} team={team} onOpen={ctx.openTeam} />
      ))}
    </View>
  );
}

/**
 * Players view: find any rostered player and see who owns him (tap the owner to open that team), or browse the
 * league position by position (all QBs with owner and value). Reads the same single rosters payload.
 */
export function SimLeaguePlayersView({ ctx, state, onRetry }: { ctx: SimCtx; state: SimLeagueRostersState; onRetry: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [pos, setPos] = useState<SimRosterPosFilter>('ALL');
  const [text, setText] = useState('');
  const [visible, setVisible] = useState(SIM_WINDOW_STEP);
  const teams = state.status === 'ready' ? state.teams : null;
  const entries = useMemo(() => (teams ? simRosterEntries(teams, pos, text) : []), [teams, pos, text]);
  const positions = useMemo(() => (teams ? simRosterPositions(teams) : []), [teams]);
  if (!teams) return <Loading state={state} onRetry={onRetry} />;
  const { shown, remaining } = simWindow(entries, visible);
  return (
    <View style={common.stack} accessibilityLabel="League players">
      <SimSectionTitle glyph="league" title="Find a player" caption="Every rostered player and who owns him. Free agents are on the Players tab." />
      <Input
        value={text}
        onChangeText={(value) => {
          setText(value);
          setVisible(SIM_WINDOW_STEP);
        }}
        placeholder="Search by player name or NFL team"
        accessibilityLabel="Find a player"
        returnKeyType="search"
        autoCorrect={false}
        autoCapitalize="none"
        clearButtonMode="while-editing"
      />
      <SegmentedTabBar<string>
        scrollable
        options={[{ key: 'ALL', label: 'All' }, ...positions.map((p) => ({ key: p as string, label: p as string }))]}
        active={pos}
        onChange={(key) => {
          setPos(key as SimRosterPosFilter);
          setVisible(SIM_WINDOW_STEP);
        }}
      />
      <AppText style={common.muted} accessibilityLiveRegion="polite">
        {entries.length} {entries.length === 1 ? 'player' : 'players'}
        {pos === 'ALL' ? '' : ` at ${pos}`}, best value first
      </AppText>
      {entries.length === 0 ? (
        <EmptyState icon="search-outline" title="No one matches" subtitle="Try another name, or pick All positions. Free agents are on the Players tab." />
      ) : (
        <View>
          {shown.map(({ player, team }) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              onOpen={ctx.openPlayer}
              stats={simListStats(player, { adp: false })}
              tags={[{ key: 'owner', label: team.is_you ? 'Your team' : team.name, tone: team.is_you ? 'accent' : undefined }]}
              trailing={
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Owned by ${team.name}${team.is_you ? ' (you)' : ''}. Open team`}
                  onPress={() => ctx.openTeam(team.team_id)}
                  style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}
                >
                  <SimCrest name={team.name} size={28} />
                </Pressable>
              }
            />
          ))}
          {remaining > 0 ? (
            <Pressable onPress={() => setVisible((n) => n + SIM_WINDOW_STEP)} accessibilityRole="button" style={{ minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
              <AppText style={{ fontSize: 14, fontWeight: '800', color: colors.accent }}>Show {Math.min(SIM_WINDOW_STEP, remaining)} more</AppText>
            </Pressable>
          ) : null}
        </View>
      )}
    </View>
  );
}

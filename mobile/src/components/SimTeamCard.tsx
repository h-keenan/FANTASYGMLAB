import React, { useMemo, type ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import { SimTeamLogo } from './SimTeamIdentity';
import { createSimStyles, simToneColor } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimLeagueRosterTeam } from '../lib/simGame';
import { playerSurname } from '../lib/playerNameDisplay';
import { simTeamChips, simTeamRecordLine } from '../lib/simLeagueRosters';
import { simGradeOf } from '../lib/simGrade';
import { LetterGrade } from './LetterGrade';

/**
 * THE Fantasy Sim team card: who a team is and who it has, at a glance. Used by the League tab's Teams view and
 * the Trade tab's partner list (twin of web-next's SimTeamCard). Crest, name, record and rank, the team's top
 * assets with their value, and what it needs vs where it is deep as position chips. The whole card is one
 * tap target (no nested buttons).
 */
export default function SimTeamCard({
  team,
  onOpen,
  selected = false,
  openLabel,
  compact = false,
  trailing,
  dense = false,
}: {
  team: SimLeagueRosterTeam;
  onOpen?: (teamId: string) => void;
  selected?: boolean;
  openLabel?: string;
  /** Hide the top assets. */
  compact?: boolean;
  trailing?: ReactNode;
  /** Pickers: the top assets run in one wrapping strip (position, surname, OVR) instead of one row each. */
  dense?: boolean;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const chips = simTeamChips(team);
  const accent = selected || team.is_you ? colors.accent : team.power_rank <= 3 ? colors.success : colors.borderStrong;
  const body = (
    <AccentCard accent={accent} compact>
      <View style={common.rowBetween}>
        <View style={[common.row, common.grow]}>
          <SimTeamLogo name={team.name} size='row' />
          <View style={common.grow}>
            <AppText style={common.bodyStrong}>
              {team.name}
              {team.is_you ? ' (you)' : ''}
            </AppText>
            <AppText style={common.small}>{simTeamRecordLine(team)}</AppText>
          </View>
        </View>
        <View style={common.row}>
          <ToneBadge label={`Power #${team.power_rank}`} color={team.power_rank <= 3 ? colors.success : colors.textSecondary} size="xs" />
          {trailing}
        </View>
      </View>
      {compact ? null : (
        <View style={dense ? { flexDirection: 'row', flexWrap: 'wrap', columnGap: 12, rowGap: 4 } : common.tight} accessibilityLabel={`${team.name} top assets`}>
          {team.top_assets.map((p) => dense ? (
            <View key={p.id} style={[common.row, { gap: 4 }]}>
              <PositionBadge position={p.pos} />
              <AppText style={{ fontSize: 13, fontWeight: '700', color: colors.textPrimary }}>{playerSurname(p.name)}</AppText>
              <LetterGrade grade={simGradeOf(p)} size="sm" />
            </View>
          ) : (
            <View key={p.id} style={common.row}>
              <PositionBadge position={p.pos} />
              <View style={common.grow}>
                <PlayerName name={p.name} style={{ fontSize: 13, fontWeight: '700', color: colors.textPrimary }} />
              </View>
              <LetterGrade grade={simGradeOf(p)} size="sm" />
            </View>
          ))}
        </View>
      )}
      {chips.length > 0 ? (
        <View style={common.wrapRow} accessibilityLabel="Needs and depth">
          {chips.map((c) => (
            <ToneBadge key={c.key} label={c.label} color={simToneColor(c.tone, colors)} size="xs" />
          ))}
        </View>
      ) : null}
    </AccentCard>
  );
  if (!onOpen) return body;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={openLabel ?? `${team.name}. Open roster`} accessibilityState={{ selected }} onPress={() => onOpen(team.team_id)} style={{ minHeight: 44 }}>
      {body}
    </Pressable>
  );
}

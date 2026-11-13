import React, { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import PositionBadge from './PositionBadge';
import { SkeletonCard } from './SkeletonBlock';
import { SimSectionTitle, createSimStyles } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import type { SimTeamHistoryPick, SimTeamHistoryResponse } from '../lib/simGame';
import { simDraftSlotText, simSeasonRecord, simTeamMoveText, simWhenLabel } from '../lib/simHistory';

function PickRow({ pick }: { pick: SimTeamHistoryPick }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <View style={[common.row, common.divider, { paddingVertical: 6 }]}>
      <PositionBadge position={pick.pos} />
      <AppText style={[common.bodyStrong, common.grow]} numberOfLines={1}>
        {pick.name}
      </AppText>
      <AppText style={common.muted}>{simDraftSlotText(pick.round, pick.pick, pick.auto).replace(' overall', '')}</AppText>
    </View>
  );
}

/**
 * A team's History tab: record by season, its draft classes (league draft and every rookie draft) and every trade,
 * claim and cut. Read from GET /teams/{id}/history, fetched once when the tab opens. Twin of web's SimTeamHistory.
 */
export function SimTeamHistory({ gameId, teamId }: { gameId: string; teamId: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [data, setData] = useState<SimTeamHistoryResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [allMoves, setAllMoves] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSimTeamHistory(gameId, teamId).then(
      (body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setData(body);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, attempt]);

  if (failed) {
    return (
      <View style={common.tight}>
        <AppText style={common.bodyStrong}>Could not load this team&apos;s history.</AppText>
        <Button
          label="Try again"
          variant="secondary"
          onPress={() => {
            setFailed(false);
            setAttempt((n) => n + 1);
          }}
        />
      </View>
    );
  }
  if (!data) return <SkeletonCard rows={5} />;
  const seasons = data.seasons ?? [];
  const classes = data.rookie_drafts ?? [];
  const moves = data.moves ?? [];
  const shown = allMoves ? moves : moves.slice(0, 8);
  return (
    <>
      {seasons.length > 0 ? (
        <View style={common.stack} accessibilityLabel="Record by season">
          <SimSectionTitle glyph="standings" title="Record by season" />
          {seasons.map((s) => (
            <AccentCard key={s.season} accent={s.champion ? colors.premium : colors.borderStrong} compact>
              <View style={common.rowBetween}>
                <AppText style={common.bodyStrong}>{s.year ?? `Season ${s.season}`}</AppText>
                <View style={common.row}>
                  {s.champion ? <ToneBadge label="Champion" color={colors.premium} size="xs" /> : null}
                  <AppText style={common.bodyStrong}>{simSeasonRecord(s)}</AppText>
                </View>
              </View>
              <AppText style={common.muted}>
                {s.pf.toFixed(1)} PF · {s.pa.toFixed(1)} PA
              </AppText>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {(data.draft ?? []).length > 0 ? (
        <View style={common.tight} accessibilityLabel="League draft class">
          <SimSectionTitle glyph="spark" title="Draft class" caption="The league draft, round by round." />
          {data.draft!.map((p) => (
            <PickRow key={p.id} pick={p} />
          ))}
        </View>
      ) : null}

      {classes.map((c) => (
        <View key={c.year ?? 'rookies'} style={common.tight} accessibilityLabel={`${c.year ?? ''} rookie draft`}>
          <SimSectionTitle glyph="spark" title={c.year ? `${c.year} rookie draft` : 'Rookie draft'} />
          {c.picks.map((p) => (
            <PickRow key={p.id} pick={p} />
          ))}
        </View>
      ))}

      <View style={common.stack} accessibilityLabel="Transactions">
        <SimSectionTitle glyph="trade" title="Transactions" caption="Trades, waiver claims and cuts, newest first." />
        {moves.length === 0 ? (
          <AppText style={common.muted}>No moves yet.</AppText>
        ) : (
          shown.map((m, i) => (
            <AccentCard key={i} accent={colors.borderStrong} compact>
              <View style={common.row}>
                <ToneBadge label={simWhenLabel(m)} color={colors.textSecondary} size="xs" />
                <ToneBadge label={m.kind} color={colors.premium} size="xs" />
              </View>
              <AppText style={common.body}>{simTeamMoveText(m)}</AppText>
            </AccentCard>
          ))
        )}
        {moves.length > 8 ? <Button label={allMoves ? 'Show fewer' : `Show all ${moves.length}`} variant="secondary" onPress={() => setAllMoves((v) => !v)} /> : null}
      </View>
    </>
  );
}
